"""R5 — Cold Start Accelerator: bootstrap trust for new themes from same-industry data."""

import json
import re
import time
from pathlib import Path

from .session_logger import _get_conn

_BOOTSTRAP_TRUST_CAP = 0.6
_MIN_INDUSTRY_SESSIONS = 3


def detect_industry(theme_path: str) -> str | None:
    """Detect industry from store-config.php or INPUT.md."""
    base = Path(theme_path)

    store_config = base / "inc" / "store-config.php"
    if store_config.exists():
        try:
            content = store_config.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"['\"]industry['\"]\s*=>\s*['\"](\w+)['\"]", content)
            if m:
                return m.group(1)
        except OSError:
            pass

    input_md = base / "docs" / "_blueprint" / "01-INPUT.md"
    if input_md.exists():
        try:
            content = input_md.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"(?:industry|ngành)[:\s]+(\w+)", content, re.IGNORECASE)
            if m:
                return m.group(1)
        except OSError:
            pass

    return None


def needs_bootstrap(theme_path: str) -> bool:
    """Check if theme has zero session data (cold start condition)."""
    conn = _get_conn()
    if not conn:
        return False

    theme_name = Path(theme_path).name
    count = conn.execute(
        "SELECT COUNT(*) FROM context_patterns WHERE theme = ?",
        (theme_name,),
    ).fetchone()[0]
    return count == 0


def get_industry_themes(industry: str, exclude_theme: str, themes_root: Path = None) -> list[str]:
    """Find themes with same industry that have session data."""
    conn = _get_conn()
    if not conn:
        return []

    rows = conn.execute(
        "SELECT DISTINCT theme FROM context_patterns WHERE theme != ?",
        (exclude_theme,),
    ).fetchall()

    if themes_root is None:
        themes_root = Path("themes")

    matching = []
    for (theme,) in rows:
        possible_paths = [
            themes_root / theme / "inc" / "store-config.php",
            themes_root / theme / "docs" / "_blueprint" / "01-INPUT.md",
        ]
        for p in possible_paths:
            if p.exists():
                try:
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    if industry.lower() in content.lower():
                        matching.append(theme)
                        break
                except OSError:
                    continue
    return matching


def bootstrap_from_industry(theme_path: str) -> dict:
    """Bootstrap trust + patterns for a new theme from same-industry themes."""
    theme_name = Path(theme_path).name
    industry = detect_industry(theme_path)

    if not industry:
        return {"status": "no_industry", "bootstrapped": False}

    if not needs_bootstrap(theme_path):
        return {"status": "has_data", "bootstrapped": False}

    conn = _get_conn()
    if not conn:
        return {"status": "no_db", "bootstrapped": False}

    industry_themes = get_industry_themes(industry, theme_name)
    if not industry_themes:
        # R8: Try LLM reasoning to infer style tokens
        try:
            from .thinker import think
            ctx = {
                'theme': theme_name,
                'industry': industry,
                'style_knowledge_count': 0,
                'task_type': 'bootstrap',
                'dna_summary': f'{industry} industry defaults',
            }
            result = think('style_ambiguity', ctx)
            if result and result.confidence >= 0.7 and result.extra.get('tokens'):
                tokens = result.extra['tokens']
                now = time.time()
                for key, value in tokens.items():
                    conn.execute(
                        "INSERT OR IGNORE INTO style_knowledge "
                        "(theme, pattern_key, value, times_seen, last_seen) "
                        "VALUES (?, ?, ?, 1, ?)",
                        (theme_name, key, str(value), now),
                    )
                conn.commit()
                return {
                    "status": "llm_inferred", "industry": industry,
                    "bootstrapped": True, "styles": len(tokens),
                    "bindings": 0, "trust": 0,
                }
        except Exception:
            pass
        return {"status": "no_industry_peers", "industry": industry, "bootstrapped": False}

    bootstrapped = {"status": "ok", "industry": industry, "bootstrapped": True,
                    "source_themes": industry_themes, "styles": 0, "bindings": 0, "trust": 0}

    # 1. Bootstrap styles from industry peers
    style_rows = conn.execute(
        "SELECT pattern_key, value, times_seen FROM style_knowledge "
        "WHERE theme IN ({}) ORDER BY times_seen DESC".format(
            ",".join("?" * len(industry_themes))
        ),
        industry_themes,
    ).fetchall()

    now = time.time()
    seen_keys = set()
    for key, value, times in style_rows:
        if key in seen_keys:
            continue
        seen_keys.add(key)
        conn.execute(
            "INSERT OR IGNORE INTO style_knowledge (theme, pattern_key, value, times_seen, last_seen) "
            "VALUES (?, ?, ?, 1, ?)",
            (theme_name, key, value, now),
        )
        bootstrapped["styles"] += 1

    # 2. Bootstrap bindings from industry peers
    binding_rows = conn.execute(
        "SELECT task_type, binding, times_seen FROM binding_knowledge "
        "WHERE theme IN ({}) AND times_seen >= 2 "
        "ORDER BY times_seen DESC LIMIT 50".format(
            ",".join("?" * len(industry_themes))
        ),
        industry_themes,
    ).fetchall()

    for task_type, binding, times in binding_rows:
        conn.execute(
            "INSERT OR IGNORE INTO binding_knowledge (task_type, binding, theme, times_seen, last_seen) "
            "VALUES (?, ?, ?, 1, ?)",
            (task_type, binding, theme_name, now),
        )
        bootstrapped["bindings"] += 1

    # 3. Bootstrap trust baselines (capped at 0.6)
    trust_rows = conn.execute(
        "SELECT task_type, AVG(trust_score) FROM trust_baselines "
        "WHERE task_type IN ("
        "  SELECT DISTINCT task_type FROM context_patterns WHERE theme IN ({})"
        ") GROUP BY task_type".format(
            ",".join("?" * len(industry_themes))
        ),
        industry_themes,
    ).fetchall()

    for task_type, avg_trust in trust_rows:
        capped = min(avg_trust, _BOOTSTRAP_TRUST_CAP)
        conn.execute(
            "INSERT OR IGNORE INTO trust_baselines (task_type, trust_score, last_calibrated, calibration_count) "
            "VALUES (?, ?, ?, 0)",
            (task_type, capped, now),
        )
        bootstrapped["trust"] += 1

    conn.commit()
    return bootstrapped