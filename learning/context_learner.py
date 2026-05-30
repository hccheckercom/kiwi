"""Context-Aware Learning — Học patterns từ fix context"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class ContextualLesson:
    """Contextual pattern learned from fix"""
    context_pattern: str
    violation_pattern: str
    fix_pattern: str
    confidence: float
    examples: List[Dict]


def learn_from_fix_context(file: str, line: int, fix_diff: str) -> Optional[ContextualLesson]:
    """
    Learn contextual patterns from successful fixes.

    Algorithm:
    1. Parse file AST
    2. Find enclosing function/class
    3. Extract context: function name, params, return type
    4. Analyze fix diff: what changed?
    5. Create contextual pattern: "In function X, pattern Y needs fix Z"

    Returns: ContextualLesson if pattern is generalizable
    """
    try:
        from .ast_detector import ASTPatternDetector

        detector = ASTPatternDetector()
        if not detector.parser:
            return None

        content = Path(file).read_bytes()
        tree = detector.parser.parse(content)
        root = tree.root_node

        node = _find_node_at_line(root, line)
        if not node:
            return None

        context = _extract_context(node, content)
        if not context:
            return None

        fix_type = _analyze_fix_diff(fix_diff)
        if not fix_type:
            return None

        if _is_generalizable(context, fix_type):
            lesson = _create_contextual_lesson(context, fix_type, fix_diff)
            return lesson

        return None

    except Exception as e:
        import sys
        print(f"[kiwi] context_learner error: {e}", file=sys.stderr)
        return None


def _find_node_at_line(root, line_number: int):
    """Find AST node at specific line"""
    def traverse(node):
        if node.start_point[0] + 1 == line_number:
            return node
        for child in node.children:
            result = traverse(child)
            if result:
                return result
        return None

    return traverse(root)


def _extract_context(node, content: bytes) -> Optional[Dict]:
    """Extract context from AST node"""
    current = node
    while current:
        if current.type == 'function_definition':
            func_name = _get_function_name(current, content)
            params = _get_function_params(current, content)
            has_nonce = _has_nonce_check(current, content)

            return {
                'type': 'function',
                'name': func_name,
                'params': params,
                'has_nonce_check': has_nonce,
                'pattern': _infer_function_pattern(func_name)
            }

        elif current.type == 'class_declaration':
            class_name = _get_class_name(current, content)
            return {
                'type': 'class',
                'name': class_name,
                'pattern': _infer_class_pattern(class_name)
            }

        current = current.parent

    return None


def _get_function_name(node, content: bytes) -> str:
    """Extract function name from node"""
    for child in node.children:
        if child.type == 'name':
            return content[child.start_byte:child.end_byte].decode('utf-8', errors='ignore')
    return ''


def _get_function_params(node, content: bytes) -> List[str]:
    """Extract function parameters"""
    params = []
    for child in node.children:
        if child.type == 'formal_parameters':
            for param in child.children:
                if param.type == 'simple_parameter':
                    param_text = content[param.start_byte:param.end_byte].decode('utf-8', errors='ignore')
                    params.append(param_text)
    return params


def _has_nonce_check(node, content: bytes) -> bool:
    """Check if function has nonce verification"""
    func_content = content[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
    return 'wp_verify_nonce' in func_content or 'check_ajax_referer' in func_content


def _infer_function_pattern(func_name: str) -> str:
    """Infer function pattern from name"""
    if re.match(r'handle_.*_ajax', func_name):
        return 'ajax_handler'
    elif re.match(r'process_.*_form', func_name):
        return 'form_handler'
    elif re.match(r'save_.*', func_name):
        return 'save_handler'
    elif re.match(r'delete_.*', func_name):
        return 'delete_handler'
    return 'generic'


def _infer_class_pattern(class_name: str) -> str:
    """Infer class pattern from name"""
    if 'Controller' in class_name:
        return 'controller'
    elif 'Service' in class_name:
        return 'service'
    elif 'Repository' in class_name:
        return 'repository'
    return 'generic'


def _analyze_fix_diff(fix_diff: str) -> Optional[str]:
    """Analyze fix diff to determine fix type.

    Recognition vocabulary MUST stay aligned with the hardening markers the
    post-edit hook triggers on (_HARDENING_MARKERS in hooks/post_edit_learn.py):
    if the hook fires but this returns None, the edit is examined and discarded,
    producing zero learning. check_ajax_referer is the nonce idiom this codebase
    actually uses (see LES-064), so it must map to add_nonce_check exactly like
    wp_verify_nonce.
    """
    if 'wp_verify_nonce' in fix_diff or 'check_ajax_referer' in fix_diff:
        return 'add_nonce_check'
    elif any(fn in fix_diff for fn in (
        'sanitize_text_field', 'esc_html', 'esc_attr', 'esc_url', 'wp_unslash'
    )):
        return 'add_sanitization'
    elif 'is_wp_error' in fix_diff:
        return 'add_error_handling'
    elif 'BEGIN' in fix_diff or 'COMMIT' in fix_diff:
        return 'add_transaction'
    elif 'try' in fix_diff and 'catch' in fix_diff:
        return 'add_try_catch'
    return None


def _is_generalizable(context: Dict, fix_type: str) -> bool:
    """Check if pattern is generalizable"""
    if context['type'] == 'function':
        pattern = context.get('pattern', '')

        if pattern == 'ajax_handler' and fix_type == 'add_nonce_check':
            return True
        elif pattern == 'form_handler' and fix_type == 'add_sanitization':
            return True
        elif fix_type == 'add_error_handling':
            return True

    return False


def _create_contextual_lesson(context: Dict, fix_type: str, fix_diff: str) -> ContextualLesson:
    """Create contextual lesson from context and fix"""
    if context['pattern'] == 'ajax_handler' and fix_type == 'add_nonce_check':
        return ContextualLesson(
            context_pattern='handle_.*_ajax',
            violation_pattern='wp_ajax_.*',
            fix_pattern='Add wp_verify_nonce() at function start',
            confidence=0.85,
            examples=[{
                'context': context,
                'fix': fix_diff
            }]
        )

    elif context['pattern'] == 'form_handler' and fix_type == 'add_sanitization':
        return ContextualLesson(
            context_pattern='process_.*_form',
            violation_pattern=r'\$_POST\[',
            fix_pattern='Add sanitize_text_field() before use',
            confidence=0.80,
            examples=[{
                'context': context,
                'fix': fix_diff
            }]
        )

    elif fix_type == 'add_error_handling':
        return ContextualLesson(
            context_pattern='.*',
            violation_pattern='wp_remote_(get|post)',
            fix_pattern='Add is_wp_error() check after call',
            confidence=0.75,
            examples=[{
                'context': context,
                'fix': fix_diff
            }]
        )

    return ContextualLesson(
        context_pattern='.*',
        violation_pattern='.*',
        fix_pattern='Generic fix',
        confidence=0.5,
        examples=[{
            'context': context,
            'fix': fix_diff
        }]
    )


def save_contextual_lesson(lesson: ContextualLesson) -> bool:
    """Save contextual lesson to database"""
    try:
        from memory.db import get_connection

        conn = get_connection()
        try:
            conn.execute("""
                INSERT INTO contextual_lessons
                (context_pattern, violation_pattern, fix_pattern, confidence, examples)
                VALUES (?, ?, ?, ?, ?)
            """, (
                lesson.context_pattern,
                lesson.violation_pattern,
                lesson.fix_pattern,
                lesson.confidence,
                json.dumps(lesson.examples)
            ))
            conn.commit()
        finally:
            conn.close()
        return True

    except Exception as e:
        import sys
        print(f"[kiwi] context_learner error: {e}", file=sys.stderr)
        return False


def get_contextual_lessons(min_confidence: float = 0.7) -> List[ContextualLesson]:
    """Get contextual lessons from database"""
    try:
        from memory.db import get_connection

        conn = get_connection()
        try:
            rows = conn.execute("""
                SELECT context_pattern, violation_pattern, fix_pattern, confidence, examples
                FROM contextual_lessons
                WHERE confidence >= ?
                ORDER BY confidence DESC
            """, (min_confidence,)).fetchall()
        finally:
            conn.close()

        lessons = []
        for row in rows:
            examples = []
            raw = row[4]
            if raw:
                # Writer now emits json.dumps; older rows were saved with str()
                # (Python repr, single quotes) which json.loads rejects. Parse
                # per-row and fall back to literal_eval so ONE legacy/bad row
                # can't blank the entire result set for the consumer.
                try:
                    examples = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    try:
                        import ast
                        examples = ast.literal_eval(raw)
                    except (ValueError, SyntaxError):
                        examples = []
            lessons.append(ContextualLesson(
                context_pattern=row[0],
                violation_pattern=row[1],
                fix_pattern=row[2],
                confidence=row[3],
                examples=examples,
            ))

        return lessons

    except Exception as e:
        import sys
        print(f"[kiwi] contextual_lessons error: {e}", file=sys.stderr)
        return []