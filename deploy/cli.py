"""CLI wrapper for kiwi_deploy with realtime logging."""
import sys
import argparse
from pathlib import Path

# Add kiwi to path
KIWI_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(KIWI_DIR))

from deploy.executor import DeployExecutor
from deploy.state import get_cache, should_rescan, log_deploy


def main():
    parser = argparse.ArgumentParser(description="Kiwi Deploy CLI with realtime logging")
    parser.add_argument("path", help="Project path or name")
    parser.add_argument("type", choices=["wp_theme", "wp_plugin", "nextjs", "demo_html"], help="Deploy type")
    parser.add_argument("--target", default="staging", choices=["staging", "production"], help="Deploy target")
    parser.add_argument("--mode", default="verify", choices=["dry-run", "verify", "execute"], help="Deploy mode")
    parser.add_argument("--skip-scan", action="store_true", help="Skip Kiwi scan (use cache)")
    parser.add_argument("--skip-git-check", action="store_true", help="Skip git clean check")
    parser.add_argument("--no-rollback", action="store_true", help="Disable auto-rollback on failure")
    parser.add_argument("--remote-path", help="Remote path for demo_html deployment")

    args = parser.parse_args()

    # Resolve path
    path = Path(args.path)
    if not path.is_absolute():
        # Try common locations
        candidates = [
            Path.cwd() / args.path,
            Path("d:/projects/wezone") / args.path,
            Path("d:/projects/wezone/themes") / args.path,
            Path("d:/projects/wezone/wezone-plugins") / args.path,
        ]
        for candidate in candidates:
            if candidate.exists():
                path = candidate
                break

    if not path.exists():
        print(f"ERROR: Path not found: {path}", file=sys.stderr)
        sys.exit(1)

    path = str(path.resolve())

    # Create executor
    executor = DeployExecutor(path, args.type, args.target)
    if args.remote_path:
        executor.remote_path = args.remote_path

    # Step 1: Check git status
    print(f"Deploy: {path} ({args.type} → {args.target})", file=sys.stderr)
    git_commit = executor.get_git_commit()
    print(f"Git commit: {git_commit[:7]}", file=sys.stderr)

    if not args.skip_git_check:
        git_clean = executor.check_git_clean()
        if not git_clean and args.mode == "execute":
            print("ERROR: Uncommitted changes detected. Commit or stash before deploying.", file=sys.stderr)
            sys.exit(1)

    # Step 2: Kiwi scan
    if args.type == "demo_html":
        print("Skipping Kiwi scan (demo_html type — no code to scan)", file=sys.stderr)
    else:
        cache = get_cache(path)
        if args.skip_scan and cache and cache["last_git_commit"] == git_commit:
            scan_result = cache.get("last_scan_result", {})
            print(f"Using cached scan result (commit {git_commit[:7]})", file=sys.stderr)
        else:
            if should_rescan(path, git_commit):
                print("Running Kiwi scan...", file=sys.stderr)
                scan_result = executor.run_kiwi_scan(severity="CRITICAL")
                print(f"Kiwi scan: {scan_result.get('critical', 0)} CRITICAL, {scan_result.get('high', 0)} HIGH", file=sys.stderr)
                if scan_result.get("critical", 0) > 0 and args.mode == "execute":
                    print(f"\nBLOCKED: {scan_result['critical']} CRITICAL violations. Fix before deploying.", file=sys.stderr)
                    sys.exit(1)
            else:
                print("Code unchanged since last deploy — skipping scan", file=sys.stderr)

    # Step 3: Build plan
    print("\nBuilding deploy plan...", file=sys.stderr)
    plan = executor.build_plan()
    if "error" in plan:
        print(f"ERROR: {plan['error']}", file=sys.stderr)
        sys.exit(1)

    print(f"\nDeploy plan ({args.mode}):", file=sys.stderr)
    for step in plan["steps"]:
        cmd_preview = step["command"][:80] + ("..." if len(step["command"]) > 80 else "")
        print(f"  {step['name']}: {cmd_preview}", file=sys.stderr)

    if args.mode == "dry-run":
        print("\nDry-run complete. Use --mode=execute to deploy.", file=sys.stderr)
        sys.exit(0)

    if args.mode == "verify":
        print("\nVerify complete. Use --mode=execute to deploy.", file=sys.stderr)
        sys.exit(0)

    # Step 4: Execute
    print("\nExecuting deployment...", file=sys.stderr)
    import time
    start_time = time.time()
    result = executor.execute(plan)
    duration_ms = int((time.time() - start_time) * 1000)

    if result["success"]:
        backup_path = result.get("backup_path")
        log_deploy(path, args.type, args.target, git_commit, True, duration_ms, backup_path=backup_path)
        print(f"\n✅ Deploy successful ({duration_ms}ms)", file=sys.stderr)
        health = result.get("health_status", {})
        if health.get("checks"):
            passed = sum(1 for c in health["checks"] if c["healthy"])
            print(f"Health checks: {passed}/{len(health['checks'])} passed", file=sys.stderr)
        sys.exit(0)
    else:
        error_pattern = result.get("error_pattern")
        backup_path = result.get("backup_path")
        log_deploy(path, args.type, args.target, git_commit, False, duration_ms, error_pattern, backup_path=backup_path)
        print(f"\n❌ Deploy failed: {result.get('error', 'Unknown error')}", file=sys.stderr)
        if result.get("fix_suggestion"):
            print(f"\nSuggested fix:\n{result['fix_suggestion']}", file=sys.stderr)

        if not args.no_rollback and backup_path:
            print("\nRolling back...", file=sys.stderr)
            rollback_result = executor.rollback(backup_path)
            if rollback_result.get("status") == "success":
                print(f"✅ Rollback successful", file=sys.stderr)
                log_deploy(path, args.type, args.target, git_commit, True, 0, rollback=True, backup_path=backup_path)
            else:
                print(f"❌ Rollback failed: {rollback_result.get('error', 'Unknown error')}", file=sys.stderr)

        sys.exit(1)


if __name__ == "__main__":
    main()
