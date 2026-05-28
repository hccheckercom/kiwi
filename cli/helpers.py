"""Shared helpers for CLI commands."""

import json
import os
import sys
from pathlib import Path


def get_kiwi_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def ensure_sys_path():
    kiwi_dir = get_kiwi_dir()
    if str(kiwi_dir) not in sys.path:
        sys.path.insert(0, str(kiwi_dir))


def resolve_project_path(path: str) -> str:
    if os.path.isdir(path):
        return os.path.abspath(path)
    meta_path = get_kiwi_dir() / "_meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        resolved = meta.get("projects", {}).get(path)
        if resolved and os.path.isdir(resolved):
            return resolved
    except (json.JSONDecodeError, OSError):
        pass
    return os.path.abspath(path)


def print_header(title: str):
    import click
    click.echo(f"\n{title}")
    click.echo("━" * 30)


def print_error(msg: str):
    import click
    click.secho(f"Error: {msg}", fg="red", err=True)


def print_success(msg: str):
    import click
    click.secho(msg, fg="green")


def load_kiwi_config(project_path: str) -> dict:
    config_path = Path(project_path) / ".kiwi" / "config.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}