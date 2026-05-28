"""Extract lesson candidates from before/after diffs."""

import re
import difflib
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from memory.db import get_connection, get_suggested_lessons


def _get_existing_patterns() -> list[str]:
    """Load all existing Kiwi lesson patterns for conflict check."""
    lessons_dir = Path(__file__).parent.parent.parent / "lessons"
    patterns = []
    for f in lessons_dir.rglob("*.md"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"^pattern:\s*(.+)$", text, re.MULTILINE)
        if m:
            patterns.append(m.group(1).strip())
    return patterns


def _is_regex_able(code: str) -> bool:
    """Check if the bad code snippet can be expressed as a regex pattern."""
    if not code.strip():
        return False
    # Heuristic: contains a recognizable PHP/JS/CSS token that can be matched
    indicators = [
        r"\$_GET", r"\$_POST", r"\$_REQUEST", r"\$_COOKIE",
        r"echo\s+\$", r"mysql_", r"eval\s*\(", r"base64_decode",
        r"<\?php", r"innerHTML\s*=", r"document\.write",
        r"SELECT.*FROM", r"INSERT.*INTO", r"UPDATE.*SET",
    ]
    return any(re.search(p, code, re.IGNORECASE) for p in indicators)


def _has_conflict(bad_lines: list[str], existing_patterns: list[str]) -> bool:
    """Return True if bad code already matches an existing lesson pattern."""
    bad_text = "\n".join(bad_lines)
    for pat in existing_patterns:
        try:
            if re.search(pat, bad_text):
                return True
        except re.error:
            pass
    return False


def _infer_category(bad_lines: list[str], file_path: str) -> str:
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

    # Build confidence score from 4 signals
    confidence = 0.0

    regex_able = _is_regex_able(bad_code)
    if regex_able:
        confidence += 0.3

    # frequency signal: will be tracked via DB upsert (frequency column)
    # check existing DB count as a proxy before first insert
    pattern_fragment = bad_code[:50]
    conn = get_connection()
    existing_freq = conn.execute(
        "SELECT frequency FROM suggested_lessons WHERE pattern LIKE ? AND status = 'pending' LIMIT 1",
        (f"{pattern_fragment[:30]}%",),
    ).fetchone()
    conn.close()
    if existing_freq and (existing_freq[0] or 0) >= 3:
        confidence += 0.2

    # consistent: good_lines are non-trivial (not just whitespace changes)
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

    # Build a simple regex pattern from the first bad line
    first_bad = bad_lines[0].strip()
    # Escape for regex but keep common wildcards readable
    pattern = re.escape(first_bad)[:120]

    category = _infer_category(bad_lines, file_path)
    severity = "HIGH" if category == "security" else "SUGGEST"

    # Find approximate line number of first bad line in before_content
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

    # Insert into suggested_lessons (upsert: increment frequency if same pattern exists)
    conn = get_connection()
    existing = conn.execute(
        "SELECT id, frequency FROM suggested_lessons WHERE pattern = ? AND status = 'pending'",
        (candidate["pattern"],),
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE suggested_lessons SET frequency = frequency + 1, confidence_score = ?, good_code = ? WHERE id = ?",
            (round(confidence, 2), good_code[:500], existing["id"]),
        )
        conn.commit()
        candidate["id"] = existing["id"]
    else:
        conn.execute(
            """
            INSERT INTO suggested_lessons
                (pattern, scope, category, severity, example_file, example_line,
                 example_code, good_code, suggested_at, status, confidence_score, frequency)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, 1)
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
        candidate["id"] = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()

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
    """
    try:
        import subprocess, sys, json
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
            timeout=30,
        )
        if result.returncode == 0:
            m = re.search(r"\b(LES|FEA|SEC)-\d+\b", result.stdout)
            if m:
                return m.group(0)
    except Exception:
        pass
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
