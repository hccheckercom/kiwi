"""JSON reporter for CI/hooks — v3 with grouped mode."""

import json

from ..models import Report


class JsonReporter:
    def format(self, report: Report, grouped: bool = False) -> str:
        output = {
            "theme": report.theme_path,
            "version": 3,
            "summary": {
                "critical": report.critical_count,
                "high": report.high_count,
                "suggest": report.suggest_count,
                "total": len(report.violations),
                "patterns_checked": report.patterns_checked,
                "files_scanned": report.files_scanned,
            },
        }

        overflow = getattr(report, "_overflow", {})
        if overflow:
            output["summary"]["hidden_by_cap"] = sum(overflow.values())

        if grouped:
            groups = report.grouped()
            output["grouped"] = {
                lid: {
                    "severity": vs[0].severity,
                    "description": vs[0].description,
                    "count": len(vs) + overflow.get(lid, 0),
                    "shown": len(vs),
                    "files": [
                        {"file": v.file, "line": v.line, "match": v.match_text}
                        for v in vs
                    ],
                }
                for lid, vs in groups.items()
            }
        else:
            output["violations"] = [
                {
                    "id": v.lesson_id,
                    "severity": v.severity,
                    "category": v.category,
                    "description": v.description,
                    "file": v.file,
                    "line": v.line,
                    "match": v.match_text,
                }
                for v in report.violations
            ]

        if hasattr(report, "_sub_reports") and report._sub_reports:
            output["mode"] = "monorepo"
            output["sub_projects"] = [
                {
                    "label": label,
                    "scope_type": scope_type,
                    "violations": len(sub.violations),
                    "critical": sum(1 for v in sub.violations if v.severity == "CRITICAL"),
                }
                for label, scope_type, sub in report._sub_reports
            ]

        return json.dumps(output, indent=2, ensure_ascii=False)