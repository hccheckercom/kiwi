# HANDOFF: Kiwi Learn from Folder — 2026-05-24

## 🎯 Feature Completed

**New MCP Tool:** `kiwi_learn_from_folder` — Scan arbitrary folder → auto-detect bug patterns → create lessons

## ✅ What Was Built

### 1. Pattern Detection Engine (`agent/learn.py`)
**10 Built-in Detectors:**
- Hardcoded credentials (CRITICAL)
- SQL injection via string concatenation (CRITICAL)
- XSS risk - unescaped output (HIGH)
- Missing nonce verification (HIGH)
- Arbitrary file inclusion (CRITICAL)
- Hardcoded URLs (HIGH)
- Missing error handling for external calls (HIGH)
- Deprecated PHP functions (HIGH)
- Inefficient loops with count() (SUGGEST)
- Missing input sanitization (HIGH)

### 2. MCP Tool Integration
**Tool:** `kiwi_learn_from_folder`

**Parameters:**
```javascript
{
  path: string,              // Folder to scan
  min_occurrences: int = 3,  // Min pattern occurrences to suggest
  auto_approve: bool = false, // Auto-create lessons or return suggestions
  categories: string[]       // Optional: focus categories
}
```

**Output:**
- Scanned files count
- Patterns found count
- Suggestions list with:
  - Pattern type, category, severity
  - Occurrences count + affected files
  - Bad/Good code examples
  - Why explanation

### 3. Auto-Lesson Generation
When `auto_approve=true`:
- Auto-creates lesson files in `.claude/kiwi/lessons/{category}/`
- Updates `_meta.json` (next_id, stats)
- Auto-rebuilds README index

## 📊 Test Results

**Test:** Scanned `wezone-plugins` (5,038 PHP files)

**Results:**
- 8 patterns detected
- 141 occurrences of "missing error handling"
- Patterns found: missing_error_handling, hardcoded_url, sql_injection, xss_risk, etc.

## 🔧 Files Modified

1. **`.claude/kiwi/agent/learn.py`** (NEW)
   - Pattern extraction logic
   - Clustering algorithm
   - Lesson suggestion generator

2. **`.claude/kiwi/mcp_server.py`**
   - Added `_handle_learn_from_folder()` handler
   - Added tool definition to TOOL_DEFS
   - Added handler to HANDLERS dict

## 🚀 How to Use

### Via MCP Tool (after restart)
```javascript
kiwi_learn_from_folder({
  path: "themes/funilux",
  min_occurrences: 3,
  auto_approve: false  // Preview suggestions first
})
```

### Via Python CLI
```powershell
cd .claude/kiwi
python -c "from agent.learn import learn_from_folder; learn_from_folder('path/to/folder', min_occurrences=3)"
```

### Workflow
1. Scan folder with `auto_approve=false` → review suggestions
2. If good → re-run with `auto_approve=true` → auto-create lessons
3. Rebuild index: `python tools/rebuild_index.py`
4. Re-index RAG: `cd ../../rag; python index_wezone.py`

## 🎯 Use Cases

1. **Learn from New Theme:**
   ```javascript
   kiwi_learn_from_folder({
     path: "themes/new-client-theme",
     min_occurrences: 2,
     categories: ["security", "performance"]
   })
   ```

2. **Learn from Plugin:**
   ```javascript
   kiwi_learn_from_folder({
     path: "wezone-plugins/packages/wezone-zalo",
     min_occurrences: 3
   })
   ```

3. **Learn from Vendor Code:**
   ```javascript
   kiwi_learn_from_folder({
     path: "vendor/some-library",
     min_occurrences: 5,
     categories: ["security"]
   })
   ```

## 🔍 Pattern Detection Logic

Each detector uses regex + context analysis:
- **Hardcoded credentials:** `(password|secret|api_key|token)\s*=\s*["'][^"']+["']`
- **SQL injection:** `$wpdb->(query|get_results).*\.\s*\$`
- **XSS risk:** `echo\s+\$(?!.*esc_)`
- **Missing nonce:** `isset($_POST.*(?!.*wp_verify_nonce)`
- **File inclusion:** `(include|require)(_once)?\s*\(\s*\$`
- **Hardcoded URL:** `https?://[a-z0-9.-]+\.[a-z]{2,}`
- **Missing error handling:** `(wp_remote_get|file_get_contents|curl_exec)\(` + no error check in next 3 lines
- **Deprecated functions:** `(mysql_query|ereg|split|create_function)\(`
- **Inefficient loop:** `(for|while).*count\(`
- **Missing sanitization:** `\$_(GET|POST|REQUEST)\[(?!.*sanitize_)`

## 📈 Impact

**Before:**
- Manual pattern discovery from code review
- Slow lesson creation process
- Patterns missed across themes

**After:**
- Automated pattern mining from any folder
- 10 built-in detectors ready to use
- Scalable to thousands of files (tested on 5,038 files)
- Auto-lesson generation with one flag

## 🔄 Next Steps

1. **Add More Detectors:**
   - Missing ABAC checks
   - Hardcoded breakpoints
   - Missing mobile-first CSS
   - BEM violations

2. **Improve Clustering:**
   - Use AST analysis instead of regex
   - Similarity scoring for code blocks
   - Deduplicate similar patterns

3. **Integration:**
   - Add to `/kiwi-audit` skill
   - Auto-run on new theme creation
   - Weekly cron job to learn from all themes

## 📝 Commits

- `66ad0c9`: feat(kiwi): self-upgrade - fix 3 bugs + 4 new lessons
- `f6c5149`: feat(kiwi): Phase 3 - Rich Human Collaboration UI (Frontend) — includes `agent/learn.py`

## 🎓 Meta-Learning Success

Kiwi can now:
1. ✅ Learn from its own codebase (meta-learning)
2. ✅ Learn from scan history (pattern mining)
3. ✅ **Learn from arbitrary folders (new feature)**

**Total:** 3 self-learning mechanisms operational

---

**Session End:** 2026-05-24 08:51 UTC  
**Status:** Feature complete + tested + committed  
**Next:** Restart Claude Code to load new MCP tool
