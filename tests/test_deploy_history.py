"""Test deployment history tracking."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.db import log_deployment, get_deployment_history

# Log test deployment
log_deployment(
    path='test-project',
    deploy_type='wp_theme',
    target='staging',
    user='test-user',
    success=True,
    rollback=False,
    scan_passed=True,
    violations_critical=0,
    violations_high=0,
    health_check_passed=True,
    error_message=None,
    duration_ms=1500
)

# Query history
history = get_deployment_history(limit=5)

print(f"Logged deployment. History count: {len(history)}")
if history:
    latest = history[0]
    status = "SUCCESS" if latest["success"] else "FAILED"
    print(f"Latest: {latest['path']} -> {latest['target']} ({status})")
    print(f"  Scan: {'PASS' if latest['scan_passed'] else 'FAIL'}")
    print(f"  Health: {'PASS' if latest['health_check_passed'] else 'FAIL'}")
    print(f"  Duration: {latest['duration_ms']}ms")