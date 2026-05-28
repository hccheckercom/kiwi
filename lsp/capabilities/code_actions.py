"""Code Actions capability — quick fix suggestions from Kiwi lessons."""

from typing import List, Optional

from lsprotocol.types import (
    CodeAction,
    CodeActionKind,
    Diagnostic,
    Position,
    Range,
    TextEdit,
    WorkspaceEdit,
    TextDocumentIdentifier,
    OptionalVersionedTextDocumentIdentifier,
    TextDocumentEdit,
)


def create_code_actions(
    uri: str,
    diagnostics: List[Diagnostic],
    bridge,
) -> List[CodeAction]:
    """Create code actions (quick fixes) for Kiwi diagnostics."""
    actions = []

    for diag in diagnostics:
        if not diag.data or "lesson_id" not in diag.data:
            continue

        lesson_id = diag.data["lesson_id"]
        fix = bridge.get_fix_suggestion(lesson_id)

        if fix and fix.get("good_code"):
            action = CodeAction(
                title=f"Kiwi Fix: {fix['description']}",
                kind=CodeActionKind.QuickFix,
                diagnostics=[diag],
                edit=WorkspaceEdit(
                    document_changes=[
                        TextDocumentEdit(
                            text_document=OptionalVersionedTextDocumentIdentifier(
                                uri=uri, version=None
                            ),
                            edits=[
                                TextEdit(
                                    range=diag.range,
                                    new_text=fix["good_code"],
                                )
                            ],
                        )
                    ]
                ),
            )
            actions.append(action)

        info_action = CodeAction(
            title=f"Kiwi: View lesson {lesson_id}",
            kind=CodeActionKind.Empty,
            diagnostics=[diag],
            command={
                "title": f"View {lesson_id}",
                "command": "kiwi.viewLesson",
                "arguments": [lesson_id],
            },
        )
        actions.append(info_action)

    return actions