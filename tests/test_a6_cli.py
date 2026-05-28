"""Comprehensive QA for A6 — CLI Packaging."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

KIWI_DIR = Path(__file__).resolve().parent.parent
CLI_DIR = KIWI_DIR / "cli"


def main():
    print("=" * 60)
    print("A6 COMPREHENSIVE QA — CLI Packaging")
    print("=" * 60)
    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  PASS [{passed}] {name}")
        else:
            failed += 1
            print(f"  FAIL [{name}] {detail}")

    # === GROUP 1: File Structure ===
    print("\n--- GROUP 1: File Structure ---")
    check("cli/ dir exists", CLI_DIR.is_dir())
    check("cli/__init__.py exists", (CLI_DIR / "__init__.py").is_file())
    check("cli/main.py exists", (CLI_DIR / "main.py").is_file())
    check("cli/helpers.py exists", (CLI_DIR / "helpers.py").is_file())
    check("cli/commands/ dir exists", (CLI_DIR / "commands").is_dir())
    check("cli/commands/__init__.py exists", (CLI_DIR / "commands" / "__init__.py").is_file())
    check("cli/commands/init_cmd.py exists", (CLI_DIR / "commands" / "init_cmd.py").is_file())
    check("cli/commands/scan.py exists", (CLI_DIR / "commands" / "scan.py").is_file())
    check("cli/commands/check.py exists", (CLI_DIR / "commands" / "check.py").is_file())
    check("cli/commands/dashboard.py exists", (CLI_DIR / "commands" / "dashboard.py").is_file())
    check("cli/commands/status.py exists", (CLI_DIR / "commands" / "status.py").is_file())
    check("cli/commands/upgrade.py exists", (CLI_DIR / "commands" / "upgrade.py").is_file())
    check("pyproject.toml exists", (KIWI_DIR / "pyproject.toml").is_file())

    # === GROUP 2: Imports ===
    print("\n--- GROUP 2: Imports ---")
    try:
        from cli import __version__
        check("cli.__version__ importable", True)
        check("version is string", isinstance(__version__, str))
    except Exception as e:
        check("cli.__version__ importable", False, str(e))
        check("version is string", False)

    try:
        from cli.helpers import (
            get_kiwi_dir, ensure_sys_path, resolve_project_path,
            print_header, print_error, print_success, load_kiwi_config,
        )
        check("helpers importable", True)
    except Exception as e:
        check("helpers importable", False, str(e))

    try:
        from cli.main import cli
        check("cli.main.cli importable", True)
    except Exception as e:
        check("cli.main.cli importable", False, str(e))

    # === GROUP 3: Helpers ===
    print("\n--- GROUP 3: Helpers ---")
    from cli.helpers import get_kiwi_dir, ensure_sys_path, resolve_project_path, load_kiwi_config

    kiwi_dir = get_kiwi_dir()
    check("get_kiwi_dir returns Path", isinstance(kiwi_dir, Path))
    check("get_kiwi_dir points to kiwi/", kiwi_dir.name == "kiwi" or "kiwi" in str(kiwi_dir))

    ensure_sys_path()
    check("ensure_sys_path adds to sys.path", str(kiwi_dir) in sys.path)

    resolved = resolve_project_path(".")
    check("resolve_project_path('.') returns abs path", os.path.isabs(resolved))

    config = load_kiwi_config(str(KIWI_DIR))
    check("load_kiwi_config returns dict", isinstance(config, dict))

    # === GROUP 4: Click CLI Group ===
    print("\n--- GROUP 4: Click CLI Group ---")
    from cli.main import cli
    import click

    check("cli is click.Group", isinstance(cli, click.Group))

    commands = list(cli.commands.keys())
    check("has 'init' command", "init" in commands)
    check("has 'scan' command", "scan" in commands)
    check("has 'check' command", "check" in commands)
    check("has 'dashboard' command", "dashboard" in commands)
    check("has 'status' command", "status" in commands)
    check("has 'upgrade' command", "upgrade" in commands)
    check("at least 6 commands", len(commands) >= 6, f"got {len(commands)}: {commands}")

    # === GROUP 5: Command Modules ===
    print("\n--- GROUP 5: Command Modules ---")
    try:
        from cli.commands.init_cmd import init_cmd
        check("init_cmd is click.Command", isinstance(init_cmd, click.BaseCommand))
    except Exception as e:
        check("init_cmd importable", False, str(e))

    try:
        from cli.commands.scan import scan
        check("scan is click.Command", isinstance(scan, click.BaseCommand))
    except Exception as e:
        check("scan importable", False, str(e))

    try:
        from cli.commands.check import check as check_cmd
        check("check is click.Command", isinstance(check_cmd, click.BaseCommand))
    except Exception as e:
        check("check importable", False, str(e))

    try:
        from cli.commands.dashboard import dashboard
        check("dashboard is click.Command", isinstance(dashboard, click.BaseCommand))
    except Exception as e:
        check("dashboard importable", False, str(e))

    try:
        from cli.commands.status import status
        check("status is click.Command", isinstance(status, click.BaseCommand))
    except Exception as e:
        check("status importable", False, str(e))

    try:
        from cli.commands.upgrade import upgrade
        check("upgrade is click.Command", isinstance(upgrade, click.BaseCommand))
    except Exception as e:
        check("upgrade importable", False, str(e))

    # === GROUP 6: pyproject.toml ===
    print("\n--- GROUP 6: pyproject.toml ---")
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            tomllib = None

    if tomllib:
        toml_path = KIWI_DIR / "pyproject.toml"
        with open(toml_path, "rb") as f:
            toml_data = tomllib.load(f)

        check("has [project] section", "project" in toml_data)
        proj = toml_data.get("project", {})
        check("name is kiwi-ai", proj.get("name") == "kiwi-ai")
        check("version is 1.0.0", proj.get("version") == "1.0.0")
        check("requires-python >= 3.9", ">=3.9" in proj.get("requires-python", ""))
        check("click in dependencies", any("click" in d for d in proj.get("dependencies", [])))
        check("pyyaml in dependencies", any("pyyaml" in d.lower() or "PyYAML" in d for d in proj.get("dependencies", [])))

        scripts = proj.get("scripts", {})
        check("kiwi entry point defined", "kiwi" in scripts)
        check("entry point is cli.main:cli", scripts.get("kiwi") == "cli.main:cli")

        check("has build-system", "build-system" in toml_data)
        check("build backend is setuptools", "setuptools" in toml_data.get("build-system", {}).get("build-backend", ""))
    else:
        print("  SKIP: tomllib/tomli not available (Python < 3.11 without tomli)")

    # === GROUP 7: Init Command Logic ===
    print("\n--- GROUP 7: Init Command Logic ---")
    from cli.commands.init_cmd import _resolve_best_plugin

    check("_resolve_best_plugin callable", callable(_resolve_best_plugin))

    with tempfile.TemporaryDirectory() as tmpdir:
        result = _resolve_best_plugin(tmpdir)
        check("empty dir resolves to generic", result == "generic", f"got: {result}")

    # === GROUP 8: No Duplication ===
    print("\n--- GROUP 8: No Duplication (reuse existing modules) ---")
    scan_src = (CLI_DIR / "commands" / "scan.py").read_text(encoding="utf-8")
    check("scan imports scanner.cli", "from scanner.cli import" in scan_src)
    check("scan uses scan_theme", "scan_theme" in scan_src)

    check_src = (CLI_DIR / "commands" / "check.py").read_text(encoding="utf-8")
    check("check imports scanner.loader", "from scanner.loader import" in check_src)
    check("check imports scanner.checkers", "from scanner.checkers import" in check_src)

    dashboard_src = (CLI_DIR / "commands" / "dashboard.py").read_text(encoding="utf-8")
    check("dashboard imports tracking.dashboard", "from tracking.dashboard import" in dashboard_src)
    check("dashboard imports tracking.savings", "from tracking.savings import" in dashboard_src)

    status_src = (CLI_DIR / "commands" / "status.py").read_text(encoding="utf-8")
    check("status imports core.tier_manager", "from core.tier_manager import" in status_src)

    upgrade_src = (CLI_DIR / "commands" / "upgrade.py").read_text(encoding="utf-8")
    check("upgrade imports core.tier_manager", "from core.tier_manager import" in upgrade_src)
    check("upgrade imports core.tier_config", "from core.tier_config import" in upgrade_src)

    init_src = (CLI_DIR / "commands" / "init_cmd.py").read_text(encoding="utf-8")
    check("init imports auto_detector", "from plugins.generic.auto_detector import" in init_src)
    check("init imports plugin_registry", "from core.plugin_registry import" in init_src)

    # === GROUP 9: Click Invocation (dry run) ===
    print("\n--- GROUP 9: Click Invocation ---")
    from click.testing import CliRunner
    from cli.main import cli

    runner = CliRunner()

    result = runner.invoke(cli, ["--version"])
    check("--version exits 0", result.exit_code == 0, f"exit={result.exit_code}")
    check("--version shows version", "1.0.0" in result.output, result.output[:100])

    result = runner.invoke(cli, ["--help"])
    check("--help exits 0", result.exit_code == 0)
    check("--help shows commands", "init" in result.output and "scan" in result.output)

    result = runner.invoke(cli, ["check", "--help"])
    check("check --help exits 0", result.exit_code == 0)
    check("check --help shows --severity", "--severity" in result.output)

    result = runner.invoke(cli, ["scan", "--help"])
    check("scan --help exits 0", result.exit_code == 0)
    check("scan --help shows --diff-only", "--diff-only" in result.output)

    result = runner.invoke(cli, ["status", "--help"])
    check("status --help exits 0", result.exit_code == 0)

    result = runner.invoke(cli, ["dashboard", "--help"])
    check("dashboard --help exits 0", result.exit_code == 0)
    check("dashboard --help shows --period", "--period" in result.output)

    result = runner.invoke(cli, ["upgrade", "--help"])
    check("upgrade --help exits 0", result.exit_code == 0)

    result = runner.invoke(cli, ["init", "--help"])
    check("init --help exits 0", result.exit_code == 0)
    check("init --help shows --register-mcp", "--register-mcp" in result.output)

    # === GROUP 10: Backward Compat (A5 tests still pass) ===
    print("\n--- GROUP 10: Backward Compat ---")
    try:
        from core.tier_config import TIER_LIMITS, FREE_TOOLS, GATED_TOOLS
        check("A5 tier_config still works", True)
    except Exception as e:
        check("A5 tier_config still works", False, str(e))

    try:
        from core.gating import gate_check, gate_tool, gated, GateResult
        check("A5 gating still works", True)
    except Exception as e:
        check("A5 gating still works", False, str(e))

    try:
        from tracking.dashboard import format_compact, format_detail
        check("A4 dashboard still works", True)
    except Exception as e:
        check("A4 dashboard still works", False, str(e))

    try:
        from plugins.generic.auto_detector import detect
        check("A3 auto_detector still works", True)
    except Exception as e:
        check("A3 auto_detector still works", False, str(e))

    # === SUMMARY ===
    print("\n" + "=" * 60)
    total = passed + failed
    print(f"RESULT: {passed}/{total} passed, {failed} failed")
    if failed == 0:
        print("ALL PASS — A6 CLI Packaging verified!")
    else:
        print("SOME TESTS FAILED — review above")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())