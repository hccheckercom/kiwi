"""Lesson Generator — Tạo lesson files từ suggested patterns"""

import re
import sys
from pathlib import Path
from typing import Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from .models import SuggestedPattern, LessonMetadata
from memory.db import get_connection, update_suggested_lesson_status


def generate_lesson(suggestion_id: int, override_severity: str = None, override_category: str = None) -> Optional[str]:
    """
    Generate lesson markdown from suggested pattern.

    Returns: lesson_id if successful, None if failed
    """
    # Get suggestion from DB
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM suggested_lessons WHERE id = ?", (suggestion_id,)).fetchone()
    finally:
        conn.close()

    if not row:
        return None

    suggestion = dict(row)

    # Generate lesson ID
    lesson_id = _get_next_lesson_id()

    # Create metadata
    metadata = LessonMetadata(
        lesson_id=lesson_id,
        severity=override_severity or suggestion['severity'],
        category=override_category or suggestion['category'],
        title=_generate_title(suggestion),
        pattern=suggestion['pattern'],
        scope=suggestion['scope']
    )

    # Generate markdown content
    content = _generate_markdown(metadata, suggestion)

    # Write to file
    category_dir = Path(__file__).parent.parent / "lessons" / metadata.category
    category_dir.mkdir(parents=True, exist_ok=True)

    lesson_file = category_dir / f"{lesson_id}.md"
    lesson_file.write_text(content, encoding='utf-8')

    # Update suggestion status
    update_suggested_lesson_status(suggestion_id, 'approved', lesson_id)

    # Update _meta.json
    _update_meta_json(lesson_id)

    return lesson_id


def _get_next_lesson_id() -> str:
    """Get next available lesson ID"""
    import json
    meta_path = Path(__file__).parent.parent / "_meta.json"

    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        next_id = meta.get('next_id', 500)
    else:
        next_id = 500

    return f"LES-{next_id:03d}"


def _generate_title(suggestion: Dict) -> str:
    """Generate lesson title from pattern"""
    pattern = suggestion['pattern']
    category = suggestion['category']

    # Simple heuristic title generation
    if 'php-security' in category:
        if '$_GET' in pattern or '$_POST' in pattern:
            return "Direct superglobal usage without sanitization"
        elif 'sql' in pattern.lower():
            return "SQL query without prepared statement"

    elif 'css-tokens' in category:
        if 'px' in pattern:
            return "Hardcoded pixel values instead of design tokens"
        elif '#' in pattern:
            return "Hardcoded hex colors instead of CSS variables"

    # Default: use pattern as title
    return f"Pattern: {pattern[:50]}"


def _generate_markdown(metadata: LessonMetadata, suggestion: Dict) -> str:
    """Generate lesson markdown content"""

    frontmatter = f"""---
id: {metadata.lesson_id}
severity: {metadata.severity}
category: {metadata.category}
title: {metadata.title}
tags: [auto-generated]

scan:
  type: presence
  pattern: {metadata.pattern}
  scope: {metadata.scope}
---

## Bad

```
{suggestion['example_code']}
```

**File:** {suggestion['example_file']}:{suggestion['example_line']}

## Good

```
# TODO: Add good example
```

## Why

This pattern was automatically detected from {suggestion.get('occurrence_count', 0)} violations across multiple files.

**Risk:** {_explain_severity(metadata.severity)}

**Auto-generated lesson** — please review and enhance with proper Good example and detailed Why explanation.
"""

    return frontmatter


def _explain_severity(severity: str) -> str:
    """Explain severity level"""
    explanations = {
        'CRITICAL': 'Security vulnerability or data integrity issue',
        'HIGH': 'Code quality issue that may cause bugs',
        'SUGGEST': 'Best practice recommendation'
    }
    return explanations.get(severity, 'Code quality issue')


def _update_meta_json(lesson_id: str):
    """Update _meta.json with new lesson ID"""
    import json
    meta_path = Path(__file__).parent.parent / "_meta.json"

    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
    else:
        meta = {'next_id': 500, 'categories': {}}

    # Increment next_id
    current_id = int(lesson_id.split('-')[1])
    meta['next_id'] = current_id + 1

    # Write back
    meta_path.write_text(json.dumps(meta, indent=2), encoding='utf-8')
