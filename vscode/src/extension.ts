import * as vscode from 'vscode';
import { KiwiClient } from './client';
import { KiwiStatusBar } from './statusBar';
import { registerCommands } from './commands/index';
import { refreshInitState } from './commands/initialize';
import { FileDecorationProvider } from './providers/fileDecorations';
import { GutterDecorationProvider } from './providers/gutterDecorations';
import { ViolationsTreeProvider } from './providers/violationsTree';
import { SuggestionsTreeProvider } from './providers/suggestionsTree';
import { DashboardProvider } from './providers/dashboard';

let client: KiwiClient;
let statusBar: KiwiStatusBar;

export async function activate(context: vscode.ExtensionContext): Promise<void> {
    const outputChannel = vscode.window.createOutputChannel('Kiwi LSP');

    statusBar = new KiwiStatusBar();
    client = new KiwiClient(context, outputChannel, statusBar);

    const fileDecorations = new FileDecorationProvider();
    const gutterDecorations = new GutterDecorationProvider();
    const violationsTree = new ViolationsTreeProvider();
    const suggestionsTree = new SuggestionsTreeProvider(client);
    const dashboard = new DashboardProvider(context, () => client.getClient());

    vscode.window.createTreeView('kiwiViolations', {
        treeDataProvider: violationsTree,
        showCollapseAll: true,
    });
    vscode.window.createTreeView('kiwiSuggestions', {
        treeDataProvider: suggestionsTree,
    });

    registerCommands(context, client, violationsTree, suggestionsTree, dashboard);
    context.subscriptions.push(
        statusBar,
        outputChannel,
        fileDecorations,
        gutterDecorations,
        violationsTree,
        suggestionsTree,
        dashboard,
    );

    // Default the welcome-view state until the server confirms onboarding.
    await vscode.commands.executeCommand('setContext', 'kiwi.initialized', false);

    await client.start();

    // Server is up — resolve onboarding state and load any pending suggestions.
    await refreshInitState(client);
    suggestionsTree.refresh();
}

export function deactivate(): Thenable<void> | undefined {
    return client?.stop();
}