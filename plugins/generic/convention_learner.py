"""Learn coding conventions from an existing codebase."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from collections import Counter

from .auto_detector import SKIP_DIRS, LANG_EXTENSIONS


@dataclass
class Convention:
    category: str
    rule: str
    pattern: str
    confidence: float
    examples: list = field(default_factory=list)
    counter_examples: list = field(default_factory=list)


@dataclass
class ConventionSet:
    conventions: list = field(default_factory=list)
    file_count: int = 0
    languages_analyzed: list = field(default_factory=list)

    def high_confidence(self, threshold: float = 0.7) -> list:
        return [c for c in self.conventions if c.confidence >= threshold]

    def by_category(self, category: str) -> list:
        return [c for c in self.conventions if c.category == category]

    def to_dict(self) -> dict:
        return {
            "file_count": self.file_count,
            "languages": self.languages_analyzed,
            "conventions": [
                {
                    "category": c.category,
                    "rule": c.rule,
                    "pattern": c.pattern,
                    "confidence": c.confidence,
                    "examples": c.examples[:3],
                    "counter_examples": c.counter_examples[:3],
                }
                for c in self.conventions
            ],
        }


def learn(path: str, max_files: int = 500) -> ConventionSet:
    """Analyze codebase and extract conventions."""
    from core.gating import gate_check
    result = gate_check("max_conventions")
    if not result.allowed:
        return ConventionSet()

    root = Path(path)
    if not root.is_dir():
        return ConventionSet()

    files_by_lang = _collect_files(root, max_files)
    result = ConventionSet()
    result.file_count = sum(len(v) for v in files_by_lang.values())
    result.languages_analyzed = list(files_by_lang.keys())

    result.conventions.extend(_learn_indent(files_by_lang))
    result.conventions.extend(_learn_naming(files_by_lang))
    result.conventions.extend(_learn_imports(files_by_lang))
    result.conventions.extend(_learn_file_naming(root))
    result.conventions.extend(_learn_structure(root))

    return result


def _collect_files(root: Path, max_files: int) -> dict:
    """Collect source files grouped by language."""
    files_by_lang = {}
    count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            ext = os.path.splitext(f)[1].lower()
            lang = LANG_EXTENSIONS.get(ext)
            if not lang:
                continue
            full = os.path.join(dirpath, f)
            files_by_lang.setdefault(lang, []).append(full)
            count += 1
            if count >= max_files:
                return files_by_lang

    return files_by_lang


def _learn_indent(files_by_lang: dict) -> list:
    """Detect indentation style."""
    conventions = []
    tab_count = 0
    space_counts = Counter()
    total_files = 0

    for lang, files in files_by_lang.items():
        if lang in ("css", "scss", "less", "html", "sql"):
            continue
        for fpath in files[:100]:
            try:
                lines = Path(fpath).read_text(encoding="utf-8", errors="ignore").split("\n")[:200]
            except OSError:
                continue
            total_files += 1
            for line in lines:
                if not line or not line[0] in (" ", "\t"):
                    continue
                if line[0] == "\t":
                    tab_count += 1
                    break
                spaces = len(line) - len(line.lstrip(" "))
                if spaces in (2, 4, 8):
                    space_counts[spaces] += 1
                    break

    if total_files < 5:
        return conventions

    total_indented = tab_count + sum(space_counts.values())
    if total_indented == 0:
        return conventions

    if tab_count > total_indented * 0.7:
        conventions.append(Convention(
            category="indent",
            rule="Use tabs for indentation",
            pattern=r"^\t",
            confidence=tab_count / total_indented,
            examples=[],
        ))
    elif space_counts:
        dominant = space_counts.most_common(1)[0]
        width, count = dominant
        conf = count / total_indented
        if conf > 0.5:
            conventions.append(Convention(
                category="indent",
                rule=f"Use {width}-space indentation",
                pattern=rf"^ {{{width}}}",
                confidence=conf,
                examples=[],
            ))

    return conventions


_FUNC_PATTERNS = {
    "python": re.compile(r"^\s*def\s+([a-zA-Z_]\w*)\s*\(", re.MULTILINE),
    "javascript": re.compile(r"(?:function\s+([a-zA-Z_$]\w*)|(?:const|let|var)\s+([a-zA-Z_$]\w*)\s*=\s*(?:async\s*)?\(|([a-zA-Z_$]\w*)\s*\([^)]*\)\s*\{)"),
    "typescript": re.compile(r"(?:function\s+([a-zA-Z_$]\w*)|(?:const|let|var)\s+([a-zA-Z_$]\w*)\s*=\s*(?:async\s*)?\(|([a-zA-Z_$]\w*)\s*\([^)]*\)\s*[:{])"),
    "php": re.compile(r"(?:function\s+([a-zA-Z_]\w*)|(?:public|private|protected)\s+(?:static\s+)?function\s+([a-zA-Z_]\w*))", re.MULTILINE),
    "go": re.compile(r"^func\s+(?:\([^)]+\)\s+)?([a-zA-Z_]\w*)\s*\(", re.MULTILINE),
    "rust": re.compile(r"^\s*(?:pub\s+)?fn\s+([a-zA-Z_]\w*)\s*[<(]", re.MULTILINE),
    "ruby": re.compile(r"^\s*def\s+([a-zA-Z_]\w*[?!]?)", re.MULTILINE),
}

_CLASS_PATTERNS = {
    "python": re.compile(r"^\s*class\s+([A-Za-z_]\w*)", re.MULTILINE),
    "javascript": re.compile(r"class\s+([A-Za-z_$]\w*)"),
    "typescript": re.compile(r"(?:class|interface|type)\s+([A-Za-z_$]\w*)"),
    "php": re.compile(r"(?:class|interface|trait)\s+([A-Za-z_]\w*)", re.MULTILINE),
    "go": re.compile(r"^type\s+([A-Za-z_]\w*)\s+struct", re.MULTILINE),
    "rust": re.compile(r"(?:pub\s+)?struct\s+([A-Za-z_]\w*)"),
    "ruby": re.compile(r"^\s*class\s+([A-Za-z_]\w*)", re.MULTILINE),
}


def _classify_case(name: str) -> str:
    if "_" in name and name == name.lower():
        return "snake_case"
    if "_" in name and name == name.upper():
        return "UPPER_SNAKE"
    if "-" in name:
        return "kebab-case"
    if name[0].isupper() and not "_" in name:
        return "PascalCase"
    if name[0].islower() and not "_" in name and any(c.isupper() for c in name):
        return "camelCase"
    if name == name.lower():
        return "lowercase"
    return "mixed"


def _learn_naming(files_by_lang: dict) -> list:
    conventions = []

    for lang, files in files_by_lang.items():
        func_pat = _FUNC_PATTERNS.get(lang)
        class_pat = _CLASS_PATTERNS.get(lang)
        if not func_pat and not class_pat:
            continue

        func_cases = Counter()
        class_cases = Counter()
        func_examples = {}
        class_examples = {}

        for fpath in files[:80]:
            try:
                content = Path(fpath).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            if func_pat:
                for m in func_pat.finditer(content):
                    name = next((g for g in m.groups() if g), None)
                    if name and len(name) > 2 and not name.startswith("__"):
                        case = _classify_case(name)
                        func_cases[case] += 1
                        func_examples.setdefault(case, []).append(name)

            if class_pat:
                for m in class_pat.finditer(content):
                    name = next((g for g in m.groups() if g), None)
                    if name and len(name) > 2:
                        case = _classify_case(name)
                        class_cases[case] += 1
                        class_examples.setdefault(case, []).append(name)

        total_funcs = sum(func_cases.values())
        if total_funcs >= 10:
            dominant = func_cases.most_common(1)[0]
            case_name, count = dominant
            conf = count / total_funcs
            if conf >= 0.6:
                conventions.append(Convention(
                    category="naming",
                    rule=f"Functions use {case_name} ({lang})",
                    pattern=case_name,
                    confidence=conf,
                    examples=func_examples.get(case_name, [])[:5],
                    counter_examples=[
                        n for c, names in func_examples.items()
                        if c != case_name for n in names[:2]
                    ][:5],
                ))

        total_classes = sum(class_cases.values())
        if total_classes >= 5:
            dominant = class_cases.most_common(1)[0]
            case_name, count = dominant
            conf = count / total_classes
            if conf >= 0.6:
                conventions.append(Convention(
                    category="naming",
                    rule=f"Classes use {case_name} ({lang})",
                    pattern=case_name,
                    confidence=conf,
                    examples=class_examples.get(case_name, [])[:5],
                ))

    return conventions


_IMPORT_PATTERNS = {
    "python": re.compile(r"^(?:from\s+(\S+)\s+import|import\s+(\S+))"),
    "javascript": re.compile(r"^import\s+.*?from\s+['\"]([^'\"]+)['\"]"),
    "typescript": re.compile(r"^import\s+.*?from\s+['\"]([^'\"]+)['\"]"),
}


def _learn_imports(files_by_lang: dict) -> list:
    conventions = []

    for lang in ("python", "javascript", "typescript"):
        files = files_by_lang.get(lang, [])
        if not files:
            continue

        pat = _IMPORT_PATTERNS[lang]
        grouped_count = 0
        ungrouped_count = 0
        relative_count = 0
        absolute_count = 0

        for fpath in files[:60]:
            try:
                lines = Path(fpath).read_text(encoding="utf-8", errors="ignore").split("\n")[:100]
            except OSError:
                continue

            imports = []
            for line in lines:
                m = pat.match(line.strip())
                if m:
                    module = next((g for g in m.groups() if g), "")
                    imports.append(module)
                    if module.startswith("."):
                        relative_count += 1
                    else:
                        absolute_count += 1

            if len(imports) >= 3:
                has_blank = False
                for i, line in enumerate(lines):
                    if pat.match(line.strip()):
                        if i > 0 and lines[i - 1].strip() == "":
                            has_blank = True
                            break
                if has_blank:
                    grouped_count += 1
                else:
                    ungrouped_count += 1

        total_grouped = grouped_count + ungrouped_count
        if total_grouped >= 10:
            if grouped_count > total_grouped * 0.6:
                conventions.append(Convention(
                    category="import",
                    rule=f"Imports are grouped with blank lines ({lang})",
                    pattern="grouped_imports",
                    confidence=grouped_count / total_grouped,
                ))
            elif ungrouped_count > total_grouped * 0.6:
                conventions.append(Convention(
                    category="import",
                    rule=f"Imports are not grouped ({lang})",
                    pattern="flat_imports",
                    confidence=ungrouped_count / total_grouped,
                ))

        total_rel = relative_count + absolute_count
        if total_rel >= 10:
            if relative_count > total_rel * 0.6:
                conventions.append(Convention(
                    category="import",
                    rule=f"Prefer relative imports ({lang})",
                    pattern="relative_imports",
                    confidence=relative_count / total_rel,
                ))
            elif absolute_count > total_rel * 0.6:
                conventions.append(Convention(
                    category="import",
                    rule=f"Prefer absolute imports ({lang})",
                    pattern="absolute_imports",
                    confidence=absolute_count / total_rel,
                ))

    return conventions


def _learn_file_naming(root: Path) -> list:
    """Detect file naming convention."""
    conventions = []
    cases = Counter()
    examples = {}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            stem = os.path.splitext(f)[0]
            ext = os.path.splitext(f)[1].lower()
            if ext not in LANG_EXTENSIONS or len(stem) < 3:
                continue
            case = _classify_case(stem)
            cases[case] += 1
            examples.setdefault(case, []).append(f)

    total = sum(cases.values())
    if total < 20:
        return conventions

    dominant = cases.most_common(1)[0]
    case_name, count = dominant
    conf = count / total
    if conf >= 0.5:
        conventions.append(Convention(
            category="naming",
            rule=f"Files use {case_name} naming",
            pattern=case_name,
            confidence=conf,
            examples=examples.get(case_name, [])[:5],
            counter_examples=[
                n for c, names in examples.items()
                if c != case_name for n in names[:2]
            ][:5],
        ))

    return conventions


def _learn_structure(root: Path) -> list:
    """Detect project structure patterns."""
    conventions = []

    has_src = (root / "src").is_dir()
    has_lib = (root / "lib").is_dir()
    has_tests_dir = (root / "tests").is_dir() or (root / "test").is_dir() or (root / "__tests__").is_dir()

    test_files_colocated = 0
    test_files_separate = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel = os.path.relpath(dirpath, root)
        for f in filenames:
            lower = f.lower()
            if "test" in lower or "spec" in lower:
                if "test" in rel or "__tests__" in rel:
                    test_files_separate += 1
                else:
                    test_files_colocated += 1

    total_tests = test_files_colocated + test_files_separate
    if total_tests >= 5:
        if test_files_colocated > total_tests * 0.7:
            conventions.append(Convention(
                category="structure",
                rule="Tests are co-located with source files",
                pattern="colocated_tests",
                confidence=test_files_colocated / total_tests,
            ))
        elif test_files_separate > total_tests * 0.7:
            conventions.append(Convention(
                category="structure",
                rule="Tests are in a separate directory",
                pattern="separate_tests",
                confidence=test_files_separate / total_tests,
            ))

    if has_src:
        conventions.append(Convention(
            category="structure",
            rule="Source code lives in src/ directory",
            pattern="src_dir",
            confidence=0.9,
        ))

    return conventions