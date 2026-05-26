#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Quick deploy theme/demo to VPS
.DESCRIPTION
    Wrapper script for Kiwi deploy - deploy theme or demo HTML to staging/production
.EXAMPLE
    .\kiwi-deploy-theme.ps1 themes/sfvn/demos/demo2
    .\kiwi-deploy-theme.ps1 themes/sfvn/demos/demo2 -Target production
    .\kiwi-deploy-theme.ps1 themes/sfvn -Type wp_theme
#>

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Path,

    [Parameter(Position=1)]
    [ValidateSet('staging', 'production')]
    [string]$Target = 'staging',

    [Parameter()]
    [ValidateSet('demo_html', 'wp_theme', 'wp_plugin', 'nextjs')]
    [string]$Type = 'demo_html',

    [Parameter()]
    [ValidateSet('verify', 'execute')]
    [string]$Mode = 'execute',

    [Parameter()]
    [string]$RemotePath = ''
)

$env:PYTHONUTF8 = 1
Set-Location (Join-Path $PSScriptRoot '..')

$args = @(
    '-m', 'deploy.cli',
    '--path', $Path,
    '--type', $Type,
    '--target', $Target,
    '--mode', $Mode
)

if ($RemotePath) {
    $args += '--remote-path', $RemotePath
}

Write-Host "Deploying $Path to $Target..." -ForegroundColor Cyan
python @args