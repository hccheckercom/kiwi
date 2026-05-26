# Kiwi Backup Integration

Tích hợp S3 backup vào Kiwi để có thể chạy `kiwi-backup` từ bất kỳ đâu trong dự án.

## Cài đặt

### Option 1: PowerShell Profile (Khuyến nghị)

Thêm vào PowerShell profile (`$PROFILE`):

```powershell
# Import Kiwi backup function
. "D:\projects\wezone\.claude\kiwi\bin\kiwi-profile.ps1"
```

Sau đó reload profile:
```powershell
. $PROFILE
```

### Option 2: PATH Environment Variable

Thêm `D:\projects\wezone\.claude\kiwi\bin` vào PATH:

```powershell
$env:PATH += ";D:\projects\wezone\.claude\kiwi\bin"
```

Sau đó chạy:
```powershell
kiwi-backup.bat
```

### Option 3: Alias tạm thời

```powershell
Set-Alias kiwi-backup "D:\projects\wezone\.claude\kiwi\bin\kiwi-backup.bat"
```

## Sử dụng

Từ bất kỳ đâu trong dự án:

```powershell
cd D:\projects\wezone\themes\sfvn
kiwi-backup
```

Hoặc:

```powershell
cd D:\projects\wezone\wezone-plugins\ai-chat
kiwi-backup
```

Script tự động tìm project root bằng cách tìm `.claude/kiwi/` và backup toàn bộ dự án.

## Cấu trúc

```
.claude/kiwi/
├── backup/
│   ├── __init__.py      # Module entry
│   ├── s3.py            # S3 backup logic (auto-detect project root)
│   └── cli.py           # CLI wrapper
└── bin/
    ├── kiwi-backup.py   # Python entry point
    ├── kiwi-backup.bat  # Windows batch wrapper
    └── kiwi-profile.ps1 # PowerShell profile integration
```

## Log

Backup log: `D:\projects\wezone\backup_s3.log`

## S3 Config

- Endpoint: `https://s3.vn-hcm-1.vietnix.cloud`
- Bucket: `wezone01`
- Prefix: `backups/YYYY-MM-DD/`

Credentials đã được hardcode trong `backup/s3.py` (giống `backup_s3.py` gốc).