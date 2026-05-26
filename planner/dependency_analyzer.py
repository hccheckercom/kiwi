"""Dependency analysis for violations."""

import re
from pathlib import Path
from typing import Dict, List, Set


class DependencyAnalyzer:
    """Analyze dependencies between violations."""

    def __init__(self, project_path: str):
        """
        Initialize dependency analyzer.

        Args:
            project_path: Root path of project
        """
        self.project_path = Path(project_path)

    def analyze(self, violations: List[dict]) -> Dict[str, List[str]]:
        """
        Build dependency graph from violations.

        Args:
            violations: List of violation dicts with keys:
                - task_id: str
                - file: str
                - line: int
                - severity: str
                - category: str
                - lesson_id: str

        Returns:
            Dependency graph: {task_id: [dependent_task_ids]}
            If task A depends on task B, then B must be fixed before A.
        """
        graph: Dict[str, List[str]] = {v["task_id"]: [] for v in violations}

        # Rule 1: Security fixes block other fixes in same file
        self._add_security_dependencies(violations, graph)

        # Rule 2: DB schema changes block queries
        self._add_db_dependencies(violations, graph)

        # Rule 3: File-level dependencies (same file = sequential)
        self._add_file_dependencies(violations, graph)

        return graph

    def _add_security_dependencies(
        self, violations: List[dict], graph: Dict[str, List[str]]
    ) -> None:
        """Security fixes must run first in each file."""
        security_categories = {"php-security", "api-security", "auth-security"}

        # Group by file
        by_file: Dict[str, List[dict]] = {}
        for v in violations:
            file_path = v["file"]
            if file_path not in by_file:
                by_file[file_path] = []
            by_file[file_path].append(v)

        # For each file, security tasks block non-security tasks
        for file_path, file_violations in by_file.items():
            security_tasks = [
                v["task_id"]
                for v in file_violations
                if v["category"] in security_categories
            ]
            non_security_tasks = [
                v["task_id"]
                for v in file_violations
                if v["category"] not in security_categories
            ]

            # Non-security tasks depend on security tasks
            for non_sec_task in non_security_tasks:
                graph[non_sec_task].extend(security_tasks)

    def _add_db_dependencies(
        self, violations: List[dict], graph: Dict[str, List[str]]
    ) -> None:
        """DB schema changes block query fixes."""
        schema_lessons = {"LES-042", "LES-089"}  # Known DB schema lessons
        query_keywords = {"query", "select", "insert", "update", "delete"}

        schema_tasks = [
            v["task_id"]
            for v in violations
            if v["lesson_id"] in schema_lessons
            or "schema" in v["lesson_id"].lower()
            or "migration" in v["lesson_id"].lower()
        ]

        query_tasks = [
            v["task_id"]
            for v in violations
            if any(kw in v["lesson_id"].lower() for kw in query_keywords)
            or v["category"] == "db-schema"
        ]

        # Query tasks depend on schema tasks
        for query_task in query_tasks:
            graph[query_task].extend(schema_tasks)

    def _add_file_dependencies(
        self, violations: List[dict], graph: Dict[str, List[str]]
    ) -> None:
        """
        Tasks in same file should run sequentially.
        Higher severity tasks run first.
        """
        severity_order = {"CRITICAL": 0, "HIGH": 1, "SUGGEST": 2}

        # Group by file
        by_file: Dict[str, List[dict]] = {}
        for v in violations:
            file_path = v["file"]
            if file_path not in by_file:
                by_file[file_path] = []
            by_file[file_path].append(v)

        # For each file, sort by severity and create chain
        for file_path, file_violations in by_file.items():
            if len(file_violations) <= 1:
                continue

            # Sort by severity (CRITICAL first)
            sorted_violations = sorted(
                file_violations,
                key=lambda v: (
                    severity_order.get(v["severity"], 3),
                    v["line"],
                ),
            )

            # Create dependency chain: each task depends on previous
            for i in range(1, len(sorted_violations)):
                current_task = sorted_violations[i]["task_id"]
                prev_task = sorted_violations[i - 1]["task_id"]
                if prev_task not in graph[current_task]:
                    graph[current_task].append(prev_task)