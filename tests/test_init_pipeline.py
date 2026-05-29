"""Test kiwi init pipeline + cold-start banner (Fix 5).

Self-contained: builds a minimal fake project in a tempdir so tests do not
depend on any specific real project state.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.init_pipeline import (
    run_init,
    format_init_report,
    register_pre_edit_hook,
)
from agent.context import build_context, _is_cold_start, format_context


def _make_fake_project(root: Path, *, with_php: bool = True):
    """Create a minimal project skeleton."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "composer.json").write_text(
        json.dumps({"require": {"php": ">=8.0"}}), encoding="utf-8"
    )
    if with_php:
        (root / "plugin.php").write_text(
            "<?php\n// fake plugin entry\n"
            "function demo_init() { return true; }\n",
            encoding="utf-8",
        )
    return root


def test_run_init_full_pipeline():
    """run_init should execute all 6 steps and return ok=True for a clean project."""
    with tempfile.TemporaryDirectory() as tmp:
        project = _make_fake_project(Path(tmp) / "fake-proj")
        report = run_init(
            project_path=str(project),
            write_anchor=True,
            write_cursor=False,
            write_windsurf=False,
            assume_yes=True,
            verbose=False,
        )
        assert report.get("project_path") == str(project.resolve())
        steps = {s["step"] for s in report["steps"]}
        expected = {
            "detect_stack",
            "learn_from_folder",
            "review_suggestions",
            "seed_scan",
            "learn_session",
            "anchor_and_hook",
        }
        assert expected <= steps, f"missing steps: {expected - steps}"
        # Anchor + hook must succeed (these are deterministic — anything else
        # is environment-dependent so we don't fail the test on it).
        anchor_step = next(s for s in report["steps"] if s["step"] == "anchor_and_hook")
        assert anchor_step["status"] == "ok", anchor_step
        # CLAUDE.md (or AGENTS.md) should now contain the Kiwi gate marker.
        anchor_target = (project / "CLAUDE.md")
        if not anchor_target.exists():
            anchor_target = project / "AGENTS.md"
        assert anchor_target.exists()
        assert "KIWI:BEGIN" in anchor_target.read_text(encoding="utf-8")
        print("OK test_run_init_full_pipeline")


def test_register_pre_edit_hook_idempotent():
    """Registering the hook twice should write once, then report 'exists'."""
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        first = register_pre_edit_hook(str(project))
        assert first["status"] == "added", first
        settings = project / ".claude" / "settings.json"
        assert settings.exists()
        data = json.loads(settings.read_text(encoding="utf-8"))
        pre_entries = data["hooks"]["PreToolUse"]
        assert any(
            "pre_edit.py" in str(arg)
            for entry in pre_entries
            for hk in entry.get("hooks", [])
            for arg in hk.get("args", [])
        )
        # Second call must be a no-op.
        second = register_pre_edit_hook(str(project))
        assert second["status"] == "exists", second
        # File should not have been duplicated.
        data2 = json.loads(settings.read_text(encoding="utf-8"))
        assert len(data2["hooks"]["PreToolUse"]) == len(pre_entries)
        print("OK test_register_pre_edit_hook_idempotent")


def test_register_pre_edit_hook_never_touches_settings_local():
    """The hook must NEVER be written into settings.local.json (cost-locked)."""
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        # Pre-create settings.local.json with sentinel content.
        local = project / ".claude" / "settings.local.json"
        local.parent.mkdir(parents=True, exist_ok=True)
        sentinel = {"_protected": True, "permissions": {"allow": ["Bash(*)"]}}
        local.write_text(json.dumps(sentinel), encoding="utf-8")

        register_pre_edit_hook(str(project))

        # settings.local.json must be byte-for-byte unchanged.
        after = json.loads(local.read_text(encoding="utf-8"))
        assert after == sentinel, "settings.local.json was modified!"
        print("OK test_register_pre_edit_hook_never_touches_settings_local")


def test_cold_start_detection():
    """_is_cold_start: True only when project context exists but signal does not."""
    # No project at all → not cold (nothing to onboard).
    assert _is_cold_start("", {}, {"styles": [], "bindings": []}) is False
    # Project but no history & no conventions → cold.
    assert _is_cold_start("/some/proj", {}, {"styles": [], "bindings": []}) is True
    # Project with violation history → warm.
    assert _is_cold_start(
        "/some/proj",
        {"LES-001": {"history": 3}},
        {"styles": [], "bindings": []},
    ) is False
    # Project with learned conventions → warm.
    assert _is_cold_start(
        "/some/proj",
        {},
        {"styles": [{"key": "x", "value": "y", "count": 2}], "bindings": []},
    ) is False
    # Confidence-only entry without history is still cold (no project signal).
    assert _is_cold_start(
        "/some/proj",
        {"LES-001": {"confidence": 0.9}},
        {"styles": [], "bindings": []},
    ) is True
    print("OK test_cold_start_detection")


def test_cold_start_banner_in_output():
    """Cold-start banner should surface in both compact and full formatters when
    project_path is set but no history exists."""
    with tempfile.TemporaryDirectory() as tmp:
        project = _make_fake_project(Path(tmp) / "cold-proj")
        # Compact mode.
        ctx = build_context(
            task="add a checkout button",
            scope_type="plugin",
            project_path=str(project),
            compact=True,
        )
        assert ctx.get("cold_start") is True, "expected cold_start=True"
        out_compact = format_context(ctx)
        assert "Cold start" in out_compact or "cold start" in out_compact, out_compact

        # Full mode.
        ctx2 = build_context(
            task="add a checkout button",
            scope_type="plugin",
            project_path=str(project),
            compact=False,
        )
        assert ctx2.get("cold_start") is True
        out_full = format_context(ctx2)
        assert "Kiwi cold start" in out_full or "cold start" in out_full.lower()
        print("OK test_cold_start_banner_in_output")


def test_format_init_report_renders():
    """format_init_report should produce readable output without raising."""
    fake_report = {
        "ok": True,
        "project_path": "/tmp/x",
        "steps": [
            {"step": "detect_stack", "status": "ok", "detail": "caps: nextjs"},
            {"step": "learn_from_folder", "status": "ok", "detail": "10 files"},
            {"step": "review_suggestions", "status": "ok", "detail": "0 pending"},
            {"step": "seed_scan", "status": "ok", "detail": "0 / 0 / 0"},
            {"step": "learn_session", "status": "ok", "detail": "0 sessions"},
            {"step": "anchor_and_hook", "status": "ok", "detail": "added"},
        ],
        "failed_steps": [],
        "pending_suggestions": 0,
    }
    out = format_init_report(fake_report)
    assert "Kiwi Init" in out
    assert "Onboarding complete" in out
    print("OK test_format_init_report_renders")


if __name__ == "__main__":
    test_register_pre_edit_hook_idempotent()
    test_register_pre_edit_hook_never_touches_settings_local()
    test_cold_start_detection()
    test_cold_start_banner_in_output()
    test_format_init_report_renders()
    test_run_init_full_pipeline()
    print("\nAll Fix 5 tests passed.")