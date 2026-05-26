"""
Impact Analysis Engine for Kiwi
Phát hiện files bị ảnh hưởng khi fix bug để ngăn regression.
"""

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Set, Optional
import json


@dataclass
class AffectedFile:
    """File bị ảnh hưởng bởi fix"""
    path: str
    reason: str
    risk: str  # LOW, MEDIUM, HIGH
    line_numbers: List[int] = field(default_factory=list)
    symbols: List[str] = field(default_factory=list)


@dataclass
class ImpactReport:
    """Báo cáo impact analysis"""
    fixed_file: str
    affected_files: List[AffectedFile]
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    suggestions: List[str]
    symbols_changed: List[str] = field(default_factory=list)


@dataclass
class CallGraph:
    """Call graph của một file"""
    file_path: str
    functions_defined: List[str] = field(default_factory=list)
    classes_defined: List[str] = field(default_factory=list)
    functions_called: List[str] = field(default_factory=list)
    classes_used: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)


class ImpactAnalyzer:
    """Core impact analyzer"""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.cache: Dict[str, CallGraph] = {}
        self.dependency_graph: Dict[str, Set[str]] = {}

    def analyze_fix_impact(self, fixed_file: str, auto_scan: bool = False) -> ImpactReport:
        """
        Phân tích impact của fix trên fixed_file.

        Args:
            fixed_file: Path to file vừa fix
            auto_scan: True = tự động scan affected files

        Returns:
            ImpactReport với affected_files, risk_level, suggestions
        """
        fixed_path = Path(fixed_file)
        if not fixed_path.is_absolute():
            fixed_path = self.project_root / fixed_path

        if not fixed_path.exists():
            return ImpactReport(
                fixed_file=str(fixed_path),
                affected_files=[],
                risk_level="UNKNOWN",
                suggestions=[f"File not found: {fixed_path}"]
            )

        # Build call graph cho file được fix
        call_graph = self._build_call_graph(str(fixed_path))

        # Tìm symbols được define trong file
        symbols = call_graph.functions_defined + call_graph.classes_defined

        if not symbols:
            return ImpactReport(
                fixed_file=str(fixed_path),
                affected_files=[],
                risk_level="LOW",
                suggestions=["No public symbols found — impact likely minimal"],
                symbols_changed=[]
            )

        # Tìm files gọi các symbols này
        affected = self._find_affected_files(str(fixed_path), symbols)

        # Calculate risk level
        risk_level = self._calculate_overall_risk(affected)

        # Generate suggestions
        suggestions = self._generate_suggestions(affected, symbols)

        return ImpactReport(
            fixed_file=str(fixed_path),
            affected_files=affected,
            risk_level=risk_level,
            suggestions=suggestions,
            symbols_changed=symbols
        )

    def _build_call_graph(self, file_path: str) -> CallGraph:
        """
        Parse file để extract call graph.
        Dùng regex-based parser (fallback nếu không có nikic/php-parser).
        """
        if file_path in self.cache:
            return self.cache[file_path]

        path = Path(file_path)
        ext = path.suffix.lower()

        if ext == '.php':
            graph = self._parse_php(file_path)
        elif ext in ['.js', '.ts', '.jsx', '.tsx']:
            graph = self._parse_js(file_path)
        else:
            graph = CallGraph(file_path=file_path)

        self.cache[file_path] = graph
        return graph

    def _parse_php(self, file_path: str) -> CallGraph:
        """Parse PHP file với regex"""
        graph = CallGraph(file_path=file_path)

        try:
            content = Path(file_path).read_text(encoding='utf-8')
        except Exception as e:
            import sys
            print(f"[kiwi] _parse_php read error: {e}", file=sys.stderr)
            return graph

        # Extract function definitions: function name(
        func_pattern = r'function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
        graph.functions_defined = list(set(re.findall(func_pattern, content)))

        # Extract class definitions: class Name
        class_pattern = r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        graph.classes_defined = list(set(re.findall(class_pattern, content)))

        # Extract function calls: name(
        call_pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
        all_calls = re.findall(call_pattern, content)
        # Filter out defined functions
        graph.functions_called = list(set(
            c for c in all_calls
            if c not in graph.functions_defined and not c.startswith('__')
        ))

        # Extract require/include
        import_pattern = r'(?:require|include)(?:_once)?\s*[(\s]+[\'"]([^\'"]+)[\'"]'
        graph.imports = list(set(re.findall(import_pattern, content)))

        return graph

    def _parse_js(self, file_path: str) -> CallGraph:
        """Parse JS/TS file với regex"""
        graph = CallGraph(file_path=file_path)

        try:
            content = Path(file_path).read_text(encoding='utf-8')
        except Exception as e:
            import sys
            print(f"[kiwi] _parse_js read error: {e}", file=sys.stderr)
            return graph

        # Extract function definitions: function name( hoặc const name = (
        func_pattern = r'(?:function|const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*[=\(]'
        graph.functions_defined = list(set(re.findall(func_pattern, content)))

        # Extract class definitions
        class_pattern = r'class\s+([a-zA-Z_$][a-zA-Z0-9_$]*)'
        graph.classes_defined = list(set(re.findall(class_pattern, content)))

        # Extract imports: import ... from '...'
        import_pattern = r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]'
        graph.imports = list(set(re.findall(import_pattern, content)))

        return graph

    def _find_affected_files(self, fixed_file: str, symbols: List[str]) -> List[AffectedFile]:
        """
        Tìm files gọi symbols từ fixed_file.
        Dùng grep để tìm nhanh.
        """
        affected = []
        fixed_path = Path(fixed_file)

        # Tìm files import/require fixed_file
        importers = self._find_importers(fixed_file)

        for importer in importers:
            # Check xem importer có gọi symbols không
            matches = self._find_symbol_usage(importer, symbols)

            if matches:
                risk = self._calculate_file_risk(importer, matches, symbols)
                affected.append(AffectedFile(
                    path=importer,
                    reason=f"imports {fixed_path.name} and calls: {', '.join(matches.keys())}",
                    risk=risk,
                    line_numbers=list(set(ln for lns in matches.values() for ln in lns)),
                    symbols=list(matches.keys())
                ))
            else:
                # Import nhưng không rõ usage
                affected.append(AffectedFile(
                    path=importer,
                    reason=f"imports {fixed_path.name} but usage unclear",
                    risk="MEDIUM",
                    line_numbers=[],
                    symbols=[]
                ))

        # Tìm files gọi symbols nhưng không import (global functions)
        callers = self._find_symbol_callers(symbols, exclude=importers + [fixed_file])

        for caller, matches in callers.items():
            risk = self._calculate_file_risk(caller, matches, symbols)
            affected.append(AffectedFile(
                path=caller,
                reason=f"calls: {', '.join(matches.keys())}",
                risk=risk,
                line_numbers=list(set(ln for lns in matches.values() for ln in lns)),
                symbols=list(matches.keys())
            ))

        return affected

    def build_dependency_graph_for_files(self, files: List[str]) -> Dict[str, Set[str]]:
        """
        Build dependency graph for a list of files.
        Returns dict mapping file -> set of files that depend on it.

        Used by planner to determine fix order.
        """
        graph = {f: set() for f in files}

        for file in files:
            try:
                call_graph = self._build_call_graph(file)
                symbols = call_graph.functions_defined + call_graph.classes_defined

                if not symbols:
                    continue

                # Find which other files in the list depend on this file
                for other_file in files:
                    if other_file == file:
                        continue

                    other_graph = self._build_call_graph(other_file)

                    # Check if other_file calls any symbols from file
                    for symbol in symbols:
                        if symbol in other_graph.functions_called or symbol in other_graph.classes_used:
                            graph[file].add(other_file)
                            break

                    # Check if other_file imports file
                    file_path = Path(file)
                    for import_path in other_graph.imports:
                        if file_path.name in import_path or str(file_path) in import_path:
                            graph[file].add(other_file)
                            break

            except Exception as e:
                import sys
                print(f"[kiwi] build_dependency_graph error: {e}", file=sys.stderr)
                continue

        return graph

    def _find_importers(self, file_path: str) -> List[str]:
        """Tìm files import/require file_path"""
        importers = []
        file_path = Path(file_path)
        filename = file_path.name

        # Patterns to search
        patterns = [
            rf"require.*{re.escape(filename)}",
            rf"include.*{re.escape(filename)}",
            rf"import.*from.*{re.escape(filename)}",
        ]

        # Walk directory tree
        for ext in ['.php', '.js', '.ts', '.jsx', '.tsx']:
            for file in self.project_root.rglob(f'*{ext}'):
                if file == file_path:
                    continue

                try:
                    content = file.read_text(encoding='utf-8')
                    for pattern in patterns:
                        if re.search(pattern, content):
                            importers.append(str(file))
                            break
                except Exception as e:
                    pass  # Expected for binary files

        return list(set(importers))

    def _find_symbol_usage(self, file_path: str, symbols: List[str]) -> Dict[str, List[int]]:
        """
        Tìm usage của symbols trong file.
        Returns: {symbol: [line_numbers]}
        """
        matches = {}

        try:
            content = Path(file_path).read_text(encoding='utf-8')
            lines = content.split('\n')

            for symbol in symbols:
                # Pattern: symbol( hoặc symbol::
                pattern = rf'\b{re.escape(symbol)}\s*[\(:]'

                line_nums = []
                for i, line in enumerate(lines, 1):
                    if re.search(pattern, line):
                        line_nums.append(i)

                if line_nums:
                    matches[symbol] = line_nums
        except Exception as e:
            import sys
            print(f"[kiwi] _find_symbol_usage error: {e}", file=sys.stderr)

        return matches

    def _find_symbol_callers(self, symbols: List[str], exclude: List[str]) -> Dict[str, Dict[str, List[int]]]:
        """
        Tìm files gọi symbols (không cần import — global functions).
        Returns: {file_path: {symbol: [line_numbers]}}
        """
        callers = {}
        exclude_set = set(Path(f).resolve() for f in exclude)

        # Walk directory tree
        for ext in ['.php', '.js', '.ts', '.jsx', '.tsx']:
            for file in self.project_root.rglob(f'*{ext}'):
                file_resolved = file.resolve()
                if file_resolved in exclude_set:
                    continue

                try:
                    content = file.read_text(encoding='utf-8')
                    lines = content.split('\n')

                    for symbol in symbols:
                        # Pattern: symbol( hoặc symbol::
                        pattern = rf'\b{re.escape(symbol)}\s*[\(:]'

                        for i, line in enumerate(lines, 1):
                            if re.search(pattern, line):
                                file_str = str(file_resolved)
                                if file_str not in callers:
                                    callers[file_str] = {}
                                if symbol not in callers[file_str]:
                                    callers[file_str][symbol] = []
                                callers[file_str][symbol].append(i)
                except Exception as e:
                    pass  # Expected for binary files

        return callers

    def _calculate_file_risk(self, file_path: str, matches: Dict[str, List[int]], all_symbols: List[str]) -> str:
        """Calculate risk level cho một affected file"""
        if not matches:
            return "LOW"

        # HIGH: gọi nhiều symbols hoặc nhiều lần
        total_calls = sum(len(lines) for lines in matches.values())
        symbols_used = len(matches)

        if symbols_used >= len(all_symbols) * 0.5 or total_calls >= 5:
            return "HIGH"
        elif symbols_used >= 2 or total_calls >= 2:
            return "MEDIUM"
        else:
            return "LOW"

    def _calculate_overall_risk(self, affected: List[AffectedFile]) -> str:
        """Calculate overall risk level"""
        if not affected:
            return "LOW"

        high_count = sum(1 for f in affected if f.risk == "HIGH")
        medium_count = sum(1 for f in affected if f.risk == "MEDIUM")

        if high_count >= 3:
            return "CRITICAL"
        elif high_count >= 1:
            return "HIGH"
        elif medium_count >= 2:
            return "MEDIUM"
        else:
            return "LOW"

    def _generate_suggestions(self, affected: List[AffectedFile], symbols: List[str]) -> List[str]:
        """Generate actionable suggestions"""
        suggestions = []

        high_risk = [f for f in affected if f.risk == "HIGH"]
        medium_risk = [f for f in affected if f.risk == "MEDIUM"]

        if high_risk:
            files = ', '.join(Path(f.path).name for f in high_risk[:3])
            suggestions.append(f"Scan {files} (HIGH priority)")

        if medium_risk:
            files = ', '.join(Path(f.path).name for f in medium_risk[:3])
            suggestions.append(f"Check {files} (MEDIUM priority)")

        if affected:
            suggestions.append(f"Run tests covering these {len(affected)} files")

        if symbols:
            suggestions.append(f"Verify behavior of: {', '.join(symbols[:5])}")

        return suggestions