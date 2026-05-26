"""HTN (Hierarchical Task Network) Planner — Optimized fix ordering."""

from dataclasses import dataclass
from typing import List, Dict, Set

from .dependency_analyzer import DependencyAnalyzer
from .risk_scorer import RiskScorer
from .effort_estimator import EffortEstimator


@dataclass
class Task:
    task_id: str
    lesson_id: str
    file: str
    line: int
    severity: str
    category: str
    description: str
    effort: int = 5
    risk: float = 0.5
    priority: int = 1


@dataclass
class Plan:
    tasks: List[Task]
    dependency_graph: Dict[str, List[str]]
    parallel_groups: List[List[str]]
    estimated_duration_minutes: int


class TaskPlanner:
    """Generate optimized execution plans for violations."""

    def __init__(self, project_path: str):
        self.project_path = project_path
        self.dep_analyzer = DependencyAnalyzer(project_path)
        self.risk_scorer = RiskScorer()
        self.effort_estimator = EffortEstimator()

    def plan(self, violations: List[dict], max_fixes: int = 10) -> Plan:
        """
        Generate optimized execution plan from violations.

        Args:
            violations: List of violation dicts with keys:
                - lesson_id: str
                - file: str
                - line: int
                - severity: str (CRITICAL|HIGH|SUGGEST)
                - category: str
                - description: str
            max_fixes: Max number of fixes to include in plan

        Returns:
            Plan with optimized task order and parallel groups
        """
        # Add task_id to each violation
        for i, v in enumerate(violations):
            v["task_id"] = f"task_{i}"

        # Score risk and estimate effort
        self.risk_scorer.score_batch(violations)
        self.effort_estimator.estimate_batch(violations)

        # Build dependency graph
        dep_graph = self.dep_analyzer.analyze(violations)

        # Topological sort by dependencies + risk
        sorted_violations = self._topological_sort(violations, dep_graph)

        # Take top max_fixes
        selected = sorted_violations[:max_fixes]

        # Convert to Task objects
        tasks = [
            Task(
                task_id=v["task_id"],
                lesson_id=v["lesson_id"],
                file=v["file"],
                line=v["line"],
                severity=v["severity"],
                category=v["category"],
                description=v.get("description", ""),
                effort=v["effort"],
                risk=v["risk"],
                priority=self._severity_to_priority(v["severity"]),
            )
            for v in selected
        ]

        # Build parallel groups
        parallel_groups = self._group_parallel(selected, dep_graph)

        # Calculate total duration
        total_duration = sum(t.effort for t in tasks)

        return Plan(
            tasks=tasks,
            dependency_graph={k: v for k, v in dep_graph.items() if k in [t.task_id for t in tasks]},
            parallel_groups=parallel_groups,
            estimated_duration_minutes=total_duration,
        )

    def _topological_sort(
        self, violations: List[dict], dep_graph: Dict[str, List[str]]
    ) -> List[dict]:
        """
        Topological sort violations by dependencies, then by risk.

        Args:
            violations: List of violations with task_id
            dep_graph: Dependency graph {task_id: [dependencies]}

        Returns:
            Sorted list of violations
        """
        # Calculate in-degree for each task
        in_degree = {v["task_id"]: 0 for v in violations}
        for task_id, deps in dep_graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[task_id] += 1

        # Start with tasks that have no dependencies
        queue = [v for v in violations if in_degree[v["task_id"]] == 0]
        # Sort queue by risk (highest first)
        queue.sort(key=lambda v: v["risk"], reverse=True)

        result = []
        while queue:
            # Pop highest risk task
            current = queue.pop(0)
            result.append(current)

            # Reduce in-degree for dependent tasks
            for v in violations:
                if current["task_id"] in dep_graph.get(v["task_id"], []):
                    in_degree[v["task_id"]] -= 1
                    if in_degree[v["task_id"]] == 0:
                        queue.append(v)
                        # Re-sort by risk
                        queue.sort(key=lambda x: x["risk"], reverse=True)

        return result

    def _group_parallel(
        self, violations: List[dict], dep_graph: Dict[str, List[str]]
    ) -> List[List[str]]:
        """
        Group independent tasks for parallel execution.

        Args:
            violations: Sorted list of violations
            dep_graph: Dependency graph

        Returns:
            List of parallel groups (each group = list of task_ids)
        """
        groups = []
        processed: Set[str] = set()

        for v in violations:
            task_id = v["task_id"]
            if task_id in processed:
                continue

            # Find all tasks that can run in parallel with this one
            group = [task_id]
            processed.add(task_id)

            for other in violations:
                other_id = other["task_id"]
                if other_id in processed:
                    continue

                # Check if independent (no dependency in either direction)
                if (
                    other_id not in dep_graph.get(task_id, [])
                    and task_id not in dep_graph.get(other_id, [])
                    and v["file"] != other["file"]  # Different files can run parallel
                ):
                    group.append(other_id)
                    processed.add(other_id)

            groups.append(group)

        return groups

    def _severity_to_priority(self, severity: str) -> int:
        """Convert severity to priority (1=highest)."""
        return {"CRITICAL": 1, "HIGH": 2, "SUGGEST": 3}.get(severity, 2)
