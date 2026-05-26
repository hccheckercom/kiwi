"""Test HTN Planner with sample violations."""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from planner.htn import TaskPlanner


def test_basic_planning():
    """Test basic planning with sample violations."""
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
    ]

    planner = TaskPlanner(".")
    plan = planner.plan(violations, max_fixes=10)

    print("=" * 60)
    print("HTN PLANNER TEST RESULTS")
    print("=" * 60)
    print(f"\nTotal tasks: {len(plan.tasks)}")
    print(f"Estimated duration: {plan.estimated_duration_minutes} minutes")
    print(f"Parallel groups: {len(plan.parallel_groups)}")

    print("\n" + "=" * 60)
    print("TASK ORDER (by dependencies + risk)")
    print("=" * 60)
    for i, task in enumerate(plan.tasks, 1):
        print(f"\n{i}. {task.task_id} — {task.lesson_id}")
        print(f"   File: {task.file}:{task.line}")
        print(f"   Severity: {task.severity} | Category: {task.category}")
        print(f"   Risk: {task.risk:.2f} | Effort: {task.effort} min")
        deps = plan.dependency_graph.get(task.task_id, [])
        if deps:
            print(f"   Dependencies: {', '.join(deps)}")

    print("\n" + "=" * 60)
    print("PARALLEL GROUPS")
    print("=" * 60)
    for i, group in enumerate(plan.parallel_groups, 1):
        print(f"\nGroup {i}: {len(group)} task(s)")
        for task_id in group:
            task = next(t for t in plan.tasks if t.task_id == task_id)
            print(f"  - {task_id}: {task.lesson_id} ({task.file})")

    print("\n" + "=" * 60)
    print("DEPENDENCY GRAPH")
    print("=" * 60)
    for task_id, deps in plan.dependency_graph.items():
        if deps:
            print(f"{task_id} depends on: {', '.join(deps)}")

    print("\n" + "=" * 60)
    print("VALIDATION")
    print("=" * 60)

    # Validate: security tasks should come first in same file
    auth_tasks = [t for t in plan.tasks if t.file == "src/auth.php"]
    if auth_tasks:
        first_auth = auth_tasks[0]
        print(f"✓ First task in auth.php: {first_auth.lesson_id} ({first_auth.category})")
        if first_auth.category == "php-security":
            print("  ✓ Security task runs first (correct)")
        else:
            print("  ✗ Security task should run first (incorrect)")

    # Validate: different files can run in parallel
    has_parallel = any(len(g) > 1 for g in plan.parallel_groups)
    if has_parallel:
        print("✓ Parallel execution detected")
    else:
        print("✗ No parallel execution (expected some)")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_basic_planning()