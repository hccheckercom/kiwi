# Phase 2: Auto-Fix Engine

## Mục tiêu

Lesson không chỉ detect mà còn biết cách sửa. Chuyển Kiwi từ "đây là lỗi" sang "đây là lỗi, đây là cách sửa".

## Lesson Schema Extension

### Thêm `fix` field vào frontmatter

```yaml
---
id: LES-016
severity: CRITICAL
category: php-security
title: "Order page thiếu IDOR check"
scan:
  type: cross-check
  pattern: '\$_GET\[''order_id''\]'
  scope: "wezone-templates/account/*.php"
  cross_check: "user_id.*get_current_user_id"

# ← NEW: fix field
fix:
  type: replace          # replace | template | llm
  search: '(\$order_id\s*=\s*)(.*\$_GET\[.order_id.\].*);'
  replace: |
    $1absint($2);
    if (!wz_verify_order_owner($order_id)) {
        wp_die('Unauthorized');
    }
---
```

### 3 Fix Types

#### Type 1: `replace` (80% cases)

Regex search/replace trên file chứa violation. Dùng cho: sanitize input, swap function call, thêm type cast.

```yaml
fix:
  type: replace
  search: 'pattern to find (regex)'
  replace: 'replacement (supports \1 \2 backreferences)'
  # Optional:
  flags: 'MULTILINE'    # regex flags
  confirm: true          # require user confirmation (default: true)
```

**Ví dụ thực tế:**

```yaml
# LES-006: Hardcoded color → CSS token
fix:
  type: replace
  search: 'color:\s*#([0-9a-fA-F]{3,8})'
  replace: 'color: var(--color-\1)  /* TODO: map to correct token */'

# LES-362: innerHTML XSS → textContent
fix:
  type: replace
  search: '\.innerHTML\s*=\s*(.*);'
  replace: '.textContent = \1;'

# LES-411: $_GET without sanitize
fix:
  type: replace
  search: '\$_GET\[.(\w+).\]'
  replace: "sanitize_text_field($_GET['\\1'])"
```

#### Type 2: `template` (15% cases)

Inject code block at specific position. Dùng cho: guard clauses, nonce checks, wrapper functions.

```yaml
fix:
  type: template
  position: before       # before | after | wrap
  anchor: 'pattern to find insertion point'
  code: |
    if (!wp_verify_nonce($_POST['_wpnonce'], 'action_name')) {
        wp_die('Invalid nonce');
    }
  # Optional:
  indent: auto           # auto-detect indentation from anchor line
```

**Ví dụ thực tế:**

```yaml
# LES-429: Missing nonce check
fix:
  type: template
  position: before
  anchor: '\$_POST\[.action.\]'
  code: |
    if (!wp_verify_nonce($_POST['_wpnonce'], 'wz_action')) {
        wp_die('Security check failed');
    }
  indent: auto

# LES-010: Missing wezone_is_active() guard
fix:
  type: template
  position: before
  anchor: '^<\?php'    # top of file
  code: |
    <?php
    if (!function_exists('wezone_is_active') || !wezone_is_active()) {
        return;
    }
```

#### Type 3: `llm` (5% cases)

Context quá phức tạp cho regex — cần LLM reasoning. Lesson cung cấp prompt + context instructions.

```yaml
fix:
  type: llm
  prompt: |
    Fix this IDOR vulnerability. The order_id comes from user input
    but there's no ownership check. Add a check that verifies
    the order belongs to the current user using wz_verify_order_owner().
    Keep the existing logic intact, only add the security check.
  context_lines: 20     # read N lines around violation for context
  model: sonnet          # sonnet | opus (default: sonnet for cost)
```

**Khi nào dùng `llm`:**
- Cross-file dependencies (fix cần hiểu code ở file khác)
- Logic phức tạp (if/else chains, state machines)
- Refactoring (không chỉ thêm/sửa 1 chỗ)

## Fixer Module

### File: `.claude/kiwi/scanner/fixer.py`

```python
"""Auto-fix engine for Kiwi violations."""

import re
from dataclasses import dataclass
from pathlib import Path

@dataclass
class FixResult:
    lesson_id: str
    file: str
    fix_type: str       # "replace" | "template" | "llm"
    success: bool
    old_lines: str      # affected lines (before)
    new_lines: str      # affected lines (after)
    diff: str           # unified diff
    error: str = ""

def apply_fix(violation, fix_config: dict, dry_run: bool = True) -> FixResult:
    """Apply fix from lesson config to a violation.
    
    Args:
        violation: Violation dataclass (lesson_id, file, line, match_text)
        fix_config: The 'fix' dict from lesson frontmatter
        dry_run: If True, return diff without modifying file
    
    Returns:
        FixResult with diff preview or applied changes
    """
    fix_type = fix_config.get("type", "replace")
    
    if fix_type == "replace":
        return _apply_replace(violation, fix_config, dry_run)
    elif fix_type == "template":
        return _apply_template(violation, fix_config, dry_run)
    elif fix_type == "llm":
        return _apply_llm(violation, fix_config, dry_run)
    else:
        return FixResult(
            lesson_id=violation.lesson_id,
            file=violation.file,
            fix_type=fix_type,
            success=False,
            old_lines="", new_lines="", diff="",
            error=f"Unknown fix type: {fix_type}"
        )

def _apply_replace(violation, fix_config, dry_run):
    """Regex search/replace fix."""
    file_path = Path(violation.file)
    content = file_path.read_text(encoding="utf-8")
    
    search = fix_config["search"]
    replace = fix_config["replace"]
    flags = _parse_flags(fix_config.get("flags", ""))
    
    new_content = re.sub(search, replace, content, flags=flags)
    
    if new_content == content:
        return FixResult(
            lesson_id=violation.lesson_id, file=violation.file,
            fix_type="replace", success=False,
            old_lines="", new_lines="", diff="",
            error="Pattern not found in file"
        )
    
    diff = _make_diff(content, new_content, violation.file)
    
    if not dry_run:
        file_path.write_text(new_content, encoding="utf-8")
    
    return FixResult(
        lesson_id=violation.lesson_id, file=violation.file,
        fix_type="replace", success=True,
        old_lines=_extract_context(content, violation.line),
        new_lines=_extract_context(new_content, violation.line),
        diff=diff
    )

def _apply_template(violation, fix_config, dry_run):
    """Inject code block at position."""
    # ... similar structure
    pass

def _apply_llm(violation, fix_config, dry_run):
    """Send to LLM for complex fix — returns placeholder in Phase 2."""
    return FixResult(
        lesson_id=violation.lesson_id, file=violation.file,
        fix_type="llm", success=False,
        old_lines="", new_lines="", diff="",
        error="LLM fix requires Phase 3 Agent Loop"
    )
```

## MCP Tool Update

`kiwi_fix` gains `apply` parameter:

```python
def _handle_fix(req_id, args):
    lesson_id = args["lesson_id"]
    file_path = args.get("file")
    line = args.get("line")
    apply = args.get("apply", False)
    
    # Load lesson
    lesson = _load_lesson(lesson_id)
    if not lesson:
        return _error(req_id, f"Lesson {lesson_id} not found")
    
    fix_config = lesson.get("fix")
    if not fix_config:
        # Fallback: return Good section
        good_code = get_fix_for_lesson(lesson_id)
        return _text_result(req_id, f"No auto-fix. Good example:\n```\n{good_code}\n```")
    
    # Create violation object
    violation = Violation(
        lesson_id=lesson_id,
        severity=lesson["severity"],
        category=lesson["category"],
        description=lesson["title"],
        file=file_path or "",
        line=line or 0,
    )
    
    result = apply_fix(violation, fix_config, dry_run=not apply)
    
    if result.success:
        action = "Applied" if apply else "Preview"
        return _text_result(req_id, f"{action} fix for {lesson_id}:\n```diff\n{result.diff}\n```")
    else:
        return _text_result(req_id, f"Fix failed: {result.error}")
```

## Initial Dataset — Top 30 CRITICAL Lessons

Priority order for adding `fix` field:

### Batch 1: php-security (10 lessons)
| ID | Title | Fix Type |
|----|-------|----------|
| LES-016 | IDOR order page | template (inject guard) |
| LES-362 | innerHTML XSS | replace (→ textContent) |
| LES-411 | $_GET unsanitized | replace (wrap sanitize) |
| LES-413 | $_POST unsanitized | replace (wrap sanitize) |
| LES-429 | Missing nonce | template (inject check) |
| LES-430 | SQL injection | replace (use prepare()) |
| LES-434 | Missing capability check | template (inject guard) |
| LES-438 | Direct file inclusion | replace (use locate_template) |
| LES-440 | Unescaped output | replace (wrap esc_html) |
| LES-444 | Missing CSRF token | template (inject wp_nonce_field) |

### Batch 2: wezone-api (10 lessons)
| ID | Title | Fix Type |
|----|-------|----------|
| LES-013 | Shim signature mismatch | llm (complex) |
| LES-038 | Cart response missing keys | template |
| LES-432 | Missing wz_config() | template (inject at boot) |
| LES-433 | N+1 insert loop | replace (→ wz_bulk_insert) |
| LES-436 | Wrong category query | replace (→ wz_get_related) |
| ... | | |

### Batch 3: css-tokens + file-structure (10 lessons)
| ID | Title | Fix Type |
|----|-------|----------|
| LES-006 | Hardcoded color | replace (→ var()) |
| LES-010 | Template: in style.css | replace (remove line) |
| ... | | |

## Verification

1. Pick 5 lessons, add `fix` field manually
2. Run `kiwi_fix --lesson_id LES-411 --file test.php` in dry-run → verify diff
3. Run with `--apply` → verify file changed correctly
4. Re-scan → verify violation gone
5. Check no new violations introduced by fix