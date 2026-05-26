"""Flow Analyzer — Data flow analysis for taint tracking"""

import re
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class TaintFlow:
    """Represents a taint flow from source to sink"""
    source: str
    source_line: int
    sink: str
    sink_line: int
    flow_path: List[str]
    sanitized: bool
    risk_level: str


def trace_tainted_data(filepath: str, taint_sources: List[str] = None) -> List[TaintFlow]:
    """
    Trace data flow from taint sources to sinks.

    Taint sources: $_GET, $_POST, user input
    Sinks: echo, DB query, file operations

    Returns: List of taint flows without sanitization
    """
    if taint_sources is None:
        taint_sources = ['$_GET', '$_POST', '$_REQUEST', '$_SERVER']

    try:
        content = Path(filepath).read_text(encoding='utf-8')
        lines = content.split('\n')

        tainted_vars = {}
        flows = []

        for i, line in enumerate(lines, 1):
            _track_taint_sources(line, i, taint_sources, tainted_vars)
            _track_sanitization(line, i, tainted_vars)
            flows.extend(_detect_taint_sinks(line, i, tainted_vars))

        return flows

    except Exception as e:
        import sys
        print(f"[kiwi] trace_tainted_data error: {e}", file=sys.stderr)
        return []


def _track_taint_sources(line: str, line_num: int, sources: List[str], tainted_vars: Dict):
    """Track variables assigned from taint sources"""
    for source in sources:
        if source in line:
            match = re.search(r'\$(\w+)\s*=\s*' + re.escape(source), line)
            if match:
                var_name = '$' + match.group(1)
                tainted_vars[var_name] = {
                    'source': source,
                    'source_line': line_num,
                    'sanitized': False,
                    'flow_path': [source]
                }

            match = re.search(re.escape(source) + r'\[([\'"]?)(\w+)\1\]', line)
            if match:
                key = match.group(2)
                var_name = f'{source}[{key}]'
                tainted_vars[var_name] = {
                    'source': source,
                    'source_line': line_num,
                    'sanitized': False,
                    'flow_path': [f'{source}[{key}]']
                }


def _track_sanitization(line: str, line_num: int, tainted_vars: Dict):
    """Track sanitization of tainted variables"""
    sanitize_funcs = [
        'sanitize_text_field', 'sanitize_email', 'sanitize_url',
        'esc_html', 'esc_attr', 'esc_url', 'esc_js',
        'absint', 'intval', 'floatval'
    ]

    for func in sanitize_funcs:
        if func in line:
            for var_name in list(tainted_vars.keys()):
                if var_name in line:
                    tainted_vars[var_name]['sanitized'] = True
                    tainted_vars[var_name]['flow_path'].append(f'{func}()')


def _detect_taint_sinks(line: str, line_num: int, tainted_vars: Dict) -> List[TaintFlow]:
    """Detect tainted data reaching sinks"""
    flows = []

    sinks = {
        'echo': 'XSS',
        'print': 'XSS',
        '$wpdb->query': 'SQL Injection',
        '$wpdb->get_results': 'SQL Injection',
        '$wpdb->insert': 'SQL Injection',
        'file_get_contents': 'Path Traversal',
        'file_put_contents': 'Path Traversal',
        'include': 'File Inclusion',
        'require': 'File Inclusion',
        'eval': 'Code Injection',
        'system': 'Command Injection',
        'exec': 'Command Injection',
        'shell_exec': 'Command Injection'
    }

    for sink, risk in sinks.items():
        if sink in line:
            for var_name, info in tainted_vars.items():
                if var_name in line and not info['sanitized']:
                    flows.append(TaintFlow(
                        source=info['source'],
                        source_line=info['source_line'],
                        sink=sink,
                        sink_line=line_num,
                        flow_path=info['flow_path'] + [sink],
                        sanitized=False,
                        risk_level=risk
                    ))

    return flows


def analyze_race_conditions(filepath: str) -> List[Dict]:
    """
    Detect race conditions in concurrent operations.

    Patterns:
    - Read-modify-write without lock
    - Stock decrement without atomic check
    - Coupon usage without transaction
    """
    violations = []

    try:
        content = Path(filepath).read_text(encoding='utf-8')
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            if re.search(r'(stock|quantity|inventory)\s*-=\s*\d+', line):
                context = '\n'.join(lines[max(0, i-5):min(len(lines), i+5)])
                if not _has_transaction_or_lock(context):
                    violations.append({
                        'line': i,
                        'type': 'race_condition',
                        'description': 'Stock decrement without transaction/lock',
                        'risk': 'CRITICAL',
                        'suggestion': 'Wrap in database transaction or use atomic operation'
                    })

            if re.search(r'usage_count\s*\+=\s*1', line):
                context = '\n'.join(lines[max(0, i-5):min(len(lines), i+5)])
                if not _has_transaction_or_lock(context):
                    violations.append({
                        'line': i,
                        'type': 'race_condition',
                        'description': 'Coupon usage increment not atomic',
                        'risk': 'HIGH',
                        'suggestion': 'Use atomic increment or transaction'
                    })

            if re.search(r'\$\w+\s*=\s*get_option\([^)]+\)', line):
                next_lines = lines[i:min(len(lines), i+10)]
                if any(re.search(r'update_option\([^)]+,\s*\$\w+', nl) for nl in next_lines):
                    context = '\n'.join(lines[max(0, i-5):min(len(lines), i+15)])
                    if not _has_transaction_or_lock(context):
                        violations.append({
                            'line': i,
                            'type': 'race_condition',
                            'description': 'Read-modify-write on option without lock',
                            'risk': 'MEDIUM',
                            'suggestion': 'Use wp_cache_add() for locking or atomic operation'
                        })

    except Exception as e:
        import sys
        print(f"[kiwi] race_condition_detector error: {e}", file=sys.stderr)

    return violations


def _has_transaction_or_lock(context: str) -> bool:
    """Check if context has transaction or lock"""
    patterns = [
        r'BEGIN',
        r'START TRANSACTION',
        r'LOCK TABLES',
        r'wp_cache_add\(',
        r'->beginTransaction\(',
        r'atomic',
        r'LOCK IN SHARE MODE',
        r'FOR UPDATE'
    ]

    for pattern in patterns:
        if re.search(pattern, context, re.IGNORECASE):
            return True

    return False


def detect_async_errors(filepath: str) -> List[Dict]:
    """
    Detect unhandled errors in async operations.

    Patterns:
    - Promise without .catch()
    - async function without try-catch
    - fetch without error handling
    """
    violations = []

    try:
        content = Path(filepath).read_text(encoding='utf-8')
        lines = content.split('\n')

        in_async_func = False
        async_func_start = 0

        for i, line in enumerate(lines, 1):
            if re.search(r'async\s+(function|\w+\s*\()', line):
                in_async_func = True
                async_func_start = i

            if in_async_func and re.search(r'^\s*\}', line):
                func_body = '\n'.join(lines[async_func_start-1:i])
                if 'await' in func_body and 'try' not in func_body:
                    violations.append({
                        'line': async_func_start,
                        'type': 'async_error',
                        'description': 'Async function with await but no try-catch',
                        'risk': 'HIGH',
                        'suggestion': 'Wrap await calls in try-catch block'
                    })
                in_async_func = False

            if re.search(r'\.then\(', line):
                context = '\n'.join(lines[i-1:min(len(lines), i+5)])
                if '.catch(' not in context:
                    violations.append({
                        'line': i,
                        'type': 'async_error',
                        'description': 'Promise without .catch() handler',
                        'risk': 'HIGH',
                        'suggestion': 'Add .catch() to handle promise rejection'
                    })

            if re.search(r'fetch\(', line):
                context = '\n'.join(lines[i-1:min(len(lines), i+10)])
                if not re.search(r'(\.catch\(|try\s*\{)', context):
                    violations.append({
                        'line': i,
                        'type': 'async_error',
                        'description': 'fetch() without error handling',
                        'risk': 'HIGH',
                        'suggestion': 'Add .catch() or wrap in try-catch'
                    })

    except Exception as e:
        import sys
        print(f"[kiwi] unhandled_async_detector error: {e}", file=sys.stderr)

    return violations


def generate_flow_report(filepath: str) -> Dict:
    """Generate comprehensive flow analysis report"""
    taint_flows = trace_tainted_data(filepath)
    race_conditions = analyze_race_conditions(filepath)
    async_errors = detect_async_errors(filepath)

    critical_flows = [f for f in taint_flows if f.risk_level in ['SQL Injection', 'Command Injection', 'Code Injection']]
    high_flows = [f for f in taint_flows if f.risk_level in ['XSS', 'Path Traversal', 'File Inclusion']]

    return {
        'file': filepath,
        'taint_flows': {
            'total': len(taint_flows),
            'critical': len(critical_flows),
            'high': len(high_flows),
            'flows': taint_flows
        },
        'race_conditions': {
            'total': len(race_conditions),
            'violations': race_conditions
        },
        'async_errors': {
            'total': len(async_errors),
            'violations': async_errors
        },
        'overall_risk': _calculate_overall_risk(taint_flows, race_conditions, async_errors)
    }


def _calculate_overall_risk(taint_flows: List[TaintFlow], race_conditions: List[Dict], async_errors: List[Dict]) -> str:
    """Calculate overall risk level"""
    critical_count = sum(1 for f in taint_flows if f.risk_level in ['SQL Injection', 'Command Injection', 'Code Injection'])
    critical_count += sum(1 for r in race_conditions if r['risk'] == 'CRITICAL')

    if critical_count > 0:
        return 'CRITICAL'

    high_count = len(taint_flows) - critical_count
    high_count += sum(1 for r in race_conditions if r['risk'] == 'HIGH')
    high_count += len(async_errors)

    if high_count > 5:
        return 'HIGH'
    elif high_count > 0:
        return 'MEDIUM'

    return 'LOW'