"""
Mock AI Engine — produces deterministic, realistic-looking analysis results
based on heuristic pattern matching on the diff content. No API key required.
Replace analyze() with a real LLM call when credentials are available.
"""
import re
from dataclasses import dataclass, field
from .diff_parser import ChangedFile


@dataclass
class Finding:
    file: str
    line_hint: str
    category: str          # e.g. "Breaking Change", "Security", "Performance"
    description: str
    suggestion: str
    severity: str          # "high" | "medium" | "low"


@dataclass
class AnalysisResult:
    findings: list[Finding] = field(default_factory=list)
    summary: str = ""
    risk_level: str = "low"   # "high" | "medium" | "low"
    risk_score: int = 0       # 0-100
    affected_files: list[str] = field(default_factory=list)
    safer_alternatives: list[str] = field(default_factory=list)
    recommended_tests: list[str] = field(default_factory=list)


# ── Heuristic rule definitions ────────────────────────────────────────────────

_RULES: list[dict] = [
    {
        "id": "public_api_removed",
        "pattern": re.compile(r"^-\s*(public|export)\s+(function|class|const|def)\s+\w+", re.MULTILINE),
        "severity": "high",
        "category": "Breaking Change",
        "description": "Public API or exported symbol removed — downstream consumers will break.",
        "suggestion": "Deprecate the symbol first with a @deprecated annotation and keep it for at least one release cycle.",
    },
    {
        "id": "auth_bypass",
        "pattern": re.compile(r"\b(skip_auth|bypass_auth|no_auth|disable_auth|AUTH\s*=\s*False)\b", re.IGNORECASE),
        "severity": "high",
        "category": "Security",
        "description": "Authentication check appears to be disabled or bypassed.",
        "suggestion": "Remove the bypass and ensure all endpoints require proper authentication tokens.",
    },
    {
        "id": "hardcoded_secret",
        "pattern": re.compile(
            r'(password|secret|api_key|token|passwd)\s*=\s*["\'][^"\']{4,}["\']',
            re.IGNORECASE,
        ),
        "severity": "high",
        "category": "Security",
        "description": "Hardcoded credential or secret detected in source code.",
        "suggestion": "Move secrets to environment variables or a secrets manager (e.g. HashiCorp Vault, AWS Secrets Manager).",
    },
    {
        "id": "sql_injection",
        "pattern": re.compile(r"(execute|query)\s*\(\s*f[\"']|%\s*\(.*\)\s*%\s*[\"'].*SELECT", re.IGNORECASE),
        "severity": "high",
        "category": "Security",
        "description": "Possible SQL injection via string interpolation in a query.",
        "suggestion": "Use parameterised queries or an ORM instead of string interpolation.",
    },
    {
        "id": "db_migration_drop",
        "pattern": re.compile(r"\b(DROP\s+TABLE|DROP\s+COLUMN|ALTER\s+TABLE.*DROP)\b", re.IGNORECASE),
        "severity": "high",
        "category": "Breaking Change",
        "description": "Destructive database schema change detected (DROP TABLE / DROP COLUMN).",
        "suggestion": "Run schema changes behind a feature flag and back up data before deploying.",
    },
    {
        "id": "force_push_reset",
        "pattern": re.compile(r"\bgit\s+(push\s+--force|reset\s+--hard)\b", re.IGNORECASE),
        "severity": "high",
        "category": "Data Loss Risk",
        "description": "Force push or hard reset command found — history rewrite or data loss risk.",
        "suggestion": "Use 'git push --force-with-lease' or avoid rewriting shared branch history.",
    },
    {
        "id": "exception_swallowed",
        "pattern": re.compile(r"except\s*(\(\s*Exception\s*\))?\s*:\s*\n\s*pass", re.MULTILINE),
        "severity": "medium",
        "category": "Reliability",
        "description": "Exception is caught and silently swallowed with `pass`.",
        "suggestion": "At minimum log the exception; consider re-raising or returning an error response.",
    },
    {
        "id": "broad_exception",
        "pattern": re.compile(r"catch\s*\(\s*Exception\s+\w*\s*\)|except\s+Exception\s+as", re.IGNORECASE),
        "severity": "medium",
        "category": "Reliability",
        "description": "Catching broad Exception type masks unexpected errors.",
        "suggestion": "Catch specific exception types to avoid hiding unrelated bugs.",
    },
    {
        "id": "todo_fixme",
        "pattern": re.compile(r"\b(TODO|FIXME|HACK|XXX)\b"),
        "severity": "low",
        "category": "Code Quality",
        "description": "TODO/FIXME comment added — unfinished work may ship to production.",
        "suggestion": "Create a tracked issue and link it in the comment rather than leaving inline markers.",
    },
    {
        "id": "console_log_debug",
        "pattern": re.compile(r"\bconsole\.(log|debug|warn)\s*\(|print\s*\(.*debug", re.IGNORECASE),
        "severity": "low",
        "category": "Code Quality",
        "description": "Debug print/console statement left in production code.",
        "suggestion": "Remove or replace with a structured logger that respects log-level configuration.",
    },
    {
        "id": "large_file_change",
        "pattern": None,  # handled programmatically
        "severity": "medium",
        "category": "Review Risk",
        "description": "File has more than 150 added/changed lines — difficult to review thoroughly.",
        "suggestion": "Consider splitting into smaller, focused commits or pull requests.",
    },
    {
        "id": "dependency_version_pin_removed",
        "pattern": re.compile(r'^-.*["\'][\w\-]+["\']:\s*["\'][\^~]', re.MULTILINE),
        "severity": "medium",
        "category": "Dependency",
        "description": "A pinned dependency version range was removed or loosened.",
        "suggestion": "Keep dependency versions pinned to avoid unexpected upstream breakages.",
    },
]


def _line_hint(file: ChangedFile, pattern: re.Pattern) -> str:
    """Find the first matching added line number (approximate)."""
    for hunk in file.hunks:
        for i, line in enumerate(hunk.added_lines):
            if pattern.search("+" + line):
                return f"~line {hunk.new_start + i}"
    return "diff hunk"


def analyze(files: list[ChangedFile]) -> AnalysisResult:
    """Run heuristic analysis on parsed diff files. Returns structured findings."""
    findings: list[Finding] = []
    affected_files: list[str] = []

    for file in files:
        if file.is_deleted:
            findings.append(
                Finding(
                    file=file.filename,
                    line_hint="entire file",
                    category="Breaking Change",
                    description=f"File '{file.filename}' was deleted entirely.",
                    suggestion="Verify no other modules import from this file before merging.",
                    severity="medium",
                )
            )
            affected_files.append(file.filename)
            continue

        file_affected = False
        # Build a searchable blob of the diff for this file
        added_blob = "\n".join("+" + l for h in file.hunks for l in h.added_lines)
        removed_blob = "\n".join("-" + l for h in file.hunks for l in h.removed_lines)
        full_blob = added_blob + "\n" + removed_blob

        for rule in _RULES:
            if rule["id"] == "large_file_change":
                if file.added_count > 150:
                    findings.append(
                        Finding(
                            file=file.filename,
                            line_hint="entire file",
                            category=rule["category"],
                            description=rule["description"],
                            suggestion=rule["suggestion"],
                            severity=rule["severity"],
                        )
                    )
                    file_affected = True
                continue

            if rule["pattern"] and rule["pattern"].search(full_blob):
                hint = _line_hint(file, rule["pattern"])
                findings.append(
                    Finding(
                        file=file.filename,
                        line_hint=hint,
                        category=rule["category"],
                        description=rule["description"],
                        suggestion=rule["suggestion"],
                        severity=rule["severity"],
                    )
                )
                file_affected = True

        if file_affected:
            affected_files.append(file.filename)

    # ── Compute overall risk ──────────────────────────────────────────────────
    high_count = sum(1 for f in findings if f.severity == "high")
    med_count = sum(1 for f in findings if f.severity == "medium")
    low_count = sum(1 for f in findings if f.severity == "low")

    score = min(100, high_count * 30 + med_count * 10 + low_count * 3)

    if high_count > 0:
        risk_level = "high"
    elif med_count > 0:
        risk_level = "medium"
    elif low_count > 0:
        risk_level = "low"
    else:
        risk_level = "low"

    if not findings:
        summary = "No significant risks detected. The diff looks clean."
    else:
        parts = []
        if high_count:
            parts.append(f"{high_count} high-severity issue{'s' if high_count > 1 else ''}")
        if med_count:
            parts.append(f"{med_count} medium")
        if low_count:
            parts.append(f"{low_count} low")
        summary = (
            f"Found {', '.join(parts)} across {len(set(affected_files))} file(s). "
            "Review all high-severity findings before merging."
        )

    return AnalysisResult(
        findings=findings,
        summary=summary,
        risk_level=risk_level,
        risk_score=score,
        affected_files=list(dict.fromkeys(affected_files)),  # deduplicated, order-preserving
    )
