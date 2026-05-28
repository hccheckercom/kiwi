"""kiwi init — detect project, create .kiwi/, register MCP."""

import json
import os

import click

from ..helpers import ensure_sys_path, get_kiwi_dir, print_header, print_success, print_error


@click.command("init")
@click.argument("path", default=".")
@click.option("--register-mcp/--no-register-mcp", default=True, help="Register as MCP server in Claude Code")
def init_cmd(path, register_mcp):
    """Initialize Kiwi AI in a project directory."""
    ensure_sys_path()

    project_path = os.path.abspath(path)
    if not os.path.isdir(project_path):
        print_error(f"Directory not found: {project_path}")
        raise SystemExit(1)

    print_header("Kiwi AI — Init")

    # 1. Detect project
    click.echo("Detecting project...")
    from plugins.generic.auto_detector import detect
    profile = detect(project_path)

    langs = ", ".join(profile.languages) if profile.languages else "unknown"
    frameworks = ", ".join(profile.frameworks) if profile.frameworks else "none"
    click.echo(f"  Languages: {langs}")
    click.echo(f"  Frameworks: {frameworks}")
    if profile.package_manager:
        click.echo(f"  Package manager: {profile.package_manager}")

    # 2. Resolve best plugin
    plugin_name = _resolve_best_plugin(project_path)
    click.echo(f"  Plugin: {plugin_name}")

    # 3. Create .kiwi/ folder
    kiwi_dir = os.path.join(project_path, ".kiwi")
    os.makedirs(kiwi_dir, exist_ok=True)

    config = {
        "project_name": os.path.basename(project_path),
        "languages": profile.languages,
        "frameworks": profile.frameworks,
        "package_manager": profile.package_manager,
        "plugin": plugin_name,
        "created_at": __import__("datetime").datetime.now().isoformat(),
    }

    config_path = os.path.join(kiwi_dir, "config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    click.echo(f"  Created: {config_path}")

    # 4. Register MCP (if Claude Code detected)
    if register_mcp:
        _register_mcp_server(project_path)

    # 5. Summary
    click.echo("")
    print_success("Kiwi AI initialized!")
    click.echo(f"  Project: {config['project_name']}")
    click.echo(f"  Plugin: {plugin_name}")
    click.echo(f"  Config: .kiwi/config.json")
    click.echo("")
    click.echo("Next steps:")
    click.echo("  kiwi scan .     — run first scan")
    click.echo("  kiwi status     — check tier & savings")
    click.echo("  kiwi dashboard  — view metrics")


def _resolve_best_plugin(project_path: str) -> str:
    """Find the best-matching plugin for this project."""
    from core.plugin_registry import discover_plugins

    plugins = discover_plugins()
    if not plugins:
        return "generic"

    best_score = 0.0
    best_name = "generic"
    for plugin in plugins:
        try:
            score = plugin.detect_project(project_path)
            manifest = plugin.get_manifest()
            if score > best_score:
                best_score = score
                best_name = manifest.name
        except Exception:
            continue

    return best_name


def _register_mcp_server(project_path: str):
    """Register Kiwi as MCP server in .claude/settings.json if present."""
    claude_dir = os.path.join(project_path, ".claude")
    settings_path = os.path.join(claude_dir, "settings.json")

    if not os.path.isdir(claude_dir):
        return

    kiwi_dir = get_kiwi_dir()
    mcp_server_path = str(kiwi_dir / "mcp_server.py")

    settings = {}
    if os.path.isfile(settings_path):
        try:
            settings = json.loads(open(settings_path, encoding="utf-8").read())
        except (json.JSONDecodeError, OSError):
            pass

    mcp_servers = settings.setdefault("mcpServers", {})
    if "kiwi" in mcp_servers:
        click.echo("  MCP: already registered")
        return

    mcp_servers["kiwi"] = {
        "command": "python",
        "args": [mcp_server_path],
        "type": "stdio",
    }

    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

    click.echo("  MCP: registered in .claude/settings.json")