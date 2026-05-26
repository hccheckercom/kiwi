"""Fix remaining YAML frontmatter issues: unescaped quotes, special chars."""
import re
import yaml
from pathlib import Path

lessons_dir = Path(__file__).parent.parent / "lessons"
fixed = 0
still_broken = []

for md in sorted(lessons_dir.rglob("*.md")):
    content = md.read_text(encoding="utf-8")
    if not content.startswith("---"):
        continue

    end_idx = content.find("\n---", 3)
    if end_idx == -1:
        continue

    yaml_block = content[4:end_idx]
    body = content[end_idx:]

    # Test if already valid
    try:
        data = yaml.safe_load(yaml_block)
        if data and "scan" in data and data["scan"] and "pattern" in data["scan"]:
            continue  # Already works
    except yaml.YAMLError:
        pass

    # Fix: rewrite the scan block with proper YAML quoting
    lines = yaml_block.split("\n")
    new_lines = []
    in_scan = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("scan:"):
            in_scan = True
            new_lines.append(line)
            continue

        if not line.startswith(" ") and ":" in stripped and stripped != "":
            in_scan = False

        if in_scan and ":" in stripped:
            indent = len(line) - len(line.lstrip())
            parts = stripped.split(":", 1)
            key = parts[0].strip()
            val = parts[1].strip() if len(parts) > 1 else ""

            if val and key in ("pattern", "exclude", "exclude_line", "pre_check",
                               "cross_check", "cross_check_scope", "scope"):
                # Strip existing quotes
                if (val.startswith('"') and val.endswith('"')) or \
                   (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]

                # Use single quotes, escape internal single quotes
                val_safe = val.replace("'", "''")
                new_lines.append(f"{' ' * indent}{key}: '{val_safe}'")
                continue

        new_lines.append(line)

    new_yaml = "\n".join(new_lines)

    # Verify the fix works
    try:
        data = yaml.safe_load(new_yaml)
        if data and "scan" in data and data["scan"] and "pattern" in data["scan"]:
            new_content = "---\n" + new_yaml + body
            md.write_text(new_content, encoding="utf-8")
            fixed += 1
        else:
            still_broken.append(f"{md.parent.name}/{md.name}: parsed but no scan.pattern")
    except yaml.YAMLError as e:
        still_broken.append(f"{md.parent.name}/{md.name}: {str(e)[:60]}")

print(f"Fixed: {fixed}")
if still_broken:
    print(f"Still broken: {len(still_broken)}")
    for s in still_broken:
        print(f"  {s}")