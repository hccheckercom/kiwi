"""AST-based checker using tree-sitter for semantic code analysis."""

import os
from pathlib import Path

from ..models import Violation

_parser_cache = {}


def _get_parser(lang: str):
    """Get cached parser for language."""
    if lang in _parser_cache:
        return _parser_cache[lang]

    try:
        from tree_sitter import Language, Parser

        if lang == "php":
            import tree_sitter_php as tslang
            language = Language(tslang.language_php())
        elif lang == "javascript":
            import tree_sitter_javascript as tslang
            language = Language(tslang.language())
        else:
            return None

        parser = Parser(language)
        _parser_cache[lang] = parser
        return parser
    except ImportError:
        return None


def _detect_lang(filepath: str) -> str:
    ext = Path(filepath).suffix.lower()
    if ext == ".php":
        return "php"
    if ext in (".js", ".jsx", ".ts", ".tsx"):
        return "javascript"
    return ""


def _parse_file(filepath: str):
    """Parse file and return tree root, content, and error message."""
    lang = _detect_lang(filepath)
    if not lang:
        return None, None, f"Unsupported file type: {Path(filepath).suffix}"

    parser = _get_parser(lang)
    if not parser:
        return None, None, f"tree-sitter parser not available for {lang}"

    try:
        with open(filepath, "rb") as f:
            content = f.read()
        tree = parser.parse(content)
        return tree.root_node, content, None
    except (OSError, IOError) as e:
        return None, None, f"File read error: {str(e)}"
    except Exception as e:
        return None, None, f"Parse error: {str(e)}"


def _find_calls(node, fn_name: str, results=None):
    """Find all function call expressions matching fn_name."""
    if results is None:
        results = []
    if node.type == "function_call_expression":
        fn = node.child_by_field_name("function")
        if fn and fn.text and fn.text.decode("utf-8", errors="ignore") == fn_name:
            results.append(node)
    for child in node.children:
        _find_calls(child, fn_name, results)
    return results


def _find_loops(node, results=None):
    """Find all loop nodes."""
    if results is None:
        results = []
    if node.type in ("foreach_statement", "for_statement", "while_statement", "do_statement"):
        results.append(node)
    for child in node.children:
        _find_loops(child, results)
    return results


def _is_inside(call_node, container_nodes):
    """Check if call_node is inside any of the container nodes."""
    for container in container_nodes:
        if (container.start_byte <= call_node.start_byte
                and call_node.end_byte <= container.end_byte):
            return True
    return False


def _has_ancestor(node, ancestor_types: set) -> bool:
    """Check if node has an ancestor of given type."""
    current = node.parent
    while current:
        if current.type in ancestor_types:
            return True
        current = current.parent
    return False


def _file_has_call(root, fn_name: str) -> bool:
    """Check if file-level contains a specific function call."""
    calls = _find_calls(root, fn_name)
    return len(calls) > 0


class AstChecker:
    """AST-based semantic checker."""

    CHECKS = {
        "n_plus_one": "_check_n_plus_one",
        "unescaped_output": "_check_unescaped_output",
        "raw_sql": "_check_raw_sql",
        "nonce_missing": "_check_nonce_missing",
        "direct_superglobal": "_check_direct_superglobal",
        "unhandled_promise": "_check_unhandled_promise",
        "xss_jsx": "_check_xss_jsx",
        "react_hooks": "_check_react_hooks",
        "idor_no_auth": "_check_idor_no_auth",
        "echo_no_escape": "_check_echo_no_escape",
        "fetch_no_nonce": "_check_fetch_no_nonce",
        "wpdb_insert_in_loop": "_check_wpdb_insert_in_loop",
    }

    def __init__(self):
        self.warnings = []

    def check(self, pattern_def: dict, files: list, theme_path: str) -> list:
        ast_check = pattern_def.get("ast_check")
        if not ast_check or ast_check not in self.CHECKS:
            return []

        method = getattr(self, self.CHECKS[ast_check])
        violations = []

        for filepath in files:
            if _has_file_level_ignore(filepath, pattern_def["id"]):
                continue

            root, content, error = _parse_file(filepath)
            if not root:
                # Collect warning instead of silent skip
                rel_path = os.path.relpath(filepath, theme_path).replace("\\", "/")
                self.warnings.append(f"{rel_path} — {error}")
                continue

            file_violations = method(root, content, filepath, pattern_def, theme_path)
            violations.extend(file_violations)

        return violations

    def _check_n_plus_one(self, root, content, filepath, pattern_def, theme_path):
        """Detect get_post_meta() inside loops without prior update_meta_cache()."""
        violations = []
        fn_name = pattern_def.get("ast_function", "get_post_meta")
        guard_fn = pattern_def.get("ast_guard", "update_meta_cache")

        calls = _find_calls(root, fn_name)
        loops = _find_loops(root)

        has_cache = _file_has_call(root, guard_fn)
        has_wp_loop = _file_has_call(root, "have_posts") or _file_has_call(root, "the_post")

        if has_cache or has_wp_loop:
            return violations

        reported_loops = set()

        for call in calls:
            if _is_inside(call, loops):
                loop_id = None
                for loop in loops:
                    if (loop.start_byte <= call.start_byte
                            and call.end_byte <= loop.end_byte):
                        loop_id = loop.start_point[0]
                        break

                if loop_id in reported_loops:
                    continue
                reported_loops.add(loop_id)

                line = call.start_point[0] + 1
                text = call.text.decode("utf-8", errors="ignore")[:120]
                rel_path = os.path.relpath(filepath, theme_path).replace("\\", "/")

                violations.append(Violation(
                    lesson_id=pattern_def["id"],
                    severity=pattern_def["severity"],
                    category=pattern_def["category"],
                    description=pattern_def["description"] + " [AST: confirmed in loop]",
                    file=rel_path,
                    line=line,
                    match_text=text,
                ))

        return violations

    def _check_unescaped_output(self, root, content, filepath, pattern_def, theme_path):
        """Detect echo/print of variables without esc_html/esc_attr."""
        violations = []
        echo_nodes = []

        def find_echo(node):
            if node.type == "echo_statement":
                echo_nodes.append(node)
            for child in node.children:
                find_echo(child)

        find_echo(root)

        esc_functions = {"esc_html", "esc_attr", "esc_url", "esc_textarea", "wp_kses",
                         "wp_kses_post", "intval", "absint", "sanitize_text_field"}

        for echo in echo_nodes:
            text = echo.text.decode("utf-8", errors="ignore")

            has_variable = "$" in text
            has_escape = any(fn in text for fn in esc_functions)

            if has_variable and not has_escape:
                if "the_" in text or "get_header" in text or "get_footer" in text:
                    continue

                line = echo.start_point[0] + 1
                rel_path = os.path.relpath(filepath, theme_path).replace("\\", "/")
                violations.append(Violation(
                    lesson_id=pattern_def["id"],
                    severity=pattern_def["severity"],
                    category=pattern_def["category"],
                    description=pattern_def["description"] + " [AST: unescaped variable]",
                    file=rel_path,
                    line=line,
                    match_text=text.strip()[:120],
                ))

        return violations

    def _check_raw_sql(self, root, content, filepath, pattern_def, theme_path):
        """Detect direct $wpdb->query() without $wpdb->prepare()."""
        violations = []

        method_calls = []

        def find_method_calls(node):
            if node.type == "member_call_expression":
                obj = node.child_by_field_name("object")
                name = node.child_by_field_name("name")
                if obj and name:
                    obj_text = obj.text.decode("utf-8", errors="ignore")
                    name_text = name.text.decode("utf-8", errors="ignore")
                    if "wpdb" in obj_text and name_text in ("query", "get_results", "get_row", "get_var"):
                        method_calls.append((node, name_text))
            for child in node.children:
                find_method_calls(child)

        find_method_calls(root)

        for call_node, method_name in method_calls:
            text = call_node.text.decode("utf-8", errors="ignore")

            if "prepare" in text or "->prepare(" in text:
                continue

            if any(safe in text for safe in ["SHOW ", "DESCRIBE ", "SELECT 1", "TRUNCATE"]):
                continue

            if "$" in text.split("(", 1)[-1] if "(" in text else "":
                line = call_node.start_point[0] + 1
                rel_path = os.path.relpath(filepath, theme_path).replace("\\", "/")
                violations.append(Violation(
                    lesson_id=pattern_def["id"],
                    severity=pattern_def["severity"],
                    category=pattern_def["category"],
                    description=pattern_def["description"] + " [AST: unprepared query]",
                    file=rel_path,
                    line=line,
                    match_text=text.strip()[:120],
                ))

        return violations

    def _check_nonce_missing(self, root, content, filepath, pattern_def, theme_path):
        """Detect AJAX handler functions without check_ajax_referer/wp_verify_nonce."""
        violations = []

        func_nodes = []
        def find_functions(node):
            if node.type in ("function_definition", "method_declaration"):
                func_nodes.append(node)
            for child in node.children:
                find_functions(child)
        find_functions(root)

        nonce_fns = {"check_ajax_referer", "wp_verify_nonce", "check_admin_referer"}
        ajax_indicators = {"wp_send_json", "wp_send_json_success", "wp_send_json_error",
                           "wp_die", "wp_ajax"}

        content_str = content.decode("utf-8", errors="ignore")
        if "wp_ajax_" not in content_str:
            return violations

        for func_node in func_nodes:
            func_text = func_node.text.decode("utf-8", errors="ignore")

            is_ajax = any(ind in func_text for ind in ajax_indicators)
            if not is_ajax:
                continue

            has_nonce = any(fn in func_text for fn in nonce_fns)
            if has_nonce:
                continue

            name_node = func_node.child_by_field_name("name")
            fn_name = name_node.text.decode("utf-8", errors="ignore") if name_node else "unknown"

            line = func_node.start_point[0] + 1
            rel_path = os.path.relpath(filepath, theme_path).replace("\\", "/")
            violations.append(Violation(
                lesson_id=pattern_def["id"],
                severity=pattern_def["severity"],
                category=pattern_def["category"],
                description=pattern_def["description"] + f" [AST: {fn_name}() missing nonce]",
                file=rel_path,
                line=line,
                match_text=f"function {fn_name}()",
            ))

        return violations

    def _check_direct_superglobal(self, root, content, filepath, pattern_def, theme_path):
        """Detect direct $_GET/$_POST/$_REQUEST usage without sanitize/absint."""
        violations = []
        content_str = content.decode("utf-8", errors="ignore")

        sanitize_fns = {"sanitize_text_field", "sanitize_email", "sanitize_file_name",
                        "sanitize_key", "sanitize_title", "sanitize_user",
                        "absint", "intval", "floatval", "wp_unslash",
                        "esc_attr", "esc_html", "esc_url", "esc_sql",
                        "wp_kses", "wp_kses_post", "array_map"}

        superglobal_nodes = []
        def find_superglobals(node):
            if node.type == "subscript_expression":
                obj = node.children[0] if node.children else None
                if obj and obj.type == "variable_name":
                    var = obj.text.decode("utf-8", errors="ignore")
                    if var in ("$_GET", "$_POST", "$_REQUEST", "$_SERVER"):
                        superglobal_nodes.append(node)
            for child in node.children:
                find_superglobals(child)
        find_superglobals(root)

        reported_lines = set()
        for sg_node in superglobal_nodes:
            line_num = sg_node.start_point[0]
            if line_num in reported_lines:
                continue

            line_text = content_str.split("\n")[line_num] if line_num < len(content_str.split("\n")) else ""
            has_sanitize = any(fn in line_text for fn in sanitize_fns)
            if has_sanitize:
                continue

            if "wp_verify_nonce" in line_text or "check_ajax_referer" in line_text:
                continue

            reported_lines.add(line_num)
            rel_path = os.path.relpath(filepath, theme_path).replace("\\", "/")
            sg_text = sg_node.text.decode("utf-8", errors="ignore")[:80]
            violations.append(Violation(
                lesson_id=pattern_def["id"],
                severity=pattern_def["severity"],
                category=pattern_def["category"],
                description=pattern_def["description"] + " [AST: unsanitized superglobal]",
                file=rel_path,
                line=line_num + 1,
                match_text=sg_text,
            ))

        return violations


    def _check_unhandled_promise(self, root, content, filepath, pattern_def, theme_path):
        """Detect Promise/await without .catch() or try/catch."""
        violations = []
        content_str = content.decode("utf-8", errors="ignore")

        def find_await(node):
            if node.type == "await_expression":
                # Check if wrapped in try/catch
                parent = node.parent
                in_try_catch = False
                while parent:
                    if parent.type == "try_statement":
                        in_try_catch = True
                        break
                    parent = parent.parent

                if not in_try_catch:
                    line = node.start_point[0] + 1
                    rel_path = os.path.relpath(filepath, theme_path).replace("\\", "/")
                    text = content_str.split("\n")[node.start_point[0]] if node.start_point[0] < len(content_str.split("\n")) else ""
                    violations.append(Violation(
                        lesson_id=pattern_def["id"],
                        severity=pattern_def["severity"],
                        category=pattern_def["category"],
                        description=pattern_def["description"] + " [AST: unhandled promise]",
                        file=rel_path,
                        line=line,
                        match_text=text.strip()[:120],
                    ))

            for child in node.children:
                find_await(child)

        find_await(root)
        return violations

    def _check_xss_jsx(self, root, content, filepath, pattern_def, theme_path):
        """Detect dangerouslySetInnerHTML in JSX."""
        violations = []
        content_str = content.decode("utf-8", errors="ignore")

        def find_dangerous_html(node):
            if node.type == "jsx_attribute":
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = content[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="ignore")
                    if name == "dangerouslySetInnerHTML":
                        line = node.start_point[0] + 1
                        rel_path = os.path.relpath(filepath, theme_path).replace("\\", "/")
                        text = content_str.split("\n")[node.start_point[0]] if node.start_point[0] < len(content_str.split("\n")) else ""
                        violations.append(Violation(
                            lesson_id=pattern_def["id"],
                            severity=pattern_def["severity"],
                            category=pattern_def["category"],
                            description=pattern_def["description"] + " [AST: dangerouslySetInnerHTML]",
                            file=rel_path,
                            line=line,
                            match_text=text.strip()[:120],
                        ))

            for child in node.children:
                find_dangerous_html(child)

        find_dangerous_html(root)
        return violations

    def _check_react_hooks(self, root, content, filepath, pattern_def, theme_path):
        """Detect React Hooks violations (conditional/loop calls)."""
        violations = []
        content_str = content.decode("utf-8", errors="ignore")

        def find_hooks(node, in_condition=False, in_loop=False):
            # Detect hook calls (functions starting with 'use')
            if node.type == "call_expression":
                function_node = node.child_by_field_name("function")
                if function_node and function_node.type == "identifier":
                    func_name = content[function_node.start_byte:function_node.end_byte].decode("utf-8", errors="ignore")
                    if func_name.startswith("use") and len(func_name) > 3 and func_name[3].isupper():
                        if in_condition or in_loop:
                            line = node.start_point[0] + 1
                            rel_path = os.path.relpath(filepath, theme_path).replace("\\", "/")
                            reason = "conditional" if in_condition else "loop"
                            text = content_str.split("\n")[node.start_point[0]] if node.start_point[0] < len(content_str.split("\n")) else ""
                            violations.append(Violation(
                                lesson_id=pattern_def["id"],
                                severity=pattern_def["severity"],
                                category=pattern_def["category"],
                                description=pattern_def["description"] + f" [AST: hook in {reason}]",
                                file=rel_path,
                                line=line,
                                match_text=text.strip()[:120],
                            ))

            # Track context
            new_in_condition = in_condition or node.type in ("if_statement", "conditional_expression")
            new_in_loop = in_loop or node.type in ("for_statement", "while_statement", "do_statement")

            for child in node.children:
                find_hooks(child, new_in_condition, new_in_loop)

        find_hooks(root)
        return violations


    def _check_idor_no_auth(self, root, content, filepath, pattern_def, theme_path):
        """Detect account template files without is_user_logged_in() check."""
        violations = []

        # Only check account template files
        if "account" not in filepath or "login.php" in filepath or "register.php" in filepath:
            return violations

        # Check if file has is_user_logged_in() call
        has_auth_check = _file_has_call(root, "is_user_logged_in")

        if not has_auth_check:
            rel_path = os.path.relpath(filepath, theme_path).replace("\\", "/")
            violations.append(Violation(
                lesson_id=pattern_def["id"],
                severity=pattern_def["severity"],
                category=pattern_def["category"],
                description=pattern_def["description"] + " [AST: no auth gate found]",
                file=rel_path,
                line=1,
                match_text="Missing is_user_logged_in() check",
            ))

        return violations

    def _check_echo_no_escape(self, root, content, filepath, pattern_def, theme_path):
        """Detect echo statements with variables but no escape functions."""
        violations = []
        echo_nodes = []

        def find_echo(node):
            if node.type == "echo_statement":
                echo_nodes.append(node)
            for child in node.children:
                find_echo(child)

        find_echo(root)

        esc_functions = {"esc_html", "esc_attr", "esc_url", "esc_textarea", "wp_kses",
                         "wp_kses_post", "intval", "absint", "sanitize_text_field"}

        for echo in echo_nodes:
            text = echo.text.decode("utf-8", errors="ignore")

            has_variable = "$" in text
            has_escape = any(fn in text for fn in esc_functions)

            if has_variable and not has_escape:
                if "the_" in text or "get_header" in text or "get_footer" in text:
                    continue

                line = echo.start_point[0] + 1
                rel_path = os.path.relpath(filepath, theme_path).replace("\\", "/")
                violations.append(Violation(
                    lesson_id=pattern_def["id"],
                    severity=pattern_def["severity"],
                    category=pattern_def["category"],
                    description=pattern_def["description"] + " [AST: unescaped variable in echo]",
                    file=rel_path,
                    line=line,
                    match_text=text.strip()[:120],
                ))

        return violations

    def _check_fetch_no_nonce(self, root, content, filepath, pattern_def, theme_path):
        """Detect fetch() calls to cart/checkout API without X-WP-Nonce header."""
        violations = []
        content_str = content.decode("utf-8", errors="ignore")

        # Find all fetch calls
        def find_fetch_calls(node):
            calls = []
            if node.type == "call_expression":
                fn = node.child_by_field_name("function")
                if fn and fn.type == "identifier":
                    fn_name = content[fn.start_byte:fn.end_byte].decode("utf-8", errors="ignore")
                    if fn_name == "fetch":
                        calls.append(node)
            for child in node.children:
                calls.extend(find_fetch_calls(child))
            return calls

        fetch_calls = find_fetch_calls(root)

        for call in fetch_calls:
            call_text = call.text.decode("utf-8", errors="ignore")

            # Check if URL contains cart or checkout
            if "cart" not in call_text.lower() and "checkout" not in call_text.lower():
                continue

            # Check if headers include X-WP-Nonce
            if "X-WP-Nonce" in call_text or "wzTheme.nonce" in call_text or "wz_nonce" in call_text:
                continue

            line = call.start_point[0] + 1
            rel_path = os.path.relpath(filepath, theme_path).replace("\\", "/")
            violations.append(Violation(
                lesson_id=pattern_def["id"],
                severity=pattern_def["severity"],
                category=pattern_def["category"],
                description=pattern_def["description"] + " [AST: fetch without nonce header]",
                file=rel_path,
                line=line,
                match_text=call_text[:120],
            ))

        return violations

    def _check_wpdb_insert_in_loop(self, root, content, filepath, pattern_def, theme_path):
        """Detect $wpdb->insert() calls inside loops without bulk insert."""
        violations = []

        # Find all $wpdb->insert() calls
        insert_calls = []
        def find_wpdb_insert(node):
            if node.type == "member_call_expression":
                obj = node.child_by_field_name("object")
                name = node.child_by_field_name("name")
                if obj and name:
                    obj_text = obj.text.decode("utf-8", errors="ignore")
                    name_text = name.text.decode("utf-8", errors="ignore")
                    if "wpdb" in obj_text and name_text == "insert":
                        insert_calls.append(node)
            for child in node.children:
                find_wpdb_insert(child)

        find_wpdb_insert(root)

        # Find all loops
        loops = _find_loops(root)

        # Check if wz_bulk_insert is used (guard function)
        has_bulk_insert = _file_has_call(root, "wz_bulk_insert")
        if has_bulk_insert:
            return violations

        reported_loops = set()

        for call in insert_calls:
            if _is_inside(call, loops):
                loop_id = None
                for loop in loops:
                    if (loop.start_byte <= call.start_byte
                            and call.end_byte <= loop.end_byte):
                        loop_id = loop.start_point[0]
                        break

                if loop_id in reported_loops:
                    continue
                reported_loops.add(loop_id)

                line = call.start_point[0] + 1
                text = call.text.decode("utf-8", errors="ignore")[:120]
                rel_path = os.path.relpath(filepath, theme_path).replace("\\", "/")

                violations.append(Violation(
                    lesson_id=pattern_def["id"],
                    severity=pattern_def["severity"],
                    category=pattern_def["category"],
                    description=pattern_def["description"] + " [AST: $wpdb->insert in loop]",
                    file=rel_path,
                    line=line,
                    match_text=text,
                ))

        return violations


def _has_file_level_ignore(filepath: str, lesson_id: str) -> bool:
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if i >= 10:
                    break
                if f"@kiwi-ignore {lesson_id}" in line or "@kiwi-ignore all" in line:
                    return True
    except (OSError, IOError):
        pass
    return False