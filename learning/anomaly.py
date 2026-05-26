"""Anomaly Detector — Phát hiện code patterns mới chưa có trong lessons"""

import hashlib
import sys
from pathlib import Path
from typing import List, Set, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from .models import PatternFingerprint, Anomaly
from scanner.loader import load_patterns


def detect_anomalies(violations: List[Dict], min_confidence: float = 0.5) -> List[Anomaly]:
    """
    Detect anomalies in violations by comparing against known patterns.

    Returns: List of anomalies with confidence scores
    """
    # Build fingerprints from existing lessons
    fingerprints = _build_fingerprints()

    # Group violations by match_text
    grouped = _group_by_match_text(violations)

    # Detect anomalies
    anomalies = []
    for match_text, group in grouped.items():
        if len(group) < 3:  # Need at least 3 occurrences
            continue

        # Calculate similarity to known patterns
        max_similarity = _max_similarity_to_fingerprints(match_text, fingerprints)

        # If similarity < 0.3, it's an anomaly
        if max_similarity < 0.3:
            confidence = min(1.0, len(group) / 10) * (1 - max_similarity)

            if confidence >= min_confidence:
                anomaly = _create_anomaly(match_text, group, confidence)
                anomalies.append(anomaly)

    return anomalies


def _build_fingerprints() -> List[PatternFingerprint]:
    """Build fingerprints from existing lessons"""
    fingerprints = []

    # Load all patterns
    patterns = load_patterns(platform=None, scope_type=None)

    for pattern in patterns:
        lesson_id = pattern.get('id', '')
        pattern_str = pattern.get('scan', {}).get('pattern', '')
        category = pattern.get('category', '')
        scope = pattern.get('scan', {}).get('scope', '')

        if not pattern_str:
            continue

        # Create fingerprint
        pattern_hash = hashlib.sha256(pattern_str.encode()).hexdigest()[:32]
        token_set = _extract_tokens(pattern_str)

        fingerprints.append(PatternFingerprint(
            lesson_id=lesson_id,
            pattern_hash=pattern_hash,
            category=category,
            scope=scope,
            token_set=token_set
        ))

    return fingerprints


def _extract_tokens(text: str) -> Set[str]:
    """Extract unique tokens from text"""
    import re
    # Simple tokenization: split on non-alphanumeric
    tokens = re.findall(r'\w+', text.lower())
    return set(tokens)


def _group_by_match_text(violations: List[Dict]) -> Dict[str, List[Dict]]:
    """Group violations by match_text"""
    from collections import defaultdict
    grouped = defaultdict(list)

    for v in violations:
        match_text = v.get('match_text', '')
        if match_text:
            grouped[match_text].append(v)

    return dict(grouped)


def _max_similarity_to_fingerprints(match_text: str, fingerprints: List[PatternFingerprint]) -> float:
    """Calculate max similarity to any fingerprint using Jaccard index"""
    tokens = _extract_tokens(match_text)

    if not tokens:
        return 0.0

    max_sim = 0.0
    for fp in fingerprints:
        similarity = _jaccard_similarity(tokens, fp.token_set)
        max_sim = max(max_sim, similarity)

    return max_sim


def _jaccard_similarity(set1: Set[str], set2: Set[str]) -> float:
    """Calculate Jaccard similarity between two sets"""
    if not set1 or not set2:
        return 0.0

    intersection = len(set1 & set2)
    union = len(set1 | set2)

    return intersection / union if union > 0 else 0.0


def _create_anomaly(match_text: str, group: List[Dict], confidence: float) -> Anomaly:
    """Create anomaly from group of violations"""
    files = [v.get('file', '') for v in group]
    example = group[0]

    # Infer category and severity
    category = _infer_category_from_match(match_text)
    severity = _infer_severity_from_confidence(confidence, len(group))

    return Anomaly(
        pattern=match_text,
        match_text=match_text,
        files=files,
        occurrence_count=len(group),
        confidence=confidence,
        suggested_category=category,
        suggested_severity=severity,
        example_file=example.get('file', ''),
        example_line=example.get('line', 0)
    )


def _infer_category_from_match(match_text: str) -> str:
    """Infer category from match text"""
    text_lower = match_text.lower()

    # Security patterns
    if any(kw in text_lower for kw in ['$_get', '$_post', '$_request', 'sql', 'query']):
        return 'php-security'

    # CSS patterns
    if any(kw in text_lower for kw in ['px', '#', 'color', 'font']):
        return 'css-tokens'

    # JS patterns
    if any(kw in text_lower for kw in ['fetch', 'axios', 'usestate', 'useeffect']):
        return 'js-contract'

    return 'code-quality'


def _infer_severity_from_confidence(confidence: float, count: int) -> str:
    """Infer severity from confidence and occurrence count"""
    if confidence > 0.8 and count >= 10:
        return 'CRITICAL'
    elif confidence > 0.6 and count >= 5:
        return 'HIGH'
    else:
        return 'SUGGEST'
