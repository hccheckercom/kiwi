"""Integration tests for multi-agent coordination."""

import os
import sys
import tempfile
from pathlib import Path

# Add kiwi to path
KIWI_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(KIWI_DIR))

# Fix encoding for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from memory import coordination as coord
from memory.db import init_db
from agent.orchestrator import AgentOrchestrator, AGENT_REGISTRY


def test_coordination_db_init():
    """Test coordination database initialization."""
    init_db()

    stats = coord.get_coordination_stats()
    assert "total_runs" in stats
    assert "active_runs" in stats
    assert "total_verdicts" in stats
    print("✓ Coordination DB initialized")


def test_agent_run_lifecycle():
    """Test agent run creation and status updates."""
    run_id = coord.create_agent_run(
        path="/test/path",
        mode="review",
        agent_type="security"
    )

    assert run_id > 0

    run = coord.get_agent_run(run_id)
    assert run["status"] == "pending"
    assert run["agent_type"] == "security"

    coord.update_agent_run(run_id, status="running")
    run = coord.get_agent_run(run_id)
    assert run["status"] == "running"

    coord.update_agent_run(run_id, status="completed")
    run = coord.get_agent_run(run_id)
    assert run["status"] == "completed"
    assert run["completed_at"] is not None

    print(f"✓ Agent run lifecycle: {run_id}")


def test_agent_consensus():
    """Test consensus calculation from multiple agent verdicts."""
    run1 = coord.create_agent_run("/test", "review", "security")
    run2 = coord.create_agent_run("/test", "review", "performance")
    run3 = coord.create_agent_run("/test", "review", "architecture")

    coord.record_verdict(run1, "security", "LES-001", "test.php", 10, "violation", 0.9)
    coord.record_verdict(run2, "performance", "LES-001", "test.php", 10, "violation", 0.8)
    coord.record_verdict(run3, "architecture", "LES-001", "test.php", 10, "false_positive", 0.7)

    consensus = coord.calculate_consensus("LES-001", "test.php", 10)

    assert consensus["consensus"] == "violation"
    assert consensus["agent_count"] == 3
    assert consensus["confidence"] > 0.5
    assert "verdicts" in consensus

    print(f"✓ Consensus: {consensus['consensus']} (confidence: {consensus['confidence']})")


def test_agent_messages():
    """Test inter-agent messaging."""
    run1 = coord.create_agent_run("/test", "review", "security")
    run2 = coord.create_agent_run("/test", "review", "performance")

    msg_id = coord.send_message(
        from_run_id=run1,
        to_run_id=run2,
        message_type="request_scan",
        payload={"file": "test.php", "severity": "CRITICAL"}
    )

    assert msg_id > 0

    messages = coord.get_messages(run2, unprocessed_only=True)
    assert len(messages) == 1
    assert messages[0]["message_type"] == "request_scan"
    assert messages[0]["payload"]["file"] == "test.php"

    coord.mark_message_processed(msg_id)

    messages = coord.get_messages(run2, unprocessed_only=True)
    assert len(messages) == 0

    print(f"✓ Message sent and processed: {msg_id}")


def test_orchestrator_spawn():
    """Test orchestrator spawning agents."""
    with tempfile.TemporaryDirectory() as tmpdir:
        orchestrator = AgentOrchestrator(tmpdir, mode="review")

        tasks = orchestrator.spawn_agents(["security", "performance"])

        assert len(tasks) == 2
        assert tasks[0].agent_type == "security"
        assert tasks[1].agent_type == "performance"
        assert all(t.run_id > 0 for t in tasks)

        for task in tasks:
            run = coord.get_agent_run(task.run_id)
            assert run["parent_run_id"] == orchestrator.parent_run_id

        print(f"✓ Orchestrator spawned {len(tasks)} agents")


def test_agent_registry():
    """Test agent registry contains expected agents."""
    assert "security" in AGENT_REGISTRY
    assert "performance" in AGENT_REGISTRY
    assert "architecture" in AGENT_REGISTRY
    assert "compliance" in AGENT_REGISTRY

    security_spec = AGENT_REGISTRY["security"]
    assert security_spec.agent_type == "security"
    assert "php-security" in security_spec.focus_categories
    assert security_spec.severity_filter == "CRITICAL"

    print(f"✓ Agent registry has {len(AGENT_REGISTRY)} agents")


def test_child_runs():
    """Test parent-child agent run relationships."""
    parent_id = coord.create_agent_run("/test", "review", "orchestrator")

    child1 = coord.create_agent_run("/test", "review", "security", parent_run_id=parent_id)
    child2 = coord.create_agent_run("/test", "review", "performance", parent_run_id=parent_id)

    children = coord.get_child_runs(parent_id)

    assert len(children) == 2
    assert children[0]["parent_run_id"] == parent_id
    assert children[1]["parent_run_id"] == parent_id

    print(f"✓ Parent {parent_id} has {len(children)} children")


def test_active_runs():
    """Test querying active runs."""
    run1 = coord.create_agent_run("/test1", "review", "security")
    run2 = coord.create_agent_run("/test2", "review", "performance")

    coord.update_agent_run(run1, status="running")
    coord.update_agent_run(run2, status="completed")

    active = coord.get_active_runs()
    active_ids = [r["id"] for r in active]

    assert run1 in active_ids
    assert run2 not in active_ids

    print(f"✓ Found {len(active)} active runs")


def run_all_tests():
    """Run all integration tests."""
    print("=" * 60)
    print("  MULTI-AGENT COORDINATION TESTS")
    print("=" * 60)

    tests = [
        test_coordination_db_init,
        test_agent_run_lifecycle,
        test_agent_consensus,
        test_agent_messages,
        test_orchestrator_spawn,
        test_agent_registry,
        test_child_runs,
        test_active_runs,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1

    print()
    print("=" * 60)
    print(f"  RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)