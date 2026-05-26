"""Kiwi Self-Scoring Confidence System.

Each tool output gets a confidence score (0-100) appended at the end.
Helps Claude decide: TRUST (code now) vs REVIEW (research more).

Adaptive: learns from feedback — if Kiwi scores high but outcome was bad,
weights auto-adjust downward for that tool. Vice versa.
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))


# --- Adaptive Weight Cache ---

_weight_cache: Dict[str, Dict[str, float]] = {}
_weight_cache_ts: float = 0
_WEIGHT_CACHE_TTL = 300  # 5 min

_DEFAULT_WEIGHTS = {
    "search":  {"coverage": 0.4, "relevance": 0.3, "completeness": 0.3},
    "context": {"task_match": 0.3, "signal_match": 0.3, "history": 0.2, "freshness": 0.2},
    "scan":    {"pattern_coverage": 0.3, "fp_risk": 0.4, "scan_depth": 0.3},
    "check":   {"pattern_coverage": 0.3, "file_complexity": 0.3, "lesson_confidence": 0.4},
    "fix":     {"fix_safety": 0.6, "side_effect": 0.4},
    "query":   {"relevance": 0.6, "coverage": 0.4},
    "agent":   {"iteration_depth": 0.2, "fix_rate": 0.4, "remaining_risk": 0.4},
}


def _get_weights(tool: str) -> Dict[str, float]:
    """Get adaptive weights for a tool, calibrated from scoring_feedback history."""
    import time
    global _weight_cache, _weight_cache_ts

    if time.time() - _weight_cache_ts < _WEIGHT_CACHE_TTL and tool in _weight_cache:
        return _weight_cache[tool]

    weights = dict(_DEFAULT_WEIGHTS.get(tool, {}))

    try:
        from memory.db import get_connection
        conn = get_connection()
        try:
            rows = conn.execute("""
                SELECT score_given, outcome
                FROM scoring_feedback
                WHERE tool = ? AND outcome IS NOT NULL
                ORDER BY scored_at DESC
                LIMIT 50
            """, (tool,)).fetchall()
        finally:
            conn.close()

        if len(rows) >= 5:
            overconfident = sum(1 for r in rows if r["score_given"] >= 80 and r["outcome"] == "bad")
            underconfident = sum(1 for r in rows if r["score_given"] < 50 and r["outcome"] == "good")
            total = len(rows)

            if overconfident / total > 0.3:
                for k in weights:
                    weights[k] *= 0.85
            elif underconfident / total > 0.3:
                for k in weights:
                    weights[k] = min(1.0, weights[k] * 1.15)

    except Exception as e:
        print(f"[kiwi] _get_weights DB error: {e}", file=sys.stderr)

    _weight_cache[tool] = weights
    _weight_cache_ts = time.time()
    return weights


def log_score(tool: str, score: int, label: str):
    """Log a scoring event for later feedback."""
    try:
        from memory.db import get_connection
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO scoring_feedback (tool, score_given, action_label) VALUES (?, ?, ?)",
                (tool, score, label)
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print(f"[kiwi] log_score error: {e}", file=sys.stderr)


def record_feedback(tool: str, outcome: str, detail: str = ""):
    """Record outcome feedback for the most recent scoring of this tool.

    outcome: 'good' (score was accurate) or 'bad' (score was wrong)
    """
    try:
        from memory.db import get_connection
        conn = get_connection()
        try:
            conn.execute("""
                UPDATE scoring_feedback
                SET outcome = ?, outcome_detail = ?
                WHERE id = (
                    SELECT id FROM scoring_feedback
                    WHERE tool = ? AND outcome IS NULL
                    ORDER BY scored_at DESC LIMIT 1
                )
            """, (outcome, detail, tool))
            conn.commit()
        finally:
            conn.close()
        global _weight_cache_ts
        _weight_cache_ts = 0
    except Exception as e:
        print(f"[kiwi] record_feedback error: {e}", file=sys.stderr)


def get_accuracy_stats(tool: str = None) -> Dict:
    """Get scoring accuracy stats for calibration review."""
    try:
        from memory.db import get_connection
        conn = get_connection()
        try:
            where = "WHERE tool = ?" if tool else ""
            params = (tool,) if tool else ()

            rows = conn.execute(f"""
                SELECT tool, score_given, outcome
                FROM scoring_feedback
                WHERE outcome IS NOT NULL
                {("AND tool = ?" if tool else "")}
                ORDER BY scored_at DESC
                LIMIT 200
            """, params).fetchall()
        finally:
            conn.close()

        if not rows:
            return {"total": 0, "message": "No feedback data yet"}

        total = len(rows)
        accurate = sum(1 for r in rows
                      if (r["score_given"] >= 70 and r["outcome"] == "good")
                      or (r["score_given"] < 70 and r["outcome"] == "bad"))
        overconfident = sum(1 for r in rows if r["score_given"] >= 80 and r["outcome"] == "bad")
        underconfident = sum(1 for r in rows if r["score_given"] < 50 and r["outcome"] == "good")

        return {
            "total": total,
            "accuracy": round(accurate / total * 100, 1),
            "overconfident": overconfident,
            "underconfident": underconfident,
            "calibration": "good" if accurate / total > 0.7 else "needs_adjustment",
        }
    except Exception as e:
        return {"total": 0, "error": f"DB not available: {e}"}


# --- Action Labels ---

def get_action_label(score: int) -> Tuple[str, str]:
    if score >= 90:
        return "TRUST", "code luon"
    elif score >= 70:
        return "USE_WITH_CARE", "dung duoc, verify edge cases"
    elif score >= 50:
        return "REVIEW", "can research them truoc khi dung"
    else:
        return "UNRELIABLE", "khong dang tin, research doc lap"


# --- Format ---

def format_confidence(score: int, dimensions: Dict[str, int], hints: List[str] = None, tool: str = None) -> str:
    score = max(0, min(100, score))
    label, advice = get_action_label(score)

    # Auto-log for adaptive learning
    if tool:
        log_score(tool, score, label)

    lines = [
        "",
        "---",
        f"Kiwi Confidence: {score}/100",
    ]

    dim_items = list(dimensions.items())
    for i, (name, val) in enumerate(dim_items):
        prefix = "└─" if i == len(dim_items) - 1 and not hints else "├─"
        lines.append(f"{prefix} {name}: {val}")

    if hints:
        for i, hint in enumerate(hints):
            prefix = "└─" if i == len(hints) - 1 else "├─"
            lines.append(f"{prefix} Tip: {hint}")

    lines.append(f"Action: {label} — {advice}")

    return "\n".join(lines)


# --- 1. kiwi_search ---

def score_search(
    query: str,
    path: str,
    matches: list,
    rg_returncode: int,
    file_types: list,
) -> Tuple[int, Dict[str, int], List[str]]:
    hints = []

    # Coverage: did we scan the right place?
    coverage = 100
    if not os.path.isdir(path):
        coverage = 10
        hints.append("path khong ton tai")
    elif rg_returncode not in (0, 1):
        coverage -= 40
        hints.append("ripgrep gap loi khi scan")

    # Count target files exist
    if os.path.isdir(path):
        target_count = 0
        for ft in file_types:
            target_count += len(list(Path(path).rglob(f"*.{ft}")))
        if target_count == 0:
            coverage = 20
            hints.append(f"khong co file .{'/'.join(file_types)} trong path")

    # Relevance: do results contain query terms?
    relevance = 100
    if not matches:
        relevance = 0 if rg_returncode == 1 else 30
    else:
        query_terms = [t.strip() for t in query.split("|") if t.strip()]
        if query_terms:
            all_text = " ".join(matches).lower()
            matched_terms = sum(1 for t in query_terms if t.lower() in all_text)
            relevance = int(matched_terms / len(query_terms) * 100)

    # Completeness: any encoding issues?
    completeness = 100
    all_text = " ".join(matches) if matches else ""
    if "Ã" in all_text or "â€" in all_text or "�" in all_text:
        completeness -= 40
        hints.append("encoding loi, co the sot ket qua Unicode")
    if rg_returncode == 2:
        completeness -= 30

    w = _get_weights("search")
    score = int(coverage * w["coverage"] + relevance * w["relevance"] + completeness * w["completeness"])
    dims = {"Coverage": coverage, "Relevance": relevance, "Completeness": completeness}
    return score, dims, hints


# --- 2. kiwi_context ---

def score_context(ctx: dict) -> Tuple[int, Dict[str, int], List[str]]:
    hints = []

    # Task match: did task map to specific categories?
    task_cats = ctx.get("task_categories", [])
    task_match = 90 if task_cats else 40
    if not task_cats:
        hints.append("task khong map duoc category cu the, ket qua generic")

    # Signal match: was target_file provided and matched?
    signal_rules = ctx.get("signal_matched_rules", 0)
    if signal_rules > 0:
        signal_match = min(100, 60 + signal_rules * 5)
    elif ctx.get("target_file"):
        signal_match = 60
        hints.append("target_file co nhung khong match pattern nao")
    else:
        signal_match = 40
        hints.append("thieu target_file, nen cung cap file dang edit")

    # History: project has scan data?
    history_boosted = ctx.get("history_boosted", 0)
    if history_boosted > 0:
        history = min(100, 60 + history_boosted * 5)
    else:
        history = 50
        hints.append("project chua co scan history, chay kiwi_scan truoc")

    # Freshness: rules count
    rules_count = ctx.get("rules_count", 0)
    freshness = min(100, rules_count * 10) if rules_count > 0 else 20

    w = _get_weights("context")
    score = int(task_match * w["task_match"] + signal_match * w["signal_match"] + history * w["history"] + freshness * w["freshness"])
    dims = {"Task Match": task_match, "Signal Match": signal_match, "History": history, "Freshness": freshness}
    return score, dims, hints


# --- 3. kiwi_scan ---

def score_scan(
    violations_count: int,
    files_scanned: int,
    total_patterns: int,
    critical_count: int = 0,
    high_count: int = 0,
    low_confidence_violations: int = 0,
) -> Tuple[int, Dict[str, int], List[str]]:
    hints = []

    # Pattern coverage: how many lessons were loaded?
    pattern_coverage = min(100, int(total_patterns / 4 * 100 / 100))  # expect ~400
    if total_patterns < 100:
        hints.append(f"chi {total_patterns} patterns loaded, co the thieu lessons")

    # FP risk: low confidence lessons in violations
    fp_risk = 100
    if violations_count > 0 and low_confidence_violations > 0:
        fp_ratio = low_confidence_violations / violations_count
        fp_risk = max(20, int(100 - fp_ratio * 80))
        if fp_ratio > 0.3:
            hints.append(f"{low_confidence_violations}/{violations_count} violations tu lessons confidence thap")

    # Scan depth
    scan_depth = 100
    if files_scanned == 0:
        scan_depth = 0
        hints.append("khong co file nao duoc scan")
    elif files_scanned < 5:
        scan_depth = 60
        hints.append(f"chi scan {files_scanned} files, co the chua du")

    w = _get_weights("scan")
    score = int(pattern_coverage * w["pattern_coverage"] + fp_risk * w["fp_risk"] + scan_depth * w["scan_depth"])
    dims = {"Pattern Coverage": pattern_coverage, "FP Risk": fp_risk, "Scan Depth": scan_depth}
    return score, dims, hints


# --- 4. kiwi_check ---

def score_check(
    violations: list,
    file_path: str,
    total_patterns: int,
) -> Tuple[int, Dict[str, int], List[str]]:
    hints = []

    # Pattern coverage
    pattern_coverage = min(100, int(total_patterns / 4 * 100 / 100))

    # File complexity
    file_complexity = 100
    try:
        line_count = len(Path(file_path).read_text(encoding="utf-8", errors="replace").splitlines())
        if line_count > 500:
            file_complexity = 70
            hints.append(f"file {line_count} dong, file lon co the co loi ma pattern chua cover")
        elif line_count > 300:
            file_complexity = 85
    except (OSError, IOError):
        file_complexity = 50
        hints.append("khong doc duoc file de danh gia complexity")

    # Lesson confidence for matched violations
    lesson_conf = 100
    if violations:
        low_conf = sum(1 for v in violations if v.get("confidence", 1.0) < 0.5)
        if low_conf > 0:
            lesson_conf = max(40, 100 - low_conf * 20)
            hints.append(f"{low_conf} violations tu lessons confidence thap, co the false positive")

    w = _get_weights("check")
    score = int(pattern_coverage * w["pattern_coverage"] + file_complexity * w["file_complexity"] + lesson_conf * w["lesson_confidence"])
    dims = {"Pattern Coverage": pattern_coverage, "File Complexity": file_complexity, "Lesson Confidence": lesson_conf}
    return score, dims, hints


# --- 5. kiwi_fix ---

def score_fix(
    lesson_id: str,
    file_path: str,
    applied: bool,
    confidence: float = 1.0,
    has_good_code: bool = True,
) -> Tuple[int, Dict[str, int], List[str]]:
    hints = []

    # Fix safety: based on lesson confidence + has good example
    fix_safety = int(confidence * 100)
    if not has_good_code:
        fix_safety = max(20, fix_safety - 30)
        hints.append("lesson khong co good code example, fix co the khong chinh xac")
    if confidence < 0.5:
        hints.append("lesson confidence thap, review fix truoc khi accept")

    # Side effect risk: check file size as proxy
    side_effect = 100
    try:
        line_count = len(Path(file_path).read_text(encoding="utf-8", errors="replace").splitlines())
        if line_count > 500:
            side_effect = 70
            hints.append("file lon, fix co the anh huong nhieu cho khac")
        elif line_count > 300:
            side_effect = 85
    except (OSError, IOError):
        side_effect = 60

    if not applied:
        hints.append("preview only, chua apply")

    w = _get_weights("fix")
    score = int(fix_safety * w["fix_safety"] + side_effect * w["side_effect"])
    dims = {"Fix Safety": fix_safety, "Side Effect Risk": side_effect}
    return score, dims, hints


# --- 6. kiwi_query ---

def score_query(
    keyword: str,
    results: list,
) -> Tuple[int, Dict[str, int], List[str]]:
    hints = []

    if not results:
        return 0, {"Relevance": 0, "Coverage": 0}, ["khong tim thay ket qua nao"]

    # Relevance: how many results match keyword in title/description
    keyword_lower = keyword.lower()
    exact_matches = 0
    for r in results:
        title = (r.get("description") or r.get("title", "")).lower()
        if keyword_lower in title:
            exact_matches += 1

    relevance = min(100, int(exact_matches / max(1, len(results)) * 100) + 20)
    if exact_matches == 0:
        hints.append("khong co result nao match keyword trong title")

    # Coverage: enough results?
    coverage = min(100, len(results) * 15)
    if len(results) < 3:
        hints.append(f"chi {len(results)} ket qua, keyword co the qua hep")

    w = _get_weights("query")
    score = int(relevance * w["relevance"] + coverage * w["coverage"])
    dims = {"Relevance": relevance, "Coverage": coverage}
    return score, dims, hints


# --- 7. kiwi_agent ---

def score_agent(report: dict) -> Tuple[int, Dict[str, int], List[str]]:
    hints = []

    scans = report.get("scans", 0)
    found = report.get("violations_found", 0)
    fixed = report.get("fixes_applied", 0)
    remaining = report.get("violations_remaining", 0)

    # Iteration depth
    iteration_depth = min(100, scans * 25)
    if scans < 2:
        hints.append("chi 1 vong scan, co the chua du de phat hien het")

    # Fix rate
    fix_rate = int(fixed / max(1, found) * 100) if found > 0 else 100

    # Remaining risk
    remaining_risk = 100
    if found > 0:
        remaining_risk = max(0, 100 - int(remaining / found * 100))
    if remaining > 0:
        hints.append(f"con {remaining} violations chua fix")

    w = _get_weights("agent")
    score = int(iteration_depth * w["iteration_depth"] + fix_rate * w["fix_rate"] + remaining_risk * w["remaining_risk"])
    dims = {"Iteration Depth": iteration_depth, "Fix Rate": fix_rate, "Remaining Risk": remaining_risk}
    return score, dims, hints