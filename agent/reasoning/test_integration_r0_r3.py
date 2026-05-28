"""Integration tests: R0 (Session Capture) → R1 (Context Assembly) → R2 (Learning) → R3 (Calibration)."""

import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.reasoning.session_logger import (
    DB_PATH,
    _get_conn,
    get_session_id,
    get_session_reads,
    get_session_writes,
    get_brief_for_session,
    get_session_log_entries,
    log_tool_call,
    mark_session_processed,
    save_brief_output,
)
from agent.reasoning.context_assembler import (
    assemble_context,
    infer_task_type,
    AssembledContext,
    PROJECT_ROOT,
)
from agent.reasoning.trust_scorer import compute_trust_score
from agent.reasoning.output import format_output, KiwiOutput
from agent.reasoning.learner import (
    learn_from_session,
    calibrate_trust_baselines,
    _extract_styles,
    _extract_bindings,
    _infer_task_type,
    _detect_theme,
)
from agent.reasoning.calibrator import (
    calibrate_trust_from_session,
    _get_trust_baseline,
    _set_trust_baseline,
    CALIBRATION_RULES,
)


PASS = 0
FAIL = 0


def ok(name):
    global PASS
    PASS += 1
    print(f"  PASS: {name}")


def fail(name, msg):
    global FAIL
    FAIL += 1
    print(f"  FAIL: {name} — {msg}")


def _reset_db():
    import agent.reasoning.session_logger as sl
    if sl._conn is not None:
        try:
            sl._conn.close()
        except Exception:
            pass
        sl._conn = None
    sl._session_id = None
    if DB_PATH.exists():
        DB_PATH.unlink()
    return _get_conn()


# ============================================================
# R0 — Session Capture
# ============================================================

def test_r0():
    print("\n[R0] Session Capture")
    conn = _reset_db()

    # Test: session ID generation
    import agent.reasoning.session_logger as sl
    sl._session_id = None
    sid = get_session_id()
    assert sid and len(sid) >= 4, f"Bad session ID: {sid}"
    ok("session_id generated")

    # Test: log_tool_call inserts correctly
    log_tool_call("Read", file_path="themes/sfvn/header.php")
    log_tool_call("Edit", file_path="themes/sfvn/header.php", metadata={"lines": 5})
    log_tool_call("Grep", file_path=None, metadata={"pattern": "wz_"})

    rows = conn.execute("SELECT COUNT(*) FROM session_log WHERE session_id = ?", (sid,)).fetchone()[0]
    if rows == 3:
        ok("log_tool_call inserts 3 entries")
    else:
        fail("log_tool_call", f"expected 3, got {rows}")

    # Test: session counters updated
    session = conn.execute(
        "SELECT files_read, files_written FROM sessions WHERE session_id = ?", (sid,)
    ).fetchone()
    if session == (1, 1):
        ok("session counters (read=1, written=1)")
    else:
        fail("session counters", f"expected (1,1), got {session}")

    # Test: get_session_reads / get_session_writes
    reads = get_session_reads(sid)
    writes = get_session_writes(sid)
    if len(reads) == 1 and reads[0]["file"] == "themes/sfvn/header.php":
        ok("get_session_reads")
    else:
        fail("get_session_reads", f"got {reads}")

    if len(writes) == 1 and writes[0]["tool"] == "Edit":
        ok("get_session_writes")
    else:
        fail("get_session_writes", f"got {writes}")

    # Test: get_session_log_entries
    entries = get_session_log_entries(sid)
    if len(entries) == 3 and entries[2]["tool"] == "Grep":
        ok("get_session_log_entries")
    else:
        fail("get_session_log_entries", f"got {len(entries)} entries")

    # Test: mark_session_processed
    mark_session_processed(sid)
    processed = conn.execute(
        "SELECT processed FROM sessions WHERE session_id = ?", (sid,)
    ).fetchone()[0]
    if processed == 1:
        ok("mark_session_processed")
    else:
        fail("mark_session_processed", f"got {processed}")


# ============================================================
# R1 — Context Assembly + Trust Score
# ============================================================

def test_r1():
    print("\n[R1] Context Assembly + Trust Score")

    # Test: infer_task_type
    cases = [
        ("Tạo trang checkout", "checkout_page"),
        ("Fix CSS responsive header", "fix_css"),
        ("Sửa bug null pointer", "fix_bug"),
        ("Thêm component sidebar", "add_component"),
        ("Random task", "generic"),
    ]
    for task, expected in cases:
        result = infer_task_type(task)
        if result == expected:
            ok(f"infer_task_type('{task[:20]}...') = {expected}")
        else:
            fail(f"infer_task_type('{task[:20]}...')", f"expected {expected}, got {result}")

    # Test: assemble_context with non-existent theme (graceful fallback)
    ctx = assemble_context("Fix checkout bug", "themes/nonexistent")
    if isinstance(ctx, AssembledContext) and ctx.task_type == "checkout_page":
        ok("assemble_context fallback (non-existent theme)")
    else:
        fail("assemble_context fallback", f"got {ctx}")

    # Test: assemble_context with real theme (if exists)
    sfvn_path = PROJECT_ROOT / "themes" / "sfvn"
    if sfvn_path.exists():
        ctx = assemble_context("Tạo trang product", str(sfvn_path))
        if ctx.task_type == "product_page" and ctx.theme.get("name") == "sfvn":
            ok("assemble_context real theme (sfvn)")
        else:
            fail("assemble_context real theme", f"type={ctx.task_type}, theme={ctx.theme}")

        # Test: compute_trust_score
        trust, breakdown = compute_trust_score(ctx, str(sfvn_path))
        if 0.0 <= trust <= 1.0 and isinstance(breakdown, dict):
            ok(f"compute_trust_score = {trust:.2f}")
        else:
            fail("compute_trust_score", f"trust={trust}")

        # Test: format_output
        output = format_output(ctx, trust, breakdown)
        if isinstance(output, KiwiOutput) and output.recommendation in ("trust", "verify_partial", "re_research"):
            ok(f"format_output recommendation = {output.recommendation}")
        else:
            fail("format_output", f"got {output}")
    else:
        ok("SKIP: themes/sfvn not found (assemble real theme)")
        ok("SKIP: compute_trust_score")
        ok("SKIP: format_output")


# ============================================================
# R2 — Passive Learning Engine
# ============================================================

def test_r2():
    print("\n[R2] Passive Learning Engine")
    conn = _reset_db()

    # Test: _extract_styles
    php_content = """
    <div class="py-8 md:py-16 max-w-7xl rounded-xl shadow-lg grid-cols-4">
        <div class="py-4 md:py-8 rounded-md shadow-sm">content</div>
    </div>
    """
    styles = _extract_styles(php_content)
    if styles.get("spacing_base") and styles.get("radius") and styles.get("container"):
        ok(f"_extract_styles: spacing={styles['spacing_base']}, radius={styles['radius']}")
    else:
        fail("_extract_styles", f"got {styles}")

    # Test: _extract_bindings
    php_bindings = """
    <?php
    $product = wz_get_product($id);
    $gallery = wz_product_gallery($product['id']);
    do_action('wezone_after_product', $product);
    wz_component('product-card');
    echo $product['title'];
    """
    bindings = _extract_bindings(php_bindings)
    if "wz_get_product" in bindings and "$product['title']" in bindings:
        ok(f"_extract_bindings: {len(bindings)} bindings found")
    else:
        fail("_extract_bindings", f"got {bindings}")

    # Test: _infer_task_type from file paths
    assert _infer_task_type(["themes/sfvn/wezone-templates/checkout/form.php"]) == "checkout_page"
    assert _infer_task_type(["themes/sfvn/templates/home.php"]) == "home_page"
    assert _infer_task_type(["themes/sfvn/style.css"]) == "fix_css"
    ok("_infer_task_type from file paths")

    # Test: _detect_theme
    assert _detect_theme(["D:/projects/wezone/themes/sfvn/header.php"]) == "sfvn"
    assert _detect_theme(["themes/funilux/footer.php"]) == "funilux"
    ok("_detect_theme")

    # Test: learn_from_session (simulated)
    import agent.reasoning.session_logger as sl
    sl._session_id = None
    sid = "test-r2-learn"
    conn.execute(
        "INSERT INTO sessions (session_id, started_at, files_read, files_written) VALUES (?, ?, 3, 2)",
        (sid, time.time()),
    )
    # Simulate reads
    ts = time.time()
    for f in ["themes/sfvn/inc/store-config.php", "themes/sfvn/header.php", "themes/sfvn/footer.php"]:
        conn.execute(
            "INSERT INTO session_log (session_id, tool, file_path, action, timestamp) VALUES (?, 'Read', ?, 'read', ?)",
            (sid, f, ts),
        )
        ts += 0.1
    # Simulate writes (need actual files for content extraction)
    for f in ["themes/sfvn/header.php", "themes/sfvn/footer.php"]:
        conn.execute(
            "INSERT INTO session_log (session_id, tool, file_path, action, timestamp) VALUES (?, 'Edit', ?, 'edit', ?)",
            (sid, f, ts),
        )
        ts += 0.1
    conn.commit()

    result = learn_from_session(sid)
    if result["status"] in ("learned", "skipped"):
        ok(f"learn_from_session: {result['status']}")
    else:
        fail("learn_from_session", f"got {result}")

    # Test: calibrate_trust_baselines (needs output_quality data)
    conn.execute(
        "INSERT INTO output_quality (session_id, week, task_type, files_re_read, edits_after_first, total_tool_calls, created_at) "
        "VALUES ('s1', 1, 'checkout_page', 0, 0, 10, ?)", (time.time(),)
    )
    conn.execute(
        "INSERT INTO output_quality (session_id, week, task_type, files_re_read, edits_after_first, total_tool_calls, created_at) "
        "VALUES ('s2', 1, 'checkout_page', 1, 0, 12, ?)", (time.time(),)
    )
    conn.execute(
        "INSERT INTO output_quality (session_id, week, task_type, files_re_read, edits_after_first, total_tool_calls, created_at) "
        "VALUES ('s3', 1, 'checkout_page', 0, 1, 8, ?)", (time.time(),)
    )
    conn.commit()

    cal_result = calibrate_trust_baselines()
    if cal_result.get("calibrated", 0) >= 1:
        baseline = conn.execute(
            "SELECT trust_score FROM trust_baselines WHERE task_type = 'checkout_page'"
        ).fetchone()
        if baseline and 0.0 < baseline[0] <= 1.0:
            ok(f"calibrate_trust_baselines: checkout_page = {baseline[0]:.2f}")
        else:
            fail("calibrate_trust_baselines", f"baseline = {baseline}")
    else:
        fail("calibrate_trust_baselines", f"got {cal_result}")


# ============================================================
# R3 — Trust Calibration
# ============================================================

def test_r3():
    print("\n[R3] Trust Calibration")
    conn = _reset_db()

    # Test: save_brief_output + get_brief_for_session
    class MockBrief:
        content = {"target": "product_page", "files_needed": ["spec.md", "config.php"]}
        trust_score = 0.72
        recommendation = "verify_partial"

    save_brief_output("test-brief-1", MockBrief())
    brief = get_brief_for_session("test-brief-1")
    if brief and brief["task_type"] == "product_page" and brief["trust_score"] == 0.72:
        ok("save_brief_output + get_brief_for_session")
    else:
        fail("brief storage", f"got {brief}")

    # Test: calibrate with no brief → early return
    result = calibrate_trust_from_session("nonexistent-session")
    if result["status"] == "no_brief":
        ok("calibrate no_brief early return")
    else:
        fail("calibrate no_brief", f"got {result}")

    # Test: full calibration cycle — positive
    _set_trust_baseline("product_page", 0.7)
    sid = "r3-positive"
    conn.execute("INSERT INTO sessions (session_id, started_at, files_written) VALUES (?, ?, 3)", (sid, time.time()))
    ts = time.time()
    # Reads: only 1 extra beyond brief (within threshold)
    for f in ["spec.md", "extra.php"]:
        conn.execute(
            "INSERT INTO session_log (session_id, tool, file_path, action, timestamp) VALUES (?, 'Read', ?, 'read', ?)",
            (sid, f, ts),
        )
        ts += 0.1
    # Writes: 3 different files, no multi-edit
    for f in ["a.php", "b.php", "c.php"]:
        conn.execute(
            "INSERT INTO session_log (session_id, tool, file_path, action, timestamp) VALUES (?, 'Edit', ?, 'edit', ?)",
            (sid, f, ts),
        )
        ts += 0.1
    conn.execute(
        "INSERT INTO brief_log (session_id, task_type, files_needed, trust_score, recommendation, created_at) "
        "VALUES (?, 'product_page', ?, 0.7, 'verify_partial', ?)",
        (sid, json.dumps(["spec.md", "config.php", "tokens.json"]), time.time()),
    )
    conn.commit()

    result = calibrate_trust_from_session(sid)
    if result["reason"] == "all_positive" and result["trust_after"] == 0.75:
        ok("calibrate all_positive: 0.7 → 0.75")
    else:
        fail("calibrate all_positive", f"got {result}")

    # Test: full calibration cycle — all negative (3 signals)
    _set_trust_baseline("cart_page", 0.8)
    sid2 = "r3-negative"
    conn.execute("INSERT INTO sessions (session_id, started_at, files_written) VALUES (?, ?, 5)", (sid2, time.time()))
    ts = time.time()
    # Signal 1: many extra reads (5 extra > max(3 briefed, 3))
    for f in ["x1.php", "x2.php", "x3.php", "x4.php", "x5.php"]:
        conn.execute(
            "INSERT INTO session_log (session_id, tool, file_path, action, timestamp) VALUES (?, 'Read', ?, 'read', ?)",
            (sid2, f, ts),
        )
        ts += 0.1
    # Signal 2: same file edited 4 times
    for _ in range(4):
        conn.execute(
            "INSERT INTO session_log (session_id, tool, file_path, action, timestamp) VALUES (?, 'Edit', 'cart.php', 'edit', ?)",
            (sid2, ts),
        )
        ts += 0.1
    # Extra write for edge case check (need >= 2 writes)
    conn.execute(
        "INSERT INTO session_log (session_id, tool, file_path, action, timestamp) VALUES (?, 'Edit', 'other.php', 'edit', ?)",
        (sid2, ts),
    )
    ts += 0.1
    # Signal 3: kiwi_block after write
    conn.execute(
        "INSERT INTO session_log (session_id, tool, file_path, action, metadata, timestamp) "
        "VALUES (?, 'Bash', NULL, 'shell', ?, ?)",
        (sid2, json.dumps({"kiwi_block": True}), ts),
    )
    conn.execute(
        "INSERT INTO brief_log (session_id, task_type, files_needed, trust_score, recommendation, created_at) "
        "VALUES (?, 'cart_page', ?, 0.8, 'trust', ?)",
        (sid2, json.dumps(["spec.md", "cart-spec.md", "config.php"]), time.time()),
    )
    conn.commit()

    result = calibrate_trust_from_session(sid2)
    if result["reason"] == "all_negative" and result["trust_after"] == 0.65:
        ok("calibrate all_negative: 0.8 → 0.65")
    else:
        fail("calibrate all_negative", f"got {result}")

    # Test: calibration_events stored
    events = conn.execute("SELECT COUNT(*) FROM calibration_events").fetchone()[0]
    if events == 2:
        ok(f"calibration_events stored: {events}")
    else:
        fail("calibration_events stored", f"expected 2, got {events}")

    # Test: trust_baselines updated
    t1 = _get_trust_baseline("product_page")
    t2 = _get_trust_baseline("cart_page")
    if t1 == 0.75 and t2 == 0.65:
        ok(f"trust_baselines: product={t1}, cart={t2}")
    else:
        fail("trust_baselines", f"product={t1}, cart={t2}")


# ============================================================
# E2E — Full Pipeline
# ============================================================

def test_e2e():
    print("\n[E2E] Full Pipeline: kiwi_reason → session → learn → calibrate")
    conn = _reset_db()

    # Simulate: kiwi_reason is called, brief is saved
    from agent.reasoning import kiwi_reason

    sfvn_path = PROJECT_ROOT / "themes" / "sfvn"
    if not sfvn_path.exists():
        ok("SKIP: E2E (themes/sfvn not found)")
        return

    output = kiwi_reason("Tạo trang checkout", str(sfvn_path))
    if isinstance(output, KiwiOutput) and output.trust_score > 0:
        ok(f"kiwi_reason returns KiwiOutput (trust={output.trust_score:.2f})")
    else:
        fail("kiwi_reason", f"got {output}")

    # Verify brief was saved
    import agent.reasoning.session_logger as sl
    sid = sl._session_id
    brief = get_brief_for_session(sid)
    if brief and brief["task_type"] == "checkout_page":
        ok("brief auto-saved after kiwi_reason")
    else:
        fail("brief auto-saved", f"got {brief}")

    # Simulate: Claude does work in this session
    log_tool_call("Read", file_path="themes/sfvn/inc/store-config.php")
    log_tool_call("Read", file_path="themes/sfvn/header.php")
    log_tool_call("Edit", file_path="themes/sfvn/wezone-templates/checkout/form.php")
    log_tool_call("Edit", file_path="themes/sfvn/wezone-templates/checkout/summary.php")

    reads = get_session_reads(sid)
    writes = get_session_writes(sid)
    if len(reads) >= 2 and len(writes) >= 2:
        ok(f"session logged: {len(reads)} reads, {len(writes)} writes")
    else:
        fail("session logging", f"reads={len(reads)}, writes={len(writes)}")

    # Simulate: session ends, next kiwi_reason triggers learn + calibrate
    # First mark current session as unprocessed with enough writes
    conn.execute(
        "UPDATE sessions SET files_written = ? WHERE session_id = ?",
        (len(writes), sid),
    )
    conn.execute(
        "UPDATE sessions SET processed = 0 WHERE session_id = ?", (sid,)
    )
    conn.commit()

    # Call kiwi_reason again (simulates next session) — triggers _auto_learn_recent
    sl._session_id = None  # force new session
    output2 = kiwi_reason("Fix CSS header", str(sfvn_path))
    if isinstance(output2, KiwiOutput):
        ok("second kiwi_reason triggers auto-learn pipeline")
    else:
        fail("second kiwi_reason", f"got {output2}")

    # Verify session was processed
    processed = conn.execute(
        "SELECT processed FROM sessions WHERE session_id = ?", (sid,)
    ).fetchone()
    if processed and processed[0] == 1:
        ok("previous session marked processed")
    else:
        fail("session processed", f"got {processed}")


# ============================================================
# Schema Migration
# ============================================================

def test_migration():
    print("\n[Migration] Existing DB gets new tables")
    import agent.reasoning.session_logger as sl
    if sl._conn is not None:
        try:
            sl._conn.close()
        except Exception:
            pass
        sl._conn = None

    # Create a DB with only old tables (simulate pre-R3 state)
    if DB_PATH.exists():
        DB_PATH.unlink()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript("""
        CREATE TABLE session_log (id INTEGER PRIMARY KEY, session_id TEXT, tool TEXT, file_path TEXT, action TEXT, metadata TEXT, timestamp REAL);
        CREATE TABLE sessions (session_id TEXT PRIMARY KEY, started_at REAL, ended_at REAL, task_hint TEXT, files_read INTEGER DEFAULT 0, files_written INTEGER DEFAULT 0, theme_path TEXT, processed INTEGER DEFAULT 0);
        CREATE TABLE trust_baselines (task_type TEXT PRIMARY KEY, trust_score REAL DEFAULT 0.5, last_calibrated REAL, calibration_count INTEGER DEFAULT 0);
    """)
    conn.close()

    # Now open via _get_conn — should trigger migration
    sl._conn = None
    conn = _get_conn()

    # Check new tables exist
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]

    if "calibration_events" in tables and "brief_log" in tables:
        ok("migration creates calibration_events + brief_log")
    else:
        fail("migration", f"tables = {tables}")


# ============================================================
# Run all
# ============================================================

# ============================================================
# R3+ — Decay + Pattern Mining + Hook Signal
# ============================================================

def test_decay():
    print("\n[R3+] Trust Baseline Decay")
    conn = _reset_db()
    from agent.reasoning.calibrator import decay_stale_baselines, CALIBRATION_RULES

    now = time.time()
    old = now - (15 * 86400)  # 15 days ago

    # Insert baselines: one stale, one fresh
    conn.execute(
        "INSERT INTO trust_baselines (task_type, trust_score, last_calibrated, calibration_count) "
        "VALUES ('stale_task', 0.8, ?, 5)",
        (old,),
    )
    conn.execute(
        "INSERT INTO trust_baselines (task_type, trust_score, last_calibrated, calibration_count) "
        "VALUES ('fresh_task', 0.8, ?, 5)",
        (now,),
    )
    conn.commit()

    result = decay_stale_baselines()
    if result["decayed"] == 1:
        ok("decay only affects stale baselines (1 decayed)")
    else:
        fail("decay count", f"expected 1, got {result}")

    # Verify stale decayed, fresh unchanged
    stale = conn.execute("SELECT trust_score FROM trust_baselines WHERE task_type = 'stale_task'").fetchone()[0]
    fresh = conn.execute("SELECT trust_score FROM trust_baselines WHERE task_type = 'fresh_task'").fetchone()[0]
    if stale == 0.77:  # 0.8 - 0.03
        ok(f"stale_task decayed: 0.8 → {stale}")
    else:
        fail("stale decay value", f"expected 0.77, got {stale}")

    if fresh == 0.8:
        ok("fresh_task unchanged: 0.8")
    else:
        fail("fresh unchanged", f"expected 0.8, got {fresh}")

    # Test decay floor
    conn.execute("UPDATE trust_baselines SET trust_score = 0.41 WHERE task_type = 'stale_task'")
    conn.commit()
    result2 = decay_stale_baselines()
    stale2 = conn.execute("SELECT trust_score FROM trust_baselines WHERE task_type = 'stale_task'").fetchone()[0]
    if stale2 == CALIBRATION_RULES["decay_floor"]:
        ok(f"decay respects floor: {stale2}")
    else:
        fail("decay floor", f"expected {CALIBRATION_RULES['decay_floor']}, got {stale2}")

    # Test: already at floor → not decayed
    result3 = decay_stale_baselines()
    if result3["decayed"] == 0:
        ok("at floor → no further decay")
    else:
        fail("at floor no decay", f"got {result3}")


def test_pattern_mining():
    print("\n[R3+] Pattern Mining")
    conn = _reset_db()
    from agent.reasoning.calibrator import mine_file_patterns

    # Not enough data → empty
    result = mine_file_patterns(min_sessions=5)
    if result == {}:
        ok("mine_file_patterns: empty when no data")
    else:
        fail("mine empty", f"got {result}")

    # Insert 6 sessions for checkout_page, all reading similar files
    common_files = ["D:\\projects\\wezone\\themes\\sfvn\\inc\\store-config.php"]
    for i in range(6):
        reads = common_files + [f"extra_{i}.php"]
        conn.execute(
            "INSERT INTO context_patterns (task_type, files_read, files_written, theme, session_id, created_at) "
            "VALUES ('checkout_page', ?, '[\"checkout.php\"]', 'sfvn', ?, ?)",
            (json.dumps(reads), f"mine-{i}", time.time() + i),
        )
    conn.commit()

    result = mine_file_patterns(min_sessions=5)
    if "checkout_page" in result:
        files = result["checkout_page"]["files_needed"]
        # store-config.php appears in all 6 sessions → should be suggested
        if any("store-config.php" in f for f in files):
            ok(f"mine_file_patterns: found common file ({len(files)} suggestions)")
        else:
            fail("mine common file", f"files = {files}")
    else:
        fail("mine checkout_page", f"got {result}")

    # Confidence scales with session count
    if result["checkout_page"]["confidence"] <= 1.0:
        ok(f"mine confidence: {result['checkout_page']['confidence']:.2f}")
    else:
        fail("mine confidence", f"got {result['checkout_page']['confidence']}")


def test_hook_signal():
    print("\n[R3+] Hook KiwiBlock Signal")
    conn = _reset_db()

    sid = "hook-test"
    conn.execute("INSERT INTO sessions (session_id, started_at, files_written) VALUES (?, ?, 3)", (sid, time.time()))
    ts = time.time()

    # Write → KiwiBlock entry (new format from hook fix)
    conn.execute(
        "INSERT INTO session_log (session_id, tool, file_path, action, metadata, timestamp) "
        "VALUES (?, 'Edit', 'header.php', 'edit', NULL, ?)", (sid, ts),
    )
    conn.execute(
        "INSERT INTO session_log (session_id, tool, file_path, action, metadata, timestamp) "
        "VALUES (?, 'Edit', 'footer.php', 'edit', NULL, ?)", (sid, ts + 1),
    )
    conn.execute(
        "INSERT INTO session_log (session_id, tool, file_path, action, metadata, timestamp) "
        "VALUES (?, 'KiwiBlock', 'header.php', 'other', ?, ?)",
        (sid, json.dumps({"kiwi_block": True, "violations": 2}), ts + 2),
    )
    conn.execute(
        "INSERT INTO brief_log (session_id, task_type, files_needed, trust_score, recommendation, created_at) "
        "VALUES (?, 'home_page', '[]', 0.7, 'verify_partial', ?)",
        (sid, time.time()),
    )
    conn.commit()

    _set_trust_baseline("home_page", 0.7)
    result = calibrate_trust_from_session(sid)

    if result.get("signals", {}).get("kiwi_violations") is True:
        ok("KiwiBlock tool detected as violation signal")
    else:
        fail("KiwiBlock detection", f"got {result}")


if __name__ == "__main__":
    test_r0()
    test_r1()
    test_r2()
    test_r3()
    test_e2e()
    test_migration()
    test_decay()
    test_pattern_mining()
    test_hook_signal()

    print(f"\n{'='*50}")
    print(f"RESULTS: {PASS} passed, {FAIL} failed")
    if FAIL == 0:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
        sys.exit(1)