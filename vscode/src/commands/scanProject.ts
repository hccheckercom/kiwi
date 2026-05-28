import * as vscode from 'vscode';
import { KiwiClient } from '../client';

export async function scanProject(client: KiwiClient): Promise<void> {
    const lc = client.getClient();
    if (!lc || !lc.isRunning()) {
        vscode.window.showWarningMessage('Kiwi LSP server is not running. Try "Kiwi: Restart Server".');
        return;
    }

    const folders = vscode.workspace.workspaceFolders;
    if (!folders || folders.length === 0) {
        vscode.window.showWarningMessage('No workspace folder open.');
        return;
    }

    await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: 'Kiwi: Scanning project...' },
        async () => {
            try {
                await lc.sendRequest('kiwi/scanWorkspace', {
                    path: folders[0].uri.fsPath,
                });
                vscode.window.showInformationMessage('Kiwi: Project scan complete. Check Problems panel.');
            } catch (err: unknown) {
                const msg = err instanceof Error ? err.message : String(err);
                vscode.window.showErrorMessage(`Kiwi scan failed: ${msg}`);
            }
        },
    );
}