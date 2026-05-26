"""Pattern Mining Engine — Phát hiện recurring patterns từ scan history"""

import re
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple
from difflib import SequenceMatcher
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from .models import SuggestedPattern
from memory.db import get_connection


def mine_patterns_from_history(
    project_path: str = None,
    lookback_days: int = 30,
    min_occurrences: int = 3
) -> List[SuggestedPattern]:
    """
    Wrapper for mine_patterns() with agent loop compatible signature.

    Args:
        project_path: Project path to filter violations
        lookback_days: Days to look back in scan history
        min_occurrences: Minimum pattern occurrences to suggest

    Returns: List of suggested patterns
    """
    return mine_patterns(
        min_occurrences=min_occurrences,
        similarity_threshold=0.8,
        lookback_days=lookback_days,
        path=project_path
    )


def mine_patterns(
    min_occurrences: int = 2,
    similarity_threshold: float = 0.8,
    lookback_days: int = 30,
    path: str = None
) -> List[SuggestedPattern]:
    """
    Mine recurring patterns from scan history.

    Algorithm:
    1. Query violations from last N days
    2. Group by file extension + category hint
    3. Cluster by match_text similarity
    4. Filter clusters with ≥ min_occurrences
    5. Extract pattern regex from cluster
    6. Insert into suggested_lessons table

    Returns: List of suggested patterns
    """

    # Query recent violations from scan history
    violations = _query_recent_violations(lookback_days, path)

    if len(violations) < min_occurrences:
        return []

    # Group by file extension
    grouped = _group_by_extension(violations)

    # Cluster similar violations
    all_patterns = []
    for ext, group_violations in grouped.items():
        clusters = _cluster_violations(group_violations, similarity_threshold)

        # Filter clusters by min_occurrences
        for cluster in clusters:
            if len(cluster) >= min_occurrences:
                pattern = _extract_pattern_from_cluster(cluster, ext)
                if pattern:
                    all_patterns.append(pattern)

    # Insert into suggested_lessons table
    for pattern in all_patterns:
        _insert_suggested_lesson(pattern)

    return all_patterns


def _query_recent_violations(lookback_days: int, path: str = None) -> List[Dict]:
    """Query violations from violations table"""
    from memory.db import get_recent_violations

    violations = get_recent_violations(lookback_days, path)
    return violations


def _group_by_extension(violations: List[Dict]) -> Dict[str, List[Dict]]:
    """Group violations by file extension"""
    grouped = defaultdict(list)

    for v in violations:
        file = v.get('file', '')
        ext = Path(file).suffix or '.unknown'
        grouped[ext].append(v)

    return dict(grouped)


def _cluster_violations(violations: List[Dict], threshold: float) -> List[List[Dict]]:
    """
    Cluster violations by match_text similarity using Levenshtein distance.

    Algorithm:
    1. Start with first violation as seed
    2. For each remaining violation, find most similar cluster
    3. If similarity > threshold, add to cluster
    4. Otherwise, create new cluster
    """
    if not violations:
        return []

    clusters = [[violations[0]]]

    for v in violations[1:]:
        match_text = v.get('match_text', '')

        # Find most similar cluster
        best_cluster_idx = 0
        best_similarity = 0.0

        for i, cluster in enumerate(clusters):
            # Compare with cluster representative (first item)
            cluster_text = cluster[0].get('match_text', '')
            similarity = _text_similarity(match_text, cluster_text)

            if similarity > best_similarity:
                best_similarity = similarity
                best_cluster_idx = i

        # Add to cluster or create new one
        if best_similarity >= threshold:
            clusters[best_cluster_idx].append(v)
        else:
            clusters.append([v])

    return clusters


def _text_similarity(text1: str, text2: str) -> float:
    """Calculate similarity between two texts using SequenceMatcher"""
    return SequenceMatcher(None, text1, text2).ratio()


def _extract_pattern_from_cluster(cluster: List[Dict], ext: str) -> SuggestedPattern:
    """
    Extract common regex pattern from cluster of similar violations.

    Algorithm:
    1. Find longest common substring
    2. Replace variable parts with regex groups
    3. Test pattern against cluster (precision check)
    """
    if not cluster:
        return None

    # Get all match texts
    match_texts = [v.get('match_text', '') for v in cluster]

    # Find common pattern
    pattern = _find_common_pattern(match_texts)

    if not pattern:
        return None

    # Infer category and severity
    category = _infer_category(match_texts, ext)
    severity = _infer_severity(cluster, category)

    # Get example
    example = cluster[0]

    return SuggestedPattern(
        pattern=pattern,
        scope=f"**/*{ext}",
        category=category,
        severity=severity,
        example_file=example.get('file', ''),
        example_line=example.get('line', 0),
        example_code=example.get('match_text', ''),
        occurrence_count=len(cluster),
        confidence=min(1.0, len(cluster) / 10),
        files=[v.get('file', '') for v in cluster]
    )


def _find_common_pattern(texts: List[str]) -> str:
    """
    Find common regex pattern from list of similar texts.

    Algorithm:
    1. Find longest common substring
    2. Replace variable parts with regex
    """
    if not texts:
        return ""

    if len(texts) == 1:
        return re.escape(texts[0])

    # Find longest common substring
    common = texts[0]
    for text in texts[1:]:
        common = _longest_common_substring(common, text)

    if len(common) < 5:  # Too short to be meaningful
        return ""

    # Build pattern by finding variable parts
    pattern_parts = []
    for text in texts:
        if common in text:
            # Find parts before, in, and after common substring
            idx = text.index(common)
            before = text[:idx]
            after = text[idx + len(common):]

            # Generalize variable parts
            if before and not any(before in p for p in pattern_parts):
                pattern_parts.append(before)
            if after and not any(after in p for p in pattern_parts):
                pattern_parts.append(after)

    # Build regex pattern
    # Escape common part
    pattern = re.escape(common)

    # Add variable parts as optional groups
    if pattern_parts:
        # Simple heuristic: if parts look like identifiers, use \w+
        var_pattern = r'[a-zA-Z_][a-zA-Z0-9_]*'
        pattern = f"{var_pattern}?{pattern}{var_pattern}?"

    return pattern


def _longest_common_substring(s1: str, s2: str) -> str:
    """Find longest common substring between two strings"""
    m = [[0] * (1 + len(s2)) for _ in range(1 + len(s1))]
    longest, x_longest = 0, 0

    for x in range(1, 1 + len(s1)):
        for y in range(1, 1 + len(s2)):
            if s1[x - 1] == s2[y - 1]:
                m[x][y] = m[x - 1][y - 1] + 1
                if m[x][y] > longest:
                    longest = m[x][y]
                    x_longest = x
            else:
                m[x][y] = 0

    return s1[x_longest - longest: x_longest]


def _infer_category(match_texts: List[str], ext: str) -> str:
    """Infer category from match texts and file extension"""

    # PHP security patterns
    if ext == '.php':
        if any('$_GET' in t or '$_POST' in t or '$_REQUEST' in t for t in match_texts):
            return 'php-security'
        if any('sql' in t.lower() or 'query' in t.lower() for t in match_texts):
            return 'php-security'
        if any('wc_' in t or 'WC_' in t for t in match_texts):
            return 'wezone-api'

    # CSS patterns
    if ext == '.css' or ext == '.scss':
        if any('px' in t or '#' in t for t in match_texts):
            return 'css-tokens'

    # JS patterns
    if ext in ['.js', '.ts', '.jsx', '.tsx']:
        if any('fetch' in t or 'axios' in t for t in match_texts):
            return 'js-contract'
        if any('useState' in t or 'useEffect' in t for t in match_texts):
            return 'nextjs-react'

    return 'code-quality'


def _infer_severity(cluster: List[Dict], category: str) -> str:
    """Infer severity based on category and occurrence count"""

    count = len(cluster)

    # Security issues are always CRITICAL
    if 'security' in category:
        return 'CRITICAL'

    # High occurrence = HIGH severity
    if count >= 10:
        return 'HIGH'

    # Medium occurrence = SUGGEST
    return 'SUGGEST'


def _insert_suggested_lesson(pattern: SuggestedPattern) -> int:
    """Insert suggested pattern into database"""
    import json
    from datetime import datetime, timezone

    conn = get_connection()
    try:
        cursor = conn.execute("""
            INSERT INTO suggested_lessons
            (pattern, scope, category, severity, example_file, example_line, example_code, suggested_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (
            pattern.pattern,
            pattern.scope,
            pattern.category,
            pattern.severity,
            pattern.example_file,
            pattern.example_line,
            pattern.example_code,
            datetime.now(timezone.utc).isoformat()
        ))

        suggestion_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()

    return suggestion_id
