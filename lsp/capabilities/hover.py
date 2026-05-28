"""Hover capability — show lesson info on hover over violations."""

from typing import Optional

from lsprotocol.types import Hover, MarkupContent, MarkupKind


def create_hover(lesson_info: Optional[dict]) -> Optional[Hover]:
    """Create hover content from Kiwi lesson info."""
    if not lesson_info:
        return None

    parts = []
    parts.append(f"### Kiwi: {lesson_info['id']} — {lesson_info.get('title', '')}")
    parts.append(f"**Severity:** {lesson_info.get('severity', 'N/A')} | **Category:** {lesson_info.get('category', 'N/A')}")

    if lesson_info.get("why"):
        parts.append(f"\n**Why:** {lesson_info['why']}")

    if lesson_info.get("bad_code"):
        parts.append(f"\n**Bad:**\n```\n{lesson_info['bad_code']}\n```")

    if lesson_info.get("good_code"):
        parts.append(f"\n**Good:**\n```\n{lesson_info['good_code']}\n```")

    content = "\n".join(parts)

    return Hover(
        contents=MarkupContent(kind=MarkupKind.Markdown, value=content)
    )