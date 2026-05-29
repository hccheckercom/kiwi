import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';
import { KiwiClient } from '../client';

/**
 * "Initialize Kiwi" — the welcome-view button (Fix 6 §6.2).
 *
 * Runs the kiwi init onboarding pipeline (Fix 5) via the CLI so the long-running
 * mine + seed-scan steps never block the single-threaded LSP server. Writes a
 * Kiwi gate anchor into CLAUDE.md/AGENTS.md, so we confirm once before running
 * (the anchor edits a file the user owns — plan R5).
 */
export async function initializeKiwi(client: KiwiClient): Promise<void> {
    const ws = vscode.workspace.workspaceFolders?.[0];
    if (!ws) {
        vscode.window.showWarningMessage('Open a workspace folder first.');
        return;
    }
    const root = ws.uri.fsPath;

    const choice = await vscode.window.showInformationMessage(
        'Initialize Kiwi for this project? This detects your stack, mines lesson ' +
            'candidates, runs a seed scan, and adds a Kiwi gate block to CLAUDE.md/AGENTS.md.',
        { modal: true },
        'Initialize',
    );
    if (choice !== 'Initialize') return;

    const config = vscode.workspace.getConfiguration('kiwi');
    const pythonPath = config.get<string>('pythonPath') || (process.platform === 'win32' ? 'python' : 'python3');
    const kiwiRoot = path.join(root, '.claude', 'kiwi');

    const channel = vscode.window.createOutputChannel('Kiwi Init');
    channel.show(true);
    channel.appendLine(`[Kiwi Init] onboarding ${root}`);

    const ok = await vscode.window.withProgress(
        {
            location: vscode.ProgressLocation.Notification,
            title: 'Kiwi: Initializing project...',
            cancellable: true,
        },
        (progress, token) => {
            progress.report({ message: 'detect stack → mine → seed scan → anchor + hook' });

            const args = ['-m', 'agent.cli', root, '--init', '--verbose'];
            const child = cp.spawn(pythonPath, args, {
                cwd: kiwiRoot,
                env: { ...process.env, PYTHONUTF8: '1' },
            });

            const timeout = setTimeout(() => {
                channel.appendLine('[Kiwi Init] TIMEOUT 10min — killing');
                child.kill();
            }, 10 * 60 * 1000);

            token.onCancellationRequested(() => {
                channel.appendLine('[Kiwi Init] cancelled by user');
                child.kill();
            });

            child.stdout.on('data', d => channel.append(d.toString()));
            child.stderr.on('data', d => channel.append(d.toString()));

            return new Promise<boolean>(resolve => {
                child.on('close', code => {
                    clearTimeout(timeout);
                    channel.appendLine(`\n[Kiwi Init] exit code ${code}`);
                    resolve(code === 0 && !token.isCancellationRequested);
                });
                child.on('error', err => {
                    clearTimeout(timeout);
                    channel.appendLine(`[Kiwi Init] spawn error: ${err.message}`);
                    vscode.window.showErrorMessage(`Kiwi Init spawn failed: ${err.message}`);
                    resolve(false);
                });
            });
        },
    );

    if (ok) {
        vscode.window.showInformationMessage('Kiwi initialized. Review mined suggestions in the Suggestions view.');
        // Pattern set may have grown (approved/seeded) — refresh server + views.
        const lc = client.getClient();
        if (lc && lc.isRunning()) {
            try {
                await lc.sendRequest('kiwi/invalidatePatterns', {});
            } catch {
                /* endpoint optional; ignore */
            }
        }
        await refreshInitState(client);
        vscode.commands.executeCommand('kiwi.refreshSuggestions');
    } else {
        vscode.window.showWarningMessage('Kiwi init did not complete. See "Kiwi Init" output for details.');
    }
}

/**
 * Query the server for onboarding state and publish it as the `kiwi.initialized`
 * context key, which drives which welcome view the sidebar shows.
 */
export async function refreshInitState(client: KiwiClient): Promise<void> {
    const ws = vscode.workspace.workspaceFolders?.[0];
    let initialized = false;
    const lc = client.getClient();
    if (ws && lc && lc.isRunning()) {
        try {
            const resp = await lc.sendRequest<{ initialized: boolean }>('kiwi/isInitialized', {
                path: ws.uri.fsPath,
            });
            initialized = !!resp?.initialized;
        } catch {
            initialized = false;
        }
    }
    await vscode.commands.executeCommand('setContext', 'kiwi.initialized', initialized);
}