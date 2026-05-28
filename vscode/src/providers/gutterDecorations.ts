import * as vscode from 'vscode';

const CRITICAL_ICON = '$(error)';
const HIGH_ICON = '$(warning)';
const SUGGEST_ICON = '$(info)';

const criticalDecoration = vscode.window.createTextEditorDecorationType({
    gutterIconPath: undefined,
    gutterIconSize: 'contain',
    overviewRulerColor: new vscode.ThemeColor('editorError.foreground'),
    overviewRulerLane: vscode.OverviewRulerLane.Left,
    before: {
        contentText: '',
        color: new vscode.ThemeColor('editorError.foreground'),
        margin: '0 4px 0 0',
    },
    backgroundColor: new vscode.ThemeColor('diffEditor.removedTextBackground'),
    isWholeLine: true,
});

const highDecoration = vscode.window.createTextEditorDecorationType({
    overviewRulerColor: new vscode.ThemeColor('editorWarning.foreground'),
    overviewRulerLane: vscode.OverviewRulerLane.Left,
    backgroundColor: new vscode.ThemeColor('diffEditor.removedTextBackground'),
    isWholeLine: true,
    opacity: '0.6',
});

const suggestDecoration = vscode.window.createTextEditorDecorationType({
    overviewRulerColor: new vscode.ThemeColor('editorInfo.foreground'),
    overviewRulerLane: vscode.OverviewRulerLane.Left,
});

export class GutterDecorationProvider implements vscode.Disposable {
    private disposables: vscode.Disposable[] = [];

    constructor() {
        this.disposables.push(
            vscode.window.onDidChangeActiveTextEditor(editor => {
                if (editor) this.updateDecorations(editor);
            }),
            vscode.languages.onDidChangeDiagnostics(e => {
                const editor = vscode.window.activeTextEditor;
                if (!editor) return;
                const affected = e.uris.some(uri => uri.toString() === editor.document.uri.toString());
                if (affected) this.updateDecorations(editor);
            }),
        );

        if (vscode.window.activeTextEditor) {
            this.updateDecorations(vscode.window.activeTextEditor);
        }
    }

    private updateDecorations(editor: vscode.TextEditor): void {
        const diagnostics = vscode.languages.getDiagnostics(editor.document.uri);
        const kiwiDiags = diagnostics.filter(d => d.source === 'kiwi');

        const critical: vscode.DecorationOptions[] = [];
        const high: vscode.DecorationOptions[] = [];
        const suggest: vscode.DecorationOptions[] = [];

        for (const diag of kiwiDiags) {
            const option: vscode.DecorationOptions = {
                range: diag.range,
                hoverMessage: new vscode.MarkdownString(diag.message),
            };

            if (diag.severity === vscode.DiagnosticSeverity.Error) {
                critical.push(option);
            } else if (diag.severity === vscode.DiagnosticSeverity.Warning) {
                high.push(option);
            } else {
                suggest.push(option);
            }
        }

        editor.setDecorations(criticalDecoration, critical);
        editor.setDecorations(highDecoration, high);
        editor.setDecorations(suggestDecoration, suggest);
    }

    dispose(): void {
        criticalDecoration.dispose();
        highDecoration.dispose();
        suggestDecoration.dispose();
        this.disposables.forEach(d => d.dispose());
    }
}
