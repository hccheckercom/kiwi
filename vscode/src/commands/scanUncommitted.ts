import * as vscode from 'vscode';
import { KiwiClient } from '../client';

export async function scanUncommitted(client: KiwiClient): Promise<void> {
    const lc = client.getClient();
    if (!lc || !lc.isRunning()) {
        vscode.window.showWarningMessage('Kiwi LSP server is not running.');
        return;
    }

    const folders = vscode.workspace.workspaceFolders;
    if (!folders || folders.length === 0) {
        vscode.window.showWarningMessage('No workspace folder open.');
        return;
    }

    await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: 'Kiwi: Scanning uncommitted changes...' },
        async () => {
            try {
                const result = await lc.sendRequest('kiwi/scanUncommitted', {
                    path: folders[0].uri.fsPath,
                }) as { total: number; violations: number; files: string[] };

                if (result.violations === 0) {
                    vscode.window.showInformationMessage('Kiwi: No violations in uncommitted changes.');
                } else {
                    vscode.window.showWarningMessage(
                        `Kiwi: ${result.violations} violation(s) in ${result.files.length} changed file(s). Check Problems panel.`
                    );
                }
            } catch (err: unknown) {
                const msg = err instanceof Error ? err.message : String(err);
                vscode.window.showErrorMessage(`Kiwi scan failed: ${msg}`);
            }
        },
    );
}