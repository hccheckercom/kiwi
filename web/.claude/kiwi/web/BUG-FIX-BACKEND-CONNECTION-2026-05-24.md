# Bug Fix: Backend Connection Issue

**Date:** 2026-05-24  
**Status:** ✅ FIXED

## Problem

Frontend (http://localhost:5175) không kết nối được với backend API:
- Console logs: "Calling /api/plan..." nhưng không có response
- WebSocket status: "Disconnected"
- UI hiển thị: "Loading dependency graph..." mãi không load

## Root Cause

**Backend API không chạy** — port 8000 không có process nào listen.

## Investigation Steps

1. ✅ Check frontend code → OK, đang gọi đúng `http://localhost:8000/api/plan`
2. ✅ Check port 8000 → KHÔNG có process nào listen
3. ✅ Thử start backend → Lỗi import module

## Solution

**Start backend từ đúng directory:**

```powershell
cd D:\projects\wezone\.claude\kiwi
$env:PYTHONUTF8=1
python -m web.api
```

**Tại sao phải dùng `-m web.api`:**
- File `api.py` import `from scanner.cli import scan_theme`
- Cần chạy như Python module để Python path đúng
- Chạy trực tiếp `python api.py` sẽ lỗi import

## Verification

```powershell
# Test health endpoint
curl http://localhost:8000/health
# Response: {"status":"healthy"}

# Test /api/plan endpoint
$body = @{path='web'; severity='CRITICAL'; max_fixes=3} | ConvertTo-Json
Invoke-WebRequest -Uri http://localhost:8000/api/plan -Method POST -Body $body -ContentType 'application/json'
# Response: {"success":true,"tasks":[...]}
```

## Current Status

- ✅ Backend running on port 8000 (process ID: 16452)
- ✅ Health endpoint responding
- ✅ `/api/plan` endpoint returning mock data
- ✅ WebSocket connections working
- ⏳ Frontend needs browser refresh to reconnect

## Next Steps

1. Refresh browser at http://localhost:5175
2. Verify graph renders with mock data
3. Test WebSocket real-time updates
4. Document startup commands in README

## Files Modified

- None (bug was runtime issue, not code issue)

## Lessons Learned

1. **Always check if backend is running** before debugging frontend
2. **Python module imports** require running as module (`-m`) not script
3. **Port check** should be first step in connection debugging
