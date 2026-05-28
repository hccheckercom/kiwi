"""kiwi scan — full project scan (delegates to scanner.cli.scan_theme)."""

import os

import click

from ..helpers import ensure_sys_path, resolve_project_path, print_header, print_error


@click.command()
@click.argument("path", default=".")
@click.option("--severity", "-s", type=click.Choice(["CRITICAL", "HIGH", "SUGGEST", "ALL"]), default="ALL")
@click.option("--platform", "-p", type=click.Choice(["wp", "nextjs"]), default=None)
@click.option("--diff-only", is_flag=True, help="Only scan git-modified files")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
def scan(path, severity, platform, diff_only, json_out):
    """Scan project for code quality issues."""
    ensure_sys_path()

    project_path = resolve_project_path(path)
    if not os.path.isdir(project_path):
        print_error(f"Directory not found: {project_path}")
        raise SystemExit(1)

    from scanner.cli import scan_theme, _detect_project_type, _discover_sub_projects, _discover_themes_in_folder
    from scanner.reporters.text import TextReporter
    from scanner.reporters.json import JsonReporter
    from scanner.models import Report

    project_type = _detect_project_type(project_path)

    if project_type in ("monorepo", "themes_folder"):
        if project_type == "themes_folder":
            sub_projects = _discover_themes_in_folder(project_path)
        else:
            sub_projects = _discover_sub_projects(project_path)

        combined = Report(theme_path=project_path)
        combined._sub_reports = []

        for sub_path, scope_type, label in sub_projects:
            report = scan_theme(
                sub_path,
                severity_filter=severity,
                diff_only=diff_only,
                platform=platform,
                scope_type=scope_type,
                rewrite_scopes=(scope_type == "theme"),
                skip_empty_scope=True,
            )
            combined.violations.extend(report.violations)
            combined.patterns_checked = max(combined.patterns_checked, report.patterns_checked)
            combined.files_scanned += report.files_scanned
            combined._sub_reports.append((label, report))

        report = combined
    else:
        scope_type = "theme" if project_type == "theme" else "plugin"
        report = scan_theme(
            project_path,
            severity_filter=severity,
            diff_only=diff_only,
            platform=platform,
            scope_type=scope_type,
            rewrite_scopes=(scope_type == "theme"),
            skip_empty_scope=True,
        )

    if json_out:
        reporter = JsonReporter()
        click.echo(reporter.format(report))
    else:
        reporter = TextReporter()
        click.echo(reporter.format(report))

    if report.critical_count > 0:
        raise SystemExit(1)