"""Human-readable text reporter — v3 with grouped mode."""

import os

from ..models import Report


class TextReporter:
    def format(self, report: Report, grouped: bool = False) -> str:
        lines = []
        lines.append("=" * 60)
        lines.append("  KIWI SMART SCANNER v3 — Violation Report")
        lines.append("=" * 60)

        is_monorepo = hasattr(report, "_sub_reports") and report._sub_reports
        if is_monorepo:
            lines.append(f"  Project: {os.path.basename(report.theme_path)} (monorepo)")
            lines.append(f"  Sub-projects: {len(report._sub_reports)}")
        else:
            lines.append(f"  Theme: {os.path.basename(report.theme_path)}")

        lines.append(f"  Patterns checked: {report.patterns_checked}")
        lines.append(f"  Files scanned: {report.files_scanned}")
        lines.append("")

        # Display AST warnings if any
        if report.warnings:
            lines.append(f"⚠️  AST Checker Warnings ({report.ast_skipped_files} files skipped):")
            for warning in report.warnings[:10]:  # Show first 10 warnings
                lines.append(f"  - {warning}")
            if len(report.warnings) > 10:
                lines.append(f"  ... and {len(report.warnings) - 10} more warnings")
            lines.append("")

        if not report.violations:
            lines.append("  ALL CLEAR — No violations found.")
            lines.append("=" * 60)
            return "\n".join(lines)

        lines.append(f"  CRITICAL: {report.critical_count}  |  HIGH: {report.high_count}  |  SUGGEST: {report.suggest_count}")

        overflow = getattr(report, "_overflow", {})
        if overflow:
            total_hidden = sum(overflow.values())
            lines.append(f"  (+ {total_hidden} more violations hidden by --max-per-lesson)")

        lines.append("=" * 60)

        if is_monorepo:
            lines.append("")
            lines.append("--- PER-PACKAGE SUMMARY ---")
            for label, scope_type, sub in report._sub_reports:
                if sub.violations:
                    c = sum(1 for v in sub.violations if v.severity == "CRITICAL")
                    h = sum(1 for v in sub.violations if v.severity == "HIGH")
                    lines.append(f"  [{scope_type}] {label}: {c} CRITICAL, {h} HIGH")
            lines.append("")

        if grouped:
            lines.extend(self._format_grouped(report, overflow))
        else:
            lines.extend(self._format_flat(report))

        lines.append("=" * 60)
        lines.append(f"  Fix: Read .claude/kiwi/lessons/<category>/<ID>.md")
        lines.append("=" * 60)
        return "\n".join(lines)

    def _format_grouped(self, report: Report, overflow: dict) -> list:
        lines = []
        groups = report.grouped()

        severity_order = {"CRITICAL": 0, "HIGH": 1, "SUGGEST": 2}
        sorted_ids = sorted(
            groups.keys(),
            key=lambda lid: (severity_order.get(groups[lid][0].severity, 9), lid),
        )

        current_severity = None
        for lesson_id in sorted_ids:
            violations = groups[lesson_id]
            sev = violations[0].severity

            if sev != current_severity:
                current_severity = sev
                lines.append("")
                lines.append(f"--- {sev} ---")

            total_count = len(violations) + overflow.get(lesson_id, 0)
            shown = len(violations)
            desc = violations[0].description

            lines.append("")
            lines.append(f"  [{lesson_id}] {desc}")
            if total_count > shown:
                lines.append(f"    Hits: {total_count} (showing {shown})")
            else:
                lines.append(f"    Hits: {total_count}")

            for v in violations[:5]:
                loc = f"{v.file}:{v.line}" if v.line else v.file
                lines.append(f"      {loc}")
                if v.match_text:
                    lines.append(f"        > {v.match_text[:100]}")

            if shown > 5:
                lines.append(f"      ... and {shown - 5} more")

        lines.append("")
        return lines

    def _format_flat(self, report: Report) -> list:
        lines = []
        critical = [v for v in report.violations if v.severity == "CRITICAL"]
        high = [v for v in report.violations if v.severity == "HIGH"]
        suggest = [v for v in report.violations if v.severity == "SUGGEST"]

        if critical:
            lines.append("")
            lines.append("--- CRITICAL ---")
            for v in critical:
                loc = f"{v.file}:{v.line}" if v.line else v.file
                lines.append(f"  [{v.lesson_id}] {loc}")
                lines.append(f"    {v.description}")
                if v.match_text:
                    lines.append(f"    > {v.match_text}")
                lines.append("")

        if high:
            lines.append("")
            lines.append("--- HIGH ---")
            for v in high:
                loc = f"{v.file}:{v.line}" if v.line else v.file
                lines.append(f"  [{v.lesson_id}] {loc}")
                lines.append(f"    {v.description}")
                if v.match_text:
                    lines.append(f"    > {v.match_text}")
                lines.append("")

        if suggest:
            lines.append("")
            lines.append("--- SUGGEST ---")
            for v in suggest:
                loc = f"{v.file}:{v.line}" if v.line else v.file
                lines.append(f"  [{v.lesson_id}] {loc}")
                lines.append(f"    {v.description}")
                if v.match_text:
                    lines.append(f"    > {v.match_text}")
                lines.append("")

        return lines