#!/usr/bin/env pwsh
# Kiwi Learn wrapper for PowerShell
# Usage: kiwilearn <file-path> [--severity CRITICAL]

$ErrorActionPreference = "Stop"

# Get Kiwi directory
$KIWI_DIR = Split-Path -Parent $PSScriptRoot

# Check if Python is available
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python not found. Please install Python 3.11+"
    exit 1
}

# Check if file argument provided
if ($args.Count -eq 0) {
    Write-Host "Usage: kiwilearn <file-path> [--severity CRITICAL|HIGH|ALL]"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  kiwilearn themes\sfvn\functions.php"
    Write-Host "  kiwilearn src\components\UserProfile.tsx --severity CRITICAL"
    exit 1
}

# Run scanner as module with --learn flag
$originalLocation = Get-Location
try {
    Set-Location $KIWI_DIR
    $args_list = @("-m", "scanner.cli", "--theme") + $args + @("--learn")
    & python @args_list
} finally {
    Set-Location $originalLocation
}