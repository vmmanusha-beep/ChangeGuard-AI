import re
from dataclasses import dataclass, field


@dataclass
class DiffHunk:
    header: str
    old_start: int
    new_start: int
    removed_lines: list[str] = field(default_factory=list)
    added_lines: list[str] = field(default_factory=list)
    context_lines: list[str] = field(default_factory=list)


@dataclass
class ChangedFile:
    filename: str
    is_new: bool = False
    is_deleted: bool = False
    hunks: list[DiffHunk] = field(default_factory=list)

    @property
    def added_count(self) -> int:
        return sum(len(h.added_lines) for h in self.hunks)

    @property
    def removed_count(self) -> int:
        return sum(len(h.removed_lines) for h in self.hunks)

    @property
    def all_added_lines(self) -> list[str]:
        return [line for h in self.hunks for line in h.added_lines]

    @property
    def all_removed_lines(self) -> list[str]:
        return [line for h in self.hunks for line in h.removed_lines]


def _extract_git_path(diff_git_line: str) -> str:
    """
    Extract the destination filename from a 'diff --git a/X b/Y' line.
    Returns the b/ path (after last ' b/') which is the new filename.
    Falls back to the a/ path for deletions.
    """
    # Match: diff --git a/<path> b/<path>
    m = re.match(r"diff --git a/(.*) b/(.*)", diff_git_line)
    if m:
        return m.group(2).strip()
    return ""


def _strip_prefix(path: str) -> str:
    """Strip leading a/ or b/ git prefix from a path."""
    if path.startswith("b/") or path.startswith("a/"):
        return path[2:]
    return path


def parse_diff(raw_diff: str) -> list[ChangedFile]:
    """Parse a unified git diff string into structured ChangedFile objects."""
    files: list[ChangedFile] = []
    current_file: ChangedFile | None = None
    current_hunk: DiffHunk | None = None
    # Filename extracted from the 'diff --git' header line, used as fallback
    # when +++ line is missing or is /dev/null (new-file / deleted-file diffs)
    pending_git_path: str = ""

    def _flush():
        nonlocal current_file, current_hunk
        if current_file is not None:
            if current_hunk is not None:
                current_file.hunks.append(current_hunk)
                current_hunk = None
            files.append(current_file)
            current_file = None

    for line in raw_diff.splitlines():

        # ── diff --git header ──────────────────────────────────────────────
        if line.startswith("diff --git "):
            _flush()
            pending_git_path = _extract_git_path(line)
            # Create a provisional file entry from the git header so that
            # mode-only diffs (no --- / +++ lines) still produce a record.
            current_file = ChangedFile(filename=pending_git_path or "unknown")

        # ── --- line (old file) ────────────────────────────────────────────
        elif line.startswith("--- "):
            # Mark deleted files detected via '--- a/file' when +++ is /dev/null
            old_path = line[4:].strip()
            if old_path == "/dev/null":
                # This is a new file being created; +++ will set the real name
                pass
            # else: we wait for +++ to set the canonical name

        # ── +++ line (new file) ────────────────────────────────────────────
        elif line.startswith("+++ "):
            raw_path = line[4:].strip()
            if raw_path == "/dev/null":
                # File was deleted — keep the name from --- / diff --git
                # Mark deletion on current_file
                if current_file is not None:
                    current_file.is_deleted = True
                    # Re-derive name from git header if still "unknown"
                    if current_file.filename in ("unknown", "") and pending_git_path:
                        current_file.filename = pending_git_path
            else:
                canonical = _strip_prefix(raw_path)
                if current_file is not None:
                    # Update the provisional filename set by diff --git
                    current_file.filename = canonical
                else:
                    current_file = ChangedFile(filename=canonical)

        # ── new file / deleted file mode lines ────────────────────────────
        elif line.startswith("new file"):
            if current_file is not None:
                current_file.is_new = True

        elif line.startswith("deleted file"):
            if current_file is not None:
                current_file.is_deleted = True
                if current_file.filename in ("unknown", "") and pending_git_path:
                    current_file.filename = pending_git_path

        # ── @@ hunk header ────────────────────────────────────────────────
        elif line.startswith("@@"):
            if current_file is None:
                # Hunk with no preceding diff header — use pending path or "unknown"
                current_file = ChangedFile(filename=pending_git_path or "unknown")
            if current_hunk is not None:
                current_file.hunks.append(current_hunk)
            match = re.search(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            old_start = int(match.group(1)) if match else 0
            new_start = int(match.group(2)) if match else 0
            current_hunk = DiffHunk(
                header=line,
                old_start=old_start,
                new_start=new_start,
            )

        # ── diff content lines ─────────────────────────────────────────────
        elif current_hunk is not None:
            if line.startswith("+"):
                current_hunk.added_lines.append(line[1:])
            elif line.startswith("-"):
                current_hunk.removed_lines.append(line[1:])
            elif line.startswith(" "):
                current_hunk.context_lines.append(line[1:])

    # Flush the last file
    _flush()

    return files
