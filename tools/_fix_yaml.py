"""Fix YAML frontmatter: convert double-quoted patterns with backslashes to single quotes."""
import re
from pathlib import Path

lessons_dir = Path(__file__).parent.parent / "lessons"
fixed = 0

for md in sorted(lessons_dir.rglob("*.md")):
    content = md.read_text(encoding="utf-8")
    if not content.startswith("---"):
        continue

    end_idx = content.find("\n---", 3)
    if end_idx == -1:
        continue

    header = content[: end_idx + 4]
    body = content[end_idx + 4:]
    original = header

    # Fix double-quoted values containing backslashes in scan block
    def replace_dq(m):
        prefix = m.group(1)
        val = m.group(2)
        # Escape any single quotes inside
        val_safe = val.replace("'", "''")
        return f"{prefix}'{val_safe}'"

    # Match key: "value" where value contains backslash
    header = re.sub(
        r'(\s+(?:pattern|exclude|exclude_line|pre_check|cross_check|cross_check_scope|scope):\s*)"([^"]*\\[^"]*)"',
        replace_dq,
        header,
    )

    # Also fix title containing special YAML chars
    def fix_title(m):
        prefix = m.group(1)
        val = m.group(2)
        if "\\" in val or ": " in val:
            val_safe = val.replace("'", "''")
            return f"{prefix}'{val_safe}'"
        return m.group(0)

    header = re.sub(r'(title:\s*)"([^"]*)"', fix_title, header)

    if header != original:
        md.write_text(header + body, encoding="utf-8")
        fixed += 1

print(f"Fixed: {fixed}")