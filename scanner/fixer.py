"""Auto-fix engine for Kiwi violations (Phase 2 with rollback)."""

import difflib
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FixResult:
    lesson_id: str
    file: str
    fix_type: str
    success: bool
    old_lines: str
    new_lines: str
    diff: str
    error: str = ""
    verified: bool = False
    rolled_back: bool = False


def apply_fix(violation, fix_config: dict, dry_run: bool = True, enable_rollback: bool = True) -> FixResult:
    fix_type = fix_config.get("type", "replace")
    file_path = violation.file

    if not file_path or not Path(file_path).is_file():
        return FixResult(
            lesson_id=violation.lesson_id, file=file_path or "",
            fix_type=fix_type, success=False,
            old_lines="", new_lines="", diff="",
            error=f"File not found: {file_path}",
        )

    # Create rollback checkpoint if enabled and not dry_run
    rollback = None
    original_content = None
    if enable_rollback and not dry_run:
        try:
            # Import here to avoid circular dependency
            kiwi_dir = Path(__file__).parent.parent
            sys.path.insert(0, str(kiwi_dir))
            from rollback.git_rollback import GitRollback, verify_fix_safety

            # Get project root (go up from scanner/ to kiwi/ to project/)
            project_root = kiwi_dir.parent.parent
            rollback = GitRollback(str(project_root))

            # Save original content for verification
            original_content = Path(file_path).read_text(encoding="utf-8")

            # Create checkpoint
            if not rollback.create_checkpoint([file_path]):
                # Checkpoint failed, but continue (rollback just won't be available)
                rollback = None
        except Exception:
            # Rollback setup failed, continue without it
            rollback = None

    if fix_type == "replace":
        result = _apply_replace(violation, fix_config, dry_run)
    elif fix_type == "template":
        result = _apply_template(violation, fix_config, dry_run)
    elif fix_type == "wrap":
        result = _apply_wrap(violation, fix_config, dry_run)
    elif fix_type == "delete":
        result = _apply_delete(violation, fix_config, dry_run)
    elif fix_type == "llm":
        result = FixResult(
            lesson_id=violation.lesson_id, file=file_path,
            fix_type="llm", success=False,
            old_lines="", new_lines="", diff="",
            error=f"LLM fix — prompt: {fix_config.get('prompt', 'No prompt')}",
        )
    else:
        result = FixResult(
            lesson_id=violation.lesson_id, file=file_path,
            fix_type=fix_type, success=False,
            old_lines="", new_lines="", diff="",
            error=f"Unknown fix type: {fix_type}",
        )

    if result.success and not dry_run:
        result.verified = _verify_fix(violation, fix_config)

        # Verify fix safety and rollback if needed
        if enable_rollback and rollback and original_content:
            try:
                from rollback.git_rollback import verify_fix_safety
                from rollback.test_verifier import TestVerifier

                # Step 1: Basic safety checks (syntax, file size, etc.)
                is_safe, reason = verify_fix_safety(file_path, original_content)

                if not is_safe:
                    # Fix broke the file, rollback
                    success, message = rollback.rollback()
                    result.success = False
                    result.error = f"Fix broke file ({reason}), rolled back: {message}"
                    result.rolled_back = success
                else:
                    # Step 2: Run tests if available
                    kiwi_dir = Path(__file__).parent.parent
                    project_root = kiwi_dir.parent.parent
                    test_verifier = TestVerifier(str(project_root))

                    test_safe, test_reason = test_verifier.verify_fix_safe(file_path)

                    if not test_safe:
                        # Tests failed, rollback
                        success, message = rollback.rollback()
                        result.success = False
                        result.error = f"Tests failed after fix ({test_reason}), rolled back: {message}"
                        result.rolled_back = success
                    else:
                        # All checks passed, cleanup checkpoint
                        rollback.cleanup()
            except Exception as e:
                # Verification failed, but don't rollback automatically
                result.error = f"Verification error: {e}"

    return result


def _apply_replace(violation, fix_config: dict, dry_run: bool) -> FixResult:
    fp = Path(violation.file)
    content = fp.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)

    search = fix_config["search"]
    replace = fix_config["replace"]
    flags = _parse_flags(fix_config.get("flags", ""))
    target_line = violation.line

    if target_line > 0 and target_line <= len(lines):
        ctx_start = max(0, target_line - 4)
        ctx_end = min(len(lines), target_line + 3)
        context_block = "".join(lines[ctx_start:ctx_end])

        new_block = re.sub(search, replace, context_block, flags=flags)
        if new_block != context_block:
            new_lines = list(lines)
            new_lines[ctx_start:ctx_end] = new_block.splitlines(keepends=True)
            new_content = "".join(new_lines)
            old_ctx = _extract_context(lines, target_line)
            new_ctx = _extract_context(new_content.splitlines(keepends=True), target_line)
            diff = _make_diff(content, new_content, str(fp))

            if not dry_run:
                fp.write_text(new_content, encoding="utf-8")

            return FixResult(
                lesson_id=violation.lesson_id, file=str(fp),
                fix_type="replace", success=True,
                old_lines=old_ctx, new_lines=new_ctx, diff=diff,
            )

    new_content = re.sub(search, replace, content, flags=flags)
    if new_content == content:
        return FixResult(
            lesson_id=violation.lesson_id, file=str(fp),
            fix_type="replace", success=False,
            old_lines="", new_lines="", diff="",
            error="Pattern not found in file",
        )

    diff = _make_diff(content, new_content, str(fp))
    old_ctx = _extract_context(lines, target_line) if target_line > 0 else ""
    new_ctx = _extract_context(new_content.splitlines(keepends=True), target_line) if target_line > 0 else ""

    if not dry_run:
        fp.write_text(new_content, encoding="utf-8")

    return FixResult(
        lesson_id=violation.lesson_id, file=str(fp),
        fix_type="replace", success=True,
        old_lines=old_ctx, new_lines=new_ctx, diff=diff,
    )


def _apply_template(violation, fix_config: dict, dry_run: bool) -> FixResult:
    fp = Path(violation.file)
    content = fp.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)

    code = fix_config["code"]
    position = fix_config.get("position", "before")
    anchor = fix_config.get("anchor")
    target_line = violation.line

    insert_idx = None

    if anchor:
        insert_idx = _find_anchor(lines, anchor, target_line)
    elif target_line > 0:
        insert_idx = target_line - 1

    if insert_idx is None:
        return FixResult(
            lesson_id=violation.lesson_id, file=str(fp),
            fix_type="template", success=False,
            old_lines="", new_lines="", diff="",
            error=f"Anchor not found: {anchor}",
        )

    if _already_has_fix(lines, insert_idx, code):
        return FixResult(
            lesson_id=violation.lesson_id, file=str(fp),
            fix_type="template", success=True,
            old_lines="", new_lines="", diff="",
            error="Fix already applied",
            verified=True,
        )

    indent = fix_config.get("indent", "auto")
    if indent == "auto":
        ref_line = lines[insert_idx] if insert_idx < len(lines) else ""
        indent_str = re.match(r"^(\s*)", ref_line).group(1)
    else:
        indent_str = indent

    code_lines = code.rstrip("\n").split("\n")
    indented_code = "\n".join(indent_str + cl if cl.strip() else cl for cl in code_lines) + "\n"

    new_lines = list(lines)
    if position == "before":
        new_lines.insert(insert_idx, indented_code)
    elif position == "after":
        new_lines.insert(insert_idx + 1, indented_code)
    elif position == "wrap":
        original_line = new_lines[insert_idx]
        new_lines[insert_idx] = indented_code + original_line

    new_content = "".join(new_lines)
    diff = _make_diff(content, new_content, str(fp))
    old_ctx = _extract_context(lines, insert_idx + 1)
    new_ctx = _extract_context(new_content.splitlines(keepends=True), insert_idx + 1)

    if not dry_run:
        fp.write_text(new_content, encoding="utf-8")

    return FixResult(
        lesson_id=violation.lesson_id, file=str(fp),
        fix_type="template", success=True,
        old_lines=old_ctx, new_lines=new_ctx, diff=diff,
    )


def _apply_wrap(violation, fix_config: dict, dry_run: bool) -> FixResult:
    """Wrap existing code with guard/try-catch/condition."""
    fp = Path(violation.file)
    content = fp.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)

    target_line = violation.line
    if target_line <= 0 or target_line > len(lines):
        return FixResult(
            lesson_id=violation.lesson_id, file=str(fp),
            fix_type="wrap", success=False,
            old_lines="", new_lines="", diff="",
            error=f"Invalid line number: {target_line}",
        )

    prefix = fix_config.get("prefix", "")
    suffix = fix_config.get("suffix", "")
    indent = fix_config.get("indent", "auto")

    if indent == "auto":
        ref_line = lines[target_line - 1]
        indent_str = re.match(r"^(\s*)", ref_line).group(1)
    else:
        indent_str = indent

    original_line = lines[target_line - 1]
    wrapped_line = indent_str + prefix + original_line.lstrip() + suffix

    if not wrapped_line.endswith("\n"):
        wrapped_line += "\n"

    new_lines = list(lines)
    new_lines[target_line - 1] = wrapped_line
    new_content = "".join(new_lines)

    diff = _make_diff(content, new_content, str(fp))
    old_ctx = _extract_context(lines, target_line)
    new_ctx = _extract_context(new_content.splitlines(keepends=True), target_line)

    if not dry_run:
        fp.write_text(new_content, encoding="utf-8")

    return FixResult(
        lesson_id=violation.lesson_id, file=str(fp),
        fix_type="wrap", success=True,
        old_lines=old_ctx, new_lines=new_ctx, diff=diff,
    )


def _apply_delete(violation, fix_config: dict, dry_run: bool) -> FixResult:
    """Delete code block (line or range)."""
    fp = Path(violation.file)
    content = fp.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)

    target_line = violation.line
    line_count = fix_config.get("line_count", 1)

    if target_line <= 0 or target_line > len(lines):
        return FixResult(
            lesson_id=violation.lesson_id, file=str(fp),
            fix_type="delete", success=False,
            old_lines="", new_lines="", diff="",
            error=f"Invalid line number: {target_line}",
        )

    start_idx = target_line - 1
    end_idx = min(len(lines), start_idx + line_count)

    old_ctx = _extract_context(lines, target_line)

    new_lines = lines[:start_idx] + lines[end_idx:]
    new_content = "".join(new_lines)

    diff = _make_diff(content, new_content, str(fp))
    new_ctx = _extract_context(new_content.splitlines(keepends=True), max(1, target_line - 1))

    if not dry_run:
        fp.write_text(new_content, encoding="utf-8")

    return FixResult(
        lesson_id=violation.lesson_id, file=str(fp),
        fix_type="delete", success=True,
        old_lines=old_ctx, new_lines=new_ctx, diff=diff,
    )


def _find_anchor(lines: list, anchor: str, target_line: int) -> int:
    """Find anchor with expanding search windows."""
    pattern = re.compile(anchor)

    windows = [
        (max(0, target_line - 5), min(len(lines), target_line + 5)),
        (max(0, target_line - 20), min(len(lines), target_line + 20)),
        (max(0, target_line - 50), min(len(lines), target_line + 50)),
        (0, len(lines)),
    ]

    for start, end in windows:
        best_idx = None
        best_dist = float("inf")
        for i in range(start, end):
            if pattern.search(lines[i]):
                dist = abs(i - (target_line - 1))
                if dist < best_dist:
                    best_dist = dist
                    best_idx = i
        if best_idx is not None:
            return best_idx

    return None


def _already_has_fix(lines: list, insert_idx: int, code: str) -> bool:
    """Check if fix code is already present near insertion point."""
    first_code_line = code.strip().split("\n")[0].strip()
    if not first_code_line:
        return False

    check_start = max(0, insert_idx - 5)
    check_end = min(len(lines), insert_idx + 5)

    for i in range(check_start, check_end):
        if first_code_line in lines[i]:
            return True

    return False


def _verify_fix(violation, fix_config: dict) -> bool:
    """Re-check file after fix to verify violation is gone."""
    fp = Path(violation.file)
    if not fp.is_file():
        return False

    try:
        content = fp.read_text(encoding="utf-8")
    except (OSError, IOError):
        return False

    scan_pattern = fix_config.get("_scan_pattern")
    if not scan_pattern:
        return True

    lines = content.splitlines()
    target = violation.line - 1
    if 0 <= target < len(lines):
        if not re.search(scan_pattern, lines[target]):
            return True
        return False

    return True


def _parse_flags(flags_str: str) -> int:
    flags = 0
    for f in flags_str.upper().split("|"):
        f = f.strip()
        if f == "MULTILINE":
            flags |= re.MULTILINE
        elif f == "DOTALL":
            flags |= re.DOTALL
        elif f == "IGNORECASE":
            flags |= re.IGNORECASE
    return flags


def _extract_context(lines, target_line: int, window: int = 3) -> str:
    if isinstance(lines, str):
        lines = lines.splitlines(keepends=True)
    start = max(0, target_line - window - 1)
    end = min(len(lines), target_line + window)
    result = []
    for i in range(start, end):
        prefix = ">>> " if i == target_line - 1 else "    "
        line_content = lines[i].rstrip("\n") if i < len(lines) else ""
        result.append(f"{prefix}{i+1:4d} | {line_content}")
    return "\n".join(result)


def _make_diff(old_content: str, new_content: str, filepath: str) -> str:
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{filepath}", tofile=f"b/{filepath}", n=3)
    return "".join(diff)