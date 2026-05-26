# Setup SSH key for VPS deployment
# This script adds your local SSH public key to VPS authorized_keys

$publicKeyPath = "C:\Users\Windows\.ssh\id_rsa.pub"
$vpsHost = "103.90.227.154"
$vpsUser = "root"

Write-Host "Reading local SSH public key..." -ForegroundColor Cyan
$publicKey = Get-Content $publicKeyPath -Raw

Write-Host "Connecting to VPS to add SSH key..." -ForegroundColor Cyan
Write-Host "You will be prompted for VPS password ONE TIME only." -ForegroundColor Yellow
Write-Host ""

# Create authorized_keys file with proper permissions
$sshCommand = @"
mkdir -p ~/.ssh
chmod 700 ~/.ssh
echo '$publicKey' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
echo 'SSH key added successfully'
"@

ssh $vpsUser@$vpsHost $sshCommand

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ SSH key setup complete!" -ForegroundColor Green
    Write-Host "Testing SSH key authentication..." -ForegroundColor Cyan

    ssh -o StrictHostKeyChecking=no -i C:/Users/Windows/.ssh/id_rsa $vpsUser@$vpsHost "echo 'SSH key works!'"

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "✅ SSH key authentication successful!" -ForegroundColor Green
        Write-Host "You can now deploy without password:" -ForegroundColor Cyan
        Write-Host "  python cli.py themes/sfvn/demos/demo1 demo_html --mode execute" -ForegroundColor White
    }
} else {
    Write-Host ""
    Write-Host "❌ Failed to add SSH key to VPS" -ForegroundColor Red
    Write-Host "Please check VPS password and try again" -ForegroundColor Yellow
}