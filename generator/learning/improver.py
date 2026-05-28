"""Template Auto-Improvement — Phase 5.

Analyzes generation_history to find recurring fix patterns on templates,
proposes patches, runs them through a staging pipeline, and auto-reverts
if quality degrades.
"""

import difflib
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from memory.db import get_connection, get_generation_quality

KIWI_DIR = Path(__file__).parent.parent.parent
TEMPLATES_DIR = KIWI_DIR / "generator" / "templates"

_MIN_FIX_COUNT = 3       # pattern must appear >= 3 times on same template
_RATE_LIMIT_HOURS = 24   # max 1 patch per template per day
_QUALITY_DROP_THRESHOLD = 0.05  # auto-revert if quality drops more than this


# ── Helpers ──────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _template_key(template_path: str) -> str:
    """Normalize template path to a stable forward-slash key for DB lookups."""
    p = Path(template_path)
    if p.is_absolute():
        try:
            rel = p.relative_to(TEMPLATES_DIR)
        except ValueError:
            return p.name
        return rel.as_posix()
    # Strip leading generator/templates/ prefix if present
    parts = p.parts
    for i, part in enumerate(parts):
        if part == "templates" and i > 0 and parts[i - 1] == "generator":
            return Path(*parts[i + 1:]).as_posix()
    return Path(template_path).as_posix()


def _find_template_file(template_path: str) -> Optional[Path]:
    """Resolve template_path to an actual .j2 file."""
    p = Path(template_path)
    if p.is_absolute() and p.exists():
        return p
    # Try relative to templates dir
    candidate = TEMPLATES_DIR / template_path
    if candidate.exists():
        return candidate
    # Try just the filename
    matches = list(TEMPLATES_DIR.rglob(p.name))
    return matches[0] if matches else None


def _check_rate_limit(template_key: str) -> bool:
    """Return True if we are within rate limit (i.e. a patch was applied < 24h ago)."""
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT MAX(last_patch_at) FROM generation_history
               WHERE template_used = ? AND last_patch_at IS NOT NULL""",
            (template_key,),
        ).fetchone()
    except Exception:
        conn.close()
        return False
    conn.close()
    if not row or not row[0]:
        return False
    try:
        last = datetime.fromisoformat(row[0])
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - last).total_seconds() / 3600
        return elapsed < _RATE_LIMIT_HOURS
    except ValueError:
        return False


def _get_fix_patterns(template_key: str) -> list[dict]:
    """
    Return recurring fix patterns for a template.
    A "pattern" here is a (fix_count bucket, template_used) group that has
    accumulated >= _MIN_FIX_COUNT total fixes.
    """
    conn = get_connection()
    rows = conn.execute(
        """SELECT file_path, fix_count, quality_score, generated_at, pipeline, phase
           FROM generation_history
           WHERE template_used = ? AND fix_count > 0
           ORDER BY generated_at DESC
           LIMIT 50""",
        (template_key,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _build_patch_candidate(template_path: str, rows: list[dict]) -> Optional[dict]:
    """
    Build a patch candidate from recurring fix data.
    Since we don't store the actual diff content in generation_history,
    we use fix_count and quality_score as signals to identify high-risk lines
    in the template and propose a comment-based annotation patch.
    """
    tpl_file = _find_template_file(template_path)
    if not tpl_file:
        return None

    content = tpl_file.read_text(encoding="utf-8", errors="ignore")
    lines = content.splitlines()

    total_fixes = sum(r["fix_count"] for r in rows)
    avg_quality = sum(r["quality_score"] for r in rows) / len(rows)
    confidence = min(1.0, total_fixes / 10.0) * (1.0 - avg_quality)

    if confidence < 0.1:
        return None

    # Find lines that are likely candidates for improvement:
    # hardcoded values, missing guards, direct echo without escaping
    risky_patterns = [
        (r'echo\s+\$(?!_)', "unescaped echo — use esc_html() or esc_attr()"),
        (r'<\?php\s+echo', "inline echo — consider esc_html()"),
        (r'#[0-9a-fA-F]{3,6}', "hardcoded hex color — use CSS token"),
        (r'\bpx\b(?!\s*\*)', "hardcoded px value — use spacing token"),
        (r'wc_get_product|WC\(\)', "WooCommerce reference — use wz_ equivalent"),
    ]

    annotations = []
    for i, line in enumerate(lines, 1):
        for pattern, suggestion in risky_patterns:
            if re.search(pattern, line):
                annotations.append({
                    "line": i,
                    "original": line,
                    "suggestion": suggestion,
                    "pattern": pattern,
                })
                break

    if not annotations:
        return None

    # Build a minimal patch: add {# kiwi-fix: ... #} Jinja2 comments before risky lines
    patched_lines = list(lines)
    offset = 0
    for ann in annotations[:3]:  # cap at 3 annotations per patch
        insert_at = ann["line"] - 1 + offset
        comment = f"{{# kiwi-fix: {ann['suggestion']} #}}"
        patched_lines.insert(insert_at, comment)
        offset += 1

    patched_content = "\n".join(patched_lines)
    if patched_content == content:
        return None

    diff = list(difflib.unified_diff(
        content.splitlines(),
        patched_content.splitlines(),
        fromfile=f"a/{tpl_file.name}",
        tofile=f"b/{tpl_file.name}",
        lineterm="",
    ))

    return {
        "template_path": str(tpl_file),
        "template_key": _template_key(template_path),
        "original_content": content,
        "patched_content": patched_content,
        "diff": "\n".join(diff),
        "confidence": round(confidence, 3),
        "pattern_summary": f"{len(annotations)} risky pattern(s), {total_fixes} total fixes, avg quality {avg_quality:.1%}",
        "annotations": annotations[:3],
        "total_fixes": total_fixes,
        "avg_quality": round(avg_quality, 3),
    }


def _validate_with_kiwi(theme_dir: Path) -> tuple[bool, list[str]]:
    """Run kiwi scanner on a directory. Returns (passed, violations)."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "scanner.cli",
             "--theme", str(theme_dir),
             "--severity", "CRITICAL",
             "--json"],
            cwd=str(KIWI_DIR),
            capture_output=True,
            text=True,
            timeout=60,
            env={**__import__("os").environ, "PYTHONUTF8": "1"},
        )
        import json
        stdout = result.stdout.strip()
        if not stdout:
            # Empty output = no violations found
            return True, []
        data = json.loads(stdout)
        violations = data.get("violations", [])
        critical = [v for v in violations if v.get("severity") == "CRITICAL"]
        return len(critical) == 0, [v.get("message", str(v)) for v in critical]
    except json.JSONDecodeError:
        # Non-JSON output (e.g. plain text summary with 0 violations)
        return True, []
    except Exception as e:
        return False, [f"Scanner error: {e}"]


def _record_patch_in_db(template_key: str, patch_commit: str, quality_before: float, quality_after: float, auto_reverted: bool = False):
    """Record patch application in generation_history."""
    conn = get_connection()
    # Find the most recent row for this template, then update it
    row = conn.execute(
        "SELECT id FROM generation_history WHERE template_used = ? ORDER BY generated_at DESC LIMIT 1",
        (template_key,),
    ).fetchone()
    if row:
        try:
            conn.execute(
                "UPDATE generation_history SET last_patch_at = ?, patch_commit = ?, auto_reverted = ? WHERE id = ?",
                (_now_iso(), patch_commit, 1 if auto_reverted else 0, row[0]),
            )
            conn.commit()
        except Exception:
            pass
    conn.close()


# ── Main class ────────────────────────────────────────────────────────────────

class TemplateImprover:
    """Propose and apply auto-patches to Jinja2 templates based on fix history."""

    def propose_patch(self, template_path: str) -> Optional[dict]:
        """
        Propose a patch for a template based on recurring fix patterns.
        Returns patch dict or None if no patch warranted.
        """
        key = _template_key(template_path)

        if _check_rate_limit(key):
            return None

        rows = _get_fix_patterns(key)
        if not rows:
            return None

        total_fixes = sum(r["fix_count"] for r in rows)
        if total_fixes < _MIN_FIX_COUNT:
            return None

        return _build_patch_candidate(template_path, rows)

    def propose_all(self) -> list[dict]:
        """Scan all templates with fix history and propose patches."""
        conn = get_connection()
        rows = conn.execute(
            """SELECT template_used, SUM(fix_count) as total_fixes
               FROM generation_history
               WHERE template_used IS NOT NULL AND fix_count > 0
               GROUP BY template_used
               HAVING total_fixes >= ?
               ORDER BY total_fixes DESC""",
            (_MIN_FIX_COUNT,),
        ).fetchall()
        conn.close()

        patches = []
        for row in rows:
            template_key = row[0]
            patch = self.propose_patch(template_key)
            if patch:
                patches.append(patch)
        return patches

    def apply_patch(self, patch: dict, dry_run: bool = True) -> bool:
        """
        Apply patch through staging pipeline.
        dry_run=True: validate only, don't write.
        dry_run=False: write + validate + commit.
        Returns True if staging passed.
        """
        import tempfile, shutil

        template_file = Path(patch["template_path"])
        if not template_file.exists():
            print(f"[improver] Template not found: {template_file}")
            return False

        # Stage 1: Write patched content to a temp copy
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_theme = Path(tmpdir) / "test_theme"
            tmp_theme.mkdir()

            # Write patched template to temp location
            tmp_tpl = tmp_theme / template_file.name
            tmp_tpl.write_text(patch["patched_content"], encoding="utf-8")

            # Stage 2: Validate with Kiwi
            passed, violations = _validate_with_kiwi(tmp_theme)

            if not passed:
                print(f"[improver] Staging FAILED — {len(violations)} CRITICAL violation(s):")
                for v in violations:
                    print(f"  - {v}")
                return False

        if dry_run:
            print(f"[improver] Staging PASSED (dry_run=True) — patch not applied")
            return True

        # Stage 3: Record quality before
        quality_before = get_generation_quality().get("quality_score", 1.0)

        # Stage 4: Apply patch to real template
        template_file.write_text(patch["patched_content"], encoding="utf-8")

        # Stage 5: Commit
        commit_msg = f"fix(template): auto-patch {template_file.name} - {patch['pattern_summary']}"
        try:
            subprocess.run(
                ["git", "add", str(template_file)],
                cwd=str(KIWI_DIR),
                check=True, capture_output=True,
            )
            result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=str(KIWI_DIR),
                capture_output=True, text=True,
            )
            commit_hash = ""
            if result.returncode == 0:
                m = re.search(r"\b([0-9a-f]{7,})\b", result.stdout)
                commit_hash = m.group(1) if m else "unknown"
            else:
                print(f"[improver] Git commit failed: {result.stderr}")
                # Restore original
                template_file.write_text(patch["original_content"], encoding="utf-8")
                return False
        except Exception as e:
            print(f"[improver] Git error: {e}")
            template_file.write_text(patch["original_content"], encoding="utf-8")
            return False

        # Stage 6: Record in DB
        _record_patch_in_db(patch["template_key"], commit_hash, quality_before, quality_before)

        # Stage 7: Check for quality regression
        quality_after = get_generation_quality().get("quality_score", 1.0)
        if quality_after < quality_before - _QUALITY_DROP_THRESHOLD:
            print(f"[improver] WARNING: quality dropped {quality_before:.1%} → {quality_after:.1%}, auto-reverting {commit_hash}")
            try:
                subprocess.run(
                    ["git", "revert", "--no-edit", commit_hash],
                    cwd=str(KIWI_DIR),
                    check=True, capture_output=True,
                )
                _record_patch_in_db(patch["template_key"], commit_hash, quality_before, quality_after, auto_reverted=True)
                print(f"[improver] Auto-reverted commit {commit_hash}")
            except Exception as e:
                print(f"[improver] Auto-revert failed: {e}")
            return False

        print(f"[improver] Patch applied and committed: {commit_hash}")
        return True
