# Kiwi Git - Commit and Push Integration

Tích hợp git commit + push vào Kiwi để có thể chạy `kiwi-compu` từ bất kỳ đâu trong dự án.

## Cài đặt

Function `kiwi-compu` đã được thêm vào PowerShell profile tự động.

Nếu chưa có, thêm vào `$PROFILE`:

```powershell
# Kiwi Commit and Push Integration
function kiwi-compu {
    param(
        [string]$message,
        [switch]$auto
    )

    $current = Get-Location
    $found = $false

    # Find project root by looking for .git
    while ($current) {
        $gitPath = Join-Path $current ".git"
        if (Test-Path $gitPath) {
            $kiwiCompuScript = Join-Path $current ".claude\kiwi\bin\kiwi-compu.py"
            if (-not (Test-Path $kiwiCompuScript)) {
                Write-Error "kiwi-compu.py not found"
                return
            }
            $found = $true
            break
        }
        $parent = Split-Path $current -Parent
        if ($parent -eq $current) { break }
        $current = $parent
    }

    if (-not $found) {
        Write-Error "Not in git repository"
        return
    }

    $args = @()
    if ($message) {
        $args += @("-m", $message)
    }
    if ($auto) {
        $args += "--auto"
    }

    python $kiwiCompuScript @args
}
```

## Sử dụng

### Option 1: Với commit message tùy chỉnh

```powershell
kiwi-compu -message "feat: add new feature"
```

### Option 2: Auto-generate commit message

```powershell
kiwi-compu -auto
```

Auto-generate sẽ tạo message dạng:
```
chore: 5 modified, 2 added, 1 deleted

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

### Option 3: Chạy trực tiếp (không cần function)

```powershell
python D:\projects\wezone\.claude\kiwi\bin\kiwi-compu.py -m "commit message"
python D:\projects\wezone\.claude\kiwi\bin\kiwi-compu.py --auto
```

## Workflow

1. Tự động tìm git root bằng cách tìm `.git/`
2. Hiển thị git status
3. Stage all changes (`git add -A`)
4. Commit với message (custom hoặc auto-generated)
5. Push to remote
6. Hiển thị kết quả

## Cấu trúc

```
.claude/kiwi/
├── git/
│   ├── __init__.py      # Module entry
│   ├── git.py           # Git logic (commit + push)
│   └── cli.py           # CLI wrapper
└── bin/
    ├── kiwi-compu.py    # Python entry point
    └── kiwi-compu.bat   # Windows batch wrapper
```

## Lưu ý

- Function tự động thêm `Co-Authored-By: Claude Sonnet 4.6` vào commit message
- Chạy được từ bất kỳ subfolder nào trong git repo
- Không cần cd về root
