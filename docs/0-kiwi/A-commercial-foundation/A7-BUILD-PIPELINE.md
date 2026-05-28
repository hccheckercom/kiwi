# A7 — Build Pipeline: Compile + Encrypt (2 days)

## Mục tiêu
Tạo pipeline: source Python → compiled binary + encrypted lessons DB. User nhận product, không nhận source.

---

## Tasks

### Day 1: Compile engine
| # | Task |
|---|------|
| 7.1 | Setup PyInstaller/Nuitka build config |
| 7.2 | Compile core + generic plugin → single binary (kiwi.exe / kiwi) |
| 7.3 | Test: binary chạy được trên Windows, macOS, Linux |
| 7.4 | Verify: không thể decompile ra readable Python |

### Day 2: Encrypt lessons + packaging
| # | Task |
|---|------|
| 7.5 | Script: compile 400+ lessons .md → encrypted SQLite DB (lessons.kiwi) |
| 7.6 | Encryption key tied to license system |
| 7.7 | Bundle binary + lessons.kiwi vào npm package |
| 7.8 | Test: `npm install -g @kiwi-ai/cli` → binary + DB installed correctly |
| 7.9 | Test: lessons.kiwi không đọc được bằng SQLite browser thông thường |

---

## Build Pipeline

```
Source (GitHub Private):
├── core/           (Python source)
├── plugins/generic/ (Python source)
└── lessons/        (400+ .md files)

    ↓ GitHub Actions CI/CD

Build steps:
1. Nuitka compile: Python → native binary
2. Lessons compile: .md → SQLite → encrypt with AES-256
3. Bundle: binary + lessons.kiwi → npm package
4. Sign: code signing (optional, chống tamper)
5. Publish: npm registry (@kiwi-ai/cli)

    ↓

User receives (npm install):
├── kiwi.exe        (compiled binary, ~30-50MB)
└── lessons.kiwi    (encrypted DB, ~5MB)
```

## Encryption Schema

```python
import sqlite3
from cryptography.fernet import Fernet

def compile_lessons(lessons_dir: str, output_path: str, license_salt: str):
    """Compile .md lessons → encrypted SQLite DB."""
    
    # 1. Parse all .md lessons
    lessons = parse_all_lessons(lessons_dir)
    
    # 2. Create SQLite DB in memory
    db = sqlite3.connect(':memory:')
    db.execute('''CREATE TABLE lessons (
        id TEXT PRIMARY KEY,
        category TEXT,
        severity TEXT,
        pattern TEXT,        -- regex pattern
        message TEXT,        -- violation message (generic, no internal details)
        scan_type TEXT,
        scope TEXT,
        platform TEXT
    )''')
    
    for lesson in lessons:
        db.execute('INSERT INTO lessons VALUES (?,?,?,?,?,?,?,?)', 
                   lesson.to_tuple())
    
    # 3. Export to bytes
    db_bytes = export_to_bytes(db)
    
    # 4. Encrypt with Fernet (AES-128-CBC)
    key = derive_key(license_salt)
    encrypted = Fernet(key).encrypt(db_bytes)
    
    # 5. Write to file
    with open(output_path, 'wb') as f:
        f.write(encrypted)
```

## License Check Flow

```
User runs: kiwi scan
  → Binary starts
  → Read .kiwi/config.json → get license_key
  → Derive decryption key from license_key
  → Decrypt lessons.kiwi → in-memory SQLite
  → Run scan with decrypted lessons
  → Output results to user
  → Lessons never written to disk in plaintext
```

## Anti-piracy (vừa đủ cho 69K/tháng)

| Measure | Implementation |
|---------|---------------|
| Machine fingerprint | Hash(MAC + hostname + OS) → tie to license |
| Periodic check | Ping license server 1x/7 ngày (offline grace: 30 ngày) |
| Encrypted DB | Lessons chỉ decrypt in-memory, never on disk |
| No export API | Scan results = generic messages, không expose raw patterns |
| Terms of Service | Legal protection: cấm redistribute, reverse engineer |

---

## Dependencies
- A1-A6 hoàn thành (có code để compile)

## Done khi
- `npm install -g @kiwi-ai/cli` cài binary thành công
- Binary chạy `kiwi scan` → decrypt lessons → output violations
- Không thể đọc lessons.kiwi bằng tool thông thường
- Không thể decompile binary ra readable source
- Build pipeline chạy tự động trên GitHub Actions