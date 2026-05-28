import * as vscode from 'vscode';

export class KiwiStatusBar implements vscode.Disposable {
    private item: vscode.StatusBarItem;

    constructor() {
        this.item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
        this.item.command = 'workbench.actions.view.problems';
        this.item.text = '$(loading~spin) Kiwi';
        this.item.tooltip = 'Kiwi: Starting...';
        this.item.show();
    }

    setReady(): void {
        this.setCount(0);
    }

    setCount(count: number): void {
        if (count === 0) {
            this.item.text = '$(shield) Kiwi: clean';
            this.item.tooltip = 'Kiwi: No violations found';
            this.item.backgroundColor = undefined;
        } else {
            this.item.text = `$(shield) Kiwi: ${count} issue${count > 1 ? 's' : ''}`;
            this.item.tooltip = `Kiwi: ${count} violation${count > 1 ? 's' : ''} found`;
            this.item.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
        }
    }

    setError(): void {
        this.item.text = '$(error) Kiwi: offline';
        this.item.tooltip = 'Kiwi LSP server is not running';
        this.item.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
    }

    dispose(): void {
        this.item.dispose();
    }
}