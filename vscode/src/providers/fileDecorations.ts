import * as vscode from 'vscode';

export class FileDecorationProvider implements vscode.FileDecorationProvider, vscode.Disposable {
    private _onDidChangeFileDecorations = new vscode.EventEmitter<vscode.Uri | vscode.Uri[] | undefined>();
    readonly onDidChangeFileDecorations = this._onDidChangeFileDecorations.event;
    private disposables: vscode.Disposable[] = [];
    private registration: vscode.Disposable;

    constructor() {
        this.registration = vscode.window.registerFileDecorationProvider(this);
        this.disposables.push(
            this.registration,
            vscode.languages.onDidChangeDiagnostics(e => {
                this._onDidChangeFileDecorations.fire(e.uris);
            }),
        );
    }

    provideFileDecoration(uri: vscode.Uri): vscode.FileDecoration | undefined {
        const diagnostics = vscode.languages.getDiagnostics(uri);
        const kiwiDiags = diagnostics.filter(d => d.source === 'kiwi');

        if (kiwiDiags.length === 0) return undefined;

        const hasCritical = kiwiDiags.some(d => d.severity === vscode.DiagnosticSeverity.Error);
        const hasHigh = kiwiDiags.some(d => d.severity === vscode.DiagnosticSeverity.Warning);

        if (hasCritical) {
            return {
                badge: `${kiwiDiags.length}`,
                tooltip: `Kiwi: ${kiwiDiags.length} violation(s) — CRITICAL`,
                color: new vscode.ThemeColor('errorForeground'),
                propagate: true,
            };
        }

        if (hasHigh) {
            return {
                badge: `${kiwiDiags.length}`,
                tooltip: `Kiwi: ${kiwiDiags.length} violation(s)`,
                color: new vscode.ThemeColor('editorWarning.foreground'),
                propagate: false,
            };
        }

        return {
            badge: `${kiwiDiags.length}`,
            tooltip: `Kiwi: ${kiwiDiags.length} suggestion(s)`,
            propagate: false,
        };
    }

    dispose(): void {
        this._onDidChangeFileDecorations.dispose();
        this.disposables.forEach(d => d.dispose());
    }
}