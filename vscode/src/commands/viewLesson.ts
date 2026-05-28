import * as vscode from 'vscode';
import { LanguageClient } from 'vscode-languageclient/node';

let panel: vscode.WebviewPanel | undefined;
let activeClient: LanguageClient | undefined;

export function setLspClient(client: LanguageClient | undefined): void {
    activeClient = client;
}

export async function viewLesson(lessonId: string): Promise<void> {
    if (!lessonId) {
        const input = await vscode.window.showInputBox({ prompt: 'Enter lesson ID (e.g. LES-001)' });
        if (input) await viewLesson(input);
        return;
    }

    if (panel) {
        panel.reveal();
    } else {
        panel = vscode.window.createWebviewPanel(
            'kiwiLesson',
            `Kiwi: ${lessonId}`,
            vscode.ViewColumn.Beside,
            { enableScripts: false },
        );
        panel.onDidDispose(() => { panel = undefined; });
    }

    panel.title = `Kiwi: ${lessonId}`;

    let info: LessonInfo | null = null;
    if (activeClient && activeClient.isRunning()) {
        try {
            info = await activeClient.sendRequest('kiwi/lessonDetail', { lesson_id: lessonId });
        } catch { /* fallback to placeholder */ }
    }

    panel.webview.html = buildLessonHtml(lessonId, info);
}

interface LessonInfo {
    id: string;
    title: string;
    severity: string;
    category: string;
    why: string;
    good_code: string;
    bad_code: string;
}

function escapeHtml(text: string): string {
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function buildLessonHtml(lessonId: string, info: LessonInfo | null): string {
    const title = info?.title || lessonId;
    const severity = info?.severity || 'UNKNOWN';
    const category = info?.category || '';
    const why = info?.why || '';
    const badCode = info?.bad_code || '';
    const goodCode = info?.good_code || '';

    const sections: string[] = [];

    sections.push(`<h1 class="severity-${severity}">${escapeHtml(lessonId)} — ${escapeHtml(title)}</h1>`);
    sections.push(`<p><strong>Severity:</strong> ${escapeHtml(severity)} | <strong>Category:</strong> ${escapeHtml(category)}</p>`);

    if (why) {
        sections.push(`<h2>Why</h2><p>${escapeHtml(why)}</p>`);
    }

    if (badCode) {
        sections.push(`<h2>Bad</h2><pre>${escapeHtml(badCode)}</pre>`);
    }

    if (goodCode) {
        sections.push(`<h2>Good</h2><pre>${escapeHtml(goodCode)}</pre>`);
    }

    if (!info) {
        sections.push(`<p><em>Could not fetch lesson details from LSP server.</em></p>`);
    }

    return `<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: var(--vscode-font-family); padding: 16px; color: var(--vscode-foreground); background: var(--vscode-editor-background); }
        h1 { font-size: 1.4em; margin-bottom: 8px; }
        h2 { font-size: 1.1em; margin-top: 16px; margin-bottom: 4px; }
        pre { background: var(--vscode-textCodeBlock-background); padding: 12px; border-radius: 4px; overflow-x: auto; font-size: 0.9em; }
        .severity-CRITICAL { color: var(--vscode-errorForeground); }
        .severity-HIGH { color: var(--vscode-editorWarning-foreground); }
        .severity-SUGGEST { color: var(--vscode-editorInfo-foreground); }
    </style>
</head>
<body>
    ${sections.join('\n    ')}
</body>
</html>`;
}