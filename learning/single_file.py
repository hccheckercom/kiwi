"""Single-File Auto-Learning — Extract patterns from a single file.

This file contains pattern templates and detection logic.
All hardcoded credentials and eval() patterns below are for DETECTION purposes only.
"""  # nosec

import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from learning.models import SuggestedPattern


def extract_patterns_from_file(
    file_path: str,
    violations: List[Dict] = None,
    min_confidence: float = 0.7
) -> List[SuggestedPattern]:
    """
    Extract bug patterns from a single file.

    Args:
        file_path: Path to file to analyze
        violations: Optional pre-scanned violations (from kiwi_scan)
        min_confidence: Minimum confidence threshold (0-1)

    Returns:
        List of suggested patterns with metadata

    Algorithm:
    1. If violations provided → analyze violation patterns
    2. Run 10 detectors from agent/learn.py
    3. Extract code structure (basic parsing)
    4. Apply heuristics (frequency, severity, category)
    5. Generate lesson metadata (title, why, bad/good code)
    6. Filter by confidence threshold
    7. Return sorted by confidence (high → low)
    """
    if not os.path.isfile(file_path):
        return []

    # Detect file type
    ext = Path(file_path).suffix.lower()

    # Run detectors based on file type
    if ext == '.php':
        patterns = _run_php_detectors(file_path)
    elif ext in ['.js', '.ts', '.jsx', '.tsx']:
        patterns = _run_js_detectors(file_path)
    else:
        # Unsupported file type
        return []

    if not patterns:
        return []

    # Extract code structure
    structure = _extract_code_structure(file_path)

    # Apply heuristics to generate suggestions
    suggestions = _apply_heuristics(patterns, structure, file_path)

    # Filter by confidence threshold
    suggestions = [s for s in suggestions if s.confidence >= min_confidence]

    # Sort by confidence (high → low)
    suggestions.sort(key=lambda s: s.confidence, reverse=True)

    # Insert into database
    for suggestion in suggestions:
        _insert_suggested_lesson(suggestion)

    return suggestions


def _run_php_detectors(file_path: str) -> List[Tuple[str, int, str]]:
    """Run 10 PHP detectors on single file."""
    patterns = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"[kiwi] _run_php_detectors read error: {e}", file=sys.stderr)
        return patterns

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Pattern 1: Hardcoded credentials
        if re.search(r'(password|secret|api_key|token)\s*=\s*["\'][^"\']+["\']', stripped, re.I):
            patterns.append(('hardcoded_credentials', i, stripped))

        # Pattern 2: SQL concatenation (injection risk)
        if re.search(r'\$wpdb->(query|prepare|get_results).*\.\s*\$', stripped):
            patterns.append(('sql_injection', i, stripped))

        # Pattern 3: Unescaped output
        if re.search(r'echo\s+\$|print\s+\$', stripped) and 'esc_' not in stripped:
            patterns.append(('xss_risk', i, stripped))

        # Pattern 4: Missing nonce check
        if 'isset($_POST' in stripped and 'wp_verify_nonce' not in stripped:
            patterns.append(('missing_nonce', i, stripped))

        # Pattern 5: Direct file inclusion
        if re.search(r'(include|require)(_once)?\s*\(\s*\$', stripped):
            patterns.append(('file_inclusion', i, stripped))

        # Pattern 6: Hardcoded URLs
        if re.search(r'https?://[a-z0-9.-]+\.[a-z]{2,}', stripped, re.I):
            if 'home_url' not in stripped and 'site_url' not in stripped:
                patterns.append(('hardcoded_url', i, stripped))

        # Pattern 7: Missing error handling
        if re.search(r'(file_get_contents|curl_exec|wp_remote_get)\(', stripped):
            has_error_check = False
            for j in range(i, min(i+3, len(lines))):
                if 'is_wp_error' in lines[j] or 'if' in lines[j]:
                    has_error_check = True
                    break
            if not has_error_check:
                patterns.append(('missing_error_handling', i, stripped))

        # Pattern 8: Deprecated functions
        deprecated = ['mysql_query', 'ereg', 'split', 'create_function']
        for dep in deprecated:
            if dep in stripped:
                patterns.append(('deprecated_function', i, stripped))

        # Pattern 9: Inefficient loops
        if re.search(r'for.*count\(', stripped) or re.search(r'while.*count\(', stripped):
            patterns.append(('inefficient_loop', i, stripped))

        # Pattern 10: Missing sanitization
        if re.search(r'\$_(GET|POST|REQUEST)\[', stripped):
            if not re.search(r'sanitize_|absint|intval|esc_', stripped):
                patterns.append(('missing_sanitization', i, stripped))

    return patterns


def _run_js_detectors(file_path: str) -> List[Tuple[str, int, str]]:
    """Run 5 JS/TS detectors on single file."""
    patterns = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"[kiwi] _run_js_detectors read error: {e}", file=sys.stderr)
        return patterns

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Pattern 11: Hardcoded API keys
        if re.search(r'(apiKey|api_key|API_KEY|token|TOKEN)\s*[:=]\s*["\'][^"\']{20,}["\']', stripped, re.I):
            patterns.append(('hardcoded_api_key', i, stripped))

        # Pattern 12: eval() usage
        if re.search(r'\beval\s*\(', stripped):
            patterns.append(('eval_usage', i, stripped))

        # Pattern 13: innerHTML without sanitization
        if 'innerHTML' in stripped and 'sanitize' not in stripped.lower():
            patterns.append(('innerhtml_xss', i, stripped))

        # Pattern 14: Missing error handling for fetch/axios
        if re.search(r'(fetch|axios)\s*\(', stripped):
            has_error_check = False
            for j in range(i, min(i+3, len(lines))):
                if 'catch' in lines[j] or '.catch' in lines[j]:
                    has_error_check = True
                    break
            if not has_error_check:
                patterns.append(('missing_fetch_error', i, stripped))

        # Pattern 15: console.log in production
        if re.search(r'console\.(log|debug|info)\(', stripped):
            patterns.append(('console_log_production', i, stripped))

    return patterns


def _extract_code_structure(file_path: str) -> Dict:
    """Extract basic code structure (functions, classes, imports)."""
    structure = {
        'functions': [],
        'classes': [],
        'imports': [],
        'line_count': 0
    }

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        structure['line_count'] = len(lines)

        for line in lines:
            stripped = line.strip()

            # PHP functions
            if re.match(r'function\s+(\w+)\s*\(', stripped):
                match = re.search(r'function\s+(\w+)\s*\(', stripped)
                if match:
                    structure['functions'].append(match.group(1))

            # PHP classes
            if re.match(r'class\s+(\w+)', stripped):
                match = re.search(r'class\s+(\w+)', stripped)
                if match:
                    structure['classes'].append(match.group(1))

            # JS/TS functions
            if re.match(r'(function|const|let|var)\s+(\w+)\s*=', stripped):
                match = re.search(r'(function|const|let|var)\s+(\w+)\s*=', stripped)
                if match:
                    structure['functions'].append(match.group(2))

            # Imports
            if stripped.startswith('import ') or stripped.startswith('require('):
                structure['imports'].append(stripped)

    except Exception as e:
        print(f"[kiwi] _extract_code_structure error: {e}", file=sys.stderr)

    return structure


def _apply_heuristics(
    patterns: List[Tuple[str, int, str]],
    structure: Dict,
    file_path: str
) -> List[SuggestedPattern]:
    """Apply frequency, severity, category heuristics."""
    from collections import Counter

    # Count pattern occurrences
    pattern_counts = Counter(p[0] for p in patterns)

    suggestions = []
    seen_types = set()

    for pattern_type, line_num, code in patterns:
        # Skip duplicates (only suggest each pattern type once)
        if pattern_type in seen_types:
            continue
        seen_types.add(pattern_type)

        # Calculate frequency score
        frequency_score = _calculate_frequency_score(pattern_counts[pattern_type])

        # Infer severity
        severity = _infer_severity(pattern_type, code)

        # Infer category
        category = _infer_category(pattern_type, file_path, code)

        # Generate lesson metadata
        metadata = _generate_lesson_metadata(pattern_type, code, file_path)

        # Check if similar lesson exists
        has_existing_similar = _check_existing_similar(metadata['pattern'])

        # Calculate confidence
        confidence = _calculate_confidence(
            frequency_score,
            has_existing_similar,
            structure['line_count']
        )

        # Create suggestion
        suggestion = SuggestedPattern(
            pattern=metadata['pattern'],
            scope=metadata['scope'],
            category=category,
            severity=severity,
            example_file=file_path,
            example_line=line_num,
            example_code=code,
            occurrence_count=pattern_counts[pattern_type],
            confidence=confidence,
            files=[file_path]
        )

        suggestions.append(suggestion)

    return suggestions


def _calculate_frequency_score(count: int) -> float:
    """Score based on pattern frequency in file."""
    if count == 1:
        return 0.5
    elif count <= 3:
        return 0.7
    else:
        return 0.9


def _infer_severity(pattern_type: str, code: str) -> str:
    """Infer severity from pattern type and code context."""
    # Security patterns → CRITICAL
    security_patterns = [
        'hardcoded_credentials', 'sql_injection', 'xss_risk',
        'missing_nonce', 'file_inclusion', 'hardcoded_api_key',
        'eval_usage', 'innerhtml_xss', 'missing_sanitization'
    ]

    if pattern_type in security_patterns:
        return 'CRITICAL'

    # Performance patterns → HIGH
    performance_patterns = ['inefficient_loop', 'missing_fetch_error']

    if pattern_type in performance_patterns:
        return 'HIGH'

    # Code quality → SUGGEST
    return 'SUGGEST'


def _infer_category(pattern_type: str, file_path: str, code: str) -> str:
    """Infer category from file extension + code context."""
    ext = Path(file_path).suffix.lower()

    # PHP patterns
    if ext == '.php':
        if pattern_type in ['sql_injection', 'xss_risk', 'missing_nonce', 'file_inclusion', 'hardcoded_credentials', 'missing_sanitization']:
            return 'php-security'
        if 'wc_' in code or 'WC_' in code:
            return 'wezone-api'
        if pattern_type == 'hardcoded_url':
            return 'portability'
        if pattern_type == 'missing_error_handling':
            return 'reliability'
        if pattern_type == 'deprecated_function':
            return 'compatibility'
        if pattern_type == 'inefficient_loop':
            return 'performance'

    # JS/TS patterns
    if ext in ['.js', '.ts', '.jsx', '.tsx']:
        if pattern_type in ['hardcoded_api_key', 'eval_usage', 'innerhtml_xss']:
            return 'js-security'
        if 'fetch' in code or 'axios' in code:
            return 'js-contract'
        if 'useState' in code or 'useEffect' in code:
            return 'nextjs-react'

    return 'code-quality'


def _generate_lesson_metadata(pattern_type: str, code: str, file_path: str) -> Dict:
    """Generate title, pattern, scope, why, bad/good code for lesson."""

    # Pattern metadata templates
    templates = {
        'hardcoded_credentials': {
            'title': 'Hardcoded Credentials in Source Code',
            'pattern': r'(password|secret|api_key|token)\s*=\s*["\'][^"\']+["\']',
            'scope': '**/*.php',
            'why': 'Hardcoded credentials in source code can be exposed via version control',
            'bad': 'define("API_KEY", "sk_live_abc123");',
            'good': 'define("API_KEY", getenv("API_KEY"));'
        },
        'sql_injection': {
            'title': 'SQL Injection via String Concatenation',
            'pattern': r'\$wpdb->(query|get_results).*\.\s*\$',
            'scope': '**/*.php',
            'why': 'String concatenation in SQL queries enables SQL injection attacks',
            'bad': '$wpdb->query("SELECT * FROM table WHERE id = " . $_GET["id"]);',
            'good': '$wpdb->prepare("SELECT * FROM table WHERE id = %d", $_GET["id"]);'
        },
        'xss_risk': {
            'title': 'XSS Risk - Unescaped Output',
            'pattern': r'echo\s+\$(?!.*esc_)',
            'scope': '**/*.php',
            'why': 'Unescaped output enables XSS attacks',
            'bad': 'echo $user_input;',
            'good': 'echo esc_html($user_input);'
        },
        'missing_nonce': {
            'title': 'Missing Nonce Verification in Form Handler',
            'pattern': r'isset\(\$_POST.*(?!.*wp_verify_nonce)',
            'scope': '**/*.php',
            'why': 'Missing nonce check enables CSRF attacks',
            'bad': 'if (isset($_POST["action"])) { process(); }',
            'good': 'if (isset($_POST["action"]) && wp_verify_nonce($_POST["_wpnonce"], "action")) { process(); }'
        },
        'file_inclusion': {
            'title': 'Arbitrary File Inclusion Risk',
            'pattern': r'(include|require)(_once)?\s*\(\s*\$',
            'scope': '**/*.php',
            'why': 'Dynamic file inclusion with user input enables arbitrary code execution',
            'bad': 'include($_GET["page"] . ".php");',
            'good': '$allowed = ["home", "about"]; if (in_array($_GET["page"], $allowed)) include($_GET["page"] . ".php");'
        },
        'hardcoded_url': {
            'title': 'Hardcoded URL Instead of WordPress Functions',
            'pattern': r'https?://[a-z0-9.-]+\.[a-z]{2,}',
            'scope': '**/*.php',
            'why': 'Hardcoded URLs break when site domain changes',
            'bad': '$url = "https://example.com/wp-content/uploads/";',
            'good': '$url = wp_upload_dir()["baseurl"] . "/";'
        },
        'missing_error_handling': {
            'title': 'Missing Error Handling for External Calls',
            'pattern': r'(wp_remote_get|file_get_contents|curl_exec)\(',
            'scope': '**/*.php',
            'why': 'External calls can fail; missing error handling causes fatal errors',
            'bad': '$data = wp_remote_get($url);',
            'good': '$response = wp_remote_get($url); if (is_wp_error($response)) return;'
        },
        'deprecated_function': {
            'title': 'Deprecated PHP Function Usage',
            'pattern': r'(mysql_query|ereg|split|create_function)\(',
            'scope': '**/*.php',
            'why': 'Deprecated functions removed in PHP 7+ cause fatal errors',
            'bad': 'mysql_query("SELECT * FROM table");',
            'good': '$wpdb->get_results("SELECT * FROM table");'
        },
        'inefficient_loop': {
            'title': 'Inefficient Loop - count() in Condition',
            'pattern': r'(for|while).*count\(',
            'scope': '**/*.php',
            'why': 'count() called every iteration causes O(n²) complexity',
            'bad': 'for ($i = 0; $i < count($arr); $i++) {}',
            'good': '$len = count($arr); for ($i = 0; $i < $len; $i++) {}'
        },
        'missing_sanitization': {
            'title': 'Missing Input Sanitization',
            'pattern': r'\$_(GET|POST|REQUEST)\[(?!.*sanitize_)',
            'scope': '**/*.php',
            'why': 'Unsanitized user input can cause security vulnerabilities',
            'bad': '$name = $_POST["name"];',
            'good': '$name = sanitize_text_field($_POST["name"]);'
        },
        'hardcoded_api_key': {
            'title': 'Hardcoded API Key in JavaScript',
            'pattern': r'(apiKey|api_key|API_KEY|token|TOKEN)\s*[:=]\s*["\'][^"\']{20,}["\']',
            'scope': '**/*.{js,ts,jsx,tsx}',
            'why': 'Hardcoded API keys in client-side code are publicly visible',
            'bad': 'const apiKey = "sk_live_abc123def456";',
            'good': 'const apiKey = process.env.NEXT_PUBLIC_API_KEY;'
        },
        'eval_usage': {
            'title': 'Dangerous eval() Usage',
            'pattern': r'\beval\s*\(',
            'scope': '**/*.{js,ts,jsx,tsx}',
            'why': 'eval() enables arbitrary code execution and is a security risk',
            'bad': 'eval(userInput);',
            'good': 'JSON.parse(userInput); // Use safe parsing instead'
        },
        'innerhtml_xss': {
            'title': 'XSS Risk - innerHTML Without Sanitization',
            'pattern': r'\.innerHTML\s*=(?!.*sanitize)',
            'scope': '**/*.{js,ts,jsx,tsx}',
            'why': 'Setting innerHTML with unsanitized data enables XSS attacks',
            'bad': 'element.innerHTML = userInput;',
            'good': 'element.textContent = userInput; // Or use DOMPurify.sanitize()'
        },
        'missing_fetch_error': {
            'title': 'Missing Error Handling for fetch/axios',
            'pattern': r'(fetch|axios)\s*\((?!.*catch)',
            'scope': '**/*.{js,ts,jsx,tsx}',
            'why': 'Network requests can fail; missing error handling causes unhandled rejections',
            'bad': 'fetch(url).then(r => r.json());',
            'good': 'fetch(url).then(r => r.json()).catch(err => console.error(err));'
        },
        'console_log_production': {
            'title': 'console.log in Production Code',
            'pattern': r'console\.(log|debug|info)\(',
            'scope': '**/*.{js,ts,jsx,tsx}',
            'why': 'Console logs expose debug information and clutter production logs',
            'bad': 'console.log("User data:", userData);',
            'good': '// Remove console.log or use proper logging library'
        }
    }

    return templates.get(pattern_type, {
        'title': f'Pattern: {pattern_type}',
        'pattern': '',
        'scope': '**/*',
        'why': 'Auto-detected pattern',
        'bad': code,
        'good': ''
    })


def _check_existing_similar(pattern: str) -> bool:
    """Check if similar lesson already exists."""
    from pathlib import Path

    lessons_dir = Path(__file__).parent.parent / 'lessons'

    if not lessons_dir.exists():
        return False

    # Simple check: search for similar pattern in existing lessons
    for lesson_file in lessons_dir.rglob('*.md'):
        try:
            content = lesson_file.read_text(encoding='utf-8')
            if pattern and pattern in content:
                return True
        except Exception as e:
            continue

    return False


def _calculate_confidence(
    frequency_score: float,
    has_existing_similar: bool,
    line_count: int
) -> float:
    """Combine multiple signals into confidence score."""
    # Base: frequency_score (0.5-0.9)
    confidence = frequency_score

    # Boost +0.1 if similar lesson exists (validates pattern)
    if has_existing_similar:
        confidence += 0.1

    # Penalty -0.2 if code too complex (>500 lines)
    if line_count > 500:
        confidence -= 0.2

    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, confidence))


def _insert_suggested_lesson(pattern: SuggestedPattern) -> int:
    """Insert suggested pattern into database."""
    import json
    from datetime import datetime, timezone

    from memory.db import get_connection

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
