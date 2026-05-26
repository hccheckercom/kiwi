"""Parallel execution engine for HTN Planner with file locking."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from planner.htn import Plan, Task


@dataclass
class FixResult:
    """Result of a fix operation."""
    success: bool
    task_id: str
    lesson_id: str
    file: str
    line: int
    duration_seconds: float
    error: Optional[str] = None


class ParallelFixExecutor:
    """Execute fixes in parallel with file locking."""

    def __init__(self, max_workers: int = 3):
        """
        Initialize parallel fix executor.

        Args:
            max_workers: Maximum number of parallel workers
        """
        self.max_workers = max_workers
        self.file_locks: Dict[str, threading.Lock] = {}
        self.lock_manager = threading.Lock()

    def execute_plan(self, plan: Plan, dry_run: bool = True, verbose: bool = False) -> Dict:
        """
        Execute HTN plan with parallel groups.

        Args:
            plan: HTN Plan with tasks and parallel groups
            dry_run: If True, preview fixes only
            verbose: Print debug info

        Returns:
            Execution results dict
        """
        results = {
            "total_tasks": len(plan.tasks),
            "completed": 0,
            "failed": 0,
            "skipped": 0,
            "duration_seconds": 0,
            "results": [],
        }

        start_time = time.time()

        if verbose:
            print(f"[parallel-executor] Executing {len(plan.parallel_groups)} parallel groups")

        # Execute each parallel group
        for group_idx, group in enumerate(plan.parallel_groups, 1):
            if verbose:
                print(f"[parallel-executor] Group {group_idx}/{len(plan.parallel_groups)}: {len(group)} task(s)")

            # Get Task objects for this group
            group_tasks = [t for t in plan.tasks if t.task_id in group]

            # Execute group (parallel if >1 task, sequential if 1)
            if len(group_tasks) > 1:
                group_results = self._execute_parallel(group_tasks, dry_run, verbose)
            else:
                group_results = self._execute_sequential(group_tasks, dry_run, verbose)

            # Aggregate results
            for result in group_results:
                results["results"].append(result)
                if result.success:
                    results["completed"] += 1
                else:
                    results["failed"] += 1

            # Stop on failure if not dry_run
            if not dry_run and results["failed"] > 0:
                if verbose:
                    print(f"[parallel-executor] Stopping due to failure in group {group_idx}")
                break

        results["duration_seconds"] = time.time() - start_time

        return results

    def _execute_parallel(self, tasks: List[Task], dry_run: bool, verbose: bool) -> List[FixResult]:
        """Execute tasks in parallel with file locking."""
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(self._execute_task_with_lock, task, dry_run, verbose): task
                for task in tasks
            }

            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)

                    if verbose:
                        status = "OK" if result.success else "FAIL"
                        print(f"[parallel-executor]   [{status}] {task.task_id}: {task.lesson_id} ({result.duration_seconds:.1f}s)")

                except Exception as e:
                    results.append(FixResult(
                        success=False,
                        task_id=task.task_id,
                        lesson_id=task.lesson_id,
                        file=task.file,
                        line=task.line,
                        duration_seconds=0,
                        error=str(e),
                    ))

                    if verbose:
                        print(f"[parallel-executor]   [FAIL] {task.task_id}: Exception: {e}")

        return results

    def _execute_sequential(self, tasks: List[Task], dry_run: bool, verbose: bool) -> List[FixResult]:
        """Execute tasks sequentially."""
        results = []

        for task in tasks:
            result = self._execute_task_with_lock(task, dry_run, verbose)
            results.append(result)

            if verbose:
                status = "OK" if result.success else "FAIL"
                print(f"[parallel-executor]   [{status}] {task.task_id}: {task.lesson_id} ({result.duration_seconds:.1f}s)")

            # Stop on failure if not dry_run
            if not dry_run and not result.success:
                break

        return results

    def _execute_task_with_lock(self, task: Task, dry_run: bool, verbose: bool) -> FixResult:
        """
        Execute a single task with file locking.

        Args:
            task: Task to execute
            dry_run: If True, preview only
            verbose: Print debug info

        Returns:
            FixResult
        """
        start_time = time.time()

        # Get or create lock for this file
        lock = self._get_file_lock(task.file)

        # Acquire lock with timeout
        acquired = lock.acquire(timeout=30.0)
        if not acquired:
            return FixResult(
                success=False,
                task_id=task.task_id,
                lesson_id=task.lesson_id,
                file=task.file,
                line=task.line,
                duration_seconds=time.time() - start_time,
                error="Lock timeout after 30s",
            )

        try:
            # Execute fix
            result = self._apply_fix(task, dry_run, verbose)
            result.duration_seconds = time.time() - start_time
            return result

        finally:
            # Always release lock
            lock.release()

    def _get_file_lock(self, file_path: str) -> threading.Lock:
        """Get or create lock for a file."""
        with self.lock_manager:
            if file_path not in self.file_locks:
                self.file_locks[file_path] = threading.Lock()
            return self.file_locks[file_path]

    def _apply_fix(self, task: Task, dry_run: bool, verbose: bool) -> FixResult:
        """
        Apply fix for a task.

        Args:
            task: Task to fix
            dry_run: If True, preview only
            verbose: Print debug info

        Returns:
            FixResult
        """
        try:
            # Import here to avoid circular dependency
            import sys
            from pathlib import Path

            kiwi_dir = Path(__file__).parent.parent
            sys.path.insert(0, str(kiwi_dir))

            from agent.tools import _ensure_scanner, _load_lesson
            from scanner.fixer import apply_fix
            from scanner.models import Violation

            _ensure_scanner()

            # Load lesson
            fm, _ = _load_lesson(task.lesson_id)
            if not fm or not fm.get("fix"):
                return FixResult(
                    success=False,
                    task_id=task.task_id,
                    lesson_id=task.lesson_id,
                    file=task.file,
                    line=task.line,
                    duration_seconds=0,
                    error="No fix available for this lesson",
                )

            # Create violation
            violation = Violation(
                lesson_id=task.lesson_id,
                severity=task.severity,
                category=task.category,
                description=task.description,
                file=task.file,
                line=task.line,
            )

            # Apply fix
            fix_result = apply_fix(violation, fm["fix"], dry_run=dry_run)

            return FixResult(
                success=fix_result.success,
                task_id=task.task_id,
                lesson_id=task.lesson_id,
                file=task.file,
                line=task.line,
                duration_seconds=0,  # Will be set by caller
                error=fix_result.error if not fix_result.success else None,
            )

        except Exception as e:
            return FixResult(
                success=False,
                task_id=task.task_id,
                lesson_id=task.lesson_id,
                file=task.file,
                line=task.line,
                duration_seconds=0,
                error=str(e),
            )
