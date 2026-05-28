import * as vscode from 'vscode';
import { KiwiClient } from '../client';

export async function dismissViolation(client: KiwiClient, scope: 'file' | 'project' = 'file'): Promise<void> {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showWarningMessage('No active editor.');
        return;
    }

    const diagnostics = vscode.languages.getDiagnostics(editor.document.uri);
    const kiwiDiags = diagnostics.filter(d => d.source === 'kiwi');

    if (kiwiDiags.length === 0) {
        vscode.window.showInformationMessage('No Kiwi violations in this file.');
        return;
    }

    const line = editor.selection.active.line;
    const diagOnLine = kiwiDiags.filter(d => d.range.start.line <= line && d.range.end.line >= line);
    const targetDiags = diagOnLine.length > 0 ? diagOnLine : kiwiDiags;

    const items = targetDiags.map(d => ({
        label: typeof d.code === 'string' ? d.code : String(d.code),
        description: d.message,
        diag: d,
    }));

    const selected = await vscode.window.showQuickPick(items, {
        placeHolder: `Select violation to dismiss (${scope} scope)`,
    });

    if (!selected) return;

    const reason = await vscode.window.showInputBox({
        prompt: 'Why is this a false positive?',
        placeHolder: 'e.g. intentional pattern, not applicable here',
    });

    if (!reason) return;

    const lc = client.getClient();
    if (!lc || !lc.isRunning()) {
        vscode.window.showWarningMessage('Kiwi LSP server is not running.');
        return;
    }

    try {
        await lc.sendRequest('kiwi/dismiss', {
            lesson_id: selected.label,
            file: editor.document.uri.fsPath,
            reason,
            scope,
        });
        vscode.window.showInformationMessage(`Dismissed ${selected.label} (${scope}).`);
    } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        vscode.window.showErrorMessage(`Dismiss failed: ${msg}`);
    }
}