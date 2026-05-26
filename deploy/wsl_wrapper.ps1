# WSL wrapper for deployment commands
# Usage: powershell -File wsl_wrapper.ps1 "rsync ..." or "ssh ..."

param(
    [Parameter(Mandatory=$true)]
    [string]$Command
)

# Convert Windows paths to WSL paths
$Command = $Command -replace 'C:/', '/mnt/c/' -replace 'D:/', '/mnt/d/' -replace '\\', '/'

# Execute via WSL
wsl $Command

# Exit with same code as WSL command
exit $LASTEXITCODE