# Kiwi Architecture: Core + Plugin Separation Plan

## Nguyên tắc

```
Kiwi Core (reasoning engine) + Plugins (knowledge packs) = Product
```

- Core: language-agnostic, 0 pre-built lessons, tự học từ bất kỳ codebase nào
- Plugin: pre-built lessons + drafter templates + quality rules cho specific stack
- Wezone Plugin: 726 lessons hiện tại, vẫn hoạt động y hệt, không mất gì

---

## Current State → Target State

### Hiện tại (monolithic)
```
.claude/kiwi/
├── lessons/          ← 726 lessons (PHP/WP specific)
├── scanner/          ← checkers hardcoded cho PHP/Tailwind
├── agent/reasoning/  ← language-agnostic ✓
├── templates/        ← WP theme templates
├── mcp_server.py     ← mixed: core tools + WP-specific logic
└── memory/           ← SQLite (language-agnostic ✓)
```

### Target (core + plugins)
```
kiwi/
├── core/                          ← NPM package: @kiwi-ai/core
│   ├── reasoning/                 ← R0-R27 (unchanged)
│   ├── scanner/
│   │   ├── engine.py              ← generic scan loop
│   │   ├── checker_base.py        ← abstract checker interface
│   │   └── reporters/             ← output formatters
│   ├── drafter/
│   │   ├── engine.py              ← generic code generation
│   │   ├── skeleton_base.py       ← abstract skeleton interface
│   │   └── quality_base.py        ← abstract quality checker
│   ├── router/
│   │   ├── decision.py            ← local vs Claude routing
│   │   └── budget.py              ← cost tracking
│   ├── mcp_server.py              ← core tools only
│   ├── cli.py                     ← kiwi init/status/dashboard
│   └── memory/                    ← SQLite (unchanged)
│
├── plugins/
│   ├── wezone-wp/                 ← Plugin: Wezone WordPress
│   │   ├── lessons/               ← 726 lessons (moved from current)
│   │   ├── checkers/              ← PHP/Tailwind/WP checkers
│   │   ├── drafters/              ← PHP template generators
│   │   ├── quality_rules.py       ← wz_*, BEM, WooCommerce checks
│   │   ├── style_extractor.py     ← Tailwind regex patterns
│   │   └── plugin.json            ← manifest
│   │
│   ├── generic/                   ← Plugin: Auto-learn (ships with core)
│   │   ├── auto_detector.py       ← detect language/framework
│   │   ├── pattern_miner.py       ← extract patterns from any code
│   │   ├── convention_learner.py  ← learn naming/structure conventions
│   │   └── plugin.json
│   │
│   ├── react/                     ← Plugin: React/Next.js (future)
│   │   ├── lessons/
│   │   ├── checkers/
│   │   └── plugin.json
│   │
│   └── python/                    ← Plugin: Python (future)
│       ├── lessons/
│       ├── checkers/
│       └── plugin.json
```

---

## Plugin Interface (Abstract)

```python
# core/plugin_base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class PluginManifest:
    name: str
    version: str
    languages: list[str]       # ["php", "js", "css"]
    frameworks: list[str]      # ["wordpress", "tailwind"]
    lessons_count: int
    checkers: list[str]
    drafters: list[str]


class KiwiPlugin(ABC):
    """Base class for all Kiwi plugins."""

    @abstractmethod
    def get_manifest(self) -> PluginManifest:
        """Return plugin metadata."""
        ...

    @abstractmethod
    def get_checkers(self) -> list:
        """Return list of checker instances."""
        ...

    @abstractmethod
    def get_drafters(self) -> list:
        """Return list of drafter instances."""
        ...

    @abstractmethod
    def get_quality_rules(self) -> list:
        """Return quality check rules for code generation."""
        ...

    @abstractmethod
    def extract_styles(self, content: str) -> dict:
        """Extract style patterns from code."""
        ...

    @abstractmethod
    def extract_bindings(self, content: str) -> list:
        """Extract API bindings/function calls from code."""
        ...

    def get_lessons_path(self) -> str | None:
        """Return path to pre-built lessons. None = auto-learn only."""
        return None
```

---

## Wezone Plugin (preserves everything)

```python
# plugins/wezone-wp/plugin.py

from kiwi.core.plugin_base import KiwiPlugin, PluginManifest


class WezonWPPlugin(KiwiPlugin):
    """Wezone WordPress plugin — 726 pre-built lessons."""

    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="wezone-wp",
            version="3.0.0",
            languages=["php", "js", "css"],
            frameworks=["wordpress", "tailwind", "wezone-commer"],
            lessons_count=726,
            checkers=["php_security", "tailwind_responsive", "wz_api", "dark_mode", "accessibility"],
            drafters=["php_template", "tailwind_component"],
        )

    def get_quality_rules(self) -> list:
        return [
            {"pattern": r"wc_get_product", "message": "Use wz_get_product instead", "severity": "CRITICAL"},
            {"pattern": r"WC\(\)", "message": "Use wz_* functions instead", "severity": "CRITICAL"},
            {"pattern": r"\$product->", "message": "Use $product['key'] accessor", "severity": "CRITICAL"},
            {"pattern": r"__\w+--\w+", "message": "No BEM classes — use Tailwind", "severity": "CRITICAL"},
            {"check": "wezone_is_active_guard", "message": "Missing wezone_is_active() guard", "severity": "CRITICAL"},
        ]

    def extract_styles(self, content: str) -> dict:
        # Current learner._extract_styles() logic — unchanged
        ...

    def extract_bindings(self, content: str) -> list:
        # Current learner._extract_bindings() logic — unchanged
        ...

    def get_lessons_path(self) -> str:
        return str(Path(__file__).parent / "lessons")
```

---

## Generic Plugin (auto-learn for any codebase)

```python
# plugins/generic/plugin.py

class GenericPlugin(KiwiPlugin):
    """Auto-learn plugin — works with any language/framework."""

    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="generic",
            version="1.0.0",
            languages=["*"],
            frameworks=["*"],
            lessons_count=0,  # starts empty, learns over time
            checkers=["naming_consistency", "import_patterns", "error_handling"],
            drafters=["generic_skeleton"],
        )

    def get_quality_rules(self) -> list:
        # No pre-built rules — learns from codebase
        return self._get_learned_rules()

    def extract_styles(self, content: str) -> dict:
        # Generic: detect indentation, naming convention, import style
        return self._auto_detect_conventions(content)

    def extract_bindings(self, content: str) -> list:
        # Generic: detect function calls, imports, exports
        return self._auto_detect_bindings(content)

    def _get_learned_rules(self) -> list:
        """Rules learned from user's codebase over time."""
        # Query memory DB for patterns with high confidence
        ...

    def _auto_detect_conventions(self, content: str) -> dict:
        """Detect code conventions from content."""
        conventions = {}
        # Indentation: tabs vs spaces, width
        # Naming: camelCase vs snake_case vs PascalCase
        # Imports: relative vs absolute, grouped vs ungrouped
        # String quotes: single vs double
        ...
        return conventions
```

---

## Plugin Loading (core/plugin_loader.py)

```python
def load_plugins(project_path: str) -> list[KiwiPlugin]:
    """Auto-detect and load appropriate plugins for project."""

    # 1. Check .kiwi/config.json for explicit plugin
    config = load_config(project_path)
    if config.get('plugin'):
        return [load_plugin_by_name(config['plugin'])]

    # 2. Auto-detect from codebase
    detected = detect_project_type(project_path)

    plugins = []

    # Always include generic (auto-learn)
    plugins.append(GenericPlugin())

    # Add specific plugin if detected
    if detected.framework == 'wordpress' and detected.has_wezone:
        plugins.append(WezonWPPlugin())
    elif detected.framework == 'react' or detected.framework == 'nextjs':
        plugins.append(ReactPlugin())  # future
    elif detected.language == 'python':
        plugins.append(PythonPlugin())  # future

    return plugins
```

---

## Migration Path (Wezone → Core + Plugin)

### Step 1: Extract interfaces (1 day)
- Create `plugin_base.py` with abstract classes
- Create `checker_base.py`, `drafter_base.py`, `quality_base.py`
- No behavior change — just define contracts

### Step 2: Wrap existing code as Wezone plugin (2 days)
- Move `lessons/` → `plugins/wezone-wp/lessons/`
- Wrap existing checkers in plugin interface
- Wrap existing drafter in plugin interface
- Wrap quality rules in plugin interface
- **Test: all 124 existing tests still pass**

### Step 3: Create generic plugin (2 days)
- Auto-detect language/framework
- Generic style/binding extraction
- Convention learning from codebase
- **Test: works on a non-WP project**

### Step 4: Plugin loader + routing (1 day)
- Load plugins based on project type
- Route scan/check/draft calls through plugin interface
- **Test: Wezone project loads wezone-wp plugin automatically**

### Step 5: Core packaging (1 day)
- Package core as standalone (npm + pip)
- Package wezone-wp as separate plugin
- `kiwi init` → detect → load correct plugin
- **Test: fresh install on non-WP project works**

**Total: ~7 days. Zero breaking changes for Wezone.**

---

## Wezone Workflow (After Separation)

**Không thay đổi gì cho Wezone:**

```
# Wezone project detected → wezone-wp plugin auto-loaded
# All 726 lessons active
# All existing MCP tools work
# All hooks work
# All tests pass

# Chỉ khác: code organized cleaner
# Core improvements benefit ALL plugins (including wezone-wp)
```

---

## Commercial Workflow (New User)

```
$ npm install -g @kiwi-ai/cli
$ cd my-react-project
$ kiwi init

  🥝 Kiwi AI
  Detected: TypeScript + React + Next.js
  Plugin: generic (auto-learn)
  
  Scanning... found 234 files
  Learned: 12 naming conventions, 8 import patterns, 5 component structures
  
  ✓ Ready! Kiwi will learn more from your Claude sessions.

# After 1 week of use:
$ kiwi status
  Plugin: generic
  Lessons learned: 47
  Trust score: 0.65 (medium)
  Local resolution: 45%
  Estimated savings: $32/month
```

---

## Revenue Split

| Component | License | Revenue |
|-----------|---------|---------|
| Core (reasoning engine) | Open source (MIT) | Free — drives adoption |
| Generic plugin | Open source (MIT) | Free — ships with core |
| Wezone-WP plugin | Private | Internal use only |
| React plugin | Freemium | Free basic, $9/mo advanced |
| Python plugin | Freemium | Free basic, $9/mo advanced |
| Team sync | SaaS | $49/user/mo |
| Enterprise | License | Custom pricing |

**Strategy:** Core open source → community builds plugins → Kiwi becomes platform → monetize team/enterprise features.

---

## Summary

| Aspect | Before (monolithic) | After (core + plugin) |
|--------|--------------------|-----------------------|
| Wezone | Works | Works identically (plugin auto-loaded) |
| New WP projects | Manual setup | Auto-detect, load wezone-wp |
| React projects | Not supported | Generic plugin auto-learns |
| Python projects | Not supported | Generic plugin auto-learns |
| Reasoning engine | Coupled to WP | Shared across all plugins |
| Improvements | Only benefit WP | Benefit ALL users |
| Commercial | Not possible | Ready for market |

---

## FAQ

### 1. User cài cái gì? Có mất Kiwi khi cài/dùng không?

**User cài:**
```
@kiwi-ai/cli (npm package) — ~5MB
```

**Bao gồm:**
- Kiwi Core (reasoning engine) — xử lý logic, routing, learning
- Generic Plugin (auto-learn) — tự học từ bất kỳ codebase nào
- `.kiwi/` folder trong project — knowledge base local (SQLite + learned patterns)

**User KHÔNG mất gì:**
- Kiwi chạy **100% local** — không upload code, không gửi data ra ngoài
- Uninstall = xóa `.kiwi/` folder + CLI → project trở lại trạng thái ban đầu
- Không modify source code của user — chỉ tạo folder riêng `.kiwi/`
- Không lock-in: bỏ Kiwi bất kỳ lúc nào, Claude Code vẫn hoạt động bình thường
- Knowledge base thuộc về user — có thể export, backup, hoặc share cho team

**So sánh:**
```
Trước cài Kiwi:  User → Claude (mọi request, full cost)
Sau cài Kiwi:    User → Kiwi (80% local, 0 cost) → Claude (20%, reduced cost)
Bỏ Kiwi:        User → Claude (quay lại như cũ, 0 side effects)
```

**Wezone-specific:** Wezone plugin (`wezone-wp`) là private, KHÔNG nằm trong package public. User thường chỉ nhận Generic Plugin. Wezone team dùng internal build có sẵn 726 lessons.

---

### 2. Kiwi có thông minh lên dần khi user dùng không?

**Có. Đây là core value proposition của Kiwi.**

**Learning curve:**
```
Ngày 1:    Kiwi biết 0 về project → handle 10% locally
Tuần 1:    Learned 30-50 patterns → handle 30% locally
Tuần 4:    Learned 100-200 patterns → handle 50% locally
Tháng 3:   Learned 300+ patterns → handle 80% locally
```

**Kiwi học từ đâu:**

| Nguồn | Cách học | Ví dụ |
|--------|----------|-------|
| Codebase scan | Phát hiện conventions, naming, structure | "Project này dùng camelCase, 2-space indent" |
| Claude sessions | Observe Claude's fixes → extract patterns | "Claude luôn thêm null check cho price → lesson mới" |
| User corrections | Khi user reject Kiwi output → learn why | "User không thích 1-col checkout → ghi nhớ 2-col" |
| Cross-project | Patterns từ project A áp dụng cho project B | "React hook pattern giống nhau across projects" |

**Cụ thể Kiwi thông minh lên thế nào:**

1. **Trust score tăng dần** — ban đầu Kiwi chỉ suggest (trust 0.3), sau vài tuần tự generate code (trust 0.8+)
2. **Local resolution rate tăng** — ngày càng ít cần gọi Claude → bill giảm
3. **Response time giảm** — patterns đã học → trả lời instant (0ms) thay vì đợi Claude (2-5s)
4. **Quality tăng** — học từ failures, không lặp lại sai lầm cũ
5. **Context assembly tốt hơn** — biết chính xác files nào cần đọc cho task nào

**Minh họa bằng số:**
```
Tháng 1:  User hỏi 100 câu → Kiwi handle 20, Claude handle 80 → bill $80
Tháng 3:  User hỏi 100 câu → Kiwi handle 60, Claude handle 40 → bill $40
Tháng 6:  User hỏi 100 câu → Kiwi handle 80, Claude handle 20 → bill $20
```

**Ceiling:** Kiwi plateau khi:
- Tất cả common tasks đã có trust > 0.9 (không còn gì để học)
- Novel tasks < 5% (codebase mature, ít feature mới)
- Lúc này value chuyển sang cross-project transfer — mang knowledge sang project mới

**Khác biệt với competitors:** Cursor, Copilot, Cody đều proxy MỌI request lên LLM. Kiwi là tool DUY NHẤT có learning loop — càng dùng càng rẻ, càng nhanh, càng chính xác. Đó là moat.

---

### 3. Kiwi source code (tài sản IP) lưu ở đâu?

**Khuyến nghị: GitHub Private Repos**

| Option | Ưu | Nhược |
|--------|-----|-------|
| GitHub Private Repos | CI/CD sẵn, npm publish tự động, backup, collaboration | $4/user/mo cho Team plan |
| VPS riêng | Full control, không phụ thuộc bên thứ 3 | Phải tự backup, tự setup CI, tự quản lý access |

**Lý do chọn GitHub:**
- npm publish từ GitHub Actions → tự động hóa release
- Private repos = source code không ai thấy
- CI/CD pipeline: build → compile → encrypt → publish
- Wezone plugin giữ private repo riêng → tách biệt hoàn toàn

**Cấu trúc repos (TẤT CẢ PRIVATE):**
```
github.com/kiwi-ai/core           (private) — reasoning engine source (Python)
github.com/kiwi-ai/cli            (private) — CLI + build pipeline
github.com/kiwi-ai/lessons-universal (private) — 400+ universal lessons source (.md)
github.com/wezone/kiwi-plugin-wp   (private) — 740 Wezone lessons, KHÔNG BAO GIỜ public
```

**Bảo vệ IP — CLOSED SOURCE:**
- Toàn bộ source code PRIVATE — không open source gì cả
- User nhận compiled binary (PyInstaller/Nuitka) — không đọc được source Python
- Lessons ship dạng encrypted SQLite DB — không phải plaintext .md
- License key check khi khởi động — không có key → không chạy được
- Wezone plugin KHÔNG BAO GIỜ ship — tài sản nội bộ

**User cài xong nhận:**
```
Global (npm install -g @kiwi-ai/cli):
├── kiwi.exe / kiwi              # Compiled binary (không đọc được source)
│   ├── Core engine (compiled)
│   ├── Generic Plugin (compiled)
│   └── lessons.kiwi             # 400+ lessons encrypted DB
│
Per-project (sau kiwi init):
├── .kiwi/
│   ├── config.json              # settings, tier, license key
│   ├── knowledge.db             # learned patterns, trust, usage
│   └── cache/                   # scan cache
```

**User KHÔNG nhận:**
- Source code Python (chỉ compiled binary)
- Lessons dạng .md (chỉ encrypted DB)
- Wezone plugin (private, không ship)
- Reasoning logic readable (compiled, obfuscated)

---

### 4. User sync patterns có chảy ngược về Kiwi repo không? Kiwi thông minh lên từ đâu?

**KHÔNG. Patterns của user KHÔNG tự động chảy về GitHub repo của Kiwi.**

Kiwi thông minh lên từ **2 nguồn độc lập:**

```
Nguồn 1: Owner improve engine (bạn code R7-R27)
  → push lên GitHub → npm publish → user update CLI
  = Engine mạnh hơn (reasoning, routing, learning algorithms)
  = TẤT CẢ users benefit

Nguồn 2: User learn patterns locally (tự động khi dùng)
  → .kiwi/ folder trên máy user → CHỈ user đó benefit
  = Knowledge riêng, không share ra ngoài
  = Team tier: sync giữa team members (qua Kiwi Cloud, KHÔNG phải GitHub)
```

**Tại sao patterns KHÔNG chảy ngược:**
- Privacy: user không muốn share code patterns ra ngoài
- Legal: patterns có thể chứa business logic nhạy cảm
- Trust: user phải tin rằng data của họ an toàn

**Nếu muốn Kiwi "thông minh từ community" (optional, opt-in):**

| Cách | Mechanism | Privacy |
|------|-----------|---------|
| Opt-in telemetry | User đồng ý gửi anonymized patterns → owner curate → thêm vào Generic Plugin | User chọn share |
| Community plugins | User tự publish plugin (như npm package) → người khác cài | User chủ động |
| Feedback loop | User report false positives → owner improve detection | Chỉ metadata, không code |

**Flow tổng thể:**
```
┌─────────────────────────────────────────────────────────┐
│  Owner (bạn)                                             │
│  ├── Code R7-R27 → GitHub → npm publish                 │
│  ├── Curate community feedback → improve Generic Plugin  │
│  └── Maintain Wezone Plugin (private, internal only)     │
├─────────────────────────────────────────────────────────┤
│  User A (solo dev)                                       │
│  ├── npm install @kiwi-ai/cli                           │
│  ├── Kiwi learns locally → .kiwi/ (KHÔNG share)         │
│  └── Update CLI khi có version mới → engine mạnh hơn    │
├─────────────────────────────────────────────────────────┤
│  User B (team, $49/user/mo)                              │
│  ├── npm install @kiwi-ai/cli                           │
│  ├── Kiwi learns locally → .kiwi/                       │
│  ├── Sync patterns giữa team (Kiwi Cloud, encrypted)    │
│  └── Team knowledge grows faster (5 devs learn 5x)      │
├─────────────────────────────────────────────────────────┤
│  Community (opt-in)                                      │
│  ├── User chọn share anonymized patterns                 │
│  ├── Owner curate → thêm vào Generic Plugin              │
│  └── ALL users benefit khi update CLI                    │
└─────────────────────────────────────────────────────────┘
```

**Tóm lại:**
- GitHub repo = source code (engine + plugins) — bạn control
- User machine = knowledge base (.kiwi/) — user control
- Kiwi Cloud = team sync (encrypted patterns) — chỉ Team tier
- Community → owner curate → Generic Plugin — opt-in, anonymized

---

### 5. Cụ thể Kiwi thông minh lên bằng cách nào khi user dùng?

Kiwi không có AI model riêng. Nó thông minh bằng cách **ghi nhớ patterns** rồi tái sử dụng — giống junior dev ngồi cạnh senior, mỗi ngày ghi lại senior fix gì, dần dần tự làm được.

**3 cơ chế cụ thể:**

#### Cơ chế 1: Observe → Extract → Store (sau mỗi Claude session)

```
User hỏi Claude: "Fix bug null price trong checkout.php"
Claude sửa: $product->price → $product['price'] ?? 0

Kiwi observe (chạy ngầm):
  - Pattern detected: "arrow accessor → bracket accessor + null coalesce"
  - Context: file checkout, variable $product, field price
  - Store vào .kiwi/knowledge.db: {pattern, context, fix, confidence: 0.5}

Lần sau user mở cart.php (cũng có $product->price):
  → Kiwi match pattern → warn: "Same bug as checkout.php — fix: dùng bracket accessor"
  → Hoặc tự fix nếu trust đủ cao
  → KHÔNG cần gọi Claude → 0 cost
```

**Kiwi observe gì từ Claude session:**
- Files Claude đọc trước khi code (→ learn: task X cần đọc files nào)
- Code Claude viết (→ learn: patterns, style, conventions)
- Code Claude sửa (→ learn: bug patterns, anti-patterns)
- Câu hỏi Claude hỏi user (→ learn: task X cần clarify gì)
- Lỗi Claude gặp rồi recover (→ learn: error → recovery strategy)

#### Cơ chế 2: Trust Score tăng dần (feedback loop)

```
Lần 1:  Kiwi suggest fix cho pattern A → trust 0.3
         → Chỉ hiện gợi ý text, Claude vẫn code
         
Lần 3:  Cùng pattern A, Kiwi đúng 3/3 → trust 0.6
         → Kiwi generate skeleton code, Claude review + hoàn thiện
         
Lần 7:  Trust 0.8 → Kiwi generate draft code gần hoàn chỉnh
         → Claude chỉ approve hoặc sửa nhỏ
         
Lần 12: Trust 0.92 → Kiwi output code final
         → Claude chỉ nói "ok" → apply ngay
```

**Trust tăng khi:** Kiwi output được Claude approve (không sửa)
**Trust giảm khi:** Claude reject hoặc sửa nhiều
**Trust decay:** Nếu lâu không gặp pattern → trust giảm dần (tránh stale knowledge)

#### Cơ chế 3: Convention Learning (scan codebase lần đầu + ongoing)

```
Kiwi scan 100 files trong project lần đầu:
  - 95/100 files dùng camelCase → lesson: "naming = camelCase" (confidence 0.95)
  - 90/100 files import từ @/utils → lesson: "import = absolute @/" (confidence 0.90)
  - 80/100 files có try/catch → lesson: "error handling = required" (confidence 0.80)
  - 70/100 files dùng 2-space indent → lesson: "indent = 2 spaces" (confidence 0.70)

Khi user tạo file mới:
  → Kiwi inject conventions vào context
  → Code sinh ra đúng style từ đầu
  → Không cần Claude "đọc lại" conventions mỗi lần
```

**Ongoing learning:** Mỗi file mới được tạo → Kiwi update conventions. Nếu team đổi style (ví dụ chuyển từ 2-space sang 4-space) → Kiwi detect shift → update lesson.

#### Timeline thực tế:

```
Ngày 1:   kiwi init → scan codebase → 30 conventions learned
           Trust: 0 (chưa observe Claude session nào)
           Local handling: 10% (chỉ convention checks)

Tuần 1:   5 Claude sessions observed → 50 patterns extracted
           Trust trung bình: 0.4
           Local handling: 25% (conventions + simple patterns)

Tuần 4:   20 sessions → 150 patterns, trust trung bình: 0.65
           Local handling: 50% (boilerplate, known bugs, style)

Tháng 3:  60 sessions → 300+ patterns, trust trung bình: 0.8
           Local handling: 75% (hầu hết routine tasks)

Tháng 6:  100+ sessions → 500+ patterns, trust trung bình: 0.85
           Local handling: 80% (chỉ novel tasks mới cần Claude)
```

**Điểm mấu chốt:** Kiwi KHÔNG dùng AI để "suy nghĩ" — nó dùng **pattern matching + trust scoring**. Nhanh (< 5ms), chính xác (vì chỉ output khi trust cao), và 0 cost (chạy local, không gọi API).

---

### FAQ 5a. Kiwi cần bao nhiêu lessons để "hoàn hảo"?

**Hiện tại: 740 lessons — đã mạnh hơn mọi tool WP hiện có.**

| Tool | Số rules | Ngôn ngữ |
|------|----------|----------|
| ESLint | ~300 | JS/TS |
| PHPStan | ~200 | PHP |
| SonarQube PHP | ~500 | PHP |
| WordPress PHPCS | ~200 | PHP/WP |
| **Kiwi** | **740** | **PHP/WP/CSS/JS** |

**Target theo mục tiêu:**

| Target | Lessons cần | Status | Nhóm |
|--------|-------------|--------|------|
| WP devs VN ($50K/year) | 400-500 universal | ✓ ĐỦ | A (ship ngay) |
| Full-stack WP (theme + plugin + API) | 800-1,000 | Gần đủ (740) | B (thêm dần) |
| Multi-language (JS + Python + Go) | 1,500-2,000 | Cần thêm | D-E (tương lai) |
| Enterprise (compliance + security) | 2,000-3,000 | Xa | E (Year 2-3) |

**Kế hoạch nâng cấp lessons:**

```
Phase A (ship):     400-500 universal lessons (từ 740 hiện có) → ĐỦ cho $50K target
Phase B (6 tháng):  +200 lessons (JS/TS patterns, React hooks, Node.js) → 700 universal
Phase C (1 năm):    +300 lessons (Python, Go, Rust basics) → 1,000 universal
Phase D (2 năm):    +500 lessons (enterprise compliance, OWASP full) → 1,500 universal
Phase E (3 năm):    +500 lessons (industry-specific, framework-specific) → 2,000+
```

**Nguồn lessons mới:**
1. Bạn code thêm projects → phát hiện patterns mới → thêm lessons
2. User feedback (report false positives/negatives) → refine + thêm
3. Community contribute (nếu mở program sau này)
4. Auto-mine từ public repos (GitHub trending, security advisories)
5. Kiwi R20 (Autonomous Failure Learning) → tự tạo lessons từ failures

**Kết luận:** 740 lessons ĐÃ DƯ cho target $50K. Không cần chạy theo số lượng — cần đóng gói tốt (A1-A7) và marketing. Lessons sẽ tăng tự nhiên qua usage + feedback.

---

### FAQ 5b. Kiwi hoạt động offline? Update thế nào?

**100% offline.** Kiwi chạy hoàn toàn trên máy user — không gửi code hay query lên server nào.

```
Kiwi:   Binary local → scan, check, learn → tất cả trên máy user
Claude: Server Anthropic → user gửi prompt → API → response → tốn tiền
```

**Khi nào cần internet:**
- License check: 1 lần/7 ngày (offline grace: 30 ngày)
- `kiwi upgrade`: tải version mới
- Team tier sync (nếu dùng)

Ngoài ra → **0 data ra ngoài, 0 network calls.**

**Update — KHÔNG tự động:**
```bash
kiwi upgrade    # User chủ động chạy khi muốn
```

**Notification trong Dashboard (hiển thị mạnh):**
```
┌─────────────────────────────────────────────────────┐
│  🥝 Kiwi Dashboard                                   │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │ ⬆️  UPDATE AVAILABLE: v1.3.0                 │    │
│  │                                             │    │
│  │ New in v1.3.0:                              │    │
│  │ • +45 new lessons (security + performance)  │    │
│  │ • 2x faster scan engine                     │    │
│  │ • Cross-project transfer (Pro tier)         │    │
│  │                                             │    │
│  │ Run: kiwi upgrade                           │    │
│  │ [Update Now]  [Remind Later]  [Skip]        │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  💰 Savings: $10.08 this month                      │
│  📊 Local: 69%                                      │
│  ...                                                │
└─────────────────────────────────────────────────────┘
```

**Tại sao hiện mạnh trong Dashboard:**
1. User đã đang nhìn Kiwi → attention sẵn có
2. Hiện value mới ("+45 lessons") → muốn update ngay
3. Không intrusive (không popup random) — chỉ khi user mở dashboard
4. 1-click update → friction thấp

**Extension status bar (nhẹ hơn):**
```
🥝 Kiwi 1.2.0 (⬆️ 1.3.0 available)
```

---

### 6. User đo lường giá trị Kiwi bằng cách nào?

Kiwi tích hợp **dashboard metrics** — user thấy ROI rõ ràng mà không cần tự tính.

**5 metrics tự động track:**

#### a) Cost savings (đo trực tiếp bằng tiền)
```bash
$ kiwi dashboard

  💰 Cost Savings (tháng này):
  ├── Requests total: 142
  ├── Kiwi handled locally: 98 (0 cost)
  ├── Claude handled: 44
  ├── Tokens saved: 67,200
  └── Money saved: ~$10.08

  So với không có Kiwi: bạn đã tiết kiệm $10.08 tháng này.
```

#### b) Local resolution rate
```
  📊 Resolution Rate:
  ├── Local (Kiwi): 69%  ████████████████░░░░░
  └── Claude:       31%  ████████░░░░░░░░░░░░░
  
  Tuần trước: 55% local → Tuần này: 69% local (+14%)
```

#### c) Response time
```
  ⚡ Speed:
  ├── Kiwi average: 42ms
  ├── Claude average: 3,200ms
  └── Speedup: 76x faster cho local tasks
```

#### d) Learning progress
```
  🧠 Knowledge:
  ├── Patterns learned: 147
  ├── Conventions detected: 23
  ├── Trust score avg: 0.72
  └── New this week: +12 patterns
```

#### e) Before/After trend
```
  📈 Trend (4 weeks):
  ├── Week 1: 80 Claude calls → $16.00
  ├── Week 2: 62 Claude calls → $12.40
  ├── Week 3: 48 Claude calls → $9.60
  └── Week 4: 35 Claude calls → $7.00
  
  Trajectory: -56% cost in 4 weeks
```

**CLI commands:**
```bash
kiwi dashboard          # Full dashboard
kiwi status --savings   # Quick savings summary
kiwi status --trend     # Week-over-week trend
```

**Tất cả metrics track local** (trong `.kiwi/knowledge.db`), không gửi ra ngoài.

**Conversion trigger:** Khi Free user thấy "Kiwi saved you $12 this month" → trả $5-7/mo để unlock full learning = no-brainer ROI.

---

### 7. Pricing đề xuất (cập nhật)

Dựa trên phân tích: $19/mo barrier quá cao cho indie devs. $5-7/mo là sweet spot.

| Plan | Giá | Target | Savings | Features |
|------|-----|--------|---------|----------|
| Free | $0 | Mọi người | 30% | Context optimization only |
| Starter | $5/mo | Indie devs | 50-60% | Local intelligence, basic learning |
| Pro | $12/mo | Active devs | 70-80% | Full learning + cross-project transfer |
| Team | $29/user/mo | Agencies | 80-90% | Shared knowledge + admin dashboard |
| Enterprise | Custom | Large orgs | 90%+ | On-prem, SSO, audit, compliance |

**Tại sao $5-7 thay vì $19:**
- Barrier thấp → conversion rate cao hơn (8-12% vs 2-3%)
- User trả $20/mo Claude + $5 Kiwi = $25 → chấp nhận được
- Churn thấp hơn (giá rẻ, ít suy nghĩ cancel)
- Volume play: 10,000 users × $5 > 2,000 users × $19

**Revenue projection (revised):**
```
Year 1: 5,000 Starter + 1,000 Pro = $37K MRR ($444K ARR)
Year 2: 15,000 Starter + 5,000 Pro + 500 Team = $150K MRR ($1.8M ARR)
Year 3: Scale → $500K+ MRR
```

---

### 8. Freemium Gating — Cho dùng thử, giới hạn đủ để muốn upgrade

**Chiến lược:** Cho user dùng FREE mãi mãi (không giới hạn thời gian), nhưng giới hạn "độ thông minh" của Kiwi. User thấy value → muốn MORE → trả tiền.

#### Free tier (dùng mãi):
```
✓ Context optimization (inject đúng files → tiết kiệm 30% tokens)
✓ Convention scan (phát hiện style codebase)
✓ Dashboard (thấy metrics, savings — QUAN TRỌNG: user thấy số tiền tiết kiệm)
✓ Basic bug detection (CRITICAL violations only)

✗ Patterns learned: MAX 30 (sau đó dừng học)
✗ Trust score cap: 0.6 (chỉ suggest, KHÔNG auto-generate code)
✗ Convention rules: MAX 5
✗ Cross-project transfer: KHÔNG
✗ Code generation: KHÔNG (chỉ text suggestions)
```

#### Hiệu ứng tâm lý (conversion trigger):
```bash
$ kiwi dashboard

  🥝 Kiwi Free — Learning Progress:
  ├── Patterns learned: 30/30 ⚠️ LIMIT REACHED
  ├── Trust score: 0.60 (capped — upgrade to unlock full autonomy)
  ├── Conventions: 5/5 ⚠️ LIMIT REACHED
  │
  ├── 💰 Savings this month: $4.20
  ├── 💰 Estimated savings if Starter: $10.50/mo
  └── 💰 Estimated savings if Pro: $16.80/mo
  
  ⚡ 12 patterns detected but NOT learned (limit reached)
  ⚡ Kiwi could auto-fix 8 issues this week — but trust cap prevents it
  
  → Upgrade: kiwi upgrade starter ($5/mo)
```

**User thấy:**
1. "Kiwi đang MUỐN học thêm nhưng bị giới hạn" → FOMO
2. "Nếu upgrade thì tiết kiệm gấp 3" → ROI rõ ràng
3. "8 issues Kiwi có thể tự fix nhưng không được phép" → frustration nhẹ → muốn unlock

#### Feature gating chi tiết:

| Feature | Free | Starter ($5) | Pro ($12) | Team ($29) |
|---------|------|-------------|-----------|------------|
| Context optimization | ✓ | ✓ | ✓ | ✓ |
| Dashboard + metrics | Basic | Full | Full + trends | Full + team view |
| Patterns learned | Max 30 | Max 200 | Unlimited | Unlimited + shared |
| Trust score cap | 0.6 | 0.8 | 1.0 | 1.0 |
| Convention rules | 5 | 20 | Unlimited | Unlimited |
| Auto-generate code | ✗ | Skeleton only | Full (draft + final) | Full |
| Cross-project | ✗ | ✗ | ✓ | ✓ |
| Bug auto-fix | ✗ | CRITICAL only | All severities | All + custom rules |
| Session learning | ✗ | Basic | Full (observe Claude) | Full + team sync |
| Export knowledge | ✗ | ✗ | ✓ | ✓ |

#### Tại sao cách này hiệu quả:

1. **Zero risk cho user** — cài Free, không mất gì, chỉ gain (30% savings ngay lập tức)
2. **Value visible trước khi trả tiền** — dashboard hiện số tiền tiết kiệm THẬT
3. **Frustration nhẹ, đúng chỗ** — "Kiwi biết cách fix nhưng bị cap" → muốn unlock
4. **Pattern limit 30** = đủ để thấy Kiwi hoạt động, nhưng thiếu để cover full workflow
5. **Trust cap 0.6** = Kiwi suggest nhưng không tự code → user thấy "nếu unlock thì Kiwi tự làm luôn"
6. **Không time-limit** — user không bị ép, tự quyết khi nào upgrade

#### Conversion funnel:

```
Install (free) → 100% users
  ↓ (1 tuần dùng, thấy dashboard)
Thấy value → 60% users nhận ra Kiwi hữu ích
  ↓ (hit pattern limit 30)
Hit limit → 40% users muốn more
  ↓ (dashboard hiện: "upgrade = save $10/mo thêm")
Upgrade Starter → 8-12% conversion
  ↓ (3 tháng dùng, muốn full autonomy)
Upgrade Pro → 30% of Starter users
```

**Estimated conversion:**
```
10,000 installs → 1,000 Starter ($5) + 300 Pro ($12) = $8,600 MRR
50,000 installs → 5,000 Starter + 1,500 Pro = $43,000 MRR
```

---

### 9. VS Code Extension — Dashboard & Beyond

**Tại sao Extension thay vì CLI:**
- Luôn visible — user thấy metrics mà không cần mở terminal
- Extensible — thêm features dần mà không cần user cài lại
- Distribution dễ — VS Code Marketplace, 1 click install
- Competitive — Copilot, Cody đều là extension → user quen UX này

#### Extension Roadmap:

**Phase 1: Dashboard Panel (Month 1)**
```
┌─────────────────────────────────┐
│ 🥝 Kiwi AI                      │
├─────────────────────────────────┤
│ Savings: $10.08 this month      │
│ Local: 69% ████████████░░░░░░░  │
│ Patterns: 147 learned           │
│ Trust: 0.72 avg                 │
├─────────────────────────────────┤
│ ⚠️ 12 patterns pending (limit)  │
│ → Upgrade to learn more         │
└─────────────────────────────────┘
```

**Phase 2: Inline Warnings (Month 2)**
```php
// User đang code, Kiwi hiện inline:
$product->price  // ⚠️ Kiwi: use $product['price'] (trust 0.85)
                 // 💡 Quick Fix: Apply Kiwi suggestion
```

**Phase 3: Code Actions (Month 3)**
- Light bulb menu: "Kiwi: Fix this pattern"
- "Kiwi: Generate skeleton for this function"
- "Kiwi: Show similar patterns in codebase"

**Phase 4: Trust Indicators (Month 4)**
```
// Status bar:
🥝 Kiwi: Ready | Trust 0.72 | 147 patterns | $10 saved

// File explorer decoration:
📄 checkout.php  [trust: 0.9 ✓]
📄 new-feature.php  [trust: 0.3 — needs Claude]
```

**Phase 5: Smart Features (Month 5-6)**
- Auto-suggest: Kiwi predict next task → pre-compute
- Team view: see team members' learning progress
- History: timeline of what Kiwi learned and when
- Settings UI: configure gating, trust thresholds, preferences

#### Extension Architecture:

```
kiwi-vscode/
├── src/
│   ├── extension.ts          # activation, register commands
│   ├── dashboard/            # webview panel (React)
│   ├── providers/
│   │   ├── diagnostics.ts    # inline warnings (squiggly lines)
│   │   ├── codeActions.ts    # light bulb quick fixes
│   │   ├── codeLens.ts       # trust indicators above functions
│   │   └── statusBar.ts      # bottom bar: savings, trust, status
│   ├── kiwi-client.ts        # communicate with Kiwi engine (localhost)
│   └── config.ts             # user settings
├── package.json              # VS Code extension manifest
└── README.md
```

**Communication:** Extension ↔ Kiwi Engine qua localhost HTTP/WebSocket. Engine chạy background process (started by `kiwi serve`).

#### Tại sao Extension là investment đúng:

1. **Moat mạnh hơn** — user quen UI → switching cost cao → churn thấp
2. **Upsell surface** — dashboard hiện "upgrade" button ngay trong IDE
3. **Data collection** — biết user dùng feature nào nhiều → prioritize development
4. **Viral** — team member thấy đồng nghiệp có Kiwi panel → hỏi "cái gì đó?" → install
5. **Platform play** — sau VS Code → JetBrains, Neovim, Zed (cùng engine, khác UI)

---

### 10. Real-time Comparison: Có Kiwi vs Không có Kiwi

**Vấn đề:** User cần THẤY rõ ràng Kiwi đang tiết kiệm bao nhiêu — không phải tin lời quảng cáo.

**Giải pháp:** Tích hợp cost tracker trực tiếp trong Extension, so sánh real-time.

#### Dashboard comparison view:

```
┌─────────────────────────────────────────────────────┐
│  🥝 Kiwi Savings — Real-time Comparison             │
├─────────────────────────────────────────────────────┤
│                                                     │
│  WITHOUT Kiwi (estimated baseline):                 │
│  ├── Requests would be: 100                         │
│  ├── Tokens would be: 450,000                       │
│  ├── Estimated cost: $13.50                         │
│  └── Avg response time: 3.2s                        │
│                                                     │
│  WITH Kiwi (actual):                                │
│  ├── Requests to Claude: 35                         │
│  ├── Tokens used: 157,500                           │
│  ├── Actual cost: $4.73                             │
│  ├── Kiwi handled locally: 65                       │
│  └── Avg response time: 0.8s (local: 42ms)         │
│                                                     │
│  ┌───────────────────────────────────────────┐      │
│  │ 💰 YOU SAVED: $8.77 (65%)                 │      │
│  │ ⚡ 4x FASTER average response             │      │
│  │ 📊 65 requests NEVER left your machine    │      │
│  └───────────────────────────────────────────┘      │
│                                                     │
│  Weekly trend:                                      │
│  W1: saved $4  ██░░░░░░░░                           │
│  W2: saved $7  ████░░░░░░                           │
│  W3: saved $9  █████░░░░░                           │
│  W4: saved $11 ██████░░░░  ← you are here          │
│                                                     │
└─────────────────────────────────────────────────────┘
```

#### Cách đo "WITHOUT Kiwi" (baseline estimation):

```python
# Mỗi request Kiwi handle locally → estimate bao nhiêu tokens NẾU gửi lên Claude
def estimate_baseline_cost(local_request):
    # Estimate context tokens Claude would need
    context_files = local_request.files_needed  # files Kiwi đã đọc
    context_tokens = sum(count_tokens(f) for f in context_files)
    
    # Estimate output tokens Claude would generate
    output_tokens = estimate_output_size(local_request.task_type)
    
    # Calculate cost at Claude pricing
    baseline_cost = (context_tokens * INPUT_PRICE) + (output_tokens * OUTPUT_PRICE)
    
    return {
        'tokens': context_tokens + output_tokens,
        'cost': baseline_cost,
        'latency_estimate': 2000 + (context_tokens / 1000) * 500  # ms
    }
```

#### Các tool/repo có thể tham khảo:

| Tool | Mô tả | Cách dùng |
|------|--------|-----------|
| **LiteLLM** (BerriAI/litellm) | Proxy layer, track cost/tokens/latency | Route Claude calls qua proxy → so sánh |
| **Helicone** (Helicone/helicone) | 1-line integration, dashboard đẹp | Đổi base URL → auto-track |
| **OpenMeter** (openmeterio/openmeter) | Usage metering cho SaaS | Track bất kỳ metric |
| **Langfuse** (langfuse/langfuse) | Open source LLM observability | Trace requests, cost breakdown |

#### Khuyến nghị: Tự build lightweight (KHÔNG dùng 3rd party)

**Lý do:**
- Privacy: không gửi usage data ra ngoài
- Đơn giản: Kiwi đã có SQLite, chỉ cần thêm 1 table
- Chính xác: Kiwi biết chính xác request nào handle local vs forward

**Schema:**
```sql
CREATE TABLE usage_tracking (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    request_type TEXT NOT NULL,        -- 'local' | 'claude'
    task_type TEXT,
    tokens_used INTEGER DEFAULT 0,     -- actual tokens (0 for local)
    tokens_estimated INTEGER,          -- estimated if sent to Claude
    cost_actual REAL DEFAULT 0,        -- actual cost (0 for local)
    cost_estimated REAL,               -- estimated cost without Kiwi
    latency_ms INTEGER,                -- actual response time
    latency_estimated_ms INTEGER       -- estimated Claude response time
);

-- Aggregation view
CREATE VIEW savings_summary AS
SELECT
    date(timestamp) as day,
    COUNT(*) as total_requests,
    SUM(CASE WHEN request_type = 'local' THEN 1 ELSE 0 END) as local_requests,
    SUM(cost_actual) as actual_cost,
    SUM(cost_estimated) as would_cost,
    SUM(cost_estimated) - SUM(cost_actual) as saved,
    AVG(latency_ms) as avg_latency,
    AVG(latency_estimated_ms) as avg_latency_without_kiwi
FROM usage_tracking
GROUP BY date(timestamp);
```

#### Extension hiện comparison thế nào:

```typescript
// kiwi-vscode/src/dashboard/SavingsPanel.ts

interface SavingsData {
  period: 'today' | 'week' | 'month';
  withKiwi: {
    requests: number;
    tokens: number;
    cost: number;
    avgLatency: number;
  };
  withoutKiwi: {
    requests: number;      // = withKiwi.requests + localRequests
    tokens: number;        // = withKiwi.tokens + estimatedTokens
    cost: number;          // = withKiwi.cost + estimatedCost
    avgLatency: number;    // = estimated Claude latency for all
  };
  savings: {
    money: number;         // withoutKiwi.cost - withKiwi.cost
    percent: number;       // savings / withoutKiwi.cost * 100
    speedup: number;       // withoutKiwi.avgLatency / withKiwi.avgLatency
    localRequests: number; // requests that never left machine
  };
}
```

#### Trust signal cho user:

Để user tin comparison là thật (không phải inflated):

1. **Transparent calculation** — user click vào bất kỳ số nào → thấy formula
2. **Conservative estimates** — estimate baseline THẤP hơn thực tế (under-promise)
3. **Verifiable** — user có thể tắt Kiwi 1 ngày → so sánh bill thật
4. **Open source tracker** — code tracking public, user audit được

```
User click "$8.77 saved":
  → Popup: "65 requests handled locally × avg 6,900 tokens each = 448,500 tokens
     At Claude pricing ($0.003/1K input + $0.015/1K output) = $8.77
     Calculation: conservative (assumes 70% input, 30% output ratio)"
```

**Đây là killer feature:** User không cần TIN Kiwi — họ THẤY bằng số. Mỗi ngày mở VS Code → dashboard hiện savings tăng dần → reinforcement loop → không muốn uninstall.