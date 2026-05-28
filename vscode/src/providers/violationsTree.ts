import * as vscode from 'vscode';

interface ViolationItem {
    type: 'severity' | 'file' | 'violation';
    label: string;
    severity?: string;
    uri?: vscode.Uri;
    range?: vscode.Range;
    lessonId?: string;
    count?: number;
    children?: ViolationItem[];
}

export class ViolationsTreeProvider implements vscode.TreeDataProvider<ViolationItem>, vscode.Disposable {
    private _onDidChangeTreeData = new vscode.EventEmitter<ViolationItem | undefined>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;
    private disposables: vscode.Disposable[] = [];

    constructor() {
        this.disposables.push(
            vscode.languages.onDidChangeDiagnostics(() => this._onDidChangeTreeData.fire(undefined)),
        );
    }

    refresh(): void {
        this._onDidChangeTreeData.fire(undefined);
    }

    getTreeItem(element: ViolationItem): vscode.TreeItem {
        const item = new vscode.TreeItem(element.label);

        if (element.type === 'severity') {
            item.collapsibleState = vscode.TreeItemCollapsibleState.Expanded;
            item.description = `${element.count}`;
            item.iconPath = element.severity === 'CRITICAL'
                ? new vscode.ThemeIcon('error', new vscode.ThemeColor('errorForeground'))
                : element.severity === 'HIGH'
                    ? new vscode.ThemeIcon('warning', new vscode.ThemeColor('editorWarning.foreground'))
                    : new vscode.ThemeIcon('info', new vscode.ThemeColor('editorInfo.foreground'));
        } else if (element.type === 'file') {
            item.collapsibleState = vscode.TreeItemCollapsibleState.Collapsed;
            item.resourceUri = element.uri;
            item.description = `${element.count}`;
            item.iconPath = vscode.ThemeIcon.File;
        } else if (element.type === 'violation') {
            item.collapsibleState = vscode.TreeItemCollapsibleState.None;
            item.description = element.lessonId;
            item.tooltip = element.label;
            if (element.uri && element.range) {
                item.command = {
                    command: 'vscode.open',
                    title: 'Go to violation',
                    arguments: [element.uri, { selection: element.range }],
                };
            }
        }

        return item;
    }

    getChildren(element?: ViolationItem): ViolationItem[] {
        if (!element) {
            return this.getRootItems();
        }
        return element.children || [];
    }

    private getRootItems(): ViolationItem[] {
        const allDiags = vscode.languages.getDiagnostics();
        const bySeverity: Record<string, Map<string, ViolationItem[]>> = {
            CRITICAL: new Map(),
            HIGH: new Map(),
            SUGGEST: new Map(),
        };

        for (const [uri, diags] of allDiags) {
            for (const diag of diags) {
                if (diag.source !== 'kiwi') continue;

                const severity = diag.severity === vscode.DiagnosticSeverity.Error ? 'CRITICAL'
                    : diag.severity === vscode.DiagnosticSeverity.Warning ? 'HIGH' : 'SUGGEST';

                const filePath = uri.fsPath;
                const fileName = filePath.split(/[/\\]/).pop() || filePath;

                if (!bySeverity[severity].has(filePath)) {
                    bySeverity[severity].set(filePath, []);
                }

                bySeverity[severity].get(filePath)!.push({
                    type: 'violation',
                    label: diag.message.replace(/^\[(CRITICAL|HIGH|SUGGEST)\]\s*/, ''),
                    uri,
                    range: diag.range,
                    lessonId: typeof diag.code === 'string' ? diag.code : String(diag.code),
                });
            }
        }

        const roots: ViolationItem[] = [];

        for (const [severity, fileMap] of Object.entries(bySeverity)) {
            if (fileMap.size === 0) continue;

            let totalCount = 0;
            const fileItems: ViolationItem[] = [];

            for (const [filePath, violations] of fileMap) {
                totalCount += violations.length;
                const fileName = filePath.split(/[/\\]/).pop() || filePath;
                fileItems.push({
                    type: 'file',
                    label: fileName,
                    uri: violations[0].uri,
                    count: violations.length,
                    children: violations,
                });
            }

            roots.push({
                type: 'severity',
                label: severity,
                severity,
                count: totalCount,
                children: fileItems,
            });
        }

        return roots;
    }

    dispose(): void {
        this._onDidChangeTreeData.dispose();
        this.disposables.forEach(d => d.dispose());
    }
}