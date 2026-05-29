"""Extract lesson candidates from before/after diffs."""

import re
import difflib
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from memory.db import get_connection, get_suggested_lessons


_PATTERNS_CACHE = {"compiled": None, "loaded_at": 0.0, "mtime": 0.0}
_PATTERNS_TTL = 300  # 5 minutes — lessons rarely change mid-session
_REGEX_TIMEOUT_BYTES = 200 * 1024  # cap input size before regex search


def _log_err(stage: str, exc: BaseException) -> None:
    """Record fix_extractor failures so silent breakage is visible."""
    try:
        kiwi_dir = Path(__file__).parent.parent.parent
        db_path = kiwi_dir / "memory" / "reasoning.db"
        if not db_path.exists():
            return
        conn = sqlite3.connect(str(db_path), timeout=5)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS learning_health ("
            "stage TEXT PRIMARY KEY, fail_count INTEGER DEFAULT 0, "
            "last_failure_at REAL, last_error TEXT)"
        )
        conn.execute(
            "INSERT INTO learning_health (stage, fail_count, last_failure_at, last_error) "
            "VALUES (?, 1, ?, ?) ON CONFLICT(stage) DO UPDATE SET "
            "fail_count = fail_count + 1, last_failure_at = excluded.last_failure_at, "
            "last_error = excluded.last_error",
            (f"fix_extractor.{stage}", time.time(), f"{type(exc).__name__}: {exc}"[:500]),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _get_existing_patterns() -> list:
    """Load all existing Kiwi lesson patterns (compiled, cached, validated).

    Returns list of (raw_pattern, compiled_re_or_None). Bad regex are stored
    with compiled=None so _has_conflict can skip them without re-compiling.
    """
    lessons_dir = Path(__file__).parent.parent.parent / "lessons"
    if not lessons_dir.exists():
        return []

    try:
        dir_mtime = max(
            (f.stat().st_mtime for f in lessons_dir.rglob("*.md")),
            default=0.0,
        )
    except OSError:
        dir_mtime = 0.0

    now = time.time()
    cached = _PATTERNS_CACHE["compiled"]
    if (
        cached is not None
        and (now - _PATTERNS_CACHE["loaded_at"]) < _PATTERNS_TTL
        and abs(dir_mtime - _PATTERNS_CACHE["mtime"]) < 1e-6
    ):
        return cached

    out = []
    for f in lessons_dir.rglob("*.md"):
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        m = re.search(r"^pattern:\s*(.+)$", text, re.MULTILINE)
        if not m:
            continue
        raw = m.group(1).strip()
        try:
            compiled = re.compile(raw)
        except re.error:
            compiled = None
        out.append((raw, compiled))

    _PATTERNS_CACHE.update({"compiled": out, "loaded_at": now, "mtime": dir_mtime})
    return out


def _is_regex_able(code: str) -> bool:
    """Check if the bad code snippet can be expressed as a regex pattern."""
    if not code.strip():
        return False
    indicators = [
        r"\$_GET", r"\$_POST", r"\$_REQUEST", r"\$_COOKIE",
        r"echo\s+\$", r"mysql_", r"eval\s*\(", r"base64_decode",
        r"<\?php", r"innerHTML\s*=", r"document\.write",
        r"SELECT.*FROM", r"INSERT.*INTO", r"UPDATE.*SET",
    ]
    return any(re.search(p, code, re.IGNORECASE) for p in indicators)


def _has_conflict(bad_lines: list, existing_patterns: list) -> bool:
    """Return True if bad code already matches an existing lesson pattern.

    Uses pre-compiled patterns; truncates input to bound regex work
    (defense against ReDoS via untrusted lesson patterns).
    """
    bad_text = "\n".join(bad_lines)
    if len(bad_text) > _REGEX_TIMEOUT_BYTES:
        bad_text = bad_text[:_REGEX_TIMEOUT_BYTES]
    for raw, compiled in existing_patterns:
        if compiled is None:
            continue
        try:
            if compiled.search(bad_text):
                return True
        except re.error:
            continue
    return False


def _safe_truncate_then_escape(raw: str, max_raw: int = 60) -> str:
    """Truncate raw string FIRST, then re.escape — never split a backslash sequence.

    BUG #20: ``re.escape(s)[:120]`` may slice between ``\`` and the next char,
    producing a dangling backslash that re.compile rejects. Truncating before
    escaping avoids that entirely.
    """
    truncated = raw[:max_raw]
    pattern = re.escape(truncated)
    try:
        re.compile(pattern)
    except re.error:
        pattern = re.escape(truncated.rstrip("\\"))
    return pattern


def _infer_category(bad_lines: list, file_path: str) -> str:
    bad_text = "\n".join(bad_lines).lower()
    if any(k in bad_text for k in ["$_get", "$_post", "$_request", "eval(", "base64_decode"]):
        return "security"
    if any(k in bad_text for k in ["select ", "insert ", "update ", "delete "]):
        return "security"
    if any(k in bad_text for k in ["echo $", "print $", "innerhtml"]):
        return "security"
    if any(k in bad_text for k in ["mysql_", "deprecated"]):
        return "deprecated"
    if file_path.endswith(".css") or file_path.endswith(".scss"):
        return "css"
    if file_path.endswith(".js") or file_path.endswith(".ts"):
        return "javascript"
    return "general"


def _ensure_suggested_unique_index(conn) -> None:
    """Create unique index so upsert is atomic across concurrent hooks (BUG #18)."""
    try:
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_sl_pattern_status "
            "ON suggested_lessons(pattern, status)"
        )
    except Exception as e:
        _log_err("ensure_unique_index", e)


def extract_lesson_candidate(
    before_content: str,
    after_content: str,
    file_path: str,
    theme_slug: str = "",
) -> Optional[dict]:
    """
    Extract lesson candidate from a before/after diff.
    Returns candidate dict if confidence >= 0.5, else None.
    """
    diff = list(difflib.unified_diff(
        before_content.splitlines(),
        after_content.splitlines(),
        lineterm="",
    ))

    bad_lines = [l[1:] for l in diff if l.startswith("-") and not l.startswith("---")]
    good_lines = [l[1:] for l in diff if l.startswith("+") and not l.startswith("+++")]

    if not bad_lines or not good_lines:
        return None

    bad_code = "\n".join(bad_lines).strip()
    good_code = "\n".join(good_lines).strip()

    if len(bad_code) < 5 or len(good_code) < 5:
        return None

    confidence = 0.0

    regex_able = _is_regex_able(bad_code)
    if regex_able:
        confidence += 0.3

    pattern_fragment = bad_code[:50]
    try:
        conn = get_connection()
        existing_freq = conn.execute(
            "SELECT frequency FROM suggested_lessons WHERE pattern LIKE ? AND status = 'pending' LIMIT 1",
            (f"{pattern_fragment[:30]}%",),
        ).fetchone()
        conn.close()
    except Exception as e:
        _log_err("read_existing_freq", e)
        existing_freq = None
    if existing_freq and (existing_freq[0] or 0) >= 3:
        confidence += 0.2

    meaningful_good = [l for l in good_lines if l.strip()]
    consistent = len(meaningful_good) > 0 and len(good_lines) <= len(bad_lines) * 3
    if consistent:
        confidence += 0.3

    existing_patterns = _get_existing_patterns()
    no_conflict = not _has_conflict(bad_lines, existing_patterns)
    if no_conflict:
        confidence += 0.2

    if confidence < 0.5:
        return None

    first_bad = bad_lines[0].strip()
    pattern = _safe_truncate_then_escape(first_bad, max_raw=60)

    category = _infer_category(bad_lines, file_path)
    severity = "HIGH" if category == "security" else "SUGGEST"

    example_line = 1
    for i, line in enumerate(before_content.splitlines(), 1):
        if line.strip() == bad_lines[0].strip():
            example_line = i
            break

    candidate = {
        "pattern": pattern,
        "scope": "**/*.php" if file_path.endswith(".php") else f"**/*{Path(file_path).suffix}",
        "category": category,
        "severity": severity,
        "example_file": file_path,
        "example_line": example_line,
        "example_code": bad_code[:500],
        "good_code": good_code[:500],
        "confidence_score": round(confidence, 2),
        "theme_slug": theme_slug,
    }

    try:
        conn = get_connection()
        _ensure_suggested_unique_index(conn)
        cursor = conn.execute(
            """
            INSERT INTO suggested_lessons
                (pattern, scope, category, severity, example_file, example_line,
                 example_code, good_code, suggested_at, status, confidence_score, frequency)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, 1)
            ON CONFLICT(pattern, status) DO UPDATE SET
                frequency = frequency + 1,
                confidence_score = excluded.confidence_score,
                good_code = excluded.good_code
            """,
            (
                candidate["pattern"],
                candidate["scope"],
                candidate["category"],
                candidate["severity"],
                candidate["example_file"],
                candidate["example_line"],
                candidate["example_code"],
                good_code[:500],
                datetime.now(timezone.utc).isoformat(),
                round(confidence, 2),
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id FROM suggested_lessons WHERE pattern = ? AND status = 'pending'",
            (candidate["pattern"],),
        ).fetchone()
        candidate["id"] = row[0] if row else None
        conn.close()
    except Exception as e:
        _log_err("upsert_suggestion", e)
        return None

    return candidate


# ── Phase 4: Auto-promote ────────────────────────────────────────────────────

_MIN_APPROVED_LESSONS = 50
_MIN_CONFIDENCE = 0.8
_MIN_FREQUENCY = 3
_QUARANTINE_DAYS = 7
_QUARANTINE_SCANS = 5  # clean scans required before lesson is active in generation


def _count_approved_lessons() -> int:
    """Count manually approved lessons (status='approved') in DB."""
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) FROM suggested_lessons WHERE status = 'approved'"
    ).fetchone()
    conn.close()
    return row[0] if row else 0


def _create_lesson_file(candidate: dict) -> Optional[str]:
    """
    Call kiwi_add to create a real lesson file from a candidate.
    Returns the new lesson_id on success, None on failure.

    SAFETY: This function spawns a subprocess (timeout 10s). DO NOT call from
    PostToolUse hooks — only from batch contexts like auto_promote_candidates().
    """
    try:
        import subprocess, sys
        kiwi_dir = Path(__file__).parent.parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "tools.add",
             "--category", candidate.get("category", "general"),
             "--severity", candidate.get("severity", "SUGGEST"),
             "--title", f"Auto: {candidate['pattern'][:60]}",
             "--pattern", candidate["pattern"],
             "--scope", candidate.get("scope", "**/*.php"),
             "--why", "Auto-promoted by learning loop (confidence>=0.8, frequency>=3)",
             "--bad-code", candidate.get("example_code", ""),
             "--good-code", candidate.get("good_code", ""),
             ],
            cwd=str(kiwi_dir),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            m = re.search(r"\b(LES|FEA|SEC)-\d+\b", result.stdout)
            if m:
                return m.group(0)
        else:
            _log_err("create_lesson_file_rc", RuntimeError(f"rc={result.returncode} stderr={result.stderr[:200]}"))
    except subprocess.TimeoutExpired as e:
        _log_err("create_lesson_file_timeout", e)
    except Exception as e:
        _log_err("create_lesson_file", e)
    return None


def auto_promote_candidates() -> dict:
    """
    Phase 4 auto-promotion loop.

    Conditions to promote a pending candidate:
      1. >= _MIN_APPROVED_LESSONS manually approved lessons exist (safety gate)
      2. candidate.confidence_score >= _MIN_CONFIDENCE
      3. pattern appears >= _MIN_FREQUENCY times (tracked via frequency column)

    Promoted lessons are quarantined: must pass _QUARANTINE_DAYS days AND
    _QUARANTINE_SCANS clean scans before being active in generation.
    Returns summary dict: {promoted, skipped_gate, skipped_confidence, skipped_frequency}.
    """
    result = {
        "promoted": [],
        "skipped_gate": 0,
        "skipped_confidence": 0,
        "skipped_frequency": 0,
    }

    approved_count = _count_approved_lessons()
    if approved_count < _MIN_APPROVED_LESSONS:
        result["skipped_gate"] = 1
        return result

    conn = get_connection()
    rows = conn.execute(
        """SELECT id, pattern, scope, category, severity,
                  example_file, example_line, example_code,
                  confidence_score, frequency
           FROM suggested_lessons
           WHERE status = 'pending'
           ORDER BY confidence_score DESC, frequency DESC"""
    ).fetchall()
    conn.close()

    for row in rows:
        row = dict(row)
        confidence = row.get("confidence_score") or 0.0
        frequency = row.get("frequency") or 1

        if confidence < _MIN_CONFIDENCE:
            result["skipped_confidence"] += 1
            continue

        if frequency < _MIN_FREQUENCY:
            result["skipped_frequency"] += 1
            continue

        lesson_id = _create_lesson_file(row)
        if not lesson_id:
            continue

        quarantine_until = (
            datetime.now(timezone.utc) + timedelta(days=_QUARANTINE_DAYS)
        ).isoformat()

        conn = get_connection()
        conn.execute(
            """UPDATE suggested_lessons
               SET status = 'auto_approved',
                   lesson_id = ?,
                   quarantine_until = ?
               WHERE id = ?""",
            (lesson_id, quarantine_until, row["id"]),
        )
        conn.commit()
        conn.close()

        result["promoted"].append({
            "suggestion_id": row["id"],
            "lesson_id": lesson_id,
            "pattern": row["pattern"][:60],
            "quarantine_until": quarantine_until,
        })

    return result


def is_quarantined(lesson_id: str) -> bool:
    """
    Return True if the lesson is still within its quarantine window.
    Both conditions must pass to exit quarantine:
      - quarantine_until date has passed (_QUARANTINE_DAYS)
      - clean_scan_count >= _QUARANTINE_SCANS
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT quarantine_until, clean_scan_count FROM suggested_lessons WHERE lesson_id = ? AND status = 'auto_approved'",
        (lesson_id,),
    ).fetchone()
    conn.close()
    if not row or not row[0]:
        return False
    try:
        until = datetime.fromisoformat(row[0])
        time_ok = datetime.now(timezone.utc) >= until
        scans_ok = (row[1] or 0) >= _QUARANTINE_SCANS
        return not (time_ok and scans_ok)
    except ValueError:
        return False


def record_clean_scan(lesson_id: str):
    """Increment clean_scan_count for a quarantined lesson after a scan with no violations."""
    conn = get_connection()
    conn.execute(
        "UPDATE suggested_lessons SET clean_scan_count = clean_scan_count + 1 WHERE lesson_id = ? AND status = 'auto_approved'",
        (lesson_id,),
    )
    conn.commit()
    conn.close()
