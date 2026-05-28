import * as vscode from 'vscode';
import { KiwiClient } from '../client';
import { ViolationsTreeProvider } from '../providers/violationsTree';
import { DashboardProvider } from '../providers/dashboard';
import { viewLesson, setLspClient } from './viewLesson';
import { scanProject } from './scanProject';
import { scanUncommitted } from './scanUncommitted';
import { dismissViolation } from './dismissViolation';
import { showEditorGuide } from './editorGuide';

export function registerCommands(
    context: vscode.ExtensionContext,
    client: KiwiClient,
    violationsTree: ViolationsTreeProvider,
    dashboard: DashboardProvider,
): void {
    const lc = client.getClient();
    if (lc) setLspClient(lc);

    context.subscriptions.push(
        vscode.commands.registerCommand('kiwi.restart', async () => {
            await client.restart();
            setLspClient(client.getClient());
        }),
        vscode.commands.registerCommand('kiwi.scanProject', () => scanProject(client)),
        vscode.commands.registerCommand('kiwi.viewLesson', (lessonId: string) => viewLesson(lessonId)),
        vscode.commands.registerCommand('kiwi.dismissFile', () => dismissViolation(client, 'file')),
        vscode.commands.registerCommand('kiwi.dismissProject', () => dismissViolation(client, 'project')),
        vscode.commands.registerCommand('kiwi.refreshViolations', () => violationsTree.refresh()),
        vscode.commands.registerCommand('kiwi.openDashboard', () => dashboard.openDashboard()),
        vscode.commands.registerCommand('kiwi.scanUncommitted', () => scanUncommitted(client)),
        vscode.commands.registerCommand('kiwi.editorGuide', (editor?: string) => showEditorGuide(editor)),
    );
}