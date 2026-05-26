"""Kiwi Command Factory — Create, list, improve, delete Claude Code commands.

Commands are stored as .md files in .claude/commands/.
Usage history is tracked in SQLite for learning and improvement.
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

COMMANDS_DIR = Path(__file__).parent.parent.parent / "commands"
KIWI_DIR = Path(__file__).parent.parent

MAX_SLUG_LENGTH = 60


def _ensure_commands_dir():
    COMMANDS_DIR.mkdir(parents=True, exist_ok=True)


def _sanitize_slug(name: str) -> str:
    """Sanitize name into a safe, filesystem-friendly slug."""
    slug = name.lower().replace(' ', '-').replace('_', '-')
    slug = slug.replace('/', '').replace('\\', '').replace('..', '')
    slug = re.sub(r'[^a-z0-9\-]', '', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    if len(slug) > MAX_SLUG_LENGTH:
        slug = slug[:MAX_SLUG_LENGTH].rstrip('-')
    return slug


def create_command(name: str, title: str, description: str,
                   template_type: str = None, steps: str = "",
                   content: str = None, overwrite: bool = False) -> dict:
    """Create a new command file.

    If content is provided, write it directly.
    Otherwise, use template_type to generate skeleton.
    """
    from .templates import get_template, suggest_template
    from .history import log_invocation

    _ensure_commands_dir()

    slug = _sanitize_slug(name)
    if not slug:
        return {"error": "Invalid command name — must contain at least one alphanumeric character."}

    filepath = COMMANDS_DIR / f"{slug}.md"

    if filepath.exists() and not overwrite:
        log_invocation(slug, "create", success=False, error_msg="already exists")
        return {"error": f"Command '{slug}' already exists. Use overwrite=true to replace.", "path": str(filepath)}

    if content:
        md_content = content
    else:
        if not template_type:
            template_type = suggest_template(description)

        tpl = get_template(template_type)
        if not tpl:
            template_type = "generic"
            tpl = get_template("generic")

        try:
            md_content = tpl["skeleton"].format(
                name=slug,
                title=title,
                description=description,
                steps=steps or "1. TODO: define steps",
                alias_for=steps if template_type == "quick-alias" else "",
                run_command=steps if template_type == "scan" else "# TODO",
                pre_check_command="# TODO",
                deploy_command="# TODO",
                health_check_command="# TODO",
                rollback_command="# TODO",
                parse_logic="# TODO",
                query_command="# TODO",
                output_format="# TODO",
                input_description="input",
                example_arg="example",
            )
        except KeyError as e:
            return {"error": f"Template format error: missing key {e}"}

    filepath.write_text(md_content, encoding="utf-8")
    log_invocation(slug, "create", success=True, notes=f"template={template_type or 'custom'}")

    return {
        "success": True,
        "command": slug,
        "path": str(filepath),
        "template_used": template_type or "custom",
        "message": f"Created /{slug}. File: {filepath}",
    }


def list_commands(filter_text: str = None) -> list[dict]:
    """List all commands with basic info."""
    from .history import get_stats

    _ensure_commands_dir()

    commands = []
    for f in sorted(COMMANDS_DIR.glob("*.md")):
        name = f.stem
        first_line = f.read_text(encoding="utf-8").split("\n", 1)[0]

        if filter_text:
            filter_lower = filter_text.lower()
            if filter_lower not in name.lower() and filter_lower not in first_line.lower():
                continue

        title = first_line.lstrip("# ").strip()

        stats = get_stats(name)
        commands.append({
            "name": name,
            "title": title,
            "path": str(f),
            "size_bytes": f.stat().st_size,
            "invocations": stats.get("total_invocations", 0),
            "last_used": stats.get("last_used"),
        })

    return commands


def delete_command(name: str) -> dict:
    """Delete a command file."""
    from .history import log_invocation

    slug = _sanitize_slug(name)
    if not slug:
        return {"error": "Invalid command name."}

    filepath = COMMANDS_DIR / f"{slug}.md"

    if not filepath.exists():
        return {"error": f"Command '{slug}' not found."}

    filepath.unlink()
    log_invocation(slug, "delete", success=True)

    return {"success": True, "message": f"Deleted /{slug}."}


def get_command_content(name: str) -> dict:
    """Read command file content."""
    slug = _sanitize_slug(name)
    if not slug:
        return {"error": "Invalid command name."}

    filepath = COMMANDS_DIR / f"{slug}.md"

    if not filepath.exists():
        return {"error": f"Command '{slug}' not found."}

    return {
        "name": slug,
        "path": str(filepath),
        "content": filepath.read_text(encoding="utf-8"),
    }


def improve_command(name: str) -> dict:
    """Analyze usage history and suggest improvements for a command."""
    from .history import get_improvement_data, log_invocation

    slug = _sanitize_slug(name)
    if not slug:
        return {"error": "Invalid command name."}

    filepath = COMMANDS_DIR / f"{slug}.md"

    if not filepath.exists():
        return {"error": f"Command '{slug}' not found."}

    data = get_improvement_data(slug)
    content = filepath.read_text(encoding="utf-8")

    suggestions = []

    if data["total_invocations"] == 0:
        suggestions.append("Command never invoked — no usage data to learn from yet.")
    else:
        if data["failure_rate"] > 0.3:
            suggestions.append(f"High failure rate ({data['failure_rate']:.0%}). Common errors:")
            for f in data["recent_failures"][:3]:
                suggestions.append(f"  - {f['error']}")

        if data["feedback"]:
            suggestions.append("User feedback:")
            for fb in data["feedback"][:5]:
                suggestions.append(f"  - [{fb['category']}] {fb['text']}")

        if data["total_invocations"] >= 10 and not any("alias" in s.lower() for s in suggestions):
            suggestions.append(f"Frequently used ({data['total_invocations']}x) — consider creating a short alias.")

        if len(content) > 3000:
            suggestions.append("Command file is large (>3KB). Consider splitting into sub-steps or extracting helpers.")

    log_invocation(slug, "improve", success=True, notes=f"{len(suggestions)} suggestions")

    return {
        "command": slug,
        "invocations": data["total_invocations"],
        "failure_rate": f"{data['failure_rate']:.0%}",
        "suggestions": suggestions,
        "current_content": content,
        "improvement_data": data,
    }


def record_feedback(name: str, feedback: str, category: str = "general") -> dict:
    """Record user feedback about a command for future improvements."""
    from .history import add_feedback, log_invocation

    slug = _sanitize_slug(name)
    if not slug:
        return {"error": "Invalid command name."}

    add_feedback(slug, feedback, category)
    log_invocation(slug, "feedback", success=True, notes=feedback[:100])

    return {"success": True, "message": f"Feedback recorded for /{slug}."}
