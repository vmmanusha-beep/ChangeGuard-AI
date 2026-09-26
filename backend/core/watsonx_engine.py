"""
watsonx_engine.py — IBM watsonx.ai-powered diff analysis.

Calls the ibm-watsonx-ai SDK to run an IBM Granite instruct model against the
parsed diff.  If credentials are missing, the model is unavailable, or the
response cannot be parsed as valid JSON, the function raises WatsonxUnavailable
so the caller can transparently fall back to the local heuristic engine.

No credentials are ever hard-coded here; all values come from environment
variables loaded via config.py / pydantic-settings.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from .diff_parser import ChangedFile
from .ai_engine import AnalysisResult, Finding

logger = logging.getLogger(__name__)


class WatsonxUnavailable(Exception):
    """Raised when watsonx.ai cannot be reached or credentials are absent."""


# ── Prompt construction ───────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are ChangeGuard AI, a senior software-security and reliability engineer.
You analyse git diffs and identify risks in software changes.
You always respond with a single, valid JSON object — no markdown fences, no prose.
"""

_USER_PROMPT_TEMPLATE = """\
Analyse the following git diff and return a JSON object with EXACTLY this schema:

{{
  "risk_level": "<high|medium|low>",
  "risk_score": <integer 0-100>,
  "summary": "<one concise sentence>",
  "affected_files": ["<file1>", ...],
  "findings": [
    {{
      "category": "<Security|Breaking Change|Reliability|Performance|Code Quality|Data Loss Risk|Review Risk|Dependency|Testing Gap|Maintainability>",
      "severity": "<high|medium|low>",
      "title": "<short title>",
      "description": "<what the risk is>",
      "file": "<filename or 'general'>",
      "line": "<line number or range, e.g. '42' or '~line 15', or 'N/A'>",
      "suggestion": "<specific actionable fix>"
    }}
  ],
  "safer_alternatives": ["<alternative approach 1>", ...],
  "recommended_tests": ["<test to write 1>", ...]
}}

Rules:
- risk_score: 0=no risk, 100=critical. high>=60, medium 20-59, low<20.
- Only include findings that are genuinely present in the diff.
- affected_files must only list files that appear in the diff.
- safer_alternatives: 1-3 high-level alternative implementation approaches.
- recommended_tests: 1-3 specific test cases that should be added.
- Analyse for: security (auth, secrets, injection), breaking API changes,
  data loss, schema changes, performance, reliability, testing gaps,
  maintainability, and dependency risks.
- Be concise. No explanatory text outside the JSON object.

Git diff to analyse:
```
{diff_text}
```
"""


def _build_prompt(files: list[ChangedFile]) -> str:
    """Reconstruct a compact diff summary to send to the model."""
    lines: list[str] = []
    for f in files:
        status = " (new)" if f.is_new else " (deleted)" if f.is_deleted else ""
        lines.append(f"--- {f.filename}{status}")
        lines.append(f"+++ {f.filename}{status}")
        for hunk in f.hunks:
            lines.append(hunk.header)
            for l in hunk.removed_lines:
                lines.append(f"-{l}")
            for l in hunk.added_lines:
                lines.append(f"+{l}")
    return "\n".join(lines)


# ── Response parsing ──────────────────────────────────────────────────────────

_SEVERITY_VALUES = {"high", "medium", "low"}
_RISK_LEVEL_VALUES = {"high", "medium", "low"}


def _extract_json(text: str) -> dict[str, Any]:
    """
    Extract a JSON object from model output that may contain prose or markdown
    fences.  Tries strict parse first, then strips fences, then regex-extracts
    the first {...} block.
    """
    text = text.strip()

    # 1. Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Strip markdown code fences
    stripped = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    stripped = re.sub(r"```\s*$", "", stripped, flags=re.MULTILINE).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # 3. Extract first {...} block
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Cannot extract JSON from model output: {text[:300]!r}")


def _parse_response(data: dict[str, Any], files: list[ChangedFile]) -> AnalysisResult:
    """Convert the model JSON into an AnalysisResult, validating fields."""
    known_filenames = {f.filename for f in files}

    risk_level = str(data.get("risk_level", "low")).lower()
    if risk_level not in _RISK_LEVEL_VALUES:
        risk_level = "low"

    risk_score = data.get("risk_score", 0)
    try:
        risk_score = max(0, min(100, int(risk_score)))
    except (TypeError, ValueError):
        risk_score = 0

    summary = str(data.get("summary", "Analysis complete."))[:500]

    # Validate affected_files — only keep names that actually appear in the diff
    raw_files = data.get("affected_files", [])
    affected_files: list[str] = []
    if isinstance(raw_files, list):
        for fn in raw_files:
            fn = str(fn).strip()
            # Accept exact matches; also accept basenames that resolve to a known path
            if fn in known_filenames:
                affected_files.append(fn)
            else:
                # Try basename match for loose model output
                for kf in known_filenames:
                    if kf.endswith(fn) or fn.endswith(kf.split("/")[-1]):
                        affected_files.append(kf)
                        break
    # Deduplicate, preserve order
    seen: set[str] = set()
    deduped: list[str] = []
    for fn in affected_files:
        if fn not in seen:
            seen.add(fn)
            deduped.append(fn)
    affected_files = deduped

    # Parse findings
    raw_findings = data.get("findings", [])
    findings: list[Finding] = []
    if isinstance(raw_findings, list):
        for raw in raw_findings:
            if not isinstance(raw, dict):
                continue
            severity = str(raw.get("severity", "low")).lower()
            if severity not in _SEVERITY_VALUES:
                severity = "low"

            # Resolve file field — never concatenate or keep "unknown" when
            # actual filenames are available
            file_val = str(raw.get("file", "general")).strip()
            if file_val in ("unknown", "", "general") and len(known_filenames) == 1:
                file_val = next(iter(known_filenames))
            elif file_val not in known_filenames and file_val not in ("general",):
                # Try suffix match
                matched = next(
                    (kf for kf in known_filenames if kf.endswith(file_val) or file_val.endswith(kf.split("/")[-1])),
                    file_val,
                )
                file_val = matched

            findings.append(
                Finding(
                    file=file_val,
                    line_hint=str(raw.get("line", "N/A")),
                    category=str(raw.get("category", "General"))[:80],
                    description=str(raw.get("description", ""))[:500],
                    suggestion=str(raw.get("suggestion", ""))[:500],
                    severity=severity,
                )
            )

    safer_alternatives: list[str] = []
    if isinstance(data.get("safer_alternatives"), list):
        safer_alternatives = [str(s)[:300] for s in data["safer_alternatives"][:5]]

    recommended_tests: list[str] = []
    if isinstance(data.get("recommended_tests"), list):
        recommended_tests = [str(t)[:300] for t in data["recommended_tests"][:5]]

    return AnalysisResult(
        findings=findings,
        summary=summary,
        risk_level=risk_level,
        risk_score=risk_score,
        affected_files=affected_files,
        safer_alternatives=safer_alternatives,
        recommended_tests=recommended_tests,
    )


# ── Main entry point ──────────────────────────────────────────────────────────

def analyze_with_watsonx(files: list[ChangedFile]) -> AnalysisResult:
    """
    Send the diff to IBM watsonx.ai and return a structured AnalysisResult.

    Raises WatsonxUnavailable if:
      - credentials are not configured
      - the SDK raises any exception
      - the model response cannot be parsed
    """
    # Import here so the module is importable even when the SDK is not installed
    try:
        from ibm_watsonx_ai import APIClient, Credentials
        from ibm_watsonx_ai.foundation_models import ModelInference
        from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams
    except ImportError as exc:
        raise WatsonxUnavailable("ibm-watsonx-ai SDK not installed") from exc

    from config import get_settings
    settings = get_settings()

    if not settings.watsonx_apikey or not settings.watsonx_project_id:
        raise WatsonxUnavailable("WATSONX_APIKEY or WATSONX_PROJECT_ID not set")

    diff_text = _build_prompt(files)
    # Keep prompt under ~3000 tokens — truncate if enormous
    if len(diff_text) > 12000:
        diff_text = diff_text[:12000] + "\n... (diff truncated for length)"

    prompt = _USER_PROMPT_TEMPLATE.format(diff_text=diff_text)

    try:
        credentials = Credentials(
            url=settings.watsonx_url,
            api_key=settings.watsonx_apikey,
        )
        client = APIClient(credentials=credentials, project_id=settings.watsonx_project_id)

        model = ModelInference(
            model_id=settings.watsonx_model_id,
            api_client=client,
        )

        params = {
            GenParams.MAX_NEW_TOKENS: 1500,
            GenParams.MIN_NEW_TOKENS: 50,
            GenParams.TEMPERATURE: 0.0,
            GenParams.DECODING_METHOD: "greedy",
            GenParams.STOP_SEQUENCES: [],
        }

        # Build messages for chat/instruct models
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ]

        response = model.chat(messages=messages, params=params)

        # Extract generated text from response
        raw_text: str = ""
        if isinstance(response, dict):
            # Standard chat completion shape
            choices = response.get("choices", [])
            if choices:
                raw_text = choices[0].get("message", {}).get("content", "")
            if not raw_text:
                # Older generate shape
                results = response.get("results", [])
                if results:
                    raw_text = results[0].get("generated_text", "")
        else:
            raw_text = str(response)

        if not raw_text.strip():
            raise WatsonxUnavailable("Model returned an empty response")

        logger.info("watsonx raw response length=%d", len(raw_text))

        data = _extract_json(raw_text)
        return _parse_response(data, files)

    except WatsonxUnavailable:
        raise
    except Exception as exc:
        logger.warning("watsonx.ai call failed: %s", exc)
        raise WatsonxUnavailable(f"watsonx.ai error: {exc}") from exc
