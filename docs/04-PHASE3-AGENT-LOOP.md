# Phase 3: Agent Loop

## Mục tiêu

Kiwi tự chạy vòng lặp **Observe → Think → Act → Verify → Learn** — không cần user điều khiển từng bước.

## Architecture

```
User: "Fix all CRITICAL in wezone-plugins"
                    │
                    ▼
    ┌───────────────────────────────────┐
    │           AGENT ENTRY             │
    │  CLI: python -m agent --mode auto │
    │  MCP: kiwi_agent(mode, path)      │
    │  Skill: /kiwi-agent               │
    └───────────────┬───────────────────┘
                    │
    ┌───────────────▼───────────────────┐
    │           AGENT LOOP              │
    │                                   │
    │  ┌─────────────────────────────┐  │
    │  │  1. OBSERVE                 │  │
    │  │  kiwi_scan(path, CRITICAL)  │  │
    │  │  → 12 violations            │  │
    │  └──────────────┬──────────────┘  │
    │                 │                 │
    │  ┌──────────────▼──────────────┐  │
    │  │  2. THINK (Claude API)      │  │
    │  │  - Group by file/category   │  │
    │  │  - Prioritize: security >   │  │
    │  │    data integrity > perf    │  │
    │  │  - Plan fix order           │  │
    │  │  - Identify dependencies    │  │
    │  └──────────────┬──────────────┘  │
    │                 │                 │
    │  ┌──────────────▼──────────────┐  │
    │  │  3. ACT                     │  │
    │  │  For each planned fix:      │  │
    │  │  - kiwi_fix(dry_run=True)   │  │
    │  │  - [interactive] ask user   │  │
    │  │  - kiwi_fix(apply=True)     │  │
    │  │  - Record outcome           │  │
    │  └──────────────┬──────────────┘  │
    │                 │                 │
    │  ┌──────────────▼──────────────┐  │
    │  │  4. VERIFY                  │  │
    │  │  kiwi_scan(path, CRITICAL)  │  │
    │  │  - Violations gone?         │  │
    │  │  - New violations intro?    │  │
    │  │  - If regression → rollback │  │
    │  └──────────────┬──────────────┘  │
    │                 │                 │
    │  ┌──────────────▼──────────────┐  │
    │  │  5. LEARN (Phase 4)         │  │
    │  │  - Log scan_history         │  │
    │  │  - Update confidence        │  │
    │  │  - Record fix_outcomes      │  │
    │  └──────────────┬──────────────┘  │
    │                 │                 │
    │    violations remain?             │
    │    YES → loop back to OBSERVE     │
    │    NO  → exit with report         │
    └───────────────────────────────────┘
```

## Module Structure

```
.claude/kiwi/agent/
├── __init__.py          # Package init + version
├── loop.py              # Main agent loop (core)
├── tools.py             # Tool definitions for Claude API
├── prompts.py           # System prompts, few-shot examples
├── state.py             # AgentState management
└── cli.py               # CLI entry point
```

## Core: `loop.py`

```python
"""Kiwi Agent — Autonomous scan-fix-verify loop."""

import json
from anthropic import Anthropic
from .tools import TOOLS, execute_tool
from .prompts import SYSTEM_PROMPT
from .state import AgentState


def run_agent(path: str, mode: str = "review", 
              severity: str = "CRITICAL",
              max_iterations: int = 3,
              max_fixes: int = 10) -> dict:
    """Run Kiwi agent loop.
    
    Args:
        path: Project path to scan
        mode: "review" | "interactive" | "auto"
        severity: Minimum severity to fix
        max_iterations: Max scan→fix→verify cycles
        max_fixes: Max total fixes to apply
    
    Returns:
        Agent report dict
    """
    client = Anthropic()
    state = AgentState(mode=mode, path=path)
    
    messages = [{
        "role": "user",
        "content": _build_initial_prompt(path, mode, severity)
    }]
    
    iteration = 0
    while iteration < max_iterations:
        iteration += 1
        state.scan_count = iteration
        
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        
        # Process response
        if response.stop_reason == "end_turn":
            # Agent decided to stop
            final_text = _extract_text(response)
            state.history.append({"action": "done", "text": final_text})
            break
        
        if response.stop_reason == "tool_use":
            # Execute tool calls
            messages.append({"role": "assistant", "content": response.content})
            
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    # Safety check
                    if state.fixes_applied >= max_fixes:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": "Max fixes reached. Stop fixing."
                        })
                        continue
                    
                    # Interactive mode: ask before applying
                    if (mode == "interactive" 
                        and block.name == "kiwi_fix" 
                        and block.input.get("apply")):
                        # In MCP context, this would prompt user
                        # In CLI context, this would print and ask
                        pass
                    
                    result = execute_tool(block.name, block.input, state)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })
            
            messages.append({"role": "user", "content": tool_results})
    
    return state.to_report()


def _build_initial_prompt(path, mode, severity):
    mode_instructions = {
        "review": "Scan and analyze only. Do NOT fix anything. Report findings with reasoning.",
        "interactive": "Scan, then propose fixes one at a time. Wait for approval before each fix.",
        "auto": "Scan, fix all violations, verify. Report what was fixed."
    }
    return f"""Scan project at: {path}
Severity filter: {severity}
Mode: {mode}

{mode_instructions[mode]}

Start by calling kiwi_scan to see current violations."""
```

## Tools: `tools.py`

```python
"""Tool definitions for Kiwi Agent — wraps scanner, fixer, file ops."""

import json
import os
import subprocess
from pathlib import Path

# Tool definitions for Claude API
TOOLS = [
    {
        "name": "kiwi_scan",
        "description": "Scan project for bug pattern violations",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "severity": {"type": "string", "enum": ["CRITICAL","HIGH","SUGGEST","ALL"]},
                "platform": {"type": "string", "enum": ["wp","nextjs"]},
                "diff_only": {"type": "boolean", "default": False},
            },
            "required": ["path"]
        }
    },
    {
        "name": "kiwi_fix",
        "description": "Get fix suggestion or apply fix for a violation",
        "input_schema": {
            "type": "object",
            "properties": {
                "lesson_id": {"type": "string"},
                "file": {"type": "string"},
                "line": {"type": "integer"},
                "apply": {"type": "boolean", "default": False},
            },
            "required": ["lesson_id"]
        }
    },
    {
        "name": "kiwi_lesson",
        "description": "Read full lesson content (Bad/Good/Why sections)",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string"}
            },
            "required": ["id"]
        }
    },
    {
        "name": "read_file",
        "description": "Read file content with optional line range",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "start_line": {"type": "integer"},
                "end_line": {"type": "integer"},
            },
            "required": ["path"]
        }
    },
    {
        "name": "edit_file",
        "description": "Replace text in a file",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
            },
            "required": ["path", "old_text", "new_text"]
        }
    },
    {
        "name": "git_stash",
        "description": "Git stash (save/pop) for safety backup",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["save", "pop"]},
                "message": {"type": "string"},
            },
            "required": ["action"]
        }
    },
]


def execute_tool(name: str, args: dict, state) -> str:
    """Execute a tool and return result as string."""
    
    if name == "kiwi_scan":
        return _exec_kiwi_scan(args)
    elif name == "kiwi_fix":
        result = _exec_kiwi_fix(args)
        if args.get("apply") and "Applied" in result:
            state.fixes_applied += 1
        return result
    elif name == "kiwi_lesson":
        return _exec_kiwi_lesson(args)
    elif name == "read_file":
        return _exec_read_file(args)
    elif name == "edit_file":
        return _exec_edit_file(args, state)
    elif name == "git_stash":
        return _exec_git_stash(args)
    else:
        return f"Unknown tool: {name}"
```

## System Prompt: `prompts.py`

```python
SYSTEM_PROMPT = """You are Kiwi Agent — an autonomous code quality agent for Wezone projects.

You have access to Kiwi's knowledge base of 427+ bug patterns across WordPress themes/plugins 
and Next.js applications.

## Your capabilities:
- kiwi_scan: Scan projects for violations
- kiwi_fix: Get fix suggestions or apply auto-fixes
- kiwi_lesson: Read full lesson details
- read_file: Read source code
- edit_file: Make code changes
- git_stash: Backup changes before fixing

## Your workflow:
1. OBSERVE: Scan the project to find violations
2. THINK: Analyze violations, group by file, prioritize (security > data > perf)
3. ACT: Fix violations using kiwi_fix or edit_file
4. VERIFY: Re-scan to confirm fixes and check for regressions

## Rules:
- ALWAYS scan before fixing (understand the problem first)
- ALWAYS verify after fixing (re-scan to confirm)
- NEVER fix more than 10 violations without re-scanning
- PREFER kiwi_fix over edit_file (kiwi_fix uses tested patterns)
- If kiwi_fix fails, read_file + edit_file as fallback
- If unsure about a fix, read the lesson first with kiwi_lesson
- Group related violations (same file, same pattern) and fix together
- Report clearly: what was found, what was fixed, what remains

## Priority order:
1. CRITICAL security (IDOR, XSS, SQL injection, CSRF)
2. CRITICAL data integrity (missing guards, wrong function calls)
3. HIGH code quality (hardcoded values, missing patterns)
4. SUGGEST improvements (optional, only if time permits)

## Safety:
- Before batch fixes, use git_stash to save current state
- If a fix introduces new violations, rollback and report
- Never modify _meta.json, README.md, or lesson files directly
"""
```

## Agent Modes

### 1. Review Mode
```
Input:  "Scan wezone-plugins, report findings"
Output: Structured analysis with:
        - Violation count by severity
        - Top issues grouped by category
        - Risk assessment
        - Recommended fix priority
Action: NONE — read-only
```

### 2. Interactive Mode
```
Input:  "Fix CRITICAL violations in wezone-plugins"
Output: For each violation:
        1. Show violation details
        2. Show proposed fix (diff)
        3. Ask: "Apply this fix? [y/n/skip]"
        4. Apply or skip
        5. Show progress
Action: Fix only after user approval
```

### 3. Auto Mode
```
Input:  "Fix all CRITICAL in wezone-plugins automatically"
Output: 1. git stash save "kiwi-agent-backup"
        2. Scan → find 12 CRITICAL
        3. Fix all 12 (kiwi_fix or edit_file)
        4. Re-scan → verify 0 CRITICAL remain
        5. Check no new violations
        6. Report: "12 fixed, 0 regressions"
Action: Fix all, verify, report
```

## CLI Entry Point: `cli.py`

```python
"""Kiwi Agent CLI."""

import argparse
import json
import sys

from .loop import run_agent


def main():
    parser = argparse.ArgumentParser(description="Kiwi Agent — autonomous code quality")
    parser.add_argument("path", help="Project path or name")
    parser.add_argument("--mode", choices=["review", "interactive", "auto"], 
                       default="review")
    parser.add_argument("--severity", choices=["CRITICAL", "HIGH", "ALL"],
                       default="CRITICAL")
    parser.add_argument("--max-iterations", type=int, default=3)
    parser.add_argument("--max-fixes", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    
    args = parser.parse_args()
    
    report = run_agent(
        path=args.path,
        mode=args.mode,
        severity=args.severity,
        max_iterations=args.max_iterations,
        max_fixes=args.max_fixes,
    )
    
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_report(report)


if __name__ == "__main__":
    main()
```

## MCP Tool: `kiwi_agent`

Thêm MCP tool để Claude Code có thể trigger agent:

```json
{
  "name": "kiwi_agent",
  "description": "Run Kiwi Agent loop: scan → analyze → fix → verify. Modes: review (read-only), interactive (ask before fix), auto (fix all).",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": {"type": "string"},
      "mode": {"type": "string", "enum": ["review", "interactive", "auto"]},
      "severity": {"type": "string", "enum": ["CRITICAL", "HIGH", "ALL"]},
      "max_fixes": {"type": "integer", "default": 10}
    },
    "required": ["path"]
  }
}
```

## Safety Mechanisms

| Mechanism | Description |
|-----------|-------------|
| **Git stash** | Auto-stash trước batch fix, pop nếu rollback |
| **Max fixes** | Default 10 — prevent runaway |
| **Max iterations** | Default 3 scan-fix-verify cycles |
| **Regression check** | Re-scan after fix → if new violations, rollback |
| **Dry-run default** | kiwi_fix dry_run=True by default |
| **File backup** | Copy file before edit, restore on failure |
| **Scope limit** | Only fix files in scanned project, not outside |

## Verification

1. **Review mode:**
   ```powershell
   cd .claude/kiwi
   python -m agent.cli D:\projects\wezone\wezone-plugins --mode review --severity CRITICAL
   ```
   Expected: Analysis report, no files changed

2. **Interactive mode:**
   ```powershell
   python -m agent.cli D:\projects\wezone\wezone-plugins --mode interactive --severity CRITICAL
   ```
   Expected: Prompts for each fix, applies only on confirmation

3. **Auto mode (on test project):**
   ```powershell
   python -m agent.cli D:\projects\wezone\themes\test-theme --mode auto --max-fixes 3
   ```
   Expected: Fixes applied, re-scan passes, report generated

4. **Regression test:**
   - Intentionally break a fix in fixer.py (wrong replacement)
   - Run auto mode → agent should detect new violation → rollback → report failure