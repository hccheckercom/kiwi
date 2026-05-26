#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Proactive Coverage Scanner — Scan for coverage gaps and suggest lessons.

.DESCRIPTION
    Scans PHP/JS/TS files to detect code patterns not covered by existing lessons.
    Reports coverage % and suggests lessons for gaps.

.PARAMETER Path
    File or folder to scan

.PARAMETER MinCoverage
    Minimum coverage threshold (default: 80)

.PARAMETER Platform
    Platform: wp or nextjs (default: wp)

.PARAMETER ShowCovered
    Show covered patterns (default: only gaps)

.EXAMPLE
    kiwicover D:\projects\wezone\wezone-plugins\packages\wezone-zalo

.EXAMPLE
    kiwicover path/to/plugin --min-coverage 80 --platform wp
#>

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Path,

    [Parameter(Mandatory=$false)]
    [int]$MinCoverage = 80,

    [Parameter(Mandatory=$false)]
    [ValidateSet('wp', 'nextjs')]
    [string]$Platform = 'wp',

    [Parameter(Mandatory=$false)]
    [switch]$ShowCovered
)

# Set UTF-8 encoding
$env:PYTHONUTF8 = 1

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$KiwiRoot = Split-Path -Parent $ScriptDir

# Build arguments
$args = @($Path, "--platform", $Platform, "--min-coverage", $MinCoverage)

if ($ShowCovered) {
    $args += "--show-covered"
}

# Run Python script
Push-Location $KiwiRoot
try {
    python bin/kiwicover.py @args
} finally {
    Pop-Location
}
