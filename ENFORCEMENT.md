# Kiwi Context Enforcement — System Reminder

**⛔ CRITICAL RULE — ENFORCED BY SYSTEM:**

Before calling `Write()` or `Edit()` on any file ending with `.php`, `.css`, `.js`, `.ts`, `.tsx`, `.jsx`:

## STEP 1: CHECK
```
IF file_path ends with (.php|.css|.js|.ts|.tsx|.jsx):
  IF kiwi_context has NOT been called in this conversation:
    → STOP — DO NOT proceed with Write/Edit
    → GO TO STEP 2
```

## STEP 2: CALL kiwi_context FIRST
```javascript
// Task code mới / feature mới
mcp__kiwi__kiwi_context({
  task: "mô tả task cụ thể",
  platform: "wp|nextjs",
  scope_type: "plugin|theme",
  compact: false  // full context
})

// Fix nhỏ / sửa bug / edit < 10 dòng
mcp__kiwi__kiwi_context({
  task: "mô tả task cụ thể",
  compact: true  // tiết kiệm ~70% token
})
```

## STEP 3: READ OUTPUT
- Nắm rules, anti-patterns, snippets từ kiwi_context
- SAU ĐÓ mới Write/Edit

## WHY THIS MATTERS
- **Vi phạm = code thiếu context** → dễ lặp bug đã biết → phải sửa lại → lãng phí token
- Post-edit hook sẽ scan CRITICAL sau khi Write/Edit → nếu BLOCK phải fix ngay

## ENFORCEMENT MECHANISM
1. **System prompt** — rule này được inject vào mọi conversation
2. **Post-edit hook** — `.claude/kiwi/hooks/post_edit.py` tự động scan CRITICAL sau mỗi file
3. **Self-check** — Claude phải tự kiểm tra trước mỗi Write/Edit

## EXCEPTIONS
- File không phải code (`.md`, `.json`, `.txt`, `.yml`) → không cần kiwi_context
- File config thuần (không chứa logic) → không cần kiwi_context
- Khi đã gọi kiwi_context trong conversation → không cần gọi lại

## VERIFICATION
Sau mỗi Write/Edit file code:
```javascript
// Verify với kiwi_check
mcp__kiwi__kiwi_check({
  file: "path/to/file.php"
})
```