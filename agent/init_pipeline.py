"""kiwi init — one-shot project onboarding pipeline (Fix 5).

Bundles the six warm-up steps a project needs before kiwi_context can rank by
project-specific signal instead of bare severity:

  1. detect_stack       → capability profile + requires/conflicts lesson filter
  2. learn_from_folder  → mine project-specific lesson candidates (no auto-create)
  3. review suggestions → surface pending candidates for human approval (lọc rác)
  4. seed scan          → persist one scan so db_scores / history warm up
  5. learn_session      → fold session logs into learned_conventions
  6. anchor + hook      → make agents call kiwi_context first (Fix 7)

Idempotent: step 2 only suggests (never auto-creates), the anchor block is
replaced in place, the PreToolUse hook is skipped when already registered, and
learn_session marks sessions processed so a re-run is a no-op. Each step is
isolated in its own try/except — one failure is recorded and the pipeline
continues, so a missing optional dependency never aborts onboarding.

The hook is written to <project>/.claude/settings.json ONLY — never
settings.local.json (cost-optimised, off-limits per project policy).
"""

import json
import os
import sys
import time
from pathlib import Path

KIWI_DIR = Path(__file__).resolve().parent.parent


def _step(name, status, detail=""):
    return {"step": name, "status": status, "detail": detail}


def _detect_stack_step(project_path, report, log):
    try:
        sys.path.insert(0, str(KIWI_DIR))
        from scanner.project_profile import detect_stack

        caps = sorted(detect_stack(project_path))
        log(f"1/6 detect_stack → {caps or 'no recognised stack'}")
        report["caps"] = caps
        return _step("detect_stack", "ok",
                     f"caps: {', '.join(caps) if caps else '(none)'}")
    except Exception as e:  # noqa: BLE001 — pipeline must survive any step
        return _step("detect_stack", "failed", str(e))


def _learn_folder_step(project_path, report, log):
    try:
        sys.path.insert(0, str(KIWI_DIR))
        from agent.learn import learn_from_folder

        # auto_approve=False — we only MINE candidates here. Auto-creating
        # lessons unattended pollutes the knowledge base; humans gate them
        # in step 3. This is also what keeps the pipeline idempotent.
        result = learn_from_folder(project_path, min_occurrences=3,
                                   auto_approve=False)
        if "error" in result:
            return _step("learn_from_folder", "failed", result["error"])
        n = len(result.get("suggestions", []))
        report["mined_candidates"] = n
        log(f"2/6 learn_from_folder → {result.get('scanned_files', 0)} files, "
            f"{n} candidate(s)")
        return _step("learn_from_folder", "ok",
                     f"{result.get('scanned_files', 0)} files, {n} candidate(s)")
    except Exception as e:  # noqa: BLE001
        return _step("learn_from_folder", "failed", str(e))


def _review_suggestions_step(report, log):
    try:
        sys.path.insert(0, str(KIWI_DIR))
        from memory.db import get_suggested_lessons

        pending = get_suggested_lessons("pending")
        report["pending_suggestions"] = len(pending)
        log(f"3/6 review → {len(pending)} pending suggestion(s)")
        if pending:
            return _step("review_suggestions", "ok",
                         f"{len(pending)} pending — review with "
                         "kiwi_review_suggestions() then kiwi_approve_suggestion(id)")
        return _step("review_suggestions", "ok", "no pending suggestions")
    except Exception as e:  # noqa: BLE001
        return _step("review_suggestions", "failed", str(e))


def _seed_scan_step(project_path, report, log):
    """Run one scan and PERSIST it so db_scores / history have data.

    The MCP kiwi_scan handler does not log to the DB; this step does, because
    warming db_scores is the whole point of the seed scan.
    """
    try:
        sys.path.insert(0, str(KIWI_DIR))
        from scanner.cli import (scan_theme, scan_monorepo, _detect_project_type,
                                  _find_theme_root)
        from memory.db import log_scan_from_report

        ptype = _detect_project_type(project_path)
        start = time.time()
        if ptype == "monorepo":
            rep = scan_monorepo(project_path, severity_filter="ALL")
            scan_path = project_path
        else:
            scan_path = (project_path if ptype in ("themes_folder", "theme",
                                                   "plugin")
                         else _find_theme_root(project_path))
            scope = ptype if ptype in ("theme", "plugin") else None
            rep = scan_theme(scan_path, severity_filter="ALL", scope_type=scope,
                             skip_empty_scope=ptype in ("unknown", "plugin"),
                             rewrite_scopes=(ptype == "theme"))
        duration_ms = int((time.time() - start) * 1000)

        try:
            log_scan_from_report(scan_path, rep, duration_ms, mode="init")
            persisted = True
        except Exception as e:  # noqa: BLE001 — scan still useful without logging
            log(f"    (warn) could not persist scan history: {e}")
            persisted = False

        total = len(rep.violations)
        report["seed_violations"] = total
        log(f"4/6 seed scan → {total} violation(s)"
            + ("" if persisted else " (not persisted)"))
        return _step("seed_scan", "ok",
                     f"{rep.critical_count} CRITICAL / {rep.high_count} HIGH / "
                     f"{rep.suggest_count} SUGGEST"
                     + ("" if persisted else " — history not persisted"))
    except Exception as e:  # noqa: BLE001
        return _step("seed_scan", "failed", str(e))


def _learn_session_step(report, log):
    try:
        sys.path.insert(0, str(KIWI_DIR))
        from agent.reasoning.learner import learn_all_unprocessed

        results = learn_all_unprocessed()
        n = len(results) if results else 0
        report["sessions_learned"] = n
        log(f"5/6 learn_session → {n} session(s) processed")
        return _step("learn_session", "ok", f"{n} session(s) processed")
    except Exception as e:  # noqa: BLE001
        return _step("learn_session", "failed", str(e))


def register_pre_edit_hook(project_root, dry_run=False):
    """Register the PreToolUse pre_edit.py gate in <project>/.claude/settings.json.

    Idempotent (skipped if any PreToolUse entry already references pre_edit.py).
    NEVER touches settings.local.json — that file is cost-optimised and off-limits.
    """
    root = Path(project_root)
    settings_path = root / ".claude" / "settings.json"
    pre_edit = (KIWI_DIR / "hooks" / "pre_edit.py").resolve()

    settings = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as e:
            return {"status": "failed", "detail": f"unreadable {settings_path}: {e}"}

    hooks = settings.setdefault("hooks", {})
    pre = hooks.setdefault("PreToolUse", [])

    def _mentions_pre_edit(entry):
        for h in entry.get("hooks", []):
            if "pre_edit.py" in h.get("command", ""):
                return True
            if any("pre_edit.py" in str(a) for a in h.get("args", [])):
                return True
        return False

    if any(isinstance(e, dict) and _mentions_pre_edit(e) for e in pre):
        return {"status": "exists", "detail": str(settings_path)}

    pre.append({
        "matcher": "Edit|Write",
        "hooks": [{
            "type": "command",
            "command": "python",
            "args": [str(pre_edit), "${file_path}", "${tool_name}"],
            "timeout": 5,
            "description": "Block Edit/Write on code files if kiwi_context not called",
        }],
    })

    if dry_run:
        return {"status": "would-add", "detail": str(settings_path)}

    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
    except OSError as e:
        return {"status": "failed", "detail": f"write {settings_path}: {e}"}
    return {"status": "added", "detail": str(settings_path)}


def _anchor_step(project_path, report, log, write_anchor, write_cursor,
                 write_windsurf, assume_yes):
    try:
        sys.path.insert(0, str(KIWI_DIR / "tools"))
        import anchor_writer

        results = []
        if write_anchor:
            targets = anchor_writer._resolve_targets(
                Path(project_path).resolve(), write_cursor, write_windsurf)
            for t in targets:
                rc = anchor_writer.write_anchor(t, assume_yes=assume_yes,
                                                remove=False)
                results.append(f"{t.name}:{'ok' if rc == 0 else 'skipped'}")
        else:
            results.append("anchor skipped (write_anchor=False)")

        hook_res = register_pre_edit_hook(project_path)
        report["hook"] = hook_res["status"]
        log(f"6/6 anchor + hook → anchor: {', '.join(results)} | "
            f"hook: {hook_res['status']}")
        return _step("anchor_and_hook", "ok",
                     f"anchor: {', '.join(results)} | hook: {hook_res['status']}")
    except Exception as e:  # noqa: BLE001
        return _step("anchor_and_hook", "failed", str(e))


def run_init(project_path, write_anchor=True, write_cursor=False,
             write_windsurf=False, assume_yes=True, verbose=False):
    """Run the full kiwi init onboarding pipeline.

    Args:
        project_path: Project root to onboard.
        write_anchor: Write the Kiwi gate block into CLAUDE.md/AGENTS.md (Fix 7).
        write_cursor / write_windsurf: Also write Cursor / Windsurf rule files.
        assume_yes: Skip the anchor_writer confirmation prompt (pipeline is
            non-interactive — defaults to True).
        verbose: Echo per-step progress to stderr.

    Returns a JSON-serialisable report dict.
    """
    project_path = os.path.abspath(project_path)
    if not os.path.isdir(project_path):
        return {"ok": False, "error": f"not a directory: {project_path}",
                "steps": []}

    def log(msg):
        if verbose:
            print(f"[kiwi init] {msg}", file=sys.stderr)

    report = {"ok": True, "project_path": project_path, "steps": []}
    log(f"onboarding {project_path}")

    report["steps"].append(_detect_stack_step(project_path, report, log))
    report["steps"].append(_learn_folder_step(project_path, report, log))
    report["steps"].append(_review_suggestions_step(report, log))
    report["steps"].append(_seed_scan_step(project_path, report, log))
    report["steps"].append(_learn_session_step(report, log))
    report["steps"].append(_anchor_step(project_path, report, log, write_anchor,
                                         write_cursor, write_windsurf, assume_yes))

    report["failed_steps"] = [s["step"] for s in report["steps"]
                              if s["status"] == "failed"]
    report["ok"] = not report["failed_steps"]
    return report


def format_init_report(report):
    """Render run_init output as readable text for CLI / MCP."""
    if not report.get("ok") and "error" in report:
        return f"kiwi init FAILED: {report['error']}"

    lines = [f"# Kiwi Init — {report['project_path']}", ""]
    for s in report["steps"]:
        icon = {"ok": "✓", "failed": "✗", "skipped": "○"}.get(s["status"], "?")
        detail = f" — {s['detail']}" if s.get("detail") else ""
        lines.append(f"{icon} {s['step']}{detail}")
    lines.append("")

    if report.get("failed_steps"):
        lines.append(f"⚠️ {len(report['failed_steps'])} step(s) failed: "
                     f"{', '.join(report['failed_steps'])}")
    else:
        lines.append("✓ Onboarding complete — Kiwi is warm for this project.")

    if report.get("pending_suggestions"):
        lines.append(f"→ {report['pending_suggestions']} lesson suggestion(s) "
                     "await review: kiwi_review_suggestions()")
    return "\n".join(lines)
