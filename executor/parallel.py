"""Parallel execution for scanner and fixer."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional
from pathlib import Path
import time


class ParallelScanner:
    """Parallel file scanning with worker pool."""

    def __init__(self, max_workers: int = 4):
        """
        Initialize parallel scanner.

        Args:
            max_workers: Maximum number of worker threads
        """
        self.max_workers = max_workers

    def scan_files_parallel(
        self,
        files: List[str],
        severity_filter: str = "ALL"
    ) -> Dict:
        """
        Scan multiple files in parallel.

        Args:
            files: List of file paths to scan
            severity_filter: Severity filter

        Returns:
            Aggregated scan results
        """
        from scanner.cli import scan_theme

        results = {
            'violations': [],
            'critical_count': 0,
            'high_count': 0,
            'suggest_count': 0,
            'files_scanned': 0,
            'duration': 0
        }

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all scan tasks
            future_to_file = {
                executor.submit(scan_theme, file_path, severity_filter): file_path
                for file_path in files
            }

            # Collect results as they complete
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    scan_result = future.result()

                    # Aggregate results
                    results['violations'].extend(scan_result.violations)
                    results['critical_count'] += scan_result.critical_count
                    results['high_count'] += scan_result.high_count
                    results['suggest_count'] += scan_result.suggest_count
                    results['files_scanned'] += 1

                except Exception as e:
                    print(f"Error scanning {file_path}: {e}")

        results['duration'] = time.time() - start_time

        return results

    def apply_fixes_parallel(
        self,
        fixes: List[Dict],
        max_workers: Optional[int] = None
    ) -> Dict:
        """
        Apply multiple fixes in parallel.

        Args:
            fixes: List of fix dicts (lesson_id, file, line, fix_content)
            max_workers: Override max workers

        Returns:
            Results dict with success/failure counts
        """
        from agent.tools import apply_fix

        workers = max_workers or self.max_workers

        results = {
            'success': 0,
            'failed': 0,
            'errors': []
        }

        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_fix = {
                executor.submit(
                    apply_fix,
                    fix['lesson_id'],
                    fix['file'],
                    fix['line'],
                    fix['fix_content']
                ): fix
                for fix in fixes
            }

            for future in as_completed(future_to_fix):
                fix = future_to_fix[future]
                try:
                    success = future.result()
                    if success:
                        results['success'] += 1
                    else:
                        results['failed'] += 1
                        results['errors'].append({
                            'fix': fix,
                            'error': 'Fix application failed'
                        })

                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append({
                        'fix': fix,
                        'error': str(e)
                    })

        return results


class ParallelDeployExecutor:
    """Execute deployment DAG in parallel."""

    def __init__(self, max_workers: int = 3):
        """Initialize parallel deploy executor."""
        self.max_workers = max_workers

    def execute_dag(self, stages: List[Dict]) -> Dict:
        """
        Execute deployment stages in parallel where possible.

        Args:
            stages: List of stage dicts with tasks and dependencies

        Returns:
            Execution results
        """
        results = {
            'stages_completed': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'duration': 0
        }

        start_time = time.time()

        for stage in stages:
            if stage.get('can_parallel', False):
                # Execute tasks in parallel
                stage_results = self._execute_stage_parallel(stage['tasks'])
            else:
                # Execute tasks sequentially
                stage_results = self._execute_stage_sequential(stage['tasks'])

            results['stages_completed'] += 1
            results['tasks_completed'] += stage_results['success']
            results['tasks_failed'] += stage_results['failed']

            # Stop on failure
            if stage_results['failed'] > 0:
                break

        results['duration'] = time.time() - start_time

        return results

    def _execute_stage_parallel(self, tasks: List[Dict]) -> Dict:
        """Execute stage tasks in parallel."""
        results = {'success': 0, 'failed': 0}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(self._execute_task, task): task
                for task in tasks
            }

            for future in as_completed(future_to_task):
                try:
                    success = future.result()
                    if success:
                        results['success'] += 1
                    else:
                        results['failed'] += 1
                except Exception as e:
                    import sys
                    print(f"[kiwi] parallel stage task error: {e}", file=sys.stderr)
                    results['failed'] += 1

        return results

    def _execute_stage_sequential(self, tasks: List[Dict]) -> Dict:
        """Execute stage tasks sequentially."""
        results = {'success': 0, 'failed': 0}

        for task in tasks:
            try:
                success = self._execute_task(task)
                if success:
                    results['success'] += 1
                else:
                    results['failed'] += 1
                    break  # Stop on first failure
            except Exception as e:
                import sys
                print(f"[kiwi] sequential stage task error: {e}", file=sys.stderr)
                results['failed'] += 1
                break

        return results

    def _execute_task(self, task: Dict) -> bool:
        """Execute a single task."""
        # Placeholder - real implementation would execute actual task
        # (rsync, SSH command, health check, etc.)
        return True