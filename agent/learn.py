"""Kiwi Learn from Folder — Auto-detect patterns and create lessons."""

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Tuple

KIWI_DIR = Path(__file__).parent.parent
PATTERNS_DIR = KIWI_DIR / 'learning' / 'patterns'

_catalog_cache = {}


def _load_catalog(language: str) -> List[Dict]:
    """Load pattern catalog from JSON file. Cached per language."""
    if language in _catalog_cache:
        return _catalog_cache[language]

    catalog_file = PATTERNS_DIR / f'{language}.json'
    if not catalog_file.exists():
        _catalog_cache[language] = []
        return []

    try:
        data = json.loads(catalog_file.read_text(encoding='utf-8'))
        patterns = data.get('patterns', [])
        _catalog_cache[language] = patterns
        return patterns
    except Exception as e:
        print(f"[kiwi] Failed to load catalog {catalog_file}: {e}", file=sys.stderr)
        _catalog_cache[language] = []
        return []


def _extract_from_catalog(file_path: str, language: str) -> List[Tuple[str, int, str]]:
    """Generic extractor using JSON pattern catalog."""
    catalog = _load_catalog(language)
    if not catalog:
        return []

    results = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except (OSError, IOError, UnicodeDecodeError):
        return results

    for entry in catalog:
        detect = entry.get('detect', '')
        if not detect:
            continue

        exclude = entry.get('detect_exclude', '')
        context_lines = entry.get('detect_context_lines', 0)
        context_match = entry.get('detect_context_match', '')
        pattern_id = entry['id']

        try:
            detect_re = re.compile(detect, re.I if entry.get('case_insensitive') else 0)
            exclude_re = re.compile(exclude) if exclude else None
            context_re = re.compile(context_match) if context_match else None
        except re.error:
            continue

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''"):
                continue

            if detect_re.search(stripped):
                if exclude_re and exclude_re.search(stripped):
                    continue

                if context_lines and context_re:
                    block = ''.join(lines[max(0, i-1):min(i+context_lines, len(lines))])
                    if not context_re.search(block):
                        continue

                results.append((pattern_id, i, stripped))

    return results


def _extract_code_patterns(file_path: str) -> List[Tuple[str, int, str]]:
    """Extract potential bug patterns from a PHP file."""
    return _extract_from_catalog(file_path, 'php')


def _extract_js_patterns(file_path: str) -> List[Tuple[str, int, str]]:
    """Extract potential bug patterns from JS/TS files."""
    return _extract_from_catalog(file_path, 'js')


def _extract_py_patterns(file_path: str) -> List[Tuple[str, int, str]]:
    """Extract potential bug patterns from Python files."""
    return _extract_from_catalog(file_path, 'python')


def _cluster_patterns(all_patterns: Dict[str, List[Tuple[str, int, str]]]) -> Dict[str, Dict]:
    """Cluster similar patterns across files."""
    clusters = defaultdict(lambda: {'count': 0, 'files': set(), 'examples': []})

    for file_path, patterns in all_patterns.items():
        for pattern_type, line_num, code in patterns:
            clusters[pattern_type]['count'] += 1
            clusters[pattern_type]['files'].add(file_path)
            if len(clusters[pattern_type]['examples']) < 3:
                clusters[pattern_type]['examples'].append({
                    'file': file_path,
                    'line': line_num,
                    'code': code
                })

    return dict(clusters)


def _generate_lesson_suggestion(pattern_type: str, cluster: Dict) -> Dict:
    """Generate lesson suggestion from catalog entry or fallback."""

    # Look up in all catalogs
    for lang in ['python', 'php', 'js']:
        catalog = _load_catalog(lang)
        for entry in catalog:
            if entry['id'] == pattern_type:
                return {
                    'pattern_type': pattern_type,
                    'category': entry.get('category', 'code-quality'),
                    'severity': entry.get('severity', 'SUGGEST'),
                    'title': entry.get('title', f'Pattern: {pattern_type}'),
                    'pattern': entry.get('pattern', ''),
                    'why': entry.get('why', 'Auto-detected pattern'),
                    'bad_code': entry.get('bad', ''),
                    'good_code': entry.get('good', ''),
                    'occurrences': cluster['count'],
                    'files': list(cluster['files']),
                    'examples': cluster['examples']
                }

    return {
        'pattern_type': pattern_type,
        'category': 'code-quality',
        'severity': 'SUGGEST',
        'title': f'Pattern: {pattern_type}',
        'pattern': '',
        'why': 'Auto-detected pattern',
        'bad_code': '',
        'good_code': '',
        'occurrences': cluster['count'],
        'files': list(cluster['files']),
        'examples': cluster['examples']
    }


def gap_detect(scan_path: str = None, file_types: List[str] = None) -> Dict:
    """Compare catalog patterns vs existing lessons. Create missing ones.

    Returns: {
        'gaps': [{'catalog_id': ..., 'title': ..., 'language': ...}],
        'created': [{'lesson_id': ..., 'file': ...}],
        'already_covered': int
    }
    """
    sys.path.insert(0, str(KIWI_DIR))
    from scanner.loader import load_patterns, invalidate_cache
    from tools.add import add_lesson

    invalidate_cache()
    existing = load_patterns(include_disabled=True)
    existing_patterns = {l.get('pattern', '').strip() for l in existing if l.get('pattern')}
    existing_titles = {l.get('description', '').strip().lower() for l in existing if l.get('description')}

    languages = file_types or ['python', 'php', 'js']
    gaps = []
    already_covered = 0

    for lang in languages:
        catalog = _load_catalog(lang)
        for entry in catalog:
            pat = entry.get('pattern', '').strip()
            title = entry.get('title', '').strip().lower()

            if pat in existing_patterns or title in existing_titles:
                already_covered += 1
                continue

            gaps.append({
                'catalog_id': entry['id'],
                'title': entry.get('title', ''),
                'category': entry.get('category', 'code-quality'),
                'severity': entry.get('severity', 'SUGGEST'),
                'pattern': pat,
                'scope': entry.get('scope', '**/*'),
                'language': lang,
                'bad': entry.get('bad', ''),
                'good': entry.get('good', ''),
                'why': entry.get('why', ''),
            })

    created = []
    for gap in gaps:
        try:
            lesson_id, filepath = add_lesson(
                category=gap['category'],
                severity=gap['severity'],
                title=gap['title'],
                scan_type='presence',
                pattern=gap['pattern'],
                scope=gap['scope'],
                tags='both',
                bad_code=gap['bad'],
                good_code=gap['good'],
                why=gap['why'],
                source=f'gap-detect from {gap["language"]}.json',
            )
            created.append({'lesson_id': lesson_id, 'file': filepath, 'catalog_id': gap['catalog_id']})
        except Exception as e:
            print(f"  [warn] Failed to create lesson for {gap['title']}: {e}", file=sys.stderr)

    return {
        'gaps': gaps,
        'created': created,
        'already_covered': already_covered
    }


def learn_from_folder(
    path: str,
    min_occurrences: int = 3,
    auto_approve: bool = False,
    categories: List[str] = None,
    progress_callback = None,
    file_types: List[str] = None
) -> Dict:
    """Scan folder and auto-detect patterns for new lessons.

    Args:
        path: Folder to scan
        min_occurrences: Minimum pattern occurrences to suggest lesson
        auto_approve: If True, auto-create lessons; if False, return suggestions
        categories: Optional list of categories to focus on
        progress_callback: Optional callback(files_scanned, total_files, current_file)
        file_types: Optional list of file types to scan ('php', 'js', 'py'). Default: all

    Returns:
        {
            'scanned_files': int,
            'patterns_found': int,
            'suggestions': [...]
            'created_lessons': [...] (if auto_approve=True)
        }
    """
    if not os.path.isdir(path):
        return {'error': f'Path not found: {path}'}

    all_patterns = {}
    scan_php = not file_types or 'php' in file_types
    scan_js = not file_types or 'js' in file_types
    scan_py = not file_types or 'py' in file_types

    php_files = list(Path(path).rglob('*.php')) if scan_php else []
    js_files = (list(Path(path).rglob('*.js')) + list(Path(path).rglob('*.ts')) +
                list(Path(path).rglob('*.jsx')) + list(Path(path).rglob('*.tsx'))) if scan_js else []
    py_files = [f for f in Path(path).rglob('*.py')
                if '__pycache__' not in str(f) and '.pyc' not in str(f)] if scan_py else []

    all_files = php_files + js_files + py_files
    total_files = len(all_files)

    parts = []
    if php_files: parts.append(f"{len(php_files)} PHP")
    if js_files: parts.append(f"{len(js_files)} JS/TS")
    if py_files: parts.append(f"{len(py_files)} Python")
    print(f"Scanning {', '.join(parts)} files in {path}...", file=sys.stderr)

    for idx, file_path in enumerate(all_files, 1):
        if progress_callback and idx % 10 == 0:
            progress_callback(idx, total_files, str(file_path))

        if file_path.suffix == '.php':
            patterns = _extract_code_patterns(str(file_path))
        elif file_path.suffix == '.py':
            patterns = _extract_py_patterns(str(file_path))
        else:
            patterns = _extract_js_patterns(str(file_path))

        if patterns:
            all_patterns[str(file_path)] = patterns

    clusters = _cluster_patterns(all_patterns)
    filtered = {k: v for k, v in clusters.items() if v['count'] >= min_occurrences}

    if categories:
        filtered = {k: v for k, v in filtered.items()
                   if _generate_lesson_suggestion(k, v)['category'] in categories}

    suggestions = []
    for pattern_type, cluster in filtered.items():
        suggestion = _generate_lesson_suggestion(pattern_type, cluster)
        suggestions.append(suggestion)

    result = {
        'scanned_files': total_files,
        'patterns_found': len(clusters),
        'suggestions': suggestions
    }

    if auto_approve and suggestions:
        sys.path.insert(0, str(KIWI_DIR))
        from tools.add import add_lesson
        from scanner.loader import load_patterns, invalidate_cache

        invalidate_cache()
        existing_lessons = load_patterns(include_disabled=True)
        existing_patterns = set()
        existing_titles = set()
        for lesson in existing_lessons:
            p = lesson.get('pattern', '')
            if p:
                existing_patterns.add(p.strip())
            t = lesson.get('description', '')
            if t:
                existing_titles.add(t.strip().lower())

        created = []
        skipped_dupes = 0
        for sug in suggestions:
            if sug['pattern'] in existing_patterns:
                skipped_dupes += 1
                continue
            if sug['title'].strip().lower() in existing_titles:
                skipped_dupes += 1
                continue

            try:
                if sug['pattern_type'].startswith('js_'):
                    scope = '**/*.{js,ts,jsx,tsx}'
                elif sug['pattern_type'].startswith('py_'):
                    scope = '**/*.py'
                else:
                    scope = '**/*.php'

                lesson_id, filepath = add_lesson(
                    category=sug['category'],
                    severity=sug['severity'],
                    title=sug['title'],
                    scan_type='presence',
                    pattern=sug['pattern'],
                    scope=scope,
                    exclude='',
                    cross_check='',
                    cross_check_scope='',
                    source='auto-learned',
                    tags='both',
                    bad_code=sug['bad_code'],
                    good_code=sug['good_code'],
                    why=sug['why']
                )
                created.append({'lesson_id': lesson_id, 'file': filepath})
            except Exception as e:
                print(f"Failed to create lesson for {sug['title']}: {e}", file=sys.stderr)

        result['created_lessons'] = created
        if skipped_dupes:
            result['skipped_duplicates'] = skipped_dupes

    return result