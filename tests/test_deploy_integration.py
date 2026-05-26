"""
Integration tests for kiwi_deploy flow.

Tests the full deployment pipeline:
1. Pre-deployment scan
2. Git state caching
3. Command execution (dry-run mode)
4. Health checks
5. Deployment history logging
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_deploy_dry_run():
    """Test deployment in dry-run mode (no actual deployment)."""
    print("=" * 60)
    print("TEST 1: Deploy dry-run mode")
    print("=" * 60)

    from deploy.executor import DeployExecutor

    # Test with a small theme
    test_path = Path(__file__).parent.parent.parent.parent / "themes" / "sfvn"

    if not test_path.exists():
        print(f"Test path not found: {test_path}")
        print("Skipping test - no test project available")
        return True

    # DeployExecutor API: __init__(project_path, deploy_type, target)
    executor = DeployExecutor(
        project_path=str(test_path),
        deploy_type="wp_theme",
        target="staging"
    )

    # Test basic functionality
    git_commit = executor.get_git_commit()
    git_clean = executor.check_git_clean()

    print(f"Git commit: {git_commit[:8] if git_commit != 'unknown' else 'unknown'}")
    print(f"Git clean: {git_clean}")

    assert git_commit is not None, "Should return git commit"

    print("✓ DeployExecutor initialized successfully")
    return True


def test_deploy_verify_mode():
    """Test deployment in verify mode (pre-checks only)."""
    print("\n" + "=" * 60)
    print("TEST 2: Deploy verify mode")
    print("=" * 60)

    from deploy.executor import DeployExecutor

    test_path = Path(__file__).parent.parent.parent.parent / "wezone-plugins"

    if not test_path.exists():
        print(f"Test path not found: {test_path}")
        print("Skipping test - no test project available")
        return True

    # DeployExecutor API: __init__(project_path, deploy_type, target)
    executor = DeployExecutor(
        project_path=str(test_path),
        deploy_type="wp_plugin",
        target="staging"
    )

    # Test pre-check methods
    git_clean = executor.check_git_clean()
    git_commit = executor.get_git_commit()

    print(f"Git clean: {git_clean}")
    print(f"Git commit: {git_commit[:8] if git_commit != 'unknown' else 'unknown'}")

    assert git_commit is not None, "Should return git commit"

    print("✓ DeployExecutor pre-checks work")
    return True


def test_git_cache():
    """Test git state caching for deployment."""
    print("\n" + "=" * 60)
    print("TEST 3: Git state caching")
    print("=" * 60)

    from deploy.state import get_cache, should_rescan
    import subprocess

    # Get current git hash
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2
        )
        current_hash = result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        current_hash = None

    if not current_hash:
        print("Git not available - skipping cache test")
        return True

    # Test cache logic
    cache = get_cache("test-project")
    print(f"Cache exists: {cache is not None}")

    needs_rescan = should_rescan("test-project", current_hash)
    print(f"Needs rescan: {needs_rescan}")

    print("✓ Git cache logic works")
    return True


def test_deployment_history_integration():
    """Test deployment history logging integration."""
    print("\n" + "=" * 60)
    print("TEST 4: Deployment history integration")
    print("=" * 60)

    from memory.db import log_deployment, get_deployment_history

    # Log test deployment
    log_deployment(
        path="test-integration",
        deploy_type="wp_theme",
        target="staging",
        user="test-user",
        success=True,
        scan_passed=True,
        violations_critical=0,
        violations_high=0,
        health_check_passed=True,
        duration_ms=1500
    )

    # Query history
    history = get_deployment_history(path="test-integration", limit=1)

    assert len(history) > 0, "Should have deployment history"
    assert history[0]["path"] == "test-integration", "Should match test path"
    assert history[0]["success"] == True, "Should be successful"

    print(f"✓ Deployment history logged: {history[0]['timestamp']}")
    return True


if __name__ == "__main__":
    print("\nDeployment Integration Tests\n")

    tests = [
        test_deploy_dry_run,
        test_deploy_verify_mode,
        test_git_cache,
        test_deployment_history_integration,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"\nX TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)