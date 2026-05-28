"""Skeleton drafter — generate boilerplate from learned conventions."""

from pathlib import Path

from .auto_detector import ProjectProfile
from .convention_learner import ConventionSet


class SkeletonDrafter:
    """Generate file skeletons matching project conventions."""

    def __init__(self, profile: ProjectProfile, conventions: ConventionSet):
        self.profile = profile
        self.conventions = conventions

    def generate(self, target_path: str, level: str = "skeleton") -> str:
        """Generate code skeleton for target file path.

        Levels: skeleton (structure only), draft (+ patterns), complete (+ error handling)
        """
        ext = Path(target_path).suffix.lower()
        generators = {
            ".py": self._gen_python,
            ".js": self._gen_javascript,
            ".ts": self._gen_typescript,
            ".tsx": self._gen_react_tsx,
            ".jsx": self._gen_react_jsx,
            ".php": self._gen_php,
            ".go": self._gen_go,
            ".rs": self._gen_rust,
        }
        gen = generators.get(ext, self._gen_generic)
        return gen(target_path, level)

    def _get_indent(self) -> str:
        for c in self.conventions.by_category("indent"):
            if "tab" in c.rule.lower():
                return "\t"
            if "2-space" in c.rule:
                return "  "
        return "    "

    def _get_func_case(self, lang: str) -> str:
        for c in self.conventions.by_category("naming"):
            if "Functions" in c.rule and lang in c.rule:
                return c.pattern
        defaults = {"python": "snake_case", "go": "camelCase", "rust": "snake_case"}
        return defaults.get(lang, "camelCase")

    def _get_class_case(self, lang: str) -> str:
        for c in self.conventions.by_category("naming"):
            if "Classes" in c.rule and lang in c.rule:
                return c.pattern
        return "PascalCase"

    def _to_case(self, name: str, case: str) -> str:
        words = _split_name(name)
        if case == "snake_case":
            return "_".join(w.lower() for w in words)
        if case == "camelCase":
            return words[0].lower() + "".join(w.capitalize() for w in words[1:])
        if case == "PascalCase":
            return "".join(w.capitalize() for w in words)
        if case == "kebab-case":
            return "-".join(w.lower() for w in words)
        return name

    def _gen_python(self, target_path: str, level: str) -> str:
        indent = self._get_indent()
        module_name = Path(target_path).stem
        class_name = self._to_case(module_name, "PascalCase")
        func_case = self._get_func_case("python")

        lines = [f'"""Module {module_name}."""', ""]

        if level in ("draft", "complete"):
            lines.extend(["from __future__ import annotations", ""])

        lines.extend([
            f"class {class_name}:",
            f"{indent}def __init__(self):",
            f"{indent}{indent}pass",
            "",
            f"{indent}def {self._to_case('do_something', func_case)}(self):",
        ])

        if level == "complete":
            lines.append(f"{indent}{indent}raise NotImplementedError")
        else:
            lines.append(f"{indent}{indent}pass")

        lines.append("")
        return "\n".join(lines)

    def _gen_javascript(self, target_path: str, level: str) -> str:
        indent = self._get_indent()
        module_name = Path(target_path).stem
        func_case = self._get_func_case("javascript")
        export_name = self._to_case(module_name, func_case)

        lines = []
        if level in ("draft", "complete"):
            has_grouped = any("grouped" in c.rule.lower() for c in self.conventions.by_category("import"))
            if has_grouped:
                lines.extend(["// External imports", "", "// Internal imports", ""])

        lines.extend([
            f"function {export_name}() {{",
            f"{indent}// TODO: implement",
            "}",
            "",
            f"module.exports = {{ {export_name} }};",
            "",
        ])
        return "\n".join(lines)

    def _gen_typescript(self, target_path: str, level: str) -> str:
        indent = self._get_indent()
        module_name = Path(target_path).stem
        func_case = self._get_func_case("typescript")
        export_name = self._to_case(module_name, func_case)

        lines = []
        if level in ("draft", "complete"):
            lines.extend([f"export interface {self._to_case(module_name, 'PascalCase')}Options {{", "}", ""])

        lines.extend([
            f"export function {export_name}(): void {{",
            f"{indent}// TODO: implement",
            "}",
            "",
        ])
        return "\n".join(lines)

    def _gen_react_tsx(self, target_path: str, level: str) -> str:
        indent = self._get_indent()
        component = self._to_case(Path(target_path).stem, "PascalCase")

        lines = ["import React from 'react';", ""]

        if level in ("draft", "complete"):
            lines.extend([
                f"interface {component}Props {{",
                f"{indent}// TODO: define props",
                "}",
                "",
            ])
            lines.extend([
                f"export function {component}(props: {component}Props) {{",
                f"{indent}return (",
                f"{indent}{indent}<div>",
                f"{indent}{indent}{indent}{{/* TODO: implement */}}",
                f"{indent}{indent}</div>",
                f"{indent});",
                "}",
                "",
            ])
        else:
            lines.extend([
                f"export function {component}() {{",
                f"{indent}return <div />;",
                "}",
                "",
            ])

        return "\n".join(lines)

    def _gen_react_jsx(self, target_path: str, level: str) -> str:
        return self._gen_react_tsx(target_path, level).replace(
            "interface ", "// Props: "
        ).replace(": void", "").replace(": " + self._to_case(Path(target_path).stem, "PascalCase") + "Props", "")

    def _gen_php(self, target_path: str, level: str) -> str:
        indent = self._get_indent()
        class_name = self._to_case(Path(target_path).stem, "PascalCase")
        func_case = self._get_func_case("php")

        lines = ["<?php", ""]

        if level in ("draft", "complete"):
            lines.append("declare(strict_types=1);")
            lines.append("")

        lines.extend([
            f"class {class_name} {{",
            "",
            f"{indent}public function {self._to_case('handle', func_case)}(): void {{",
        ])

        if level == "complete":
            lines.append(f"{indent}{indent}throw new \\RuntimeException('Not implemented');")
        else:
            lines.append(f"{indent}{indent}// TODO: implement")

        lines.extend([
            f"{indent}}}",
            "}",
            "",
        ])
        return "\n".join(lines)

    def _gen_go(self, target_path: str, level: str) -> str:
        indent = "\t"
        pkg = Path(target_path).parent.name or "main"
        func_case = self._get_func_case("go")
        func_name = self._to_case("do_something", func_case)
        if func_name[0].islower():
            func_name = func_name[0].upper() + func_name[1:]

        lines = [f"package {pkg}", ""]

        if level in ("draft", "complete"):
            lines.extend(["import (", f'{indent}"fmt"', ")", ""])

        lines.extend([
            f"func {func_name}() error {{",
        ])

        if level == "complete":
            lines.append(f'{indent}return fmt.Errorf("not implemented")')
        else:
            lines.append(f"{indent}return nil")

        lines.extend(["}", ""])
        return "\n".join(lines)

    def _gen_rust(self, target_path: str, level: str) -> str:
        indent = self._get_indent()
        func_case = self._get_func_case("rust")
        func_name = self._to_case("do_something", func_case)

        lines = []
        if level in ("draft", "complete"):
            struct_name = self._to_case(Path(target_path).stem, "PascalCase")
            lines.extend([
                f"pub struct {struct_name} {{",
                f"{indent}// TODO: fields",
                "}",
                "",
                f"impl {struct_name} {{",
                f"{indent}pub fn {func_name}(&self) -> Result<(), Box<dyn std::error::Error>> {{",
                f"{indent}{indent}todo!()",
                f"{indent}}}",
                "}",
                "",
            ])
        else:
            lines.extend([
                f"pub fn {func_name}() {{",
                f"{indent}todo!()",
                "}",
                "",
            ])

        return "\n".join(lines)

    def _gen_generic(self, target_path: str, level: str) -> str:
        return f"// TODO: implement {Path(target_path).stem}\n"


def _split_name(name: str) -> list[str]:
    """Split identifier into words."""
    if "-" in name:
        return [w for w in name.split("-") if w]
    if "_" in name:
        return [w for w in name.split("_") if w]
    words = []
    current = ""
    for ch in name:
        if ch.isupper() and current:
            words.append(current)
            current = ch
        else:
            current += ch
    if current:
        words.append(current)
    return words or [name]