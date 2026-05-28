"""kiwi check — single file check (delegates to scanner)."""

import os

import click

from ..helpers import ensure_sys_path, print_header, print_error


@click.command()
@click.argument("file")
@click.option("--severity", "-s", type=click.Choice(["CRITICAL", "HIGH", "ALL"]), default="CRITICAL")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
def check(file, severity, json_out):
    """Check a single file for violations."""
    ensure_sys_path()

    file_path = os.path.abspath(file)
    if not os.path.isfile(file_path):
        print_error(f"File not found: {file_path}")
        raise SystemExit(1)

    theme_path = os.path.dirname(file_path)

    from scanner.loader import load_patterns
    from scanner.resolver import resolve_scope
    from scanner.checkers import get_checker
    from scanner.models import Report, Violation
    from scanner.reporters.text import TextReporter

    patterns = load_patterns()
    report = Report(theme_path=theme_path)

    for pattern_def in patterns:
        if pattern_def.get("severity") == "INFO":
            continue
        if severity != "ALL" and pattern_def["severity"] != severity:
            continue

        report.patterns_checked += 1
        ptype = pattern_def.get("type", "presence")
        checker = get_checker(ptype)
        if not checker:
            continue

        violations = checker.check(pattern_def, [file_path], theme_path)
        report.violations.extend(violations)

    report.files_scanned = 1

    if json_out:
        from scanner.reporters.json import JsonReporter
        click.echo(JsonReporter().format(report))
    else:
        if not report.violations:
            click.secho(f"PASS — {os.path.basename(file_path)}: no violations", fg="green")
        else:
            click.echo(TextReporter().format(report))

    if report.critical_count > 0:
        raise SystemExit(1)