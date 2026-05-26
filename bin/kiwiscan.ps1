#!/usr/bin/env pwsh
# Kiwi Scan wrapper for PowerShell
# Usage: kiwiscan <path> [--severity CRITICAL] [--learn]

$ErrorActionPreference = "Stop"

# Get Kiwi directory
$KIWI_DIR = Split-Path -Parent $PSScriptRoot
$SCANNER_CLI = Join-Path $KIWI_DIR "scanner\cli.py"

# Check if Python is available
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python not found. Please install Python 3.11+"
    exit 1
}

# Pass all arguments to scanner CLI
$args_list = @("--theme") + $args
python $SCANNER_CLI @args_list