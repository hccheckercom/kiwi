"""Command templates for Kiwi Command Factory.

Each template type defines a skeleton .md structure.
Templates are chosen based on the command's purpose.
"""

TEMPLATES = {
    "quick-alias": {
        "description": "Short alias for an existing command",
        "skeleton": """# /{name} — {title}

> Alias ngắn cho `/{alias_for}`

Chạy `/{alias_for}` — {description}
""",
    },

    "scan": {
        "description": "Scan/check command (lint, audit, validate)",
        "skeleton": """# /{name} — {title}

> {description}

## Quy trình

### 1. Xác định target
```
Nếu $ARGUMENTS là tên → path = {{auto-resolve}}
Nếu $ARGUMENTS là path → dùng trực tiếp
Nếu trống → hỏi user
```

### 2. Chạy scan
```powershell
{run_command}
```

### 3. Xử lý kết quả
- Nếu có lỗi CRITICAL → liệt kê + suggest fix
- Nếu ALL CLEAR → output "✅ {name} clean"

## Ví dụ
```
/{name} {example_arg}
```
""",
    },

    "deploy": {
        "description": "Deploy/publish command (staging, production)",
        "skeleton": """# /{name} — {title}

> {description}

## Pre-checks (BẮT BUỘC)
1. Git status clean (không uncommitted changes)
2. Scan/lint pass
3. Build thành công

## Quy trình

### 1. Pre-flight
```powershell
{pre_check_command}
```

### 2. Deploy
```powershell
{deploy_command}
```

### 3. Health check
```powershell
{health_check_command}
```

### 4. Rollback (nếu fail)
```powershell
{rollback_command}
```

## Ví dụ
```
/{name} {example_arg}
```
""",
    },

    "workflow": {
        "description": "Multi-step workflow (commit+push, build+test+deploy)",
        "skeleton": """# /{name} — {title}

> {description}

## Quy trình

{steps}

## Ví dụ
```
/{name} {example_arg}
```
""",
    },

    "query": {
        "description": "Search/lookup command (query DB, search files, lookup info)",
        "skeleton": """# /{name} — {title}

> {description}

## Input
- `$ARGUMENTS` = {input_description}

## Quy trình

### 1. Parse input
{parse_logic}

### 2. Execute query
```powershell
{query_command}
```

### 3. Format output
{output_format}

## Ví dụ
```
/{name} {example_arg}
```
""",
    },

    "generic": {
        "description": "General-purpose command",
        "skeleton": """# /{name} — {title}

> {description}

## Quy trình

{steps}

## Ví dụ
```
/{name} {example_arg}
```
""",
    },
}


def get_template(template_type: str) -> dict | None:
    return TEMPLATES.get(template_type)


def list_templates() -> list[dict]:
    return [{"type": k, "description": v["description"]} for k, v in TEMPLATES.items()]


def suggest_template(description: str) -> str:
    """Suggest best template type based on description keywords."""
    desc_lower = description.lower()
    if any(w in desc_lower for w in ["alias", "shortcut", "rút gọn", "quick"]):
        return "quick-alias"
    if any(w in desc_lower for w in ["scan", "check", "lint", "audit", "validate", "kiểm tra"]):
        return "scan"
    if any(w in desc_lower for w in ["deploy", "publish", "release", "triển khai"]):
        return "deploy"
    if any(w in desc_lower for w in ["commit", "push", "build", "test", "workflow", "quy trình"]):
        return "workflow"
    if any(w in desc_lower for w in ["search", "query", "find", "lookup", "tìm", "tra cứu"]):
        return "query"
    return "generic"
