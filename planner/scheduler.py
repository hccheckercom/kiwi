"""Task scheduler with parallel execution planning."""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Set, Dict

KIWI_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(KIWI_DIR))


@dataclass
class ExecutionStage:
    """A stage in the execution plan where tasks can run in parallel."""
    stage_number: int
    task_ids: List[str]
    estimated_duration_minutes: int


class TaskScheduler:
    """Schedules tasks respecting dependencies and enabling parallelization."""

    def __init__(self, tasks: list, dependency_graph: Dict[str, List[str]]):
        """
        Args:
            tasks: List of Task objects from planner.htn
            dependency_graph: Dict mapping task_id -> list of dependent task_ids
        """
        self.tasks = {t.task_id: t for t in tasks}
        self.dependency_graph = dependency_graph

    def schedule(self) -> List[ExecutionStage]:
        """
        Create execution stages where tasks in same stage can run in parallel.
        Uses topological sort with level-based grouping.
        """
        stages = []
        remaining = set(self.tasks.keys())
        completed = set()
        stage_num = 0

        while remaining:
            # Find tasks with all dependencies satisfied
            ready = []
            for task_id in remaining:
                deps = self.dependency_graph.get(task_id, [])
                if all(dep in completed or dep not in remaining for dep in deps):
                    ready.append(task_id)

            if not ready:
                # Circular dependency or orphaned tasks
                ready = list(remaining)

            # Calculate stage duration (max of all tasks in stage)
            duration = max(
                self._task_duration(task_id) for task_id in ready
            )

            stages.append(ExecutionStage(
                stage_number=stage_num,
                task_ids=ready,
                estimated_duration_minutes=duration
            ))

            for task_id in ready:
                remaining.remove(task_id)
                completed.add(task_id)

            stage_num += 1

        return stages

    def _task_duration(self, task_id: str) -> int:
        """Get estimated duration for a task."""
        task = self.tasks.get(task_id)
        if not task:
            return 15

        effort_map = {"low": 5, "medium": 15, "high": 30}
        return effort_map.get(task.effort, 15)

    def can_run_parallel(self, task_id_1: str, task_id_2: str) -> bool:
        """Check if two tasks can run in parallel (no dependency between them)."""
        deps_1 = set(self.dependency_graph.get(task_id_1, []))
        deps_2 = set(self.dependency_graph.get(task_id_2, []))

        # Check if either depends on the other
        if task_id_2 in deps_1 or task_id_1 in deps_2:
            return False

        # Check if they modify the same file
        task1 = self.tasks.get(task_id_1)
        task2 = self.tasks.get(task_id_2)

        if task1 and task2 and task1.file == task2.file:
            return False

        return True

    def reorder_for_risk(self, stages: List[ExecutionStage]) -> List[ExecutionStage]:
        """
        Reorder tasks within stages to prioritize low-risk tasks first.
        High-risk tasks run later so we can catch issues early.
        """
        risk_priority = {"low": 0, "medium": 1, "high": 2}

        for stage in stages:
            stage.task_ids.sort(
                key=lambda tid: (
                    risk_priority.get(self.tasks[tid].risk, 1),
                    -self.tasks[tid].priority
                )
            )

        return stages

    def estimate_total_duration(self, stages: List[ExecutionStage]) -> int:
        """Estimate total duration if stages run sequentially."""
        return sum(stage.estimated_duration_minutes for stage in stages)

    def estimate_parallel_duration(self, stages: List[ExecutionStage]) -> int:
        """
        Estimate duration if stages run in parallel.
        Same as sequential since stages must run in order.
        """
        return self.estimate_total_duration(stages)

    def get_critical_path(self, stages: List[ExecutionStage]) -> List[str]:
        """
        Find critical path (longest dependency chain).
        Tasks on critical path cannot be parallelized.
        """
        # Build reverse graph (task -> tasks that depend on it)
        reverse_graph = {}
        for task_id, deps in self.dependency_graph.items():
            for dep in deps:
                if dep not in reverse_graph:
                    reverse_graph[dep] = []
                reverse_graph[dep].append(task_id)

        # Find longest path using DFS
        def dfs(task_id: str, visited: Set[str]) -> List[str]:
            if task_id in visited:
                return []

            visited.add(task_id)
            dependents = reverse_graph.get(task_id, [])

            if not dependents:
                return [task_id]

            longest = []
            for dep in dependents:
                path = dfs(dep, visited.copy())
                if len(path) > len(longest):
                    longest = path

            return [task_id] + longest

        # Find path from each root task
        roots = [tid for tid in self.tasks.keys() if tid not in reverse_graph]
        critical = []

        for root in roots:
            path = dfs(root, set())
            if len(path) > len(critical):
                critical = path

        return critical
