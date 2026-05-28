import * as vscode from 'vscode';

export interface KiwiSettings {
    severity: string;
    scanOnOpen: boolean;
    scanOnSave: boolean;
    scanOnChange: boolean;
    platform: string;
    pythonPath: string;
    serverPath: string;
}

export function getSettings(): KiwiSettings {
    const config = vscode.workspace.getConfiguration('kiwi');
    return {
        severity: config.get('severity', 'ALL'),
        scanOnOpen: config.get('scanOnOpen', true),
        scanOnSave: config.get('scanOnSave', true),
        scanOnChange: config.get('scanOnChange', false),
        platform: config.get('platform', 'wp'),
        pythonPath: config.get('pythonPath', ''),
        serverPath: config.get('serverPath', ''),
    };
}