# A3 — Generic Plugin: Auto-Learn Engine (2 days)

## Mục tiêu
Plugin auto-learn cho bất kỳ codebase nào. Không cần pre-built lessons.
Biến generic plugin từ "static lesson wrapper" thành "intelligent code analyzer".

## Hiện trạng (A2 output)
- `plugins/generic/plugin.py` — wraps 379 static lessons + 4 checkers (presence/absence/cross-check/bom-check)
- `detect_project()` returns hardcoded 0.1
- `manifest.json` — metadata only
- Lessons copied from source, no auto-learning capability

## Tasks

### T1: Auto-Detector (4h)
Detect language/framework từ file extensions + config files.

**Input:** project path
**Output:** `ProjectProfile` dataclass:
```python
@dataclass
class ProjectProfile:
    languages: dict[str, float]    # {"python": 0.7, "js": 0.2, "css": 0.1}
    frameworks: list[str]          # ["react", "nextjs", "tailwind"]
    package_manager: str | None    # "npm", "pip", "composer"
    test_framework: str | None     # "pytest", "jest", "phpunit"
    build_tool: str | None         # "webpack", "vite", "esbuild"
    entry_points: list[str]        # ["src/index.ts", "main.py"]
```

**Detection signals:**
| Signal | Detects |
|--------|---------|
| `package.json` | Node.js, deps → framework (react, vue, next, etc.) |
| `composer.json` | PHP, deps → framework (laravel, wordpress, symfony) |
| `pyproject.toml` / `setup.py` / `requirements.txt` | Python, deps |
| `Cargo.toml` | Rust |
| `go.mod` | Go |
| `tsconfig.json` | TypeScript |
| `tailwind.config.*` | Tailwind CSS |
| `.eslintrc*` / `biome.json` | Linter config |
| File extension distribution | Primary language |

### T2: Convention Learner (6h)
Scan codebase → extract naming, indent, import style as machine-readable rules.

**Output:** `ConventionSet` — list of `Convention` objects:
```python
@dataclass
class Convention:
    category: str       # "naming", "indent", "import", "structure"
    rule: str           # human-readable: "Functions use snake_case"
    pattern: str        # regex or glob for checking
    confidence: float   # 0.0-1.0 based on consistency in codebase
    examples: list[str] # 3-5 examples from actual code
    counter_examples: list[str]  # violations found (if any)
```

**Learners:**
1. **NamingLearner** — detect case style per entity type:
   - Functions: snake_case / camelCase / PascalCase
   - Classes: PascalCase / UPPER_CASE
   - Variables: snake_case / camelCase
   - Files: kebab-case / snake_case / camelCase
   - Constants: UPPER_SNAKE_CASE
   
2. **IndentLearner** — detect indent style:
   - Tabs vs spaces
   - Width (2/4/8)
   - Consistency score

3. **ImportLearner** — detect import patterns:
   - Grouped (stdlib → third-party → local)?
   - Sorted alphabetically?
   - Relative vs absolute imports
   - Barrel exports (index.ts re-exports)

4. **StructureLearner** — detect project structure patterns:
   - Flat vs nested modules
   - Co-located tests vs separate test dir
   - Component file structure (component + style + test together?)

### T3: Pattern Miner (4h)
Detect repeated code patterns → suggest as new lessons.

**Strategy:** AST-free approach using text heuristics (works across languages):
1. Extract function signatures → find naming patterns
2. Find repeated error handling patterns (try/catch, if err != nil)
3. Detect common import groups
4. Find repeated boilerplate (file headers, class structure)

**Output:** `PatternSuggestion` list:
```python
@dataclass
class PatternSuggestion:
    title: str
    category: str
    pattern_regex: str
    occurrences: int
    example_files: list[str]
    suggested_lesson: str  # markdown content for lesson file
    confidence: float
```

**Mining rules:**
- Min 3 occurrences to suggest
- Confidence = occurrences / total_possible * consistency_factor
- Ignore patterns already covered by existing lessons
- Deduplicate similar patterns (Levenshtein > 0.8)

### T4: Generic Checkers (4h)
Language-agnostic checks that work on any codebase.

**Checkers:**
1. **NamingConsistencyChecker** — flag names that deviate from learned convention
   - Input: ConventionSet from T2
   - Output: violations where naming doesn't match majority style
   
2. **ImportOrderChecker** — flag imports not matching learned order
   - Input: ConventionSet from T2
   - Output: violations where import order deviates

3. **ErrorHandlingChecker** — flag missing/inconsistent error handling
   - Detect: empty catch blocks, swallowed errors, inconsistent patterns
   - Language-aware: try/catch (JS/PHP), if err (Go), Result (Rust)

4. **DeadCodeChecker** — flag obvious dead code
   - Unreachable code after return/throw
   - Commented-out code blocks (> 5 lines)
   - Unused imports (basic heuristic, not full resolution)

5. **FileSizeChecker** — flag files exceeding learned average by 3x

### T5: Skeleton Drafter (3h)
Generate boilerplate from learned conventions.

**Implements:** `BaseDrafter` from `core/drafter_base.py`

**Capabilities:**
- Generate file with correct naming, imports, structure based on ConventionSet
- Support levels: skeleton (structure only), draft (+ common patterns), complete (+ error handling)
- Template per detected framework (React component, Python module, PHP class)

### T6: Smart detect_project() (2h)
Replace hardcoded 0.1 with intelligent detection.

**Logic:**
```python
def detect_project(self, path: str) -> float:
    profile = AutoDetector.detect(path)
    
    # If wezone-wp plugin matches better, yield to it
    if profile.has_wordpress_signals():
        return 0.05  # let wezone-wp win
    
    # Score based on how well we can analyze this project
    score = 0.1  # base
    if profile.languages:
        score += 0.2
    if profile.frameworks:
        score += 0.2
    if profile.package_manager:
        score += 0.1
    
    return min(score, 0.8)  # cap below wezone-wp's 0.9
```

### T7: `kiwi init` Integration (1h)
Wire auto-detector into a CLI command.

```bash
kiwi init <path>
# Output:
# Detected: TypeScript + React + Next.js
# Package manager: npm
# Test framework: jest
# Learned 14 conventions
# Suggested 3 new patterns
# Ready to scan with 379 + 3 = 382 rules
```

**Integration points:**
- `mcp_server.py` — new tool `kiwi_init`
- `agent/cli.py` — new `--init` flag
- Stores learned conventions in `.kiwi/conventions.json` in target project

## Output Files
```
plugins/
└── generic/
    ├── __init__.py          # (exists)
    ├── plugin.py            # UPDATE: wire new components
    ├── manifest.json        # (exists)
    ├── lessons/             # (exists, 379 lessons)
    ├── auto_detector.py     # NEW: T1
    ├── convention_learner.py # NEW: T2
    ├── pattern_miner.py     # NEW: T3
    ├── checkers.py          # NEW: T4
    └── drafter.py           # NEW: T5
```

## Dependencies
- A1 (core plugin interface) ✅ done
- A2 (generic plugin skeleton + lessons) ✅ done

## Done Criteria
1. `kiwi init` on React project → detect TypeScript + React + Next.js
2. Convention learner extracts 10+ rules from any codebase with 50+ files
3. Pattern miner suggests 3+ patterns from codebase with 100+ files
4. Generic checkers detect naming inconsistency (e.g., mix of camelCase/snake_case)
5. Skeleton drafter generates valid file matching learned conventions
6. `detect_project()` returns > 0.5 for non-WP projects with config files
7. 0 WP-specific logic in generic plugin
8. All existing 21 A1/A2 tests still pass (backward compat)
9. New test suite: `tests/test_a3_generic.py` with 20+ assertions

## Risks
- AST-free pattern mining has lower precision than AST-based → mitigate with high min_occurrences threshold
- Convention learning on small codebases (< 20 files) may be unreliable → require min file count, report confidence
- Framework detection from deps can be ambiguous (e.g., project has both React and Vue deps) → report all with confidence scores

## Token Budget
- Auto-detector: pure file I/O, 0 LLM tokens
- Convention learner: pure regex/heuristic, 0 LLM tokens
- Pattern miner: pure text analysis, 0 LLM tokens
- Checkers: pure pattern matching, 0 LLM tokens
- Drafter: template-based, 0 LLM tokens
- **Total: 0 LLM tokens at runtime** (all local computation)
