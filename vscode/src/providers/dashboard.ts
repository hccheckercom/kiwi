import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';
import { LanguageClient } from 'vscode-languageclient/node';

let dashboardPanel: vscode.WebviewPanel | undefined;

interface StatsResponse {
    total_files: number;
    total_violations: number;
    by_severity: { CRITICAL: number; HIGH: number; SUGGEST: number };
    top_lessons: Array<{ id: string; count: number }>;
    total_patterns: number;
}

interface LearningHealth {
    status: 'healthy' | 'degraded' | 'stalled' | 'disabled' | 'error';
    stats?: {
        total_sessions: number;
        total_writes_logged: number;
        total_bindings_learned: number;
        total_styles_learned: number;
        total_context_patterns: number;
        total_suggestions_pending: number;
        total_suggestions_promoted: number;
        last_session_at: string | null;
        last_promotion_at: string | null;
    };
    health_signals?: {
        learning_disabled: boolean;
        fail_counts: Record<string, number>;
        stale_sessions: number;
        recent_sessions_7d: number;
        db_size_mb: number;
    };
    themes_learned?: string[];
    top_bindings?: Array<{ binding: string; times_seen: number }>;
}

interface ProgressData {
    lessonsEncountered: string[];
    lessonsFixed: string[];
    lessonsDismissed: string[];
    scansToday: number;
    lastScanTime: string;
}

const SAVINGS_PER_SEVERITY = {
    CRITICAL: 4.0,
    HIGH: 1.5,
    SUGGEST: 0.3,
};

export class DashboardProvider implements vscode.Disposable {
    private progress: ProgressData;
    private storageKey = 'kiwi.dashboard.progress';

    constructor(
        private readonly context: vscode.ExtensionContext,
        private readonly getClient: () => LanguageClient | undefined,
    ) {
        this.progress = this.loadProgress();
    }

    async openDashboard(): Promise<void> {
        if (dashboardPanel) {
            dashboardPanel.reveal();
        } else {
            dashboardPanel = vscode.window.createWebviewPanel(
                'kiwiDashboard',
                'Kiwi Dashboard',
                vscode.ViewColumn.One,
                { enableScripts: true },
            );
            dashboardPanel.onDidDispose(() => { dashboardPanel = undefined; });
        }

        await this.refreshDashboard();
    }

    async refreshDashboard(): Promise<void> {
        if (!dashboardPanel) return;

        const stats = await this.fetchStats();
        const learning = await this.fetchLearningHealth();
        const savings = this.calculateSavings(stats);
        const progress = this.progress;

        dashboardPanel.webview.html = this.buildHtml(stats, savings, progress, learning);
    }

    recordScan(): void {
        this.progress.scansToday++;
        this.progress.lastScanTime = new Date().toISOString();
        this.saveProgress();
    }

    recordLessonEncountered(lessonId: string): void {
        if (!this.progress.lessonsEncountered.includes(lessonId)) {
            this.progress.lessonsEncountered.push(lessonId);
            this.saveProgress();
        }
    }

    recordLessonFixed(lessonId: string): void {
        if (!this.progress.lessonsFixed.includes(lessonId)) {
            this.progress.lessonsFixed.push(lessonId);
            this.saveProgress();
        }
    }

    recordLessonDismissed(lessonId: string): void {
        if (!this.progress.lessonsDismissed.includes(lessonId)) {
            this.progress.lessonsDismissed.push(lessonId);
            this.saveProgress();
        }
    }

    private async fetchStats(): Promise<StatsResponse | null> {
        const client = this.getClient();
        if (!client || !client.isRunning()) return null;

        try {
            return await client.sendRequest('kiwi/stats', {});
        } catch {
            return null;
        }
    }

    private calculateSavings(stats: StatsResponse | null): { hours: number; bugs: number } {
        if (!stats) return { hours: 0, bugs: 0 };

        const hours =
            stats.by_severity.CRITICAL * SAVINGS_PER_SEVERITY.CRITICAL +
            stats.by_severity.HIGH * SAVINGS_PER_SEVERITY.HIGH +
            stats.by_severity.SUGGEST * SAVINGS_PER_SEVERITY.SUGGEST;

        return { hours: Math.round(hours * 10) / 10, bugs: stats.total_violations };
    }

    private async fetchLearningHealth(): Promise<LearningHealth | null> {
        return await new Promise<LearningHealth | null>((resolve) => {
            try {
                const folders = vscode.workspace.workspaceFolders;
                if (!folders || folders.length === 0) {
                    resolve(null);
                    return;
                }
                const root = folders[0].uri.fsPath;
                const script = path.join(root, '.claude', 'kiwi', 'tools', 'learning_health.py');
                const proc = cp.spawn('python', [script], {
                    cwd: path.join(root, '.claude', 'kiwi'),
                    env: { ...process.env, PYTHONUTF8: '1' },
                });
                let stdout = '';
                proc.stdout.on('data', (d) => { stdout += d.toString(); });
                proc.on('close', () => {
                    try {
                        resolve(JSON.parse(stdout) as LearningHealth);
                    } catch {
                        resolve(null);
                    }
                });
                proc.on('error', () => resolve(null));
                setTimeout(() => { try { proc.kill(); } catch {} resolve(null); }, 5000);
            } catch {
                resolve(null);
            }
        });
    }

    private loadProgress(): ProgressData {
        const stored = this.context.workspaceState.get<ProgressData>(this.storageKey);
        if (stored) return stored;
        return {
            lessonsEncountered: [],
            lessonsFixed: [],
            lessonsDismissed: [],
            scansToday: 0,
            lastScanTime: '',
        };
    }

    private saveProgress(): void {
        this.context.workspaceState.update(this.storageKey, this.progress);
    }

    private buildHtml(stats: StatsResponse | null, savings: { hours: number; bugs: number }, progress: ProgressData, learning: LearningHealth | null): string {
        const totalPatterns = stats?.total_patterns || 726;
        const encountered = progress.lessonsEncountered.length;
        const fixed = progress.lessonsFixed.length;
        const dismissed = progress.lessonsDismissed.length;
        const addressed = fixed + dismissed;
        const progressPct = encountered > 0 ? Math.round((addressed / encountered) * 100) : 0;

        const topLessonsHtml = (stats?.top_lessons || [])
            .map(l => `<tr><td>${l.id}</td><td>${l.count}</td></tr>`)
            .join('');

        const learningStatusColor: Record<string, string> = {
            healthy: 'var(--vscode-testing-iconPassed, #4ec9b0)',
            degraded: 'var(--vscode-editorWarning-foreground, #d7ba7d)',
            stalled: 'var(--vscode-disabledForeground, #888)',
            disabled: 'var(--vscode-disabledForeground, #888)',
            error: 'var(--vscode-errorForeground, #f48771)',
        };
        const learningStatus = learning?.status || 'error';
        const learningHtml = learning && learning.stats ? `
    <h2>Active Learning</h2>
    <p>
        Status: <strong style="color: ${learningStatusColor[learningStatus] || ''}">● ${learningStatus.toUpperCase()}</strong>
        &nbsp;|&nbsp; DB: ${learning.health_signals?.db_size_mb ?? 0} MB
        &nbsp;|&nbsp; Last session: ${learning.stats.last_session_at ? new Date(learning.stats.last_session_at).toLocaleString() : 'never'}
    </p>
    <div class="grid">
        <div class="card">
            <h3>Sessions</h3>
            <div class="value">${learning.stats.total_sessions}</div>
            <div class="sub">${learning.health_signals?.recent_sessions_7d ?? 0} in last 7d</div>
        </div>
        <div class="card">
            <h3>Writes Captured</h3>
            <div class="value">${learning.stats.total_writes_logged}</div>
            <div class="sub">Write/Edit calls logged</div>
        </div>
        <div class="card">
            <h3>Bindings Learned</h3>
            <div class="value">${learning.stats.total_bindings_learned}</div>
            <div class="sub">${learning.themes_learned?.length || 0} themes</div>
        </div>
        <div class="card">
            <h3>Suggestions</h3>
            <div class="value">${learning.stats.total_suggestions_pending}</div>
            <div class="sub">${learning.stats.total_suggestions_promoted} promoted</div>
        </div>
    </div>
    ${learning.top_bindings && learning.top_bindings.length > 0 ? `
    <h2>Top Bindings Learned</h2>
    <table>
        <tr><th>Binding</th><th>Times Seen</th></tr>
        ${learning.top_bindings.slice(0, 5).map(b => `<tr><td>${b.binding}</td><td>${b.times_seen}</td></tr>`).join('')}
    </table>` : ''}
    ${learning.health_signals && Object.keys(learning.health_signals.fail_counts).length > 0 ? `
    <h2>Fail Counters</h2>
    <table>
        <tr><th>Stage</th><th>Failures</th></tr>
        ${Object.entries(learning.health_signals.fail_counts).map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join('')}
    </table>` : ''}
` : `<h2>Active Learning</h2><p class="empty">No learning data yet — code with Kiwi to start building patterns.</p>`;

        return `<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {
            font-family: var(--vscode-font-family);
            padding: 20px;
            color: var(--vscode-foreground);
            background: var(--vscode-editor-background);
        }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .card {
            background: var(--vscode-editorWidget-background);
            border: 1px solid var(--vscode-editorWidget-border);
            border-radius: 8px;
            padding: 16px;
        }
        .card h3 { margin: 0 0 8px 0; font-size: 0.85em; opacity: 0.7; text-transform: uppercase; letter-spacing: 0.5px; }
        .card .value { font-size: 2em; font-weight: bold; }
        .card .sub { font-size: 0.85em; opacity: 0.7; margin-top: 4px; }
        .severity-bar { display: flex; height: 8px; border-radius: 4px; overflow: hidden; margin: 8px 0; }
        .severity-bar .critical { background: var(--vscode-errorForeground); }
        .severity-bar .high { background: var(--vscode-editorWarning-foreground); }
        .severity-bar .suggest { background: var(--vscode-editorInfo-foreground); }
        .progress-bar { background: var(--vscode-progressBar-background); height: 6px; border-radius: 3px; margin: 8px 0; }
        .progress-fill { background: var(--vscode-progressBar-background); height: 100%; border-radius: 3px; transition: width 0.3s; }
        table { width: 100%; border-collapse: collapse; }
        th, td { text-align: left; padding: 6px 12px; border-bottom: 1px solid var(--vscode-editorWidget-border); }
        th { opacity: 0.7; font-size: 0.85em; }
        h2 { margin-top: 24px; font-size: 1.1em; }
        .empty { opacity: 0.5; font-style: italic; }
    </style>
</head>
<body>
    <h1>Kiwi Dashboard</h1>

    <div class="grid">
        <div class="card">
            <h3>Bugs Caught</h3>
            <div class="value">${savings.bugs}</div>
            <div class="sub">across ${stats?.total_files || 0} files</div>
        </div>
        <div class="card">
            <h3>Time Saved</h3>
            <div class="value">${savings.hours}h</div>
            <div class="sub">estimated debugging time</div>
        </div>
        <div class="card">
            <h3>Patterns Active</h3>
            <div class="value">${totalPatterns}</div>
            <div class="sub">learned from past bugs</div>
        </div>
        <div class="card">
            <h3>Scans Today</h3>
            <div class="value">${progress.scansToday}</div>
            <div class="sub">${progress.lastScanTime ? 'last: ' + new Date(progress.lastScanTime).toLocaleTimeString() : 'no scans yet'}</div>
        </div>
    </div>

    <h2>Severity Breakdown</h2>
    ${stats ? `
    <div class="severity-bar">
        <div class="critical" style="flex: ${stats.by_severity.CRITICAL}"></div>
        <div class="high" style="flex: ${stats.by_severity.HIGH}"></div>
        <div class="suggest" style="flex: ${stats.by_severity.SUGGEST}"></div>
    </div>
    <p>
        <span style="color: var(--vscode-errorForeground)">CRITICAL: ${stats.by_severity.CRITICAL}</span> &nbsp;
        <span style="color: var(--vscode-editorWarning-foreground)">HIGH: ${stats.by_severity.HIGH}</span> &nbsp;
        <span style="color: var(--vscode-editorInfo-foreground)">SUGGEST: ${stats.by_severity.SUGGEST}</span>
    </p>` : '<p class="empty">Run a scan to see severity breakdown</p>'}

    <h2>Learning Progress</h2>
    <p>Patterns encountered: <strong>${encountered}</strong> | Fixed: <strong>${fixed}</strong> | Dismissed: <strong>${dismissed}</strong></p>
    <div style="background: var(--vscode-editorWidget-border); height: 6px; border-radius: 3px; overflow: hidden;">
        <div style="background: var(--vscode-progressBar-background); height: 100%; width: ${progressPct}%; border-radius: 3px;"></div>
    </div>
    <p class="sub">${progressPct}% of encountered patterns addressed</p>

    ${topLessonsHtml ? `
    <h2>Top Violations</h2>
    <table>
        <tr><th>Lesson</th><th>Count</th></tr>
        ${topLessonsHtml}
    </table>` : ''}

    ${learningHtml}
</body>
</html>`;
    }

    dispose(): void {
        if (dashboardPanel) {
            dashboardPanel.dispose();
            dashboardPanel = undefined;
        }
    }
}
