import * as vscode from 'vscode';
import { KiwiClient } from './client';
import { KiwiStatusBar } from './statusBar';
import { registerCommands } from './commands/index';
import { FileDecorationProvider } from './providers/fileDecorations';
import { GutterDecorationProvider } from './providers/gutterDecorations';
import { ViolationsTreeProvider } from './providers/violationsTree';
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
    const dashboard = new DashboardProvider(context, () => client.getClient());

    vscode.window.createTreeView('kiwiViolations', {
        treeDataProvider: violationsTree,
        showCollapseAll: true,
    });

    registerCommands(context, client, violationsTree, dashboard);
    context.subscriptions.push(
        statusBar,
        outputChannel,
        fileDecorations,
        gutterDecorations,
        violationsTree,
        dashboard,
    );

    await client.start();
}

export function deactivate(): Thenable<void> | undefined {
    return client?.stop();
}