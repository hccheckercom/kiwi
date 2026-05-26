"""Test parallel execution with multiple violations."""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from planner.htn import TaskPlanner
from executor.htn_executor import ParallelFixExecutor


def test_parallel_execution():
    """Test parallel execution with multiple violations in different files."""
    violations = [
        {
            "lesson_id": "LES-001",
            "file": "src/auth.php",
            "line": 42,
            "severity": "CRITICAL",
            "category": "php-security",
            "description": "SQL injection vulnerability",
        },
        {
            "lesson_id": "LES-002",
            "file": "src/auth.php",
            "line": 55,
            "severity": "HIGH",
            "category": "performance",
            "description": "N+1 query",
        },
        {
            "lesson_id": "LES-003",
            "file": "src/product.php",
            "line": 100,
            "severity": "CRITICAL",
            "category": "php-security",
            "description": "XSS vulnerability",
        },
        {
            "lesson_id": "LES-004",
            "file": "src/product.php",
            "line": 120,
            "severity": "SUGGEST",
            "category": "css-tokens",
            "description": "Hardcoded color",
        },
        {
            "lesson_id": "LES-005",
            "file": "src/cart.php",
            "line": 200,
            "severity": "HIGH",
            "category": "performance",
            "description": "Missing cache",
        },
        {
            "lesson_id": "LES-006",
            "file": "src/checkout.php",
            "line": 150,
            "severity": "CRITICAL",
            "category": "php-security",
            "description": "CSRF vulnerability",
        },
        {
            "lesson_id": "LES-007",
            "file": "src/checkout.php",
            "line": 180,
            "severity": "HIGH",
            "category": "performance",
            "description": "Slow query",
        },
    ]

    print("=" * 70)
    print("PARALLEL EXECUTION TEST")
    print("=" * 70)

    # Step 1: Create plan
    print("\n[1] Creating HTN Plan...")
    planner = TaskPlanner(".")
    plan = planner.plan(violations, max_fixes=10)

    print(f"    Total tasks: {len(plan.tasks)}")
    print(f"    Estimated duration: {plan.estimated_duration_minutes} minutes")
    print(f"    Parallel groups: {len(plan.parallel_groups)}")

    # Show parallel groups
    print("\n[2] Parallel Groups:")
    for i, group in enumerate(plan.parallel_groups, 1):
        print(f"    Group {i}: {len(group)} task(s)")
        for task_id in group:
            task = next(t for t in plan.tasks if t.task_id == task_id)
            print(f"      - {task_id}: {task.lesson_id} ({task.file}) [risk={task.risk:.2f}]")

    # Step 2: Execute plan
    print("\n[3] Executing Plan (dry_run=True)...")
    executor = ParallelFixExecutor(max_workers=3)
    results = executor.execute_plan(plan, dry_run=True, verbose=True)

    # Step 3: Show results
    print("\n" + "=" * 70)
    print("EXECUTION RESULTS")
    print("=" * 70)
    print(f"Total tasks:    {results['total_tasks']}")
    print(f"Completed:      {results['completed']}")
    print(f"Failed:         {results['failed']}")
    print(f"Duration:       {results['duration_seconds']:.2f}s")

    # Show detailed results
    print("\n[4] Detailed Results:")
    for result in results["results"]:
        status = "OK" if result.success else "FAIL"
        print(f"    [{status}] {result.task_id}: {result.lesson_id} ({result.file}:{result.line})")
        if result.error:
            print(f"       Error: {result.error}")

    # Validation
    print("\n" + "=" * 70)
    print("VALIDATION")
    print("=" * 70)

    # Check: Security tasks should be in first group
    first_group = plan.parallel_groups[0]
    first_group_tasks = [t for t in plan.tasks if t.task_id in first_group]
    security_count = sum(1 for t in first_group_tasks if t.category in ["php-security", "api-security"])
    print(f"[OK] Security tasks in first group: {security_count}/{len(first_group_tasks)}")

    # Check: Different files should be in same parallel group
    has_parallel = any(len(g) > 1 for g in plan.parallel_groups)
    if has_parallel:
        print("[OK] Parallel execution detected")
        max_parallel = max(len(g) for g in plan.parallel_groups)
        print(f"  Max parallel tasks: {max_parallel}")
    else:
        print("[FAIL] No parallel execution")

    # Check: Same-file tasks should be sequential
    auth_tasks = [t for t in plan.tasks if t.file == "src/auth.php"]
    if len(auth_tasks) > 1:
        # Check if they're in different groups
        auth_groups = []
        for i, group in enumerate(plan.parallel_groups):
            if any(t.task_id in group for t in auth_tasks):
                auth_groups.append(i)
        if len(set(auth_groups)) > 1:
            print(f"[OK] Same-file tasks (auth.php) are in different groups (sequential)")
        else:
            print(f"[FAIL] Same-file tasks should be sequential")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    test_parallel_execution()