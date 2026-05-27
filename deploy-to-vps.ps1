#!/usr/bin/env pwsh
# Deploy Kiwi to VPS for standalone CLI usage

param(
    [switch]$DryRun,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

# VPS config
$VPS_HOST = "103.90.227.103"
$VPS_PORT = "2222"
$VPS_USER = "root"
$VPS_SSH_KEY = "C:/Users/Windows/.ssh/id_rsa"
$VPS_KIWI_PATH = "/opt/kiwi"
$KIWI_LOCAL = ".claude/kiwi"

Write-Host "=== Kiwi VPS Deployment ===" -ForegroundColor Cyan
Write-Host "Source: $KIWI_LOCAL"
Write-Host "Target: ${VPS_USER}@${VPS_HOST}:${VPS_KIWI_PATH}"
Write-Host ""

# Test SSH
Write-Host "[1/5] Testing SSH connection..." -ForegroundColor Yellow
$sshTest = ssh -i $VPS_SSH_KEY -p $VPS_PORT -o ConnectTimeout=10 "${VPS_USER}@${VPS_HOST}" "echo 'SSH OK'"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: SSH connection failed" -ForegroundColor Red
    exit 1
}
Write-Host "✓ SSH connection OK" -ForegroundColor Green
Write-Host ""

# Create directory
Write-Host "[2/5] Creating remote directory..." -ForegroundColor Yellow
ssh -i $VPS_SSH_KEY -p $VPS_PORT "${VPS_USER}@${VPS_HOST}" "mkdir -p $VPS_KIWI_PATH"
Write-Host "✓ Directory created: $VPS_KIWI_PATH" -ForegroundColor Green
Write-Host ""

# Rsync
Write-Host "[3/5] Syncing files to VPS..." -ForegroundColor Yellow
$rsyncArgs = @(
    "-avz"
    "--delete"
    "--exclude=__pycache__"
    "--exclude=*.pyc"
    "--exclude=*.pyo"
    "--exclude=.pytest_cache"
    "--exclude=tests/"
    "--exclude=test_*.py"
    "--exclude=.git"
    "--exclude=.vscode"
    "--exclude=memory/confidence.db"
    "-e"
    "ssh -i $VPS_SSH_KEY -p $VPS_PORT"
    "$KIWI_LOCAL/"
    "${VPS_USER}@${VPS_HOST}:${VPS_KIWI_PATH}/"
)

if ($DryRun) {
    Write-Host "DRY RUN - would execute rsync" -ForegroundColor Magenta
} else {
    & rsync @rsyncArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Rsync failed" -ForegroundColor Red
        exit 1
    }
    Write-Host "✓ Files synced" -ForegroundColor Green
}
Write-Host ""

if ($SkipInstall) {
    Write-Host "Skipping installation" -ForegroundColor Yellow
    exit 0
}

# Install
Write-Host "[4/5] Installing Python dependencies..." -ForegroundColor Yellow
if ($DryRun) {
    Write-Host "DRY RUN - would install on VPS" -ForegroundColor Magenta
} else {
    ssh -i $VPS_SSH_KEY -p $VPS_PORT "${VPS_USER}@${VPS_HOST}" "cd $VPS_KIWI_PATH; python3 -m pip install --upgrade pip; python3 -m pip install -e .; echo 'Installation complete'"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Installation failed" -ForegroundColor Red
        exit 1
    }
    Write-Host "✓ Dependencies installed" -ForegroundColor Green
}
Write-Host ""

# Verify
Write-Host "[5/5] Verifying installation..." -ForegroundColor Yellow
if ($DryRun) {
    Write-Host "DRY RUN - would verify" -ForegroundColor Magenta
} else {
    ssh -i $VPS_SSH_KEY -p $VPS_PORT "${VPS_USER}@${VPS_HOST}" "cd $VPS_KIWI_PATH; python3 -c 'from scanner.cli import main; print(\"Scanner OK\")'; python3 -c 'from agent.cli import main; print(\"Agent OK\")'"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARNING: Verification had issues" -ForegroundColor Yellow
    } else {
        Write-Host "✓ Installation verified" -ForegroundColor Green
    }
}
Write-Host ""

Write-Host "=== Deployment Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Usage on VPS:" -ForegroundColor White
Write-Host "  ssh -i $VPS_SSH_KEY -p $VPS_PORT ${VPS_USER}@${VPS_HOST}" -ForegroundColor Gray
Write-Host "  cd $VPS_KIWI_PATH" -ForegroundColor Gray
Write-Host '  python3 -m scanner.cli --theme /var/www/wp.wezone.vn/wp-content/themes/sfvn' -ForegroundColor Gray
Write-Host '  python3 -m agent.cli /var/www/wp.wezone.vn --lite --apply' -ForegroundColor Gray
