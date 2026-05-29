import * as vscode from 'vscode';
import { State } from 'vscode-languageclient/node';
import { KiwiClient } from '../client';

interface Suggestion {
    id: number;
    pattern: string;
    scope: string;
    category?: string;
    severity?: string;
    example_file?: string;
    example_line?: number;
    example_code?: string;
    suggested_at?: string;
    status?: string;
}

const SEVERITY_ICON: Record<string, [string, string]> = {
    CRITICAL: ['error', 'errorForeground'],
    HIGH: ['warning', 'editorWarning.foreground'],
    SUGGEST: ['info', 'editorInfo.foreground'],
};

export class SuggestionsTreeProvider implements vscode.TreeDataProvider<Suggestion>, vscode.Disposable {
    private _onDidChangeTreeData = new vscode.EventEmitter<Suggestion | undefined>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    private suggestions: Suggestion[] = [];
    private loaded = false;

    constructor(private client: KiwiClient) {}

    refresh(): void {
        this.loaded = false;
        this.suggestions = [];
        this._onDidChangeTreeData.fire(undefined);
    }

    /** Number of pending suggestions — used to surface a badge on the view. */
    get count(): number {
        return this.suggestions.length;
    }

    getTreeItem(s: Suggestion): vscode.TreeItem {
        const title = this.shortTitle(s);
        const item = new vscode.TreeItem(title, vscode.TreeItemCollapsibleState.None);
        item.description = s.category ? `${s.category} · #${s.id}` : `#${s.id}`;

        const sev = (s.severity || 'SUGGEST').toUpperCase();
        const [icon, color] = SEVERITY_ICON[sev] ?? SEVERITY_ICON.SUGGEST;
        item.iconPath = new vscode.ThemeIcon(icon, new vscode.ThemeColor(color));

        // contextValue drives the inline ✓ / ✗ buttons declared in package.json.
        item.contextValue = 'kiwiSuggestion';
        item.tooltip = this.buildTooltip(s);

        // Clicking the row opens the example location when we know it.
        if (s.example_file) {
            const uri = vscode.Uri.file(s.example_file);
            const line = Math.max(0, (s.example_line ?? 1) - 1);
            item.command = {
                command: 'vscode.open',
                title: 'Open example',
                arguments: [uri, { selection: new vscode.Range(line, 0, line, 0) }],
            };
        }
        return item;
    }

    async getChildren(element?: Suggestion): Promise<Suggestion[]> {
        if (element) return [];
        await this.ensureLoaded();
        return this.suggestions;
    }

    private async ensureLoaded(): Promise<void> {
        if (this.loaded) return;
        const lc = this.client.getClient();
        if (!lc || lc.state !== State.Running) return;
        try {
            const resp = await lc.sendRequest<{ success: boolean; suggestions?: Suggestion[]; error?: string }>(
                'kiwi/listSuggestions',
                { status: 'pending' },
            );
            if (resp?.success && resp.suggestions) {
                this.suggestions = resp.suggestions;
            } else {
                this.suggestions = [];
            }
            this.loaded = true;
        } catch (err) {
            console.error('[Kiwi] listSuggestions failed:', err);
            this.suggestions = [];
        }
    }

    private shortTitle(s: Suggestion): string {
        const pat = (s.pattern || '').trim().replace(/\s+/g, ' ');
        if (pat.length <= 60) return pat || `Suggestion #${s.id}`;
        return pat.slice(0, 57) + '…';
    }

    private buildTooltip(s: Suggestion): vscode.MarkdownString {
        const md = new vscode.MarkdownString();
        md.appendMarkdown(`**Suggested lesson #${s.id}**  \n`);
        if (s.severity) md.appendMarkdown(`Severity: \`${s.severity}\`  \n`);
        if (s.category) md.appendMarkdown(`Category: ${s.category}  \n`);
        if (s.scope) md.appendMarkdown(`Scope: \`${s.scope}\`  \n`);
        if (s.example_file) {
            const loc = s.example_line ? `${s.example_file}:${s.example_line}` : s.example_file;
            md.appendMarkdown(`Example: ${loc}  \n`);
        }
        md.appendMarkdown(`\nPattern:\n`);
        md.appendCodeblock(s.pattern || '', 'text');
        if (s.example_code) {
            md.appendMarkdown(`\nExample code:\n`);
            md.appendCodeblock(s.example_code, 'php');
        }
        return md;
    }

    dispose(): void {
        this._onDidChangeTreeData.dispose();
        this.suggestions = [];
    }
}