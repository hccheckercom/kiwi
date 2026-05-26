# Kiwi Agent — Architecture

## Kiến trúc tổng thể

```
┌─────────────────────────────────────────────────────────────────────┐
│                         KIWI AGENT SYSTEM                          │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    INTERFACE LAYER                             │  │
│  │                                                               │  │
│  │  ┌──────────┐  ┌──────────────┐  ┌─────────┐  ┌───────────┐  │  │
│  │  │ MCP      │  │ Claude Code  │  │ CLI     │  │ Post-Edit │  │  │
│  │  │ Server   │  │ Skills       │  │ Direct  │  │ Hook      │  │  │
│  │  │ (stdio)  │  │ (.md cmds)   │  │ Python  │  │ (auto)    │  │  │
│  │  └────┬─────┘  └──────┬───────┘  └────┬────┘  └─────┬─────┘  │  │
│  └───────┼───────────────┼────────────────┼─────────────┼────────┘  │
│          │               │                │             │           │
│  ┌───────▼───────────────▼────────────────▼─────────────▼────────┐  │
│  │                    AGENT LAYER (Phase 3)                       │  │
│  │                                                               │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │  Agent Loop: Observe → Think → Act → Verify → Learn    │  │  │
│  │  │  Modes: review | interactive | auto                     │  │  │
│  │  │  Brain: Claude API (anthropic SDK)                      │  │  │
│  │  └──────────────────────┬──────────────────────────────────┘  │  │
│  └─────────────────────────┼─────────────────────────────────────┘  │
│                            │                                        │
│  ┌─────────────────────────▼─────────────────────────────────────┐  │
│  │                    ENGINE LAYER                                │  │
│  │                                                               │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │  │
│  │  │ Scanner  │  │ Fixer    │  │ Query    │  │ Template     │  │  │
│  │  │ (v3)     │  │ (Phase2) │  │ Engine   │  │ Library      │  │  │
│  │  │          │  │          │  │          │  │              │  │  │
│  │  │ checkers │  │ replace  │  │ keyword  │  │ sections/    │  │  │
│  │  │ loader   │  │ template │  │ category │  │ query.py     │  │  │
│  │  │ resolver │  │ llm      │  │ fulltext │  │ add.py       │  │  │
│  │  │ reporter │  │          │  │          │  │              │  │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                            │                                        │
│  ┌─────────────────────────▼─────────────────────────────────────┐  │
│  │                    DATA LAYER                                 │  │
│  │                                                               │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐  │  │
│  │  │ Lessons      │  │ Templates    │  │ Memory (Phase 4)    │  │  │
│  │  │ 427 .md      │  │ 14 .md       │  │ SQLite              │  │  │
│  │  │ YAML front   │  │ YAML front   │  │ scan_history        │  │  │
│  │  │ 15 categories│  │ 15 sections  │  │ false_positives     │  │  │
│  │  │              │  │              │  │ lesson_confidence   │  │  │
│  │  │ _meta.json   │  │ _meta.json   │  │ fix_outcomes        │  │  │
│  │  └──────────────┘  └──────────────┘  └─────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Module Map

```
.claude/kiwi/
├── mcp_server.py              ← NEW: MCP Server (Phase 1)
├── _meta.json                 ← Registry
├── README.md                  ← Auto-generated index
│
├── scanner/                   ← EXISTING: Core scanner
│   ├── cli.py                 ← Main entry + scan_theme()
│   ├── models.py              ← Violation, Report dataclasses
│   ├── loader.py              ← YAML frontmatter parser
│   ├── resolver.py            ← Glob → file paths
│   ├── fixer.py               ← NEW: Auto-fix engine (Phase 2)
│   ├── checkers/
│   │   ├── presence.py        ← Pattern should NOT exist
│   │   ├── absence.py         ← Pattern MUST exist
│   │   ├── cross_check.py     ← Cross-file verification
│   │   └── bom.py             ← UTF-8 BOM detection
│   └── reporters/
│       ├── text.py            ← Human-readable output
│       └── json.py            ← Machine-readable output (v3)
│
├── agent/                     ← NEW: Agent system (Phase 3)
│   ├── __init__.py
│   ├── loop.py                ← Observe→Think→Act→Verify
│   ├── tools.py               ← Tool definitions for Claude API
│   ├── prompts.py             ← System prompts, few-shot
│   └── state.py               ← Scan state management
│
├── memory/                    ← NEW: Learning system (Phase 4)
│   ├── __init__.py
│   ├── db.py                  ← SQLite operations
│   ├── confidence.py          ← Confidence scoring
│   └── trends.py              ← Trend analysis
│
├── lessons/                   ← EXISTING: 427 bug patterns
│   ├── php-security/          ← 76 lessons
│   ├── wezone-api/            ← 92 lessons
│   ├── performance/           ← 49 lessons
│   ├── css-tokens/            ← 31 lessons
│   ├── nextjs-react/          ← 36 lessons
│   ├── ads-compliance/        ← 26 lessons
│   ├── supabase/              ← 26 lessons
│   ├── file-structure/        ← 21 lessons
│   ├── edge-cases/            ← 16 lessons
│   ├── db-schema/             ← 13 lessons
│   ├── js-contract/           ← 12 lessons
│   ├── concurrency/           ← 11 lessons
│   ├── ai-safety/             ← 7 lessons
│   ├── feature-suggest/       ← 37 lessons (FEA-*)
│   └── placeholder/           ← 1 lesson
│
├── templates/                 ← EXISTING: Verified code templates
│   ├── sections/              ← 14 templates (hero, header, etc.)
│   └── tools/                 ← query.py, add.py
│
├── tools/                     ← EXISTING: Maintenance tools
│   ├── add.py                 ← Add new lesson
│   ├── rebuild_index.py       ← Rebuild README.md
│   └── stats.py               ← Statistics
│
├── hooks/                     ← EXISTING: Auto-triggers
│   └── post_edit.py           ← Scan CRITICAL on file edit
│
├── docs/                      ← NEW: This documentation
│   ├── 00-VISION.md
│   ├── 01-ARCHITECTURE.md     ← (this file)
│   └── ...
│
└── kiwi.db                    ← NEW: SQLite memory (Phase 4)
```

## Data Flow

### Scan Flow (hiện tại + Phase 1 MCP)

```
User/Claude Code
       │
       ▼
  ┌─────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
  │  MCP     │────▶│  loader  │────▶│ resolver │────▶│ checkers │
  │ kiwi_scan│     │ .py      │     │ .py      │     │ /*.py    │
  └─────────┘     └──────────┘     └──────────┘     └──────────┘
                   parse YAML       glob → files      regex match
                   frontmatter      filter platform    context guard
                   filter severity  exclude patterns   @kiwi-ignore
                        │                                   │
                        │           ┌──────────┐            │
                        └──────────▶│  Report  │◀───────────┘
                                    │ model    │
                                    └────┬─────┘
                                         │
                                    ┌────▼─────┐
                                    │ reporter │
                                    │ text/json│
                                    └──────────┘
```

### Agent Flow (Phase 3)

```
User: "Fix all CRITICAL in wezone-plugins"
       │
       ▼
  ┌─────────────────────────────────────────────┐
  │              AGENT LOOP                      │
  │                                              │
  │  1. OBSERVE                                  │
  │     kiwi_scan(path, severity=CRITICAL)       │
  │     → Report: 12 violations                  │
  │                                              │
  │  2. THINK (Claude API)                       │
  │     "12 violations. Group by file.            │
  │      LES-016 IDOR in 3 files → fix first.   │
  │      LES-362 XSS in 2 files → fix second."  │
  │                                              │
  │  3. ACT                                      │
  │     kiwi_fix(LES-016, file1) → applied       │
  │     kiwi_fix(LES-016, file2) → applied       │
  │     kiwi_fix(LES-362, file3) → needs LLM    │
  │     → Claude reasons about context → fix     │
  │                                              │
  │  4. VERIFY                                   │
  │     kiwi_scan(path, severity=CRITICAL)       │
  │     → Report: 2 violations (10 fixed!)       │
  │     Re-scan → no new violations introduced   │
  │                                              │
  │  5. LEARN (Phase 4)                          │
  │     Record: 10 fixes successful              │
  │     Update confidence scores                 │
  │     Log scan_history                         │
  │                                              │
  │  → Loop back to OBSERVE if violations remain │
  └─────────────────────────────────────────────┘
```

## Dependency Graph

```
Phase 4: Learning
    │ depends on
    ▼
Phase 3: Agent Loop
    │ depends on
    ▼
Phase 2: Auto-Fix
    │ depends on
    ▼
Phase 1: MCP Server
    │ depends on
    ▼
Existing: Scanner v3 (loader, checkers, resolver, reporters)
```

Mỗi phase build on top of phase trước, nhưng **mỗi phase đều ship được độc lập**:
- Phase 1 alone = Claude Code gọi Kiwi trực tiếp (đã có giá trị)
- Phase 2 alone = lessons có fix suggestions (đã có giá trị)
- Phase 3 needs Phase 1+2 = agent loop cần tools + fix engine
- Phase 4 enhances Phase 3 = learning cải thiện agent quality

## Key Interfaces

### Violation (existing — không thay đổi)
```python
@dataclass
class Violation:
    lesson_id: str      # "LES-016"
    severity: str       # "CRITICAL" | "HIGH" | "SUGGEST" | "INFO"
    category: str       # "php-security"
    description: str    # "Order page thiếu IDOR check"
    file: str           # "wezone-templates/account/orders.php"
    line: int           # 42
    match_text: str     # "$_GET['order_id']"
```

### Report (existing — không thay đổi)
```python
@dataclass
class Report:
    theme_path: str
    violations: list[Violation]
    patterns_checked: int
    files_scanned: int
    # Properties: critical_count, high_count, suggest_count
    # Methods: cap_per_lesson(), grouped()
```

### FixResult (Phase 2 — mới)
```python
@dataclass
class FixResult:
    lesson_id: str
    file: str
    fix_type: str       # "replace" | "template" | "llm"
    success: bool
    old_content: str    # affected lines only
    new_content: str    # after fix
    diff: str           # unified diff
    error: str = ""     # if failed
```

### AgentState (Phase 3 — mới)
```python
@dataclass
class AgentState:
    mode: str           # "review" | "interactive" | "auto"
    path: str           # project path
    scan_count: int     # number of scan iterations
    fixes_applied: int  # total fixes applied
    fixes_failed: int   # fixes that failed verification
    violations_start: int   # initial violation count
    violations_current: int # current violation count
    history: list[dict]     # action log
```