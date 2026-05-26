Kế Hoạch Nâng Cấp Kiwi v2.1 → v2.5: Self-Upgrading System (95%+ Tự Học)
Context
Kiwi v2.1 hiện đạt 75-80% khả năng tự học với:

✅ Pattern mining engine hoàn chỉnh (miner.py, anomaly.py)
✅ Auto-promotion system (confidence ≥ 0.7)
✅ Coverage analysis & gap detection
✅ Fix outcome tracking
✅ 473 lessons tự động maintain
Gaps chính cần lấp đầy:

⚠️ Pattern refinement loop chưa hoàn thiện (TODO comment tại learning/loop.py:52)
⚠️ Chưa tự động demote/disable noisy patterns
⚠️ Chưa merge duplicate lessons
⚠️ Chưa có cross-project learning
⚠️ Thiếu semantic understanding (chỉ regex, chưa hiểu code flow)
Mục tiêu: Đạt 95%+ tự học trong 2 tuần với 4 phases:

Phase 1: Pattern Refinement (2-3 ngày)
Phase 2: Lesson Deduplication (1-2 ngày)
Phase 3: Cross-Project Learning (3-4 ngày)
Phase 4: Semantic Understanding (5-7 ngày)
Phase 1: Pattern Refinement Loop (2-3 ngày)
Mục tiêu: Tự động cải thiện patterns khi false positive rate cao

1.1 Implement Pattern Refiner Module
File mới: .claude/kiwi/learning/refiner.py

def refine_noisy_pattern(lesson_id: str, fp_threshold: float = 0.3) -> Optional[str]:
    """
    Refine pattern khi FP rate > threshold.
    
    Algorithm:
    1. Get false positives from memory
    2. Extract common tokens from FPs
    3. Add negative lookahead to pattern
    4. Test refined pattern on history
    5. Update lesson if accuracy improves
    
    Returns: refined_pattern if successful, None if failed
    """
Key functions:

extract_fp_tokens(fps: List[Dict]) -> Set[str] - Extract common tokens từ FPs
add_negative_lookahead(pattern: str, exclude_tokens: Set[str]) -> str - Thêm (?!...) vào pattern
test_pattern_accuracy(pattern: str, lesson_id: str) -> float - Test trên scan history
update_lesson_pattern(lesson_id: str, new_pattern: str, reason: str) - Update lesson file + _meta.json
1.2 Integrate Refiner vào Learning Loop
File sửa: .claude/kiwi/learning/loop.py

Thay TODO comment (line 52) bằng:

def on_fix_applied(lesson_id: str, file: str, success: bool):
    from memory.confidence import record_fix_outcome, get_lesson_confidence
    from .refiner import refine_noisy_pattern
    
    # Record fix outcome
    record_fix_outcome(lesson_id, success)
    
    # Trigger refinement if FP rate high
    confidence = get_lesson_confidence(lesson_id)
    if confidence and confidence['confidence'] < 0.5:
        refined = refine_noisy_pattern(lesson_id, fp_threshold=0.3)
        if refined:
            return {'fix_recorded': True, 'pattern_refined': True}
    
    return {'fix_recorded': True}
1.3 Add Refinement History Tracking
File sửa: .claude/kiwi/memory/db.py

Thêm table mới:

CREATE TABLE IF NOT EXISTS pattern_refinements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id TEXT NOT NULL,
    old_pattern TEXT NOT NULL,
    new_pattern TEXT NOT NULL,
    reason TEXT,
    fp_rate_before REAL,
    fp_rate_after REAL,
    timestamp TEXT DEFAULT (datetime('now'))
);
1.4 Testing
File test: .claude/kiwi/tests/test_refiner.py

Test cases:

Refine pattern với 5 FPs có common token
Verify negative lookahead được thêm đúng
Test accuracy improvement trên history
Verify lesson file được update
Phase 2: Lesson Deduplication (1-2 ngày)
Mục tiêu: Tự động merge similar lessons để giảm redundancy

2.1 Implement Deduplication Module
File mới: .claude/kiwi/learning/dedup.py

def find_duplicate_lessons(similarity_threshold: float = 0.9) -> List[List[str]]:
    """
    Find clusters of similar lessons.
    
    Algorithm:
    1. Load all lessons
    2. Calculate pairwise similarity (pattern + title + category)
    3. Cluster by similarity threshold
    4. Return clusters with ≥2 lessons
    """

def merge_lessons(cluster: List[str]) -> Dict:
    """
    Merge cluster of similar lessons.
    
    Strategy:
    - Keep lesson with highest confidence
    - Merge patterns with OR operator
    - Combine examples from all lessons
    - Archive old lessons to lessons/_archived/
    """
Similarity calculation:

Pattern similarity: Levenshtein distance (50% weight)
Title similarity: Token overlap (30% weight)
Category match: Exact match (20% weight)
2.2 Add Dedup Command
File sửa: .claude/kiwi/mcp_server.py

Thêm MCP tool mới:

@server.call_tool()
async def kiwi_dedup(arguments: dict) -> list[TextContent]:
    """
    Find and merge duplicate lessons.
    
    Args:
        threshold: Similarity threshold (default 0.9)
        dry_run: Show duplicates without merging
    """
2.3 Integrate vào Agent Loop
File sửa: .claude/kiwi/agent/loop.py

Thêm dedup check sau mỗi 10 lessons mới:

if len(new_lessons) >= 10:
    from learning.dedup import find_duplicate_lessons, merge_lessons
    duplicates = find_duplicate_lessons(threshold=0.9)
    for cluster in duplicates:
        merge_lessons(cluster)
2.4 Testing
File test: .claude/kiwi/tests/test_dedup.py

Test cases:

Detect 2 lessons với patterns gần giống (similarity > 0.9)
Merge lessons và verify pattern OR logic
Verify archived lessons vẫn readable
Test edge case: 3+ lessons trong cluster
Phase 3: Cross-Project Learning (3-4 ngày)
Mục tiêu: Học patterns từ tất cả projects, không chỉ 1 project

3.1 Global Pattern Aggregation
File sửa: .claude/kiwi/learning/miner.py

Thêm function:

def mine_patterns_global(
    min_occurrences: int = 5,
    similarity_threshold: float = 0.8,
    lookback_days: int = 30
) -> List[SuggestedPattern]:
    """
    Mine patterns across ALL projects.
    
    Differences from mine_patterns():
    - Query violations with path=None (all projects)
    - Classify patterns as universal vs platform-specific
    - Higher confidence for cross-project patterns
    """
Platform classification:

Universal: Pattern xuất hiện ở cả wp + nextjs projects
Platform-specific: Chỉ xuất hiện ở 1 platform
Project-specific: Chỉ xuất hiện ở 1 project (không tạo lesson)
3.2 Cross-Project Confidence Boost
File sửa: .claude/kiwi/learning/models.py

Update SuggestedPattern:

@dataclass
class SuggestedPattern:
    # ... existing fields ...
    project_count: int = 1  # Number of projects with this pattern
    is_universal: bool = False  # True if appears in multiple platforms
Confidence boost:

Base confidence × 1.2 nếu xuất hiện ở 2+ projects
Base confidence × 1.5 nếu universal (wp + nextjs)
3.3 Add Global Mining Schedule
File sửa: .claude/kiwi/learning/loop.py

Thêm scheduled task:

def schedule_global_mining():
    """
    Run global mining weekly.
    
    Triggered by:
    - Cron job (Sunday 2am)
    - Manual via kiwi_mine_global MCP tool
    """
3.4 MCP Tool for Global Mining
File sửa: .claude/kiwi/mcp_server.py

@server.call_tool()
async def kiwi_mine_global(arguments: dict) -> list[TextContent]:
    """
    Mine patterns across all projects.
    
    Args:
        lookback_days: Days to look back (default 30)
        min_projects: Min projects for pattern (default 2)
    """
3.5 Testing
File test: .claude/kiwi/tests/test_cross_project.py

Test cases:

Mine patterns từ 3 projects khác nhau
Verify universal patterns có confidence boost
Test platform classification logic
Verify project-specific patterns không tạo lesson
Phase 4: Semantic Understanding (5-7 ngày)
Mục tiêu: Hiểu code flow, không chỉ line-by-line regex

4.1 Expand AST Detector
File sửa: .claude/kiwi/learning/ast_detector.py

Thêm detectors:

def detect_missing_error_handling_flow(tree, source_code: str) -> List[CodePattern]:
    """
    Detect API calls without error handling in control flow.
    
    Checks:
    - fetch/axios without try-catch or .catch()
    - wp_remote_get without is_wp_error check
    - DB queries without error check
    """

def detect_unvalidated_input_flow(tree, source_code: str) -> List[CodePattern]:
    """
    Trace $_GET/$_POST usage through function calls.
    
    Checks:
    - Input used in DB query without sanitize
    - Input echoed without esc_html
    - Input used in file path without validation
    """

def detect_race_conditions(tree, source_code: str) -> List[CodePattern]:
    """
    Detect concurrent access patterns.
    
    Checks:
    - Read-modify-write without lock
    - Stock decrement without atomic check
    - Coupon usage without transaction
    """
4.2 Context-Aware Fix Learning
File mới: .claude/kiwi/learning/context_learner.py

def learn_from_fix_context(file: str, line: int, fix_diff: str) -> Optional[ContextualLesson]:
    """
    Learn contextual patterns from successful fixes.
    
    Algorithm:
    1. Parse file AST
    2. Find enclosing function/class
    3. Extract context: function name, params, return type
    4. Analyze fix diff: what changed?
    5. Create contextual pattern: "In function X, pattern Y needs fix Z"
    
    Returns: ContextualLesson if pattern is generalizable
    """
Example contextual lesson:

context:
  function_pattern: "handle_.*_ajax"
  has_nonce_check: false
pattern: "wp_ajax_.*"
fix: "Add wp_verify_nonce() at function start"
confidence: 0.85
4.3 Integrate Tree-sitter for JS/TS
File sửa: .claude/kiwi/learning/ast_detector.py

Hiện tại chỉ support PHP. Thêm JS/TS:

def parse_js_file(file_path: str):
    """Parse JS/TS file using tree-sitter-javascript"""
    import tree_sitter_javascript
    # ... implementation
New detectors:

detect_unhandled_promise() - Promise without .catch()
detect_xss_in_jsx() - dangerouslySetInnerHTML usage
detect_missing_null_check() - Optional chaining violations
4.4 Flow Analysis for Security
File mới: .claude/kiwi/learning/flow_analyzer.py

def trace_tainted_data(tree, source_code: str, taint_sources: List[str]) -> List[TaintFlow]:
    """
    Trace data flow from taint sources to sinks.
    
    Taint sources: $_GET, $_POST, user input
    Sinks: echo, DB query, file operations
    
    Returns: List of taint flows without sanitization
    """
4.5 Testing
File test: .claude/kiwi/tests/test_semantic.py

Test cases:

Detect error handling missing trong async function
Trace $_GET từ input → DB query
Detect race condition trong stock update
Learn contextual pattern từ fix diff
Verification Plan
1. Unit Tests
cd .claude/kiwi
python -m pytest tests/test_refiner.py -v
python -m pytest tests/test_dedup.py -v
python -m pytest tests/test_cross_project.py -v
python -m pytest tests/test_semantic.py -v
2. Integration Tests
Test refinement loop:

# Create noisy pattern with 10 FPs
python -m learning.refiner --lesson LES-999 --simulate-fps 10
# Verify pattern refined automatically
Test deduplication:

# Create 3 similar lessons
python -m learning.dedup --dry-run
# Verify clusters detected
python -m learning.dedup --merge
# Verify lessons merged
Test cross-project mining:

# Scan 3 projects
python -m scanner.cli --theme wezone-plugins
python -m scanner.cli --theme webstore-vn
python -m scanner.cli --theme themes/sfvn
# Run global mining
python -m learning.miner --global
# Verify universal patterns promoted
Test semantic analysis:

# Scan file with complex flow
python -m learning.ast_detector --file test_fixtures/complex_flow.php
# Verify flow-based violations detected
3. End-to-End Test
Scenario: Tạo bug mới → Kiwi tự học → Tự refine → Tự merge

# 1. Introduce new bug pattern in 3 files
# 2. Scan → violations detected
python -m scanner.cli --theme test-project
# 3. Mine patterns → suggestion created
# 4. Auto-promote → lesson generated
# 5. Apply fixes → some fail (FPs)
# 6. Refinement triggered → pattern improved
# 7. Re-scan → FP rate drops
# 8. Create similar lesson manually
# 9. Dedup detects → lessons merged
4. Performance Benchmarks
Metrics to track:

Pattern refinement time: < 5s per lesson
Dedup clustering time: < 10s for 500 lessons
Global mining time: < 60s for 10K violations
AST parsing time: < 100ms per file
5. Quality Metrics
Before vs After:

False positive rate: 15% → < 5%
Duplicate lessons: 23 pairs → 0
Cross-project patterns: 0 → 50+
Flow-based detections: 0 → 100+
Critical Files to Modify
New Files (8 files)
.claude/kiwi/learning/refiner.py - Pattern refinement engine
.claude/kiwi/learning/dedup.py - Lesson deduplication
.claude/kiwi/learning/context_learner.py - Contextual learning
.claude/kiwi/learning/flow_analyzer.py - Data flow analysis
.claude/kiwi/tests/test_refiner.py - Refiner tests
.claude/kiwi/tests/test_dedup.py - Dedup tests
.claude/kiwi/tests/test_cross_project.py - Cross-project tests
.claude/kiwi/tests/test_semantic.py - Semantic tests
Modified Files (7 files)
.claude/kiwi/learning/loop.py - Add refinement trigger, dedup check, global mining
.claude/kiwi/learning/miner.py - Add mine_patterns_global()
.claude/kiwi/learning/models.py - Add project_count, is_universal fields
.claude/kiwi/learning/ast_detector.py - Add JS/TS support, flow detectors
.claude/kiwi/memory/db.py - Add pattern_refinements table
.claude/kiwi/mcp_server.py - Add kiwi_dedup, kiwi_mine_global tools
.claude/kiwi/agent/loop.py - Integrate dedup into agent loop
Documentation Updates (3 files)
.claude/kiwi/docs/ARCHITECTURE.md - Document new modules
.claude/kiwi/docs/QUICKSTART.md - Add refinement/dedup examples
.claude/kiwi/README.md - Update capabilities section
Dependencies
Python packages (add to requirements.txt):

tree-sitter-javascript>=0.20.0  # JS/TS AST parsing
python-Levenshtein>=0.21.0      # Fast string similarity
networkx>=3.0                    # Graph analysis for flow tracing
Install:

cd .claude/kiwi
pip install tree-sitter-javascript python-Levenshtein networkx
Rollout Strategy
Week 1: Foundation (Phase 1 + 2)
Day 1-3: Implement refiner.py + integrate vào loop
Day 4-5: Implement dedup.py + MCP tools
Day 6-7: Testing + bug fixes
Week 2: Advanced (Phase 3 + 4)
Day 8-10: Cross-project learning + global mining
Day 11-14: Semantic understanding + flow analysis
Day 15: Integration testing + documentation
Rollback Plan
Mỗi phase có feature flag trong _meta.json:
{
  "features": {
    "pattern_refinement": true,
    "deduplication": true,
    "cross_project_learning": true,
    "semantic_analysis": true
  }
}
Nếu phase nào fail → disable feature flag
Rollback về v2.1 bằng cách restore _meta.json + xóa new files
Success Criteria
Kiwi v2.5 đạt 95%+ tự học khi:

✅ Pattern refinement tự động khi FP rate > 30%
✅ Duplicate lessons tự động merge (0 duplicates)
✅ Cross-project patterns được promote với confidence boost
✅ Flow-based violations được detect (không chỉ line-by-line)
✅ False positive rate < 5% (từ 15%)
✅ 50+ universal patterns được mine từ multiple projects
✅ Contextual lessons được learn từ fix outcomes
Metrics dashboard:

Self-learning rate: 95%+
Manual intervention: < 5% cases
Pattern quality score: > 0.9
Time to learn new pattern: < 24h