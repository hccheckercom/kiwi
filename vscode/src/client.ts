import * as vscode from 'vscode';
import * as path from 'path';
import {
    LanguageClient,
    LanguageClientOptions,
    ServerOptions,
    TransportKind,
} from 'vscode-languageclient/node';
import { KiwiStatusBar } from './statusBar';

export class KiwiClient {
    private client: LanguageClient | undefined;
    private restartCount = 0;
    private readonly maxRestarts = 3;

    constructor(
        private readonly context: vscode.ExtensionContext,
        private readonly outputChannel: vscode.OutputChannel,
        private readonly statusBar: KiwiStatusBar,
    ) {}

    async start(): Promise<void> {
        const serverOptions = this.getServerOptions();
        if (!serverOptions) return;

        const clientOptions: LanguageClientOptions = {
            documentSelector: [
                { scheme: 'file', language: 'php' },
                { scheme: 'file', language: 'javascript' },
                { scheme: 'file', language: 'typescript' },
                { scheme: 'file', language: 'css' },
                { scheme: 'file', language: 'html' },
            ],
            outputChannel: this.outputChannel,
            initializationOptions: this.getInitOptions(),
        };

        this.client = new LanguageClient(
            'kiwi-lsp',
            'Kiwi LSP',
            serverOptions,
            clientOptions,
        );

        this.client.onDidChangeState(({ newState }) => {
            if (newState === 1) { // stopped
                this.statusBar.setError();
                if (this.restartCount < this.maxRestarts) {
                    this.restartCount++;
                    setTimeout(() => this.start(), 2000);
                } else {
                    vscode.window.showErrorMessage(
                        'Kiwi LSP server crashed repeatedly. Check Output > Kiwi LSP for details.'
                    );
                }
            } else if (newState === 3) { // running
                this.restartCount = 0;
                this.statusBar.setReady();
            }
        });

        this.context.subscriptions.push(
            vscode.workspace.onDidChangeConfiguration(e => {
                if (e.affectsConfiguration('kiwi')) {
                    this.client?.sendNotification('workspace/didChangeConfiguration', {
                        settings: this.getInitOptions(),
                    });
                }
            })
        );

        this.context.subscriptions.push(
            vscode.languages.onDidChangeDiagnostics(() => this.updateDiagnosticCount())
        );

        await this.client.start();
    }

    async stop(): Promise<void> {
        if (this.client) {
            await this.client.stop();
        }
    }

    async restart(): Promise<void> {
        this.restartCount = 0;
        await this.stop();
        await this.start();
    }

    getClient(): LanguageClient | undefined {
        return this.client;
    }

    private getServerOptions(): ServerOptions | undefined {
        const config = vscode.workspace.getConfiguration('kiwi');
        const pythonPath = config.get<string>('pythonPath') || this.detectPython();
        const serverPath = config.get<string>('serverPath') || this.detectServerPath();

        if (!serverPath) {
            vscode.window.showErrorMessage(
                'Kiwi: Cannot find LSP server. Set kiwi.serverPath in settings.'
            );
            return undefined;
        }

        return {
            command: pythonPath,
            args: ['-m', 'lsp.server'],
            options: { cwd: serverPath },
            transport: TransportKind.stdio,
        };
    }

    private getInitOptions(): Record<string, unknown> {
        const config = vscode.workspace.getConfiguration('kiwi');
        return {
            severity: config.get('severity', 'ALL'),
            scanOnOpen: config.get('scanOnOpen', true),
            scanOnSave: config.get('scanOnSave', true),
            scanOnChange: config.get('scanOnChange', false),
            platform: config.get('platform', 'wp'),
        };
    }

    private detectPython(): string {
        return process.platform === 'win32' ? 'python' : 'python3';
    }

    private detectServerPath(): string | undefined {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) return undefined;

        for (const folder of workspaceFolders) {
            const candidate = path.join(folder.uri.fsPath, '.claude', 'kiwi');
            return candidate;
        }
        return undefined;
    }

    private updateDiagnosticCount(): void {
        const diagnostics = vscode.languages.getDiagnostics();
        let count = 0;
        for (const [, diags] of diagnostics) {
            count += diags.filter(d => d.source === 'kiwi').length;
        }
        this.statusBar.setCount(count);
    }
}