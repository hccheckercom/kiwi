"""Lesson Deduplication — Tự động merge similar lessons"""

import re
import sys
from pathlib import Path
from typing import List, Dict, Optional
from difflib import SequenceMatcher

sys.path.insert(0, str(Path(__file__).parent.parent))

from scanner.loader import load_patterns
from memory.confidence import get_confidence

# Feature flag for semantic embeddings
USE_SEMANTIC_SIMILARITY = True

try:
    from .embeddings import embed_pattern, semantic_similarity
    _embeddings_available = True
except ImportError:
    _embeddings_available = False
    USE_SEMANTIC_SIMILARITY = False


def find_duplicate_lessons(similarity_threshold: float = 0.9) -> List[List[str]]:
    """
    Find clusters of similar lessons.

    Algorithm:
    1. Load all lessons
    2. Calculate pairwise similarity (pattern + title + category)
    3. Cluster by similarity threshold
    4. Return clusters with ≥2 lessons

    Returns: List of clusters, each cluster is list of lesson IDs
    """
    lessons = load_patterns(platform=None, scope_type=None)

    if len(lessons) < 2:
        return []

    clusters = []
    processed = set()

    for i, lesson_a in enumerate(lessons):
        if lesson_a['id'] in processed:
            continue

        cluster = [lesson_a['id']]

        for j, lesson_b in enumerate(lessons):
            if i >= j or lesson_b['id'] in processed:
                continue

            similarity = calculate_lesson_similarity(lesson_a, lesson_b)

            if similarity >= similarity_threshold:
                cluster.append(lesson_b['id'])
                processed.add(lesson_b['id'])

        if len(cluster) >= 2:
            clusters.append(cluster)
            for lesson_id in cluster:
                processed.add(lesson_id)

    return clusters


def calculate_lesson_similarity(lesson_a: Dict, lesson_b: Dict) -> float:
    """
    Calculate similarity between two lessons.

    Uses semantic embeddings if available, otherwise falls back to Levenshtein.

    Weights:
    - Pattern similarity: 50%
    - Title similarity: 30%
    - Category match: 20%

    Returns: Similarity score (0-1)
    """
    if USE_SEMANTIC_SIMILARITY and _embeddings_available:
        return _calculate_semantic_similarity(lesson_a, lesson_b)
    else:
        return _calculate_levenshtein_similarity(lesson_a, lesson_b)


def _calculate_semantic_similarity(lesson_a: Dict, lesson_b: Dict) -> float:
    """Calculate similarity using semantic embeddings."""
    pattern_a = lesson_a.get('scan', {}).get('pattern', '')
    pattern_b = lesson_b.get('scan', {}).get('pattern', '')

    context_a = f"{lesson_a.get('title', '')} {lesson_a.get('category', '')}"
    context_b = f"{lesson_b.get('title', '')} {lesson_b.get('category', '')}"

    emb_a = embed_pattern(pattern_a, context_a)
    emb_b = embed_pattern(pattern_b, context_b)

    pattern_sim = semantic_similarity(emb_a, emb_b)

    # Title similarity (still use token overlap)
    title_sim = _token_overlap_similarity(
        lesson_a.get('title', ''),
        lesson_b.get('title', '')
    )

    # Category match
    category_match = 1.0 if lesson_a.get('category') == lesson_b.get('category') else 0.0

    # Weighted combination
    similarity = (pattern_sim * 0.5) + (title_sim * 0.3) + (category_match * 0.2)
    return similarity


def _calculate_levenshtein_similarity(lesson_a: Dict, lesson_b: Dict) -> float:
    """Calculate similarity using Levenshtein distance (fallback)."""
    pattern_a = lesson_a.get('scan', {}).get('pattern', '')
    pattern_b = lesson_b.get('scan', {}).get('pattern', '')
    pattern_sim = _string_similarity(pattern_a, pattern_b)

    title_a = lesson_a.get('title', '')
    title_b = lesson_b.get('title', '')
    title_sim = _token_overlap_similarity(title_a, title_b)

    category_a = lesson_a.get('category', '')
    category_b = lesson_b.get('category', '')
    category_match = 1.0 if category_a == category_b else 0.0

    similarity = (pattern_sim * 0.5) + (title_sim * 0.3) + (category_match * 0.2)
    return similarity


def _string_similarity(str_a: str, str_b: str) -> float:
    """Levenshtein-based string similarity"""
    if not str_a or not str_b:
        return 0.0
    return SequenceMatcher(None, str_a, str_b).ratio()


def _token_overlap_similarity(str_a: str, str_b: str) -> float:
    """Token overlap similarity"""
    if not str_a or not str_b:
        return 0.0

    tokens_a = set(re.findall(r'\w+', str_a.lower()))
    tokens_b = set(re.findall(r'\w+', str_b.lower()))

    if not tokens_a or not tokens_b:
        return 0.0

    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b

    return len(intersection) / len(union) if union else 0.0


def merge_lessons(cluster: List[str]) -> Dict:
    """
    Merge cluster of similar lessons.

    Strategy:
    - Keep lesson with highest confidence
    - Merge patterns with OR operator
    - Combine examples from all lessons
    - Archive old lessons to lessons/_archived/

    Returns: Dict with merge result
    """
    if len(cluster) < 2:
        return {'success': False, 'error': 'Need at least 2 lessons to merge'}

    kiwi_dir = Path(__file__).parent.parent
    lessons_dir = kiwi_dir / 'lessons'
    archive_dir = lessons_dir / '_archived'
    archive_dir.mkdir(exist_ok=True)

    # Load all lessons in cluster
    lessons_data = []
    for lesson_id in cluster:
        lesson_file = _find_lesson_file(lessons_dir, lesson_id)
        if lesson_file:
            content = lesson_file.read_text(encoding='utf-8')
            lessons_data.append({
                'id': lesson_id,
                'file': lesson_file,
                'content': content,
                'confidence': get_confidence(lesson_id)
            })

    if not lessons_data:
        return {'success': False, 'error': 'No lesson files found'}

    # Sort by confidence (highest first)
    lessons_data.sort(key=lambda x: x['confidence'].get('confidence', 0.0) if x['confidence'] else 0.0, reverse=True)

    # Keep the lesson with highest confidence
    primary = lessons_data[0]
    others = lessons_data[1:]

    # Extract patterns from all lessons
    patterns = []
    for lesson in lessons_data:
        pattern = _extract_pattern(lesson['content'])
        if pattern:
            patterns.append(pattern)

    # Merge patterns with OR operator
    if len(patterns) > 1:
        merged_pattern = '|'.join(f'({p})' for p in patterns)
    else:
        merged_pattern = patterns[0] if patterns else ''

    # Update primary lesson with merged pattern
    updated_content = _update_pattern_in_content(primary['content'], merged_pattern)

    # Add merge note
    merge_note = f"\n\n<!-- Merged from: {', '.join(l['id'] for l in others)} -->\n"
    updated_content += merge_note

    # Write updated primary lesson
    primary['file'].write_text(updated_content, encoding='utf-8')

    # Archive other lessons
    archived = []
    for lesson in others:
        archive_path = archive_dir / lesson['file'].name
        lesson['file'].rename(archive_path)
        archived.append(lesson['id'])

    return {
        'success': True,
        'primary': primary['id'],
        'archived': archived,
        'merged_pattern': merged_pattern
    }


def _find_lesson_file(lessons_dir: Path, lesson_id: str) -> Optional[Path]:
    """Find lesson file by ID"""
    for category_dir in lessons_dir.iterdir():
        if category_dir.is_dir() and not category_dir.name.startswith('_'):
            lesson_file = category_dir / f'{lesson_id}.md'
            if lesson_file.exists():
                return lesson_file
    return None


def _extract_pattern(content: str) -> Optional[str]:
    """Extract pattern from lesson content"""
    match = re.search(r'pattern:\s*["\']?([^"\'\n]+)["\']?', content)
    if match:
        return match.group(1).strip()
    return None


def _update_pattern_in_content(content: str, new_pattern: str) -> str:
    """Update pattern in lesson content"""
    return re.sub(
        r'(pattern:\s*)["\']?[^"\'\n]+["\']?',
        f'pattern: "{new_pattern}"',
        content
    )


def estimate_noise(lesson_ids: List[str], scan_path: str = None,
                   noise_threshold: int = 100) -> Dict:
    """Estimate false-positive noise for newly created lessons.

    Runs a quick grep for each lesson's pattern against the codebase.
    If a lesson produces > noise_threshold hits, it's flagged as noisy.

    Returns: {
        'noisy': [{'id': str, 'hits': int, 'pattern': str}],
        'clean': [str],
        'demoted': [str]  (auto-demoted to SUGGEST)
    }
    """
    if not scan_path:
        scan_path = str(Path(__file__).parent.parent)

    lessons = load_patterns(platform=None, scope_type=None)
    lessons_by_id = {l['id']: l for l in lessons}

    noisy = []
    clean = []
    demoted = []

    for lid in lesson_ids:
        lesson = lessons_by_id.get(lid)
        if not lesson:
            continue

        pattern = lesson.get('scan', {}).get('pattern', '')
        scope = lesson.get('scan', {}).get('scope', '**/*')
        if not pattern:
            clean.append(lid)
            continue

        hit_count = _count_pattern_hits(pattern, scope, scan_path)

        if hit_count > noise_threshold:
            noisy.append({'id': lid, 'hits': hit_count, 'pattern': pattern})
            _demote_to_suggest(lid)
            demoted.append(lid)
        else:
            clean.append(lid)

    return {'noisy': noisy, 'clean': clean, 'demoted': demoted}


def _count_pattern_hits(pattern: str, scope: str, scan_path: str) -> int:
    """Count how many times a regex pattern matches in the codebase."""
    import subprocess

    scope_map = {
        '**/*.php': '--include=*.php',
        '**/*.py': '--include=*.py',
        '**/*.{js,ts,jsx,tsx}': '--include=*.js --include=*.ts --include=*.jsx --include=*.tsx',
    }
    include_flag = scope_map.get(scope, '')

    try:
        cmd = f'rg -c "{pattern}" {include_flag} "{scan_path}" 2>$null | Measure-Object -Sum -Property {{[int]($_ -split ":")[-1]}}'
        # Simpler approach: just count lines
        cmd_parts = ['rg', '--count-matches', '--no-filename', pattern, scan_path]
        if '*.php' in scope:
            cmd_parts.extend(['-g', '*.php'])
        elif '*.py' in scope:
            cmd_parts.extend(['-g', '*.py'])
        elif '*.js' in scope or '*.ts' in scope:
            cmd_parts.extend(['-g', '*.js', '-g', '*.ts', '-g', '*.jsx', '-g', '*.tsx'])

        result = subprocess.run(
            cmd_parts, capture_output=True, text=True, timeout=30,
            cwd=scan_path
        )
        if result.returncode == 0 and result.stdout.strip():
            return sum(int(line) for line in result.stdout.strip().split('\n') if line.strip().isdigit())
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return 0


def _demote_to_suggest(lesson_id: str):
    """Demote a lesson's severity to SUGGEST by editing its file."""
    kiwi_dir = Path(__file__).parent.parent
    lesson_file = _find_lesson_file(kiwi_dir / 'lessons', lesson_id)
    if not lesson_file:
        return

    content = lesson_file.read_text(encoding='utf-8')
    # Only demote if currently CRITICAL or HIGH
    if 'severity: CRITICAL' in content:
        content = content.replace('severity: CRITICAL', 'severity: SUGGEST', 1)
    elif 'severity: HIGH' in content:
        content = content.replace('severity: HIGH', 'severity: SUGGEST', 1)
    else:
        return
    lesson_file.write_text(content, encoding='utf-8')


def post_create_guardrail(created_ids: List[str], scan_path: str = None,
                          auto_merge: bool = True, auto_demote: bool = True,
                          noise_threshold: int = 100) -> Dict:
    """Post-create validation: dedup + noise detection + auto-cleanup.

    Call this AFTER auto-creating lessons to catch duplicates and noisy patterns.

    Returns: {
        'dedup': {clusters_found, merged, disabled},
        'noise': {noisy, demoted},
        'report': str  (human-readable summary)
    }
    """
    result = {'dedup': {}, 'noise': {}, 'report': ''}
    report_lines = []

    # --- Phase 1: Dedup ---
    clusters = find_duplicate_lessons(similarity_threshold=0.85)
    new_set = set(created_ids)

    relevant_clusters = [c for c in clusters if new_set & set(c)]

    merged_ids = []
    disabled_ids = []

    if relevant_clusters:
        for cluster in relevant_clusters:
            sims = []
            lessons = load_patterns(platform=None, scope_type=None)
            lessons_by_id = {l['id']: l for l in lessons}
            cluster_lessons = [lessons_by_id[lid] for lid in cluster if lid in lessons_by_id]

            if len(cluster_lessons) < 2:
                continue

            avg_sim = 0
            count = 0
            for i, la in enumerate(cluster_lessons):
                for lb in cluster_lessons[i+1:]:
                    avg_sim += calculate_lesson_similarity(la, lb)
                    count += 1
            avg_sim = avg_sim / count if count else 0

            new_in_cluster = [lid for lid in cluster if lid in new_set]
            old_in_cluster = [lid for lid in cluster if lid not in new_set]

            if avg_sim >= 0.9 and auto_merge and old_in_cluster:
                # High similarity with existing lesson → merge (archive new)
                merge_result = merge_lessons(cluster)
                if merge_result.get('success'):
                    merged_ids.extend(merge_result.get('archived', []))
                    report_lines.append(
                        f"  MERGED: {', '.join(merge_result.get('archived', []))} "
                        f"→ kept {merge_result['primary']} (sim={avg_sim:.2f})"
                    )
            elif avg_sim >= 0.7:
                # Medium similarity → disable new lessons, keep old
                for lid in new_in_cluster:
                    lesson_file = _find_lesson_file(
                        Path(__file__).parent.parent / 'lessons', lid
                    )
                    if lesson_file:
                        content = lesson_file.read_text(encoding='utf-8')
                        content = content.replace('scan:', 'disabled: true\nscan:', 1)
                        lesson_file.write_text(content, encoding='utf-8')
                        disabled_ids.append(lid)
                        similar_to = ', '.join(old_in_cluster) if old_in_cluster else ', '.join(c for c in cluster if c != lid)
                        report_lines.append(
                            f"  DISABLED: {lid} — similar to {similar_to} (sim={avg_sim:.2f})"
                        )

    result['dedup'] = {
        'clusters_found': len(relevant_clusters),
        'merged': merged_ids,
        'disabled': disabled_ids
    }

    # --- Phase 2: Noise estimation ---
    remaining_ids = [lid for lid in created_ids if lid not in merged_ids and lid not in disabled_ids]

    if remaining_ids and auto_demote:
        noise_result = estimate_noise(remaining_ids, scan_path, noise_threshold)
        result['noise'] = noise_result

        for n in noise_result.get('noisy', []):
            report_lines.append(
                f"  DEMOTED: {n['id']} → SUGGEST ({n['hits']} hits, threshold={noise_threshold})"
            )

    # --- Build report ---
    total_issues = len(merged_ids) + len(disabled_ids) + len(result.get('noise', {}).get('demoted', []))
    if total_issues > 0:
        header = f"Post-create guardrail: {total_issues} issues found in {len(created_ids)} new lessons"
        result['report'] = header + '\n' + '\n'.join(report_lines)
    else:
        result['report'] = f"Post-create guardrail: {len(created_ids)} new lessons — all clean"

    return result


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Find and merge duplicate lessons')
    parser.add_argument('--dry-run', action='store_true', help='Show duplicates without merging')
    parser.add_argument('--merge', action='store_true', help='Merge duplicates')
    parser.add_argument('--threshold', type=float, default=0.9, help='Similarity threshold')

    args = parser.parse_args()

    print(f'Finding duplicates with threshold {args.threshold}...')
    clusters = find_duplicate_lessons(args.threshold)

    if not clusters:
        print('No duplicates found.')
        sys.exit(0)

    print(f'\nFound {len(clusters)} duplicate clusters:')
    for i, cluster in enumerate(clusters, 1):
        print(f'\nCluster {i}: {len(cluster)} lessons')
        for lesson_id in cluster:
            print(f'  - {lesson_id}')

    if args.merge:
        print('\nMerging duplicates...')
        for cluster in clusters:
            result = merge_lessons(cluster)
            if result['success']:
                print(f"  Merged {result['primary']} (kept) with {', '.join(result['archived'])} (archived)")
            else:
                print(f"  Failed: {result['error']}")
    elif not args.dry_run:
        print('\nUse --merge to merge duplicates, or --dry-run to preview only')


def get_dedup_report(similarity_threshold: float = 0.9) -> Dict:
    """
    Get deduplication report without merging.

    Returns: Dict with clusters_found, total_duplicates, clusters
    """
    clusters = find_duplicate_lessons(similarity_threshold)

    if not clusters:
        return {
            'clusters_found': 0,
            'total_duplicates': 0,
            'clusters': []
        }

    lessons = load_patterns(platform=None, scope_type=None)
    lessons_by_id = {l['id']: l for l in lessons}

    report_clusters = []
    total_duplicates = 0

    for cluster in clusters:
        cluster_lessons = [lessons_by_id.get(lid) for lid in cluster if lid in lessons_by_id]

        if len(cluster_lessons) < 2:
            continue

        # Calculate average similarity within cluster
        similarities = []
        for i, la in enumerate(cluster_lessons):
            for lb in cluster_lessons[i+1:]:
                similarities.append(calculate_lesson_similarity(la, lb))

        avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0

        report_clusters.append({
            'lesson_ids': cluster,
            'titles': [l.get('title', '') for l in cluster_lessons],
            'similarity': avg_similarity
        })

        total_duplicates += len(cluster) - 1  # All except primary

    return {
        'clusters_found': len(report_clusters),
        'total_duplicates': total_duplicates,
        'clusters': report_clusters
    }