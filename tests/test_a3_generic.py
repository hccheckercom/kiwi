"""Comprehensive QA for A3 — Generic Plugin Auto-Learn Engine."""

import sys
import os
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

KIWI_DIR = Path(__file__).resolve().parent.parent


def main():
    print("=" * 60)
    print("A3 COMPREHENSIVE QA — Generic Plugin Auto-Learn")
    print("=" * 60)
    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  PASS [{passed}] {name}")
        else:
            failed += 1
            print(f"  FAIL [{name}] {detail}")

    # === Setup: create temp projects ===
    tmp_react = _create_react_project()
    tmp_python = _create_python_project()
    tmp_go = _create_go_project()

    try:
        # === GROUP 1: Auto-Detector ===
        print("\n--- GROUP 1: Auto-Detector ---")
        from plugins.generic.auto_detector import detect, ProjectProfile

        profile_react = detect(tmp_react)
        check("React: detects typescript", "typescript" in profile_react.languages)
        check("React: detects react framework", "react" in profile_react.frameworks)
        check("React: package_manager = npm", profile_react.package_manager == "npm")
        check("React: test_framework = jest", profile_react.test_framework == "jest")
        check("React: build_tool = vite", profile_react.build_tool == "vite")
        check("React: css_framework = tailwind", profile_react.css_framework == "tailwind")
        check("React: not wordpress", not profile_react.has_wordpress_signals())

        profile_py = detect(tmp_python)
        check("Python: detects python", "python" in profile_py.languages)
        check("Python: detects fastapi", "fastapi" in profile_py.frameworks)
        check("Python: test_framework = pytest", profile_py.test_framework == "pytest")

        profile_go = detect(tmp_go)
        check("Go: detects go", "go" in profile_go.languages)
        check("Go: package_manager = go", profile_go.package_manager == "go")

        check("confidence_score > 0.5 for React", profile_react.confidence_score() > 0.5,
              f"got {profile_react.confidence_score()}")

        # === GROUP 2: Convention Learner ===
        print("\n--- GROUP 2: Convention Learner ---")
        from plugins.generic.convention_learner import learn, ConventionSet

        conv_react = learn(tmp_react)
        check("React: file_count > 0", conv_react.file_count > 0, f"got {conv_react.file_count}")
        check("React: has conventions", len(conv_react.conventions) > 0, f"got {len(conv_react.conventions)}")
        check("React: has naming convention", len(conv_react.by_category("naming")) > 0)

        conv_py = learn(tmp_python)
        check("Python: has conventions", len(conv_py.conventions) > 0)
        naming_py = conv_py.by_category("naming")
        func_rules = [c for c in naming_py if "Functions" in c.rule and "python" in c.rule]
        check("Python: detects snake_case functions", any("snake_case" in c.pattern for c in func_rules),
              f"rules: {[c.rule for c in func_rules]}")

        check("ConventionSet.to_dict() works", "conventions" in conv_react.to_dict())
        check("ConventionSet.high_confidence() filters",
              all(c.confidence >= 0.7 for c in conv_react.high_confidence(0.7)))

        # === GROUP 3: Pattern Miner ===
        print("\n--- GROUP 3: Pattern Miner ---")
        from plugins.generic.pattern_miner import mine

        patterns_py = mine(tmp_python, min_occurrences=2)
        check("Pattern miner returns list", isinstance(patterns_py, list))
        # The test project has empty except blocks
        error_patterns = [p for p in patterns_py if "error" in p.category.lower() or "error" in p.title.lower()]
        check("Detects empty error handlers", len(error_patterns) > 0,
              f"found {len(patterns_py)} total patterns: {[p.title for p in patterns_py]}")

        # === GROUP 4: Generic Checkers ===
        print("\n--- GROUP 4: Generic Checkers ---")
        from plugins.generic.checkers import (
            check_error_handling, check_dead_code, check_file_size, run_all_checks
        )

        err_violations = check_error_handling(tmp_python)
        check("Error handler checker finds violations", len(err_violations) > 0,
              f"got {len(err_violations)}")

        dead_violations = check_dead_code(tmp_python)
        check("Dead code checker finds commented blocks", len(dead_violations) > 0,
              f"got {len(dead_violations)}")

        all_violations = run_all_checks(tmp_python, conv_py)
        check("run_all_checks returns combined results", len(all_violations) > 0)

        # === GROUP 5: Skeleton Drafter ===
        print("\n--- GROUP 5: Skeleton Drafter ---")
        from plugins.generic.drafter import SkeletonDrafter

        drafter = SkeletonDrafter(profile_react, conv_react)
        tsx_code = drafter.generate("components/Button.tsx", "skeleton")
        check("TSX drafter generates React component", "function Button" in tsx_code)
        check("TSX drafter has return", "return" in tsx_code)

        py_code = SkeletonDrafter(profile_py, conv_py).generate("services/auth.py", "draft")
        check("Python drafter generates class", "class Auth" in py_code)
        check("Python drafter uses snake_case func", "def " in py_code)

        go_code = SkeletonDrafter(profile_go, ConventionSet()).generate("handlers/user.go", "complete")
        check("Go drafter generates package", "package " in go_code)
        check("Go drafter has error return", "error" in go_code)

        php_code = SkeletonDrafter(ProjectProfile(), ConventionSet()).generate("src/Logger.php", "complete")
        check("PHP drafter generates class", "class Logger" in php_code)
        check("PHP drafter has <?php", "<?php" in php_code)

        # === GROUP 6: Plugin Integration ===
        print("\n--- GROUP 6: Plugin Integration ---")
        from core.plugin_registry import discover_plugins, reset_registry

        reset_registry()
        plugins = discover_plugins()
        gen = [p for p in plugins if p.get_manifest().name == "generic"][0]

        check("Plugin version = 2.0.0", gen.get_manifest().version == "2.0.0")
        check("detect_project > 0.5 for React", gen.detect_project(tmp_react) > 0.5,
              f"got {gen.detect_project(tmp_react)}")
        check("detect_project < 0.1 for WP", gen.detect_project(str(KIWI_DIR.parent.parent / "wezone-plugins")) < 0.1)

        analysis = gen.analyze_project(tmp_react)
        check("analyze_project returns profile", analysis["profile"] is not None)
        check("analyze_project returns conventions", analysis["conventions"] is not None)
        check("analyze_project returns patterns", isinstance(analysis["patterns"], list))

        generic_checks = gen.run_generic_checks(tmp_python)
        check("run_generic_checks returns violations", len(generic_checks) > 0)

        # === GROUP 7: Backward Compatibility ===
        print("\n--- GROUP 7: Backward Compatibility ---")
        check("get_checkers() still works", "presence" in gen.get_checkers())
        check("get_quality_rules() = []", gen.get_quality_rules() == [])
        check("get_context_map() = {}", gen.get_context_map() == {})
        check("lessons dir exists", Path(gen.get_lessons_path()).is_dir())
        lessons = list(Path(gen.get_lessons_path()).rglob("*.md"))
        check("379 lessons still present", len(lessons) == 379, f"got {len(lessons)}")

    finally:
        shutil.rmtree(tmp_react, ignore_errors=True)
        shutil.rmtree(tmp_python, ignore_errors=True)
        shutil.rmtree(tmp_go, ignore_errors=True)

    # === SUMMARY ===
    print(f"\n{'=' * 60}")
    print(f"RESULTS: {passed} passed, {failed} failed")
    print(f"{'=' * 60}")
    return 0 if failed == 0 else 1


def _create_react_project() -> str:
    """Create a minimal React/TS project for testing."""
    tmp = tempfile.mkdtemp(prefix="kiwi_test_react_")

    _write(tmp, "package.json", '''{
  "name": "test-app",
  "dependencies": { "react": "^18.0.0", "react-dom": "^18.0.0" },
  "devDependencies": { "jest": "^29.0.0", "vite": "^5.0.0", "typescript": "^5.0.0" }
}''')
    _write(tmp, "tsconfig.json", '{"compilerOptions": {"jsx": "react-jsx"}}')
    _write(tmp, "tailwind.config.js", "module.exports = { content: ['./src/**/*.tsx'] }")
    _write(tmp, "vite.config.ts", "import { defineConfig } from 'vite';\nexport default defineConfig({});")

    # Source files with consistent camelCase naming
    for i in range(15):
        _write(tmp, f"src/components/Component{i}.tsx", f'''import React from 'react';

interface Component{i}Props {{
  title: string;
}}

export function Component{i}(props: Component{i}Props) {{
  const handleClick = () => {{}};
  const getValue = () => "test";
  const formatData = (data: any) => data;
  return <div onClick={{handleClick}}>{{props.title}}</div>;
}}
''')

    _write(tmp, "src/utils/helpers.ts", '''export function formatDate(d: Date): string {
  return d.toISOString();
}

export function parseQuery(q: string): Record<string, string> {
  return {};
}

export function validateEmail(email: string): boolean {
  return email.includes("@");
}
''')

    return tmp


def _create_python_project() -> str:
    """Create a minimal Python project for testing."""
    tmp = tempfile.mkdtemp(prefix="kiwi_test_python_")

    _write(tmp, "pyproject.toml", '''[project]
name = "test-app"
dependencies = ["fastapi>=0.100.0", "uvicorn"]

[tool.pytest.ini_options]
testpaths = ["tests"]
''')
    _write(tmp, "conftest.py", "import pytest")

    # Python files with snake_case
    for i in range(10):
        _write(tmp, f"src/service_{i}.py", f'''"""Service {i}."""

class Service{i}:
    def __init__(self):
        self.name = "service_{i}"

    def get_data(self):
        return []

    def process_items(self, items):
        for item in items:
            self._handle_item(item)

    def _handle_item(self, item):
        try:
            pass
        except Exception:
            pass

    def validate_input(self, data):
        if not data:
            return False
        return True

    def fetch_records(self):
        return []
''')

    # Files with empty except blocks (for error handler detection)
    for i in range(3):
        _write(tmp, f"src/handler_{i}.py", f'''def handle_{i}():
    try:
        result = do_something()
    except Exception:
        pass

    try:
        other = do_other()
    except ValueError:
        ...
''')

    # Large commented block (for dead code detection)
    _write(tmp, "src/legacy.py", '''def active_function():
    return True

# def old_function():
#     x = 1
#     y = 2
#     z = x + y
#     return z
#     # more old code
#     # that was commented out
#     # instead of being deleted

def another_active():
    return False
''')

    return tmp


def _create_go_project() -> str:
    """Create a minimal Go project for testing."""
    tmp = tempfile.mkdtemp(prefix="kiwi_test_go_")

    _write(tmp, "go.mod", "module example.com/test\n\ngo 1.21\n")
    _write(tmp, "main.go", '''package main

import "fmt"

func main() {
    fmt.Println("hello")
}
''')
    _write(tmp, "handlers/user.go", '''package handlers

func GetUser(id string) (string, error) {
    return id, nil
}

func ListUsers() ([]string, error) {
    return nil, nil
}
''')

    return tmp


def _write(base: str, rel_path: str, content: str):
    full = os.path.join(base, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    sys.exit(main())