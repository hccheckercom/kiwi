"""Global Pattern Mining — Học patterns từ tất cả projects"""

import sys
from pathlib import Path
from typing import List, Dict, Set, Optional
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from .miner import (
    _query_recent_violations,
    _group_by_extension,
    _cluster_violations,
    _extract_pattern_from_cluster,
    _insert_suggested_lesson
)
from .models import SuggestedPattern


def mine_patterns_global(
    min_occurrences: int = 2,
    similarity_threshold: float = 0.8,
    lookback_days: int = 30,
    min_projects: int = 2
) -> List[SuggestedPattern]:
    """
    Mine patterns across ALL projects.

    Differences from mine_patterns():
    - Query violations with path=None (all projects)
    - Classify patterns as universal vs platform-specific
    - Higher confidence for cross-project patterns

    Args:
        min_occurrences: Minimum pattern occurrences
        similarity_threshold: Clustering threshold
        lookback_days: Days to look back
        min_projects: Minimum projects for pattern (default 2)

    Returns: List of suggested patterns
    """
    violations = _query_recent_violations(lookback_days, path=None)

    if len(violations) < min_occurrences:
        return []

    grouped = _group_by_extension(violations)

    all_patterns = []
    for ext, group_violations in grouped.items():
        clusters = _cluster_violations(group_violations, similarity_threshold)

        for cluster in clusters:
            if len(cluster) >= min_occurrences:
                project_count = _count_unique_projects(cluster)

                if project_count >= min_projects:
                    pattern = _extract_pattern_from_cluster(cluster, ext)
                    if pattern:
                        pattern = _enhance_with_cross_project_data(pattern, cluster, project_count)
                        all_patterns.append(pattern)

    for pattern in all_patterns:
        _insert_suggested_lesson(pattern)

    return all_patterns


def _count_unique_projects(cluster: List[Dict]) -> int:
    """Count unique projects in cluster"""
    projects = set()
    for violation in cluster:
        file_path = violation.get('file', '')
        project = _extract_project_from_path(file_path)
        if project:
            projects.add(project)
    return len(projects)


def _extract_project_from_path(file_path: str) -> Optional[str]:
    """Extract project name from file path"""
    parts = file_path.replace('\\', '/').split('/')

    for i, part in enumerate(parts):
        if part in ('themes', 'plugins', 'wezone-plugins', 'webstore-vn'):
            if i + 1 < len(parts):
                return parts[i + 1]
            return part

    if 'wezone-plugins' in file_path:
        return 'wezone-plugins'
    if 'webstore-vn' in file_path:
        return 'webstore-vn'

    return None


def _enhance_with_cross_project_data(
    pattern: SuggestedPattern,
    cluster: List[Dict],
    project_count: int
) -> SuggestedPattern:
    """Enhance pattern with cross-project metadata"""
    pattern.project_count = project_count

    platforms = _detect_platforms(cluster)
    pattern.is_universal = len(platforms) > 1

    if pattern.is_universal:
        pattern.confidence = min(1.0, pattern.confidence * 1.5)
    elif project_count >= 2:
        pattern.confidence = min(1.0, pattern.confidence * 1.2)

    return pattern


def _detect_platforms(cluster: List[Dict]) -> Set[str]:
    """Detect platforms from file paths"""
    platforms = set()

    for violation in cluster:
        file_path = violation.get('file', '')

        if any(ext in file_path for ext in ['.php', '.blade.php']):
            platforms.add('wp')
        if any(ext in file_path for ext in ['.tsx', '.jsx', '.ts', '.js']):
            if 'node_modules' not in file_path:
                platforms.add('nextjs')

    return platforms


def get_global_mining_report(lookback_days: int = 30) -> Dict:
    """Generate global mining report"""
    violations = _query_recent_violations(lookback_days, path=None)

    projects = defaultdict(int)
    platforms = defaultdict(int)
    categories = defaultdict(int)

    for v in violations:
        project = _extract_project_from_path(v.get('file', ''))
        if project:
            projects[project] += 1

        file_path = v.get('file', '')
        if '.php' in file_path:
            platforms['wp'] += 1
        elif any(ext in file_path for ext in ['.tsx', '.jsx', '.ts']):
            platforms['nextjs'] += 1

        category = v.get('category', 'unknown')
        categories[category] += 1

    return {
        'total_violations': len(violations),
        'lookback_days': lookback_days,
        'projects': dict(projects),
        'platforms': dict(platforms),
        'categories': dict(categories),
        'unique_projects': len(projects),
        'cross_project_potential': sum(1 for count in projects.values() if count >= 5)
    }
