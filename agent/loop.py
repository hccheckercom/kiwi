"""Kiwi Agent — Autonomous scan-fix-verify loop."""

import json
import os
import re
import sys

from .tools import execute_tool
from .prompts import SYSTEM_PROMPT, MODE_INSTRUCTIONS
from .state import AgentState
from .retry import RetryConfig, retry_with_backoff, is_retryable_api_error
from .cost import CostTracker, TokenUsage


def run_multi_agent(
    path: str,
    mode: str = "review",
    agent_types: list = None,
    severity: str = "CRITICAL",
    max_fixes: int = 10,
    verbose: bool = False,
) -> dict:
    """Multi-agent mode — spawn specialized agents and aggregate results."""
    from .orchestrator import run_multi_agent as orchestrator_run

    if verbose:
        print(f"[kiwi-multi] path={path} mode={mode} agents={agent_types}", file=sys.stderr)

    result = orchestrator_run(path=path, mode=mode, agent_types=agent_types)

    # Trigger learning if enough violations found
    violations_count = result.get("violations_found", 0)
    _trigger_learning(path, violations_count, verbose)

    # Add planning if enabled
    if verbose:
        print(f"[kiwi-multi] Planning integration available but not yet implemented", file=sys.stderr)

    return result


def run_lite(
    path: str,
    severity: str = "CRITICAL",
    max_fixes: int = 10,
    dry_run: bool = True,
    verbose: bool = False,
    use_planner: bool = True,
) -> dict:
    """Lite mode — scan + auto-fix without Claude API. Zero token cost."""
    state = AgentState(mode="lite", path=os.path.abspath(path))

    if verbose:
        print(f"[kiwi-lite] path={path} severity={severity} dry_run={dry_run} planner={use_planner}", file=sys.stderr)

    scan_result = execute_tool("kiwi_scan", {"path": path, "severity": severity}, state)

    if verbose:
        for line in scan_result.split("\n")[:6]:
            print(f"[kiwi-lite] {line}", file=sys.stderr)

    if state.violations_found == 0:
        state.log("done", "No violations found")
        report = state.to_report()
        report["final_message"] = "No violations found."
        return report

    from .tools import _ensure_scanner, _load_lesson, KIWI_DIR
    _ensure_scanner()
    from scanner.fixer import apply_fix
    from scanner.models import Violation

    violations = _parse_violations(scan_result, base_path=state.path)

    # NEW: Use HTN Planner to optimize fix order
    if use_planner and len(violations) > 1:
        if verbose:
            print(f"[kiwi-lite] Planning fix order for {len(violations)} violations...", file=sys.stderr)

        violations = _plan_fixes(violations, path, max_fixes, verbose)

    if verbose:
        print(f"[kiwi-lite] {len(violations)} fixable violations parsed", file=sys.stderr)

    # NEW: Use parallel executor if planner was used
    if use_planner and len(violations) > 1:
        fixed, failed = _execute_fixes_parallel(violations, dry_run, verbose, state)
    else:
        # Original sequential execution
        fixed, failed = _execute_fixes_sequential(violations, max_fixes, dry_run, verbose, state)

    state.violations_remaining = state.violations_found - state.fixes_applied

    lines = [f"Kiwi Lite {'Preview' if dry_run else 'Auto-Fix'} Report"]
    lines.append(f"Violations: {state.violations_found} found")
    lines.append(f"{'Previewed' if dry_run else 'Fixed'}: {len(fixed)}")
    if failed:
        lines.append(f"Failed: {len(failed)}")
    lines.append(f"Remaining: {state.violations_remaining}")
    lines.append("")

    if fixed:
        lines.append("Fixes:")
        for f in fixed:
            lines.append(f"  [{f['action']}] {f['lesson_id']} — {f['file']}:{f['line']}")
    if failed:
        lines.append("Failed:")
        for f in failed:
            lines.append(f"  {f['lesson_id']} — {f['error']}")

    final = "\n".join(lines)
    state.log("done", final[:200])
    report = state.to_report()
    report["final_message"] = final
    report["fixed"] = fixed
    report["failed"] = failed

    # Trigger learning if enough violations found
    _trigger_learning(path, state.violations_found, verbose)

    return report


def _parse_violations(scan_output: str, base_path: str = "") -> list:
    """Parse violations from scan output text into structured list."""
    violations = []
    current_lesson = None

    for line in scan_output.split("\n"):
        stripped = line.strip()

        m = re.match(r"(LES-\d+|FEA-\d+)\s", stripped)
        if m:
            current_lesson = m.group(1)
            continue

        if current_lesson:
            m2 = re.match(r"(?:→\s+)?(.+?):(\d+)\s", stripped)
            if m2:
                filepath = m2.group(1).strip()
                lineno = int(m2.group(2))
                if not os.path.isabs(filepath) and base_path:
                    filepath = os.path.join(base_path, filepath)
                violations.append({"lesson_id": current_lesson, "file": filepath, "line": lineno})

    seen = set()
    unique = []
    for v in violations:
        key = (v["lesson_id"], v["file"], v["line"])
        if key not in seen:
            seen.add(key)
            unique.append(v)

    return unique


def run_agent(
    path: str,
    mode: str = "review",
    severity: str = "CRITICAL",
    max_iterations: int = 3,
    max_fixes: int = 10,
    model: str = None,
    verbose: bool = False,
) -> dict:
    from anthropic import Anthropic
    from .tools import TOOLS

    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    base_url = os.environ.get("ANTHROPIC_BASE_URL")

    client = Anthropic(
        api_key=api_key,
        **({"base_url": base_url} if base_url else {}),
    )

    if model is None:
        model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    state = AgentState(mode=mode, path=os.path.abspath(path))

    # Initialize cost tracker
    cost_tracker = CostTracker(model)

    user_prompt = (
        f"Scan project at: {path}\n"
        f"Severity filter: {severity}\n"
        f"Mode: {mode}\n\n"
        f"{MODE_INSTRUCTIONS[mode]}\n\n"
        f"Start by calling kiwi_scan."
    )

    messages = [{"role": "user", "content": user_prompt}]

    if verbose:
        print(f"[kiwi-agent] mode={mode} path={path} severity={severity}", file=sys.stderr)
        print(f"[kiwi-agent] model={model}", file=sys.stderr)

    # Retry configuration for API calls
    retry_config = RetryConfig(
        max_retries=3,
        initial_delay=1.0,
        max_delay=60.0,
        exponential_base=2.0,
        jitter=True,
    )

    iteration = 0
    while iteration < max_iterations * 5:
        iteration += 1

        def make_api_call():
            return client.messages.create(
                model=model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

        def on_retry_error(error: Exception, attempt: int):
            state.log("api_retry", f"Attempt {attempt + 1}: {error}")
            if verbose:
                print(f"[kiwi-agent] API error (attempt {attempt + 1}): {error}", file=sys.stderr)
                print(f"[kiwi-agent] Retrying with exponential backoff...", file=sys.stderr)

        try:
            # Retry API call with exponential backoff
            response = retry_with_backoff(
                func=make_api_call,
                config=retry_config,
                error_callback=on_retry_error,
                retryable_exceptions=(Exception,),
                non_retryable_exceptions=(),
            )

            # Track token usage
            if hasattr(response, 'usage'):
                usage = TokenUsage(
                    input_tokens=getattr(response.usage, 'input_tokens', 0),
                    output_tokens=getattr(response.usage, 'output_tokens', 0),
                    cache_creation_tokens=getattr(response.usage, 'cache_creation_input_tokens', 0),
                    cache_read_tokens=getattr(response.usage, 'cache_read_input_tokens', 0),
                )
                cost_tracker.add_usage(usage)
        except Exception as e:
            # All retries exhausted
            state.log("api_error", str(e))
            if verbose:
                print(f"[kiwi-agent] API error after {retry_config.max_retries + 1} attempts: {e}", file=sys.stderr)

            # Check if error is retryable - if not, break immediately
            if not is_retryable_api_error(e):
                if verbose:
                    print(f"[kiwi-agent] Non-retryable error detected. Stopping agent.", file=sys.stderr)
                break

            # For retryable errors, continue to next iteration
            if verbose:
                print(f"[kiwi-agent] Continuing to next iteration...", file=sys.stderr)
            continue

        if response.stop_reason == "end_turn":
            final_text = _extract_text(response)
            state.log("done", final_text[:200])
            if verbose:
                print(f"[kiwi-agent] Agent finished.", file=sys.stderr)

            # Trigger learning if enough violations found
            _trigger_learning(path, state.violations_found, verbose)

            # Add cost summary to report
            cost_summary = cost_tracker.get_summary()
            report = state.to_report()
            report["final_message"] = final_text
            report["cost"] = {
                "total_tokens": cost_summary.total_tokens,
                "total_cost_usd": cost_summary.total_cost_usd,
                "api_calls": cost_summary.api_calls,
                "duration_seconds": cost_summary.duration_seconds,
            }

            if verbose:
                print(f"\n{cost_tracker.format_summary()}", file=sys.stderr)

            return report

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                if state.fixes_applied >= max_fixes and block.name in ("kiwi_fix", "edit_file"):
                    if block.name == "kiwi_fix" and block.input.get("apply"):
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"Max fixes ({max_fixes}) reached. Stop fixing and report results.",
                        })
                        continue
                    if block.name == "edit_file":
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"Max fixes ({max_fixes}) reached. Stop fixing and report results.",
                        })
                        continue

                if verbose:
                    args_str = json.dumps(block.input, ensure_ascii=False)[:120]
                    print(f"[kiwi-agent] tool: {block.name}({args_str})", file=sys.stderr)

                result = execute_tool(block.name, block.input, state)

                if verbose and block.name == "kiwi_scan":
                    for line in result.split("\n")[:5]:
                        print(f"[kiwi-agent]   {line}", file=sys.stderr)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

            messages.append({"role": "user", "content": tool_results})
        else:
            state.log("unexpected_stop", response.stop_reason)
            break

    state.log("max_iterations", f"Reached iteration limit ({iteration})")
    report = state.to_report()
    report["final_message"] = "Agent stopped: iteration limit reached."
    return report


def _extract_text(response) -> str:
    parts = []
    for block in response.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "\n".join(parts)


def _plan_fixes(violations: list[dict], path: str, max_fixes: int, verbose: bool) -> list[dict]:
    """
    Use HTN Planner to optimize fix order.

    Args:
        violations: List of violation dicts
        path: Project path
        max_fixes: Max fixes to plan
        verbose: Print debug info

    Returns:
        Reordered list of violations (optimized by dependencies + risk)
    """
    try:
        import sys
        from pathlib import Path

        # Add planner to path
        kiwi_dir = Path(__file__).parent.parent
        sys.path.insert(0, str(kiwi_dir))

        from planner.htn import TaskPlanner

        planner = TaskPlanner(path)
        plan = planner.plan(violations, max_fixes=max_fixes)

        if verbose:
            print(f"[kiwi-planner] Generated plan: {len(plan.tasks)} tasks, {plan.estimated_duration_minutes} min", file=sys.stderr)
            print(f"[kiwi-planner] Parallel groups: {len(plan.parallel_groups)}", file=sys.stderr)
            for i, group in enumerate(plan.parallel_groups, 1):
                print(f"[kiwi-planner]   Group {i}: {len(group)} task(s)", file=sys.stderr)

        # Convert plan back to violations list (in optimized order)
        task_map = {v["task_id"]: v for v in violations}
        ordered_violations = [task_map[task.task_id] for task in plan.tasks]

        return ordered_violations

    except Exception as e:
        if verbose:
            print(f"[kiwi-planner] Planning failed: {e}, falling back to original order", file=sys.stderr)
        return violations[:max_fixes]


def _execute_fixes_parallel(violations: list[dict], dry_run: bool, verbose: bool, state) -> tuple[list, list]:
    """Execute fixes in parallel using HTN Planner."""
    try:
        import sys
        from pathlib import Path

        kiwi_dir = Path(__file__).parent.parent
        sys.path.insert(0, str(kiwi_dir))

        from planner.htn import TaskPlanner, Task
        from executor.htn_executor import ParallelFixExecutor

        # Build plan
        planner = TaskPlanner(state.path)
        plan = planner.plan(violations, max_fixes=len(violations))

        # Execute plan
        executor = ParallelFixExecutor(max_workers=3)
        results = executor.execute_plan(plan, dry_run=dry_run, verbose=verbose)

        # Convert results to fixed/failed lists
        fixed = []
        failed = []

        for result in results["results"]:
            if result.success:
                fixed.append({
                    "lesson_id": result.lesson_id,
                    "file": result.file,
                    "line": result.line,
                    "action": "preview" if dry_run else "applied",
                })
                if not dry_run:
                    state.fixes_applied += 1
            else:
                failed.append({
                    "lesson_id": result.lesson_id,
                    "file": result.file,
                    "error": result.error,
                })
                state.fixes_failed += 1

        return fixed, failed

    except Exception as e:
        if verbose:
            print(f"[kiwi-parallel] Parallel execution failed: {e}, falling back to sequential", file=sys.stderr)
        return _execute_fixes_sequential(violations, len(violations), dry_run, verbose, state)


def _execute_fixes_sequential(violations: list[dict], max_fixes: int, dry_run: bool, verbose: bool, state) -> tuple[list, list]:
    """Execute fixes sequentially (original implementation)."""
    from .tools import _load_lesson
    from scanner.fixer import apply_fix
    from scanner.models import Violation

    fixed = []
    failed = []

    for v in violations:
        if state.fixes_applied >= max_fixes:
            break

        fm, _ = _load_lesson(v["lesson_id"])
        if not fm or not fm.get("fix"):
            continue

        fix_config = fm["fix"]
        violation = Violation(
            lesson_id=v["lesson_id"],
            severity=fm.get("severity", "HIGH"),
            category=fm.get("category", ""),
            description=fm.get("title", ""),
            file=v["file"],
            line=v["line"],
        )

        result = apply_fix(violation, fix_config, dry_run=dry_run)

        if result.success:
            action = "preview" if dry_run else "applied"
            fixed.append({"lesson_id": v["lesson_id"], "file": v["file"], "line": v["line"], "action": action})
            if not dry_run:
                state.fixes_applied += 1
                try:
                    from memory.confidence import record_fix_outcome
                    record_fix_outcome(v["lesson_id"], success=True, file=v["file"], line=v["line"])
                except (ImportError, Exception):
                    pass
            state.log("fix" if not dry_run else "preview", f"{v['lesson_id']} {v['file']}:{v['line']}")

            if verbose:
                print(f"[kiwi-lite] {action}: {v['lesson_id']} {v['file']}:{v['line']}", file=sys.stderr)
        else:
            failed.append({"lesson_id": v["lesson_id"], "file": v["file"], "error": result.error})
            state.fixes_failed += 1
            if not dry_run:
                try:
                    from memory.confidence import record_fix_outcome
                    record_fix_outcome(v["lesson_id"], success=False, file=v["file"], line=v["line"])
                except (ImportError, Exception):
                    pass

    return fixed, failed


def _trigger_learning(path: str, violations_count: int, verbose: bool = False) -> None:
    """Trigger pattern learning after scan if enough violations found.

    Args:
        path: Project path
        violations_count: Number of violations found in scan
        verbose: Print debug info
    """
    if violations_count < 5:
        return

    if verbose:
        print(f"[kiwi-learning] Triggering pattern mining ({violations_count} violations)", file=sys.stderr)

    try:
        from learning.miner import mine_patterns_from_history

        suggestions = mine_patterns_from_history(
            project_path=path,
            lookback_days=30,
            min_occurrences=3
        )

        if verbose:
            print(f"[kiwi-learning] Mined {len(suggestions)} pattern suggestions", file=sys.stderr)

    except Exception as e:
        if verbose:
            print(f"[kiwi-learning] Mining failed: {e}", file=sys.stderr)