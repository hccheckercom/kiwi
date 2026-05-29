import * as vscode from 'vscode';
import { KiwiClient } from '../client';
import { SuggestionsTreeProvider } from '../providers/suggestionsTree';

/**
 * Suggestion review commands (Fix 6 §6.3) — the ✓ / ✗ inline buttons on the
 * kiwiSuggestions tree. Each tree item carries `{ id }` as its node; VS Code
 * passes that node back as the command argument.
 */

interface SuggestionNode {
    id: number;
    severity?: string;
    category?: string;
}

export async function approveSuggestion(
    client: KiwiClient,
    tree: SuggestionsTreeProvider,
    node?: SuggestionNode,
): Promise<void> {
    if (!node || node.id === undefined) {
        vscode.window.showWarningMessage('No suggestion selected.');
        return;
    }
    const lc = client.getClient();
    if (!lc || !lc.isRunning()) {
        vscode.window.showWarningMessage('Kiwi LSP server is not running.');
        return;
    }
    try {
        const resp = await lc.sendRequest<{ success: boolean; lesson_id?: string; error?: string }>(
            'kiwi/approveSuggestion',
            { suggestion_id: node.id, severity: node.severity, category: node.category },
        );
        if (resp?.success) {
            vscode.window.showInformationMessage(`Kiwi: approved → ${resp.lesson_id}. Run rebuild_index.py to refresh README.`);
            tree.refresh();
        } else {
            vscode.window.showErrorMessage(`Kiwi: approve failed — ${resp?.error ?? 'unknown error'}`);
        }
    } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        vscode.window.showErrorMessage(`Kiwi: approve failed — ${msg}`);
    }
}

export async function rejectSuggestion(
    client: KiwiClient,
    tree: SuggestionsTreeProvider,
    node?: SuggestionNode,
): Promise<void> {
    if (!node || node.id === undefined) {
        vscode.window.showWarningMessage('No suggestion selected.');
        return;
    }
    const lc = client.getClient();
    if (!lc || !lc.isRunning()) {
        vscode.window.showWarningMessage('Kiwi LSP server is not running.');
        return;
    }
    try {
        const resp = await lc.sendRequest<{ success: boolean; error?: string }>(
            'kiwi/rejectSuggestion',
            { suggestion_id: node.id },
        );
        if (resp?.success) {
            tree.refresh();
        } else {
            vscode.window.showErrorMessage(`Kiwi: reject failed — ${resp?.error ?? 'unknown error'}`);
        }
    } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        vscode.window.showErrorMessage(`Kiwi: reject failed — ${msg}`);
    }
}
