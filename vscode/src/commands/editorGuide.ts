import * as vscode from 'vscode';

type Lang = 'en' | 'vi';

interface EditorGuide {
    name: string;
    icon: string;
    config: string;
    steps: { en: string[]; vi: string[] };
}

const GUIDES: Record<string, EditorGuide> = {
    neovim: {
        name: 'Neovim',
        icon: 'terminal',
        config: `-- lua/lspconfig: add to your init.lua or lsp.lua
local lspconfig = require('lspconfig')
local configs = require('lspconfig.configs')

if not configs.kiwi then
  configs.kiwi = {
    default_config = {
      cmd = { 'python', '-m', 'lsp' },
      cmd_cwd = vim.fn.expand('~/.claude/kiwi'),
      filetypes = { 'php', 'javascript', 'typescript', 'css', 'html' },
      root_dir = lspconfig.util.root_pattern('.git', 'composer.json', 'package.json'),
      settings = {},
      init_options = {
        severity = 'ALL',
        scanOnOpen = true,
        scanOnSave = true,
        platform = 'wp',
      },
    },
  }
end

lspconfig.kiwi.setup({
  on_attach = function(client, bufnr)
    vim.keymap.set('n', 'gd', vim.lsp.buf.definition, { buffer = bufnr })
    vim.keymap.set('n', 'K', vim.lsp.buf.hover, { buffer = bufnr })
    vim.keymap.set('n', '<leader>ca', vim.lsp.buf.code_action, { buffer = bufnr })
  end,
})`,
        steps: {
            en: [
                'Install nvim-lspconfig: `Plug "neovim/nvim-lspconfig"` or lazy.nvim equivalent',
                'Copy the config above into your `init.lua` or `lua/lsp.lua`',
                'Adjust `cmd_cwd` to point to your Kiwi installation path',
                'Restart Neovim and open a PHP/JS/CSS file',
                'Verify: `:LspInfo` should show "kiwi" as attached',
                'Diagnostics appear inline, use `K` for hover, `<leader>ca` for code actions',
            ],
            vi: [
                'Cài nvim-lspconfig: `Plug "neovim/nvim-lspconfig"` hoặc lazy.nvim tương đương',
                'Copy config trên vào `init.lua` hoặc `lua/lsp.lua`',
                'Sửa `cmd_cwd` trỏ đến thư mục Kiwi của bạn',
                'Restart Neovim và mở file PHP/JS/CSS',
                'Kiểm tra: `:LspInfo` phải hiện "kiwi" đã attached',
                'Diagnostics hiện inline, dùng `K` để hover, `<leader>ca` cho code actions',
            ],
        },
    },
    jetbrains: {
        name: 'JetBrains (PhpStorm/WebStorm)',
        icon: 'code',
        config: `// Settings → Languages & Frameworks → Language Servers
// Add new server:
{
  "name": "Kiwi",
  "command": "python -m lsp",
  "workingDir": "C:\\\\Users\\\\<you>\\\\.claude\\\\kiwi",
  "languages": ["PHP", "JavaScript", "TypeScript", "CSS", "HTML"],
  "initializationOptions": {
    "severity": "ALL",
    "scanOnOpen": true,
    "scanOnSave": true,
    "platform": "wp"
  }
}`,
        steps: {
            en: [
                'Open Settings → Languages & Frameworks → Language Servers (requires LSP plugin)',
                'Click "+" to add a new language server',
                'Name: "Kiwi", Command: `python -m lsp`',
                'Set Working Directory to your Kiwi path (e.g. `~/.claude/kiwi`)',
                'Add file type mappings: PHP, JavaScript, TypeScript, CSS, HTML',
                'Apply and restart IDE — diagnostics will appear in editor',
            ],
            vi: [
                'Mở Settings → Languages & Frameworks → Language Servers (cần cài LSP plugin)',
                'Nhấn "+" để thêm language server mới',
                'Name: "Kiwi", Command: `python -m lsp`',
                'Đặt Working Directory trỏ đến thư mục Kiwi (vd: `~/.claude/kiwi`)',
                'Thêm file type mappings: PHP, JavaScript, TypeScript, CSS, HTML',
                'Apply và restart IDE — diagnostics sẽ hiện trong editor',
            ],
        },
    },
    cursor: {
        name: 'Cursor / Windsurf',
        icon: 'sparkle',
        config: `// These editors are VS Code-compatible.
// Install the .vsix directly:
//   1. Download kiwi-lsp-0.1.0.vsix
//   2. Extensions panel → "..." menu → "Install from VSIX..."
//   3. Select the .vsix file
//
// Or via command line:
cursor --install-extension kiwi-lsp-0.1.0.vsix
windsurf --install-extension kiwi-lsp-0.1.0.vsix`,
        steps: {
            en: [
                'Download `kiwi-lsp-0.1.0.vsix` from the release',
                'Open Extensions panel → click "..." → "Install from VSIX..."',
                'Select the downloaded .vsix file',
                'Reload the editor — Kiwi activates automatically on PHP/JS/CSS files',
                'All features work identically to VS Code (diagnostics, hover, quick fix)',
            ],
            vi: [
                'Tải `kiwi-lsp-0.1.0.vsix` từ release',
                'Mở Extensions panel → nhấn "..." → "Install from VSIX..."',
                'Chọn file .vsix đã tải',
                'Reload editor — Kiwi tự kích hoạt khi mở file PHP/JS/CSS',
                'Mọi tính năng hoạt động giống VS Code (diagnostics, hover, quick fix)',
            ],
        },
    },
    sublime: {
        name: 'Sublime Text',
        icon: 'file-text',
        config: `// Install "LSP" package via Package Control first.
// Then create: Preferences → Package Settings → LSP → Settings
{
  "clients": {
    "kiwi": {
      "enabled": true,
      "command": ["python", "-m", "lsp"],
      "working_dir": "C:\\\\Users\\\\<you>\\\\.claude\\\\kiwi",
      "selector": "source.php | source.js | source.ts | source.css | text.html",
      "initializationOptions": {
        "severity": "ALL",
        "scanOnOpen": true,
        "scanOnSave": true,
        "platform": "wp"
      }
    }
  }
}`,
        steps: {
            en: [
                'Install "LSP" package via Package Control (Ctrl+Shift+P → Install Package → LSP)',
                'Open: Preferences → Package Settings → LSP → Settings',
                'Add the Kiwi client config (see above) to the "clients" object',
                'Adjust `working_dir` to your Kiwi installation path',
                'Save and reopen a PHP/JS/CSS file',
                'Diagnostics appear as inline phantoms, hover for details, Ctrl+. for code actions',
            ],
            vi: [
                'Cài package "LSP" qua Package Control (Ctrl+Shift+P → Install Package → LSP)',
                'Mở: Preferences → Package Settings → LSP → Settings',
                'Thêm config Kiwi (xem trên) vào object "clients"',
                'Sửa `working_dir` trỏ đến thư mục Kiwi của bạn',
                'Lưu và mở lại file PHP/JS/CSS',
                'Diagnostics hiện inline, hover để xem chi tiết, Ctrl+. cho code actions',
            ],
        },
    },
};

let guidePanel: vscode.WebviewPanel | undefined;

export function showEditorGuide(editor?: string): void {
    const lang = getLanguage();

    if (!editor) {
        const items = Object.entries(GUIDES).map(([key, g]) => ({
            label: `$(${g.icon}) ${g.name}`,
            description: key,
            key,
        }));

        vscode.window.showQuickPick(items, {
            placeHolder: lang === 'vi' ? 'Chọn editor để xem hướng dẫn setup' : 'Select editor for setup guide',
        }).then(selected => {
            if (selected) showEditorGuide(selected.key);
        });
        return;
    }

    const guide = GUIDES[editor];
    if (!guide) return;

    if (guidePanel) {
        guidePanel.reveal();
    } else {
        guidePanel = vscode.window.createWebviewPanel(
            'kiwiEditorGuide',
            `Kiwi: ${guide.name} Setup`,
            vscode.ViewColumn.One,
            { enableScripts: false },
        );
        guidePanel.onDidDispose(() => { guidePanel = undefined; });
    }

    guidePanel.title = `Kiwi: ${guide.name} Setup`;
    guidePanel.webview.html = buildGuideHtml(guide, lang);
}

function getLanguage(): Lang {
    const vscodeLang = vscode.env.language;
    return vscodeLang.startsWith('vi') ? 'vi' : 'en';
}

function escapeHtml(text: string): string {
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function buildGuideHtml(guide: EditorGuide, lang: Lang): string {
    const title = lang === 'vi'
        ? `Hướng dẫn cài đặt Kiwi cho ${guide.name}`
        : `Kiwi Setup Guide for ${guide.name}`;

    const stepsTitle = lang === 'vi' ? 'Các bước' : 'Steps';
    const configTitle = lang === 'vi' ? 'Cấu hình' : 'Configuration';
    const requireTitle = lang === 'vi' ? 'Yêu cầu' : 'Requirements';
    const requireText = lang === 'vi'
        ? 'Python 3.9+ với <code>pygls</code> và <code>lsprotocol</code> đã cài'
        : 'Python 3.9+ with <code>pygls</code> and <code>lsprotocol</code> installed';

    const steps = guide.steps[lang];
    const stepsHtml = steps.map((s, i) => `<li>${formatStep(s)}</li>`).join('\n');

    return `<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: var(--vscode-font-family); padding: 20px; color: var(--vscode-foreground); background: var(--vscode-editor-background); max-width: 800px; }
        h1 { font-size: 1.4em; margin-bottom: 4px; }
        h2 { font-size: 1.1em; margin-top: 20px; color: var(--vscode-textLink-foreground); }
        pre { background: var(--vscode-textCodeBlock-background); padding: 14px; border-radius: 6px; overflow-x: auto; font-size: 0.88em; line-height: 1.5; }
        code { background: var(--vscode-textCodeBlock-background); padding: 2px 5px; border-radius: 3px; font-size: 0.9em; }
        ol { padding-left: 20px; line-height: 1.8; }
        li { margin-bottom: 6px; }
        .badge { display: inline-block; background: var(--vscode-badge-background); color: var(--vscode-badge-foreground); padding: 2px 8px; border-radius: 10px; font-size: 0.8em; margin-left: 8px; }
        .req { background: var(--vscode-editorWidget-background); border: 1px solid var(--vscode-editorWidget-border); border-radius: 6px; padding: 12px; margin: 12px 0; }
    </style>
</head>
<body>
    <h1>${escapeHtml(title)} <span class="badge">LSP stdio</span></h1>

    <div class="req">
        <strong>${requireTitle}:</strong> ${requireText}
    </div>

    <h2>${configTitle}</h2>
    <pre>${escapeHtml(guide.config)}</pre>

    <h2>${stepsTitle}</h2>
    <ol>${stepsHtml}</ol>
</body>
</html>`;
}

function formatStep(step: string): string {
    return step.replace(/`([^`]+)`/g, '<code>$1</code>');
}
