"""Diagnostics capability — publish violations as LSP diagnostics."""

from typing import List

from lsprotocol.types import (
    Diagnostic,
    DiagnosticSeverity,
    Position,
    Range,
)


SEVERITY_MAP = {
    "CRITICAL": DiagnosticSeverity.Error,
    "HIGH": DiagnosticSeverity.Warning,
    "SUGGEST": DiagnosticSeverity.Information,
    "INFO": DiagnosticSeverity.Hint,
}


def violations_to_diagnostics(violations: list) -> List[Diagnostic]:
    """Convert Kiwi Violation objects to LSP Diagnostic objects."""
    diagnostics = []
    for v in violations:
        line = max(0, v.line - 1)
        diag = Diagnostic(
            range=Range(
                start=Position(line=line, character=0),
                end=Position(line=line, character=len(v.match_text) if v.match_text else 120),
            ),
            severity=SEVERITY_MAP.get(v.severity, DiagnosticSeverity.Information),
            source="kiwi",
            code=v.lesson_id,
            message=f"[{v.severity}] {v.description}",
            data={"lesson_id": v.lesson_id, "category": v.category},
        )
        diagnostics.append(diag)
    return diagnostics