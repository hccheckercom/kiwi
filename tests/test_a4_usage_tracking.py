"""Comprehensive QA for A4 — Usage Tracking + Savings Dashboard."""

import sys
import time
import tempfile
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

KIWI_DIR = Path(__file__).resolve().parent.parent


def main():
    print("=" * 60)
    print("A4 COMPREHENSIVE QA — Usage Tracking + Savings Dashboard")
    print("=" * 60)
    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  PASS [{passed}] {name}")
        else:
            failed += 1
            print(f"  FAIL [{name}] {detail}")

    # === GROUP 1: Module Structure ===
    print("\n--- GROUP 1: Module Structure ---")
    tracking_dir = KIWI_DIR / "tracking"
    check("tracking/ dir exists", tracking_dir.is_dir())
    check("__init__.py exists", (tracking_dir / "__init__.py").is_file())
    check("usage_tracker.py exists", (tracking_dir / "usage_tracker.py").is_file())
    check("baseline_estimator.py exists", (tracking_dir / "baseline_estimator.py").is_file())
    check("savings.py exists", (tracking_dir / "savings.py").is_file())
    check("dashboard.py exists", (tracking_dir / "dashboard.py").is_file())
    check("schema.sql exists", (tracking_dir / "schema.sql").is_file())

    # === GROUP 2: Imports ===
    print("\n--- GROUP 2: Imports ---")
    try:
        from tracking.usage_tracker import UsageTracker, get_tracker
        check("UsageTracker importable", True)
    except Exception as e:
        check("UsageTracker importable", False, str(e))

    try:
        from tracking.baseline_estimator import estimate_baseline, OPERATION_FORMULAS
        check("estimate_baseline importable", True)
    except Exception as e:
        check("estimate_baseline importable", False, str(e))

    try:
        from tracking.savings import get_savings
        check("get_savings importable", True)
    except Exception as e:
        check("get_savings importable", False, str(e))

    try:
        from tracking.dashboard import dashboard, format_compact, format_detail
        check("dashboard importable", True)
    except Exception as e:
        check("dashboard importable", False, str(e))

    # === GROUP 3: Baseline Estimator ===
    print("\n--- GROUP 3: Baseline Estimator ---")
    from tracking.baseline_estimator import estimate_baseline, OPERATION_FORMULAS, BASELINE_MODEL

    check("BASELINE_MODEL is sonnet", "sonnet" in BASELINE_MODEL)
    check("10+ operation formulas", len(OPERATION_FORMULAS) >= 10, f"got {len(OPERATION_FORMULAS)}")

    est_context = estimate_baseline("context", files_processed=5)
    check("context estimate has tokens", est_context["tokens"] > 0)
    check("context estimate has cost_usd", est_context["cost_usd"] > 0)
    check("context estimate has latency_ms", est_context["latency_ms"] > 0)
    check("context estimate has model", est_context["model"] == BASELINE_MODEL)

    est_scan = estimate_baseline("scan", files_processed=50)
    check("scan(50 files) > context(5 files)", est_scan["tokens"] > est_context["tokens"])

    est_check = estimate_baseline("check", files_processed=1, file_lines=200)
    check("check estimate reasonable", 500 < est_check["tokens"] < 5000, f"got {est_check['tokens']}")

    est_unknown = estimate_baseline("unknown_op")
    check("unknown op uses default formula", est_unknown["tokens"] > 0)

    # === GROUP 4: UsageTracker with temp DB ===
    print("\n--- GROUP 4: UsageTracker ---")
    tmp_db = Path(tempfile.mktemp(suffix=".db"))
    try:
        tracker = UsageTracker(db_path=tmp_db)
        check("tracker created with temp DB", True)

        check("initial count = 0", tracker.get_event_count() == 0)

        row_id = tracker.record(
            operation="scan",
            target_path="/test/project",
            files_processed=10,
            latency_ms=150,
            violations_found=3,
        )
        check("record returns row_id > 0", row_id > 0)
        check("count after 1 record = 1", tracker.get_event_count() == 1)

        row_id2 = tracker.record(
            operation="check",
            target_path="/test/file.php",
            files_processed=1,
            latency_ms=20,
        )
        check("second record works", row_id2 == row_id + 1)
        check("count after 2 records = 2", tracker.get_event_count() == 2)

        events = tracker.get_events(limit=10)
        check("get_events returns 2", len(events) == 2)
        check("events have operation field", all("operation" in e for e in events))
        check("events have timestamp", all("timestamp" in e for e in events))

        scan_events = tracker.get_events(limit=10, operation="scan")
        check("filter by operation works", len(scan_events) == 1)
        check("filtered event is scan", scan_events[0]["operation"] == "scan")

        row_id3 = tracker.record(
            operation="context",
            target_path="/test/theme",
            tokens_baseline=1500,
            cost_baseline_usd=0.0055,
            latency_baseline_ms=15000,
            files_processed=5,
            latency_ms=50,
        )
        check("explicit baseline overrides auto-calc", True)
        events_all = tracker.get_events(limit=10)
        ctx_event = [e for e in events_all if e["operation"] == "context"][0]
        check("explicit tokens_baseline stored", ctx_event["tokens_baseline"] == 1500)
        check("explicit cost_baseline stored", abs(ctx_event["cost_baseline_usd"] - 0.0055) < 0.0001)

        failed_id = tracker.record(
            operation="deploy",
            target_path="/test/deploy",
            success=False,
            latency_ms=5000,
        )
        check("failed record stored", failed_id > 0)
        events_all2 = tracker.get_events(limit=10)
        deploy_event = [e for e in events_all2 if e["operation"] == "deploy"][0]
        check("success=0 for failed", deploy_event["success"] == 0)

        tracker.close()
    finally:
        if tmp_db.exists():
            tmp_db.unlink()

    # === GROUP 5: Savings Calculator ===
    print("\n--- GROUP 5: Savings Calculator ---")
    tmp_db2 = Path(tempfile.mktemp(suffix=".db"))
    try:
        tracker2 = UsageTracker(db_path=tmp_db2)
        for i in range(5):
            tracker2.record(
                operation="scan",
                target_path=f"/project/{i}",
                files_processed=10,
                latency_ms=100,
            )
        for i in range(3):
            tracker2.record(
                operation="context",
                target_path=f"/theme/{i}",
                files_processed=3,
                latency_ms=30,
            )
        tracker2.close()

        savings = get_savings(period="all", db_path=tmp_db2)
        check("savings has period", savings["period"] == "all")
        check("savings has totals", "totals" in savings)
        check("savings has by_operation", "by_operation" in savings)
        check("savings has daily", "daily" in savings)

        t = savings["totals"]
        check("total_ops = 8", t["total_ops"] == 8, f"got {t['total_ops']}")
        check("local_ops = 8 (all local)", t["local_ops"] == 8)
        check("local_rate = 100%", t["local_rate_pct"] == 100.0)
        check("baseline_usd > 0", t["baseline_usd"] > 0)
        check("actual_usd = 0 (all local)", t["actual_usd"] == 0.0)
        check("saved_usd = baseline_usd", t["saved_usd"] == t["baseline_usd"])
        check("savings_pct = 100%", t["savings_pct"] == 100.0)

        ops = savings["by_operation"]
        check("2 operation groups", len(ops) == 2, f"got {len(ops)}")
        check("scan is top saver", ops[0]["operation"] == "scan")
    finally:
        if tmp_db2.exists():
            tmp_db2.unlink()

    # Empty DB case
    empty_savings = get_savings(period="week", db_path=Path("/nonexistent.db"))
    check("nonexistent DB returns empty", empty_savings["totals"]["total_ops"] == 0)

    # === GROUP 6: Dashboard Formatting ===
    print("\n--- GROUP 6: Dashboard Formatting ---")
    tmp_db3 = Path(tempfile.mktemp(suffix=".db"))
    try:
        tracker3 = UsageTracker(db_path=tmp_db3)
        for i in range(10):
            tracker3.record(
                operation="scan" if i % 2 == 0 else "check",
                target_path=f"/file/{i}",
                files_processed=5,
                latency_ms=50,
            )
        tracker3.close()

        from tracking.savings import get_savings as _gs
        data = _gs(period="all", db_path=tmp_db3)
        compact = format_compact(data)
        check("compact has 'Kiwi Savings'", "Kiwi Savings" in compact)
        check("compact has 'Operations:'", "Operations:" in compact)
        check("compact has 'Saved:'", "Saved:" in compact)
        check("compact has 'Top operations:'", "Top operations:" in compact)

        detail = format_detail(data)
        check("detail longer than compact", len(detail) > len(compact))
        check("detail has 'Per-operation breakdown'", "Per-operation breakdown" in detail)
    finally:
        if tmp_db3.exists():
            tmp_db3.unlink()

    # === GROUP 7: Schema Integrity ===
    print("\n--- GROUP 7: Schema Integrity ---")
    tmp_db4 = Path(tempfile.mktemp(suffix=".db"))
    try:
        conn = sqlite3.connect(str(tmp_db4))
        schema_sql = (KIWI_DIR / "tracking" / "schema.sql").read_text(encoding="utf-8")
        conn.executescript(schema_sql)

        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        check("usage_events table created", "usage_events" in table_names)

        views = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='view'"
        ).fetchall()
        view_names = [v[0] for v in views]
        check("savings_daily view created", "savings_daily" in view_names)
        check("savings_cumulative view created", "savings_cumulative" in view_names)

        cols = conn.execute("PRAGMA table_info(usage_events)").fetchall()
        col_names = [c[1] for c in cols]
        expected_cols = [
            "id", "timestamp", "session_id", "operation", "sub_operation",
            "target_path", "tokens_local", "tokens_claude", "cost_actual_usd",
            "latency_ms", "tokens_baseline", "cost_baseline_usd",
            "latency_baseline_ms", "violations_found", "files_processed", "success",
        ]
        for col in expected_cols:
            check(f"column '{col}' exists", col in col_names, f"missing from {col_names}")

        conn.close()
    finally:
        if tmp_db4.exists():
            tmp_db4.unlink()

    # === GROUP 8: Pricing Reuse ===
    print("\n--- GROUP 8: Pricing Reuse (no duplication) ---")
    from agent.cost import PRICING as agent_pricing
    from tracking.baseline_estimator import _PRICING as tracker_pricing

    check("tracker uses agent/cost.py PRICING", tracker_pricing == agent_pricing[BASELINE_MODEL])

    # === SUMMARY ===
    print(f"\n{'=' * 60}")
    print(f"RESULTS: {passed} passed, {failed} failed")
    print(f"{'=' * 60}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())