"""Multi-agent orchestration engine."""

import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import sys
from pathlib import Path

# Add parent to path for imports
KIWI_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(KIWI_DIR))

from memory import coordination as coord
from agent.state import AgentState


@dataclass
class AgentSpec:
    """Specification for a specialized agent."""
    agent_type: str
    description: str
    focus_categories: list[str]
    severity_filter: str = "ALL"
    max_fixes: int = 5


AGENT_REGISTRY = {
    "security": AgentSpec(
        agent_type="security",
        description="Security specialist focusing on IDOR, XSS, SQL injection, CSRF",
        focus_categories=["php-security", "api-security", "auth-security"],
        severity_filter="CRITICAL",
        max_fixes=10
    ),
    "performance": AgentSpec(
        agent_type="performance",
        description="Performance specialist focusing on caching, queries, N+1",
        focus_categories=["performance", "db-schema"],
        severity_filter="HIGH",
        max_fixes=5
    ),
    "architecture": AgentSpec(
        agent_type="architecture",
        description="Architecture specialist focusing on design patterns, structure",
        focus_categories=["code-quality", "maintainability"],
        severity_filter="HIGH",
        max_fixes=3
    ),
    "compliance": AgentSpec(
        agent_type="compliance",
        description="Compliance specialist focusing on GDPR, accessibility, SEO",
        focus_categories=["ads-compliance", "css-tokens", "seo"],
        severity_filter="HIGH",
        max_fixes=5
    ),
}


@dataclass
class AgentTask:
    """Task assigned to an agent."""
    agent_type: str
    path: str
    mode: str
    severity: str
    max_fixes: int
    run_id: Optional[int] = None
    status: str = "pending"
    result: Optional[dict] = None


class AgentOrchestrator:
    """Orchestrates multiple specialized agents."""

    def __init__(self, path: str, mode: str = "review"):
        self.path = path
        self.mode = mode
        self.parent_run_id = coord.create_agent_run(path, mode, agent_type="orchestrator")
        self.tasks: list[AgentTask] = []

    def spawn_agents(self, agent_types: list[str]) -> list[AgentTask]:
        """Spawn multiple specialized agents."""
        tasks = []

        for agent_type in agent_types:
            if agent_type not in AGENT_REGISTRY:
                print(f"Warning: Unknown agent type '{agent_type}', skipping", file=sys.stderr)
                continue

            spec = AGENT_REGISTRY[agent_type]
            run_id = coord.create_agent_run(
                path=self.path,
                mode=self.mode,
                agent_type=spec.agent_type,
                parent_run_id=self.parent_run_id
            )

            task = AgentTask(
                agent_type=spec.agent_type,
                path=self.path,
                mode=self.mode,
                severity=spec.severity_filter,
                max_fixes=spec.max_fixes,
                run_id=run_id
            )

            self.tasks.append(task)
            tasks.append(task)

        return tasks

    def run_agent_subprocess(self, task: AgentTask) -> dict:
        """Run agent in subprocess (lite mode for now)."""
        kiwi_dir = Path(__file__).parent.parent
        cmd = [
            sys.executable,
            "-m", "agent.cli",
            task.path,
            "--lite",
            "--severity", task.severity,
            "--max-fixes", str(task.max_fixes),
            "--json"
        ]

        if task.mode == "auto":
            cmd.append("--apply")

        try:
            result = subprocess.run(
                cmd,
                cwd=str(kiwi_dir),
                capture_output=True,
                text=True,
                timeout=300,
                encoding="utf-8",
                errors="replace"
            )

            if result.returncode == 0 and result.stdout:
                return json.loads(result.stdout)
            else:
                return {
                    "error": f"Agent failed with code {result.returncode}",
                    "stderr": result.stderr[:500]
                }

        except subprocess.TimeoutExpired:
            return {"error": "Agent timeout after 300s"}
        except Exception as e:
            return {"error": str(e)}

    def run_parallel(self, tasks: list[AgentTask]) -> list[dict]:
        """Run multiple agents in parallel (sequential for now, parallel later)."""
        results = []

        for task in tasks:
            print(f"[orchestrator] Running {task.agent_type} agent...", file=sys.stderr)
            coord.update_agent_run(task.run_id, status="running")

            result = self.run_agent_subprocess(task)
            task.result = result
            task.status = "completed" if "error" not in result else "failed"

            coord.update_agent_run(
                task.run_id,
                status=task.status,
                checkpoint_data={"result_summary": self._summarize_result(result)}
            )

            results.append(result)

        return results

    def _summarize_result(self, result: dict) -> dict:
        """Summarize agent result for checkpoint data."""
        if "error" in result:
            return {"error": result["error"]}

        return {
            "violations_found": result.get("violations_found", 0),
            "fixes_applied": result.get("fixes_applied", 0),
            "fixes_failed": result.get("fixes_failed", 0),
        }

    def collect_verdicts(self, tasks: list[AgentTask]) -> dict:
        """Collect verdicts from all agents and build consensus."""
        all_violations = {}

        for task in tasks:
            if not task.result or "error" in task.result:
                continue

            fixed = task.result.get("fixed", [])
            for fix in fixed:
                key = (fix["lesson_id"], fix["file"], fix.get("line", 0))

                if key not in all_violations:
                    all_violations[key] = []

                coord.record_verdict(
                    run_id=task.run_id,
                    agent_type=task.agent_type,
                    lesson_id=fix["lesson_id"],
                    file=fix["file"],
                    line=fix.get("line", 0),
                    verdict="violation",
                    confidence=1.0,
                    reasoning=f"Fixed by {task.agent_type} agent"
                )

                all_violations[key].append({
                    "agent_type": task.agent_type,
                    "verdict": "violation",
                    "action": fix.get("action", "unknown")
                })

        consensus_results = {}
        for (lesson_id, file, line), verdicts in all_violations.items():
            consensus = coord.calculate_consensus(lesson_id, file, line)
            consensus_results[(lesson_id, file, line)] = consensus

        return consensus_results

    def aggregate_results(self, tasks: list[AgentTask]) -> dict:
        """Aggregate results from all agents."""
        total_violations = 0
        total_fixes = 0
        total_failed = 0
        agent_summaries = []

        for task in tasks:
            if not task.result:
                continue

            summary = {
                "agent_type": task.agent_type,
                "status": task.status,
            }

            if "error" in task.result:
                summary["error"] = task.result["error"]
            else:
                summary["violations_found"] = task.result.get("violations_found", 0)
                summary["fixes_applied"] = task.result.get("fixes_applied", 0)
                summary["fixes_failed"] = task.result.get("fixes_failed", 0)

                total_violations += summary["violations_found"]
                total_fixes += summary["fixes_applied"]
                total_failed += summary["fixes_failed"]

            agent_summaries.append(summary)

        consensus = self.collect_verdicts(tasks)

        return {
            "orchestrator_run_id": self.parent_run_id,
            "total_violations": total_violations,
            "total_fixes": total_fixes,
            "total_failed": total_failed,
            "consensus_count": len(consensus),
            "needs_human_review": sum(1 for c in consensus.values() if c.get("needs_human")),
            "agents": agent_summaries,
        }

    def run(self, agent_types: list[str]) -> dict:
        """Main orchestration flow."""
        coord.update_agent_run(self.parent_run_id, status="running")

        tasks = self.spawn_agents(agent_types)
        print(f"[orchestrator] Spawned {len(tasks)} agents: {[t.agent_type for t in tasks]}", file=sys.stderr)

        self.run_parallel(tasks)

        result = self.aggregate_results(tasks)

        coord.update_agent_run(
            self.parent_run_id,
            status="completed",
            checkpoint_data={"summary": result}
        )

        return result


def run_multi_agent(path: str, mode: str = "review", agent_types: list[str] = None) -> dict:
    """Run multi-agent orchestration."""
    if agent_types is None:
        agent_types = ["security", "performance", "architecture", "compliance"]

    orchestrator = AgentOrchestrator(path, mode)
    return orchestrator.run(agent_types)
