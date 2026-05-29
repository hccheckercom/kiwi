"""Idempotent anchor writer for CLAUDE.md / AGENTS.md.

Inserts a KIWI:BEGIN/END block telling agents to call kiwi_context before
Write/Edit on code files. The block is auto-managed and re-runs replace
the existing block in-place rather than duplicating.

Usage:
    python tools/anchor_writer.py /path/to/project [--yes] [--remove]
        [--cursor] [--windsurf] [--all]

Behaviour:
- First run on a target file prompts Y/N unless --yes is passed.
- Re-runs are silent and idempotent (replace block between markers).
- --remove strips the block (and removes the file if it was created
  by this tool and now becomes empty after stripping the trailing newline).
- --all writes CLAUDE.md/AGENTS.md plus Cursor + Windsurf rule files.

Exit codes:
    0 — success or no-op
    1 — user declined or write failed
    2 — invalid arguments
"""

import argparse
import os
import sys
from pathlib import Path

ANCHOR_BEGIN = "<!-- KIWI:BEGIN (auto-managed by anchor_writer.py — do not edit) -->"
ANCHOR_END = "<!-- KIWI:END -->"

ANCHOR_BODY = """\
## Kiwi Gate — đọc trước khi code

Trước khi Write/Edit bất kỳ file `.php` / `.css` / `.js` / `.ts` / `.tsx` / `.jsx`:
→ BẮT BUỘC gọi `kiwi_context(task=..., target_file=..., compact=true|false)` TRƯỚC.

Bỏ qua = code có thể bị PreToolUse hook chặn (Claude Code) hoặc thiếu context
quan trọng (rules, anti-patterns, snippets, learned conventions).

Nếu sửa file có sẵn — luôn truyền `target_file=` để Kiwi quét tín hiệu nội dung
(+30 boost). Task mơ hồ + không có file = Kiwi rớt về chấm điểm severity-only.
"""

CURSOR_RULE_PATH = ".cursor/rules/kiwi.mdc"
WINDSURF_RULE_PATH = ".windsurfrules"


def _build_block() -> str:
    return f"{ANCHOR_BEGIN}\n{ANCHOR_BODY}{ANCHOR_END}\n"


def _has_block(content: str) -> bool:
    return ANCHOR_BEGIN in content and ANCHOR_END in content


def _replace_block(content: str, block: str) -> str:
    start = content.find(ANCHOR_BEGIN)
    end = content.find(ANCHOR_END, start)
    if start == -1 or end == -1:
        return content
    end_with_marker = end + len(ANCHOR_END)
    tail = content[end_with_marker:]
    if tail.startswith("\n"):
        tail = tail[1:]
    return content[:start] + block + tail


def _strip_block(content: str) -> str:
    start = content.find(ANCHOR_BEGIN)
    end = content.find(ANCHOR_END, start)
    if start == -1 or end == -1:
        return content
    end_with_marker = end + len(ANCHOR_END)
    tail = content[end_with_marker:]
    if tail.startswith("\n"):
        tail = tail[1:]
    head = content[:start].rstrip("\n")
    if head and tail:
        return head + "\n\n" + tail
    return head or tail


def _confirm(path: Path, action: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        print(f"[kiwi-anchor] {action} {path} — non-interactive, pass --yes to proceed",
              file=sys.stderr)
        return False
    resp = input(f"[kiwi-anchor] {action} {path}? [y/N] ").strip().lower()
    return resp in ("y", "yes")


def write_anchor(target: Path, assume_yes: bool, remove: bool) -> int:
    block = _build_block()
    existed = target.exists()
    content = target.read_text(encoding="utf-8") if existed else ""

    if remove:
        if not existed or not _has_block(content):
            return 0
        new_content = _strip_block(content)
        if not new_content.strip() and not existed:
            target.unlink()
            print(f"[kiwi-anchor] removed {target} (file now empty)")
            return 0
        target.write_text(new_content, encoding="utf-8")
        print(f"[kiwi-anchor] stripped Kiwi block from {target}")
        return 0

    if existed and _has_block(content):
        new_content = _replace_block(content, block)
        if new_content == content:
            return 0
        target.write_text(new_content, encoding="utf-8")
        print(f"[kiwi-anchor] refreshed Kiwi block in {target}")
        return 0

    action = "Create" if not existed else "Insert Kiwi block into"
    if not _confirm(target, action, assume_yes):
        print(f"[kiwi-anchor] skipped {target}")
        return 1

    if existed:
        new_content = block + "\n" + content if content else block
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        new_content = block

    target.write_text(new_content, encoding="utf-8")
    print(f"[kiwi-anchor] wrote Kiwi block to {target}")
    return 0


def _resolve_targets(project_root: Path, write_cursor: bool, write_windsurf: bool) -> list:
    claude_md = project_root / "CLAUDE.md"
    agents_md = project_root / "AGENTS.md"

    targets = []
    if claude_md.exists():
        targets.append(claude_md)
    else:
        targets.append(agents_md)

    if write_cursor:
        targets.append(project_root / CURSOR_RULE_PATH)
    if write_windsurf:
        targets.append(project_root / WINDSURF_RULE_PATH)

    return targets


def main():
    parser = argparse.ArgumentParser(
        description="Insert/remove the Kiwi anchor block in CLAUDE.md / AGENTS.md."
    )
    parser.add_argument("project_root", help="Project root directory.")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Skip confirmation when creating/inserting the block.")
    parser.add_argument("--remove", action="store_true",
                        help="Strip the Kiwi block instead of writing it.")
    parser.add_argument("--cursor", action="store_true",
                        help="Also write .cursor/rules/kiwi.mdc.")
    parser.add_argument("--windsurf", action="store_true",
                        help="Also write .windsurfrules.")
    parser.add_argument("--all", action="store_true",
                        help="Write CLAUDE.md/AGENTS.md + Cursor + Windsurf.")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    if not project_root.is_dir():
        print(f"[kiwi-anchor] not a directory: {project_root}", file=sys.stderr)
        sys.exit(2)

    write_cursor = args.cursor or args.all
    write_windsurf = args.windsurf or args.all

    targets = _resolve_targets(project_root, write_cursor, write_windsurf)
    rc = 0
    for t in targets:
        rc |= write_anchor(t, assume_yes=args.yes, remove=args.remove)
    sys.exit(rc)


if __name__ == "__main__":
    main()