# Kiwi PowerShell Profile Integration
# Add this to your PowerShell profile to enable kiwi-backup command

function kiwi-backup {
    $kiwiBackupScript = Join-Path $PSScriptRoot ".claude\kiwi\bin\kiwi-backup.py"

    # Find project root by looking for .claude/kiwi
    $current = Get-Location
    $found = $false

    while ($current) {
        $kiwiPath = Join-Path $current ".claude\kiwi"
        if (Test-Path $kiwiPath) {
            $kiwiBackupScript = Join-Path $current ".claude\kiwi\bin\kiwi-backup.py"
            $found = $true
            break
        }
        $parent = Split-Path $current -Parent
        if ($parent -eq $current) { break }
        $current = $parent
    }

    if (-not $found) {
        Write-Error "Not in wezone project. Cannot find .claude/kiwi/"
        return
    }

    python $kiwiBackupScript
}

# Export function
Export-ModuleMember -Function kiwi-backup
