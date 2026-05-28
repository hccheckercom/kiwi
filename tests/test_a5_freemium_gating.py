"""Comprehensive QA for A5 — Freemium Gating."""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

KIWI_DIR = Path(__file__).resolve().parent.parent


def main():
    print("=" * 60)
    print("A5 COMPREHENSIVE QA — Freemium Gating")
    print("=" * 60)
    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  PASS [{passed}] {name}")
        else:
            failed += 1
            print(f"  FAIL [{name}] {detail}")

    # === GROUP 1: Module Structure ===
    print("\n--- GROUP 1: Module Structure ---")
    core_dir = KIWI_DIR / "core"
    check("core/ dir exists", core_dir.is_dir())
    check("tier_config.py exists", (core_dir / "tier_config.py").is_file())
    check("tier_manager.py exists", (core_dir / "tier_manager.py").is_file())
    check("gating.py exists", (core_dir / "gating.py").is_file())
    check("upgrade_prompts.py exists", (core_dir / "upgrade_prompts.py").is_file())

    # === GROUP 2: Imports ===
    print("\n--- GROUP 2: Imports ---")
    try:
        from core.tier_config import TIER_LIMITS, TIER_ORDER, TierConfig, get_tier_config, FREE_TOOLS, GATED_TOOLS, GRACE_PERIOD_DAYS
        check("tier_config importable", True)
    except Exception as e:
        check("tier_config importable", False, str(e))

    try:
        from core.tier_manager import TierManager, get_tier_manager
        check("tier_manager importable", True)
    except Exception as e:
        check("tier_manager importable", False, str(e))

    try:
        from core.gating import gate_check, gate_tool, gated, GateResult
        check("gating importable", True)
    except Exception as e:
        check("gating importable", False, str(e))

    try:
        from core.upgrade_prompts import get_upgrade_prompt, format_tier_status
        check("upgrade_prompts importable", True)
    except Exception as e:
        check("upgrade_prompts importable", False, str(e))

    # === GROUP 3: Tier Config ===
    print("\n--- GROUP 3: Tier Config ---")
    from core.tier_config import TIER_LIMITS, TIER_ORDER, TierConfig, get_tier_config, FREE_TOOLS, GATED_TOOLS

    check("3 tiers defined", len(TIER_LIMITS) == 3, f"got {len(TIER_LIMITS)}")
    check("tier order correct", TIER_ORDER == ["free", "starter", "pro"])
    check("free has max_patterns=30", TIER_LIMITS["free"]["max_patterns"] == 30)
    check("free has trust_cap=0.6", TIER_LIMITS["free"]["trust_cap"] == 0.6)
    check("free has max_conventions=5", TIER_LIMITS["free"]["max_conventions"] == 5)
    check("free has max_scans_day=20", TIER_LIMITS["free"]["max_scans_day"] == 20)
    check("free code_generation=False", TIER_LIMITS["free"]["code_generation"] is False)
    check("free agent_mode=False", TIER_LIMITS["free"]["agent_mode"] is False)
    check("starter has max_patterns=200", TIER_LIMITS["starter"]["max_patterns"] == 200)
    check("starter agent_mode=review", TIER_LIMITS["starter"]["agent_mode"] == "review")
    check("pro max_patterns=None", TIER_LIMITS["pro"]["max_patterns"] is None)
    check("pro trust_cap=1.0", TIER_LIMITS["pro"]["trust_cap"] == 1.0)
    check("pro agent_mode=auto", TIER_LIMITS["pro"]["agent_mode"] == "auto")

    cfg = get_tier_config("free")
    check("get_tier_config returns TierConfig", isinstance(cfg, TierConfig))
    check("TierConfig.name correct", cfg.name == "free")
    check("TierConfig.get_limit works", cfg.get_limit("max_patterns") == 30)
    check("TierConfig.is_unlimited False for free", not cfg.is_unlimited("max_patterns"))
    check("TierConfig.next_tier from free", cfg.next_tier() == "starter")

    pro_cfg = get_tier_config("pro")
    check("pro is_unlimited max_patterns", pro_cfg.is_unlimited("max_patterns"))
    check("pro next_tier is None", pro_cfg.next_tier() is None)

    check("FREE_TOOLS has kiwi_check", "kiwi_check" in FREE_TOOLS)
    check("FREE_TOOLS has kiwi_context", "kiwi_context" in FREE_TOOLS)
    check("GATED_TOOLS has kiwi_scan", "kiwi_scan" in GATED_TOOLS)
    check("GATED_TOOLS has kiwi_agent", "kiwi_agent" in GATED_TOOLS)

    invalid_cfg = get_tier_config("nonexistent")
    check("invalid tier falls back to free", invalid_cfg.name == "free")

    # === GROUP 4: Tier Resolution ===
    print("\n--- GROUP 4: Tier Resolution ---")
    from core.tier_manager import TierManager

    # Reset singleton
    import core.tier_manager as tm_mod
    tm_mod._instance = None

    # Test ENV override
    os.environ["KIWI_TIER"] = "pro"
    mgr = TierManager()
    tier = mgr.resolve_tier()
    check("ENV override resolves pro", tier.name == "pro")
    check("resolved_from is env", tier.resolved_from == "env")
    del os.environ["KIWI_TIER"]

    # Test license file
    tmp_license = Path(tempfile.mkdtemp()) / "license.json"
    tmp_license.write_text(json.dumps({"tier": "starter", "key": "sk-kiwi-test"}), encoding="utf-8")
    old_license = tm_mod._LICENSE_PATH
    tm_mod._LICENSE_PATH = tmp_license
    mgr2 = TierManager()
    tier2 = mgr2.resolve_tier()
    check("license file resolves starter", tier2.name == "starter")
    check("resolved_from is license", tier2.resolved_from == "license")
    tm_mod._LICENSE_PATH = old_license

    # Test default (no env, no license, expired trial)
    tmp_trial = Path(tempfile.mkdtemp()) / "trial.json"
    tmp_trial.write_text(json.dumps({"started_at": time.time() - 86400 * 30}), encoding="utf-8")
    old_trial = tm_mod._TRIAL_PATH
    tm_mod._TRIAL_PATH = tmp_trial
    old_license2 = tm_mod._LICENSE_PATH
    tm_mod._LICENSE_PATH = Path(tempfile.mkdtemp()) / "nonexistent.json"
    mgr3 = TierManager()
    tier3 = mgr3.resolve_tier()
    check("expired trial resolves free", tier3.name == "free")
    check("resolved_from is default", tier3.resolved_from == "default")
    tm_mod._TRIAL_PATH = old_trial
    tm_mod._LICENSE_PATH = old_license2

    # Test grace period (fresh trial)
    tmp_trial2 = Path(tempfile.mkdtemp()) / "trial.json"
    tmp_trial2.write_text(json.dumps({"started_at": time.time()}), encoding="utf-8")
    tm_mod._TRIAL_PATH = tmp_trial2
    tm_mod._LICENSE_PATH = Path(tempfile.mkdtemp()) / "nonexistent2.json"
    mgr4 = TierManager()
    tier4 = mgr4.resolve_tier()
    check("fresh trial resolves pro", tier4.name == "pro")
    check("resolved_from is trial", tier4.resolved_from == "trial")
    tm_mod._TRIAL_PATH = old_trial
    tm_mod._LICENSE_PATH = old_license

    # === GROUP 5: Limit Enforcement ===
    print("\n--- GROUP 5: Limit Enforcement ---")

    # Force free tier
    os.environ["KIWI_TIER"] = "free"
    tm_mod._instance = None
    mgr5 = TierManager()
    mgr5.resolve_tier()

    r1 = mgr5.check_limit("max_patterns", 10)
    check("under limit: allowed=True", r1["allowed"] is True)
    check("under limit: remaining=20", r1["remaining"] == 20)
    check("under limit: limit=30", r1["limit"] == 30)

    r2 = mgr5.check_limit("max_patterns", 30)
    check("at limit: allowed=False", r2["allowed"] is False)
    check("at limit: remaining=0", r2["remaining"] == 0)

    r3 = mgr5.check_limit("max_patterns", 50)
    check("over limit: allowed=False", r3["allowed"] is False)

    r4 = mgr5.check_limit("code_generation", 0)
    check("bool feature False: allowed=False", r4["allowed"] is False)

    r5 = mgr5.check_limit("agent_mode", 0)
    check("agent_mode False: allowed=False", r5["allowed"] is False)

    # Pro tier — unlimited
    os.environ["KIWI_TIER"] = "pro"
    tm_mod._instance = None
    mgr6 = TierManager()
    mgr6.resolve_tier()

    r6 = mgr6.check_limit("max_patterns", 9999)
    check("pro unlimited: allowed=True", r6["allowed"] is True)
    check("pro unlimited: remaining=None", r6["remaining"] is None)

    r7 = mgr6.check_limit("code_generation", 0)
    check("pro code_gen: allowed=True", r7["allowed"] is True)

    # Dev mode bypass
    os.environ["KIWI_DEV"] = "1"
    os.environ["KIWI_TIER"] = "free"
    tm_mod._instance = None
    mgr7 = TierManager()
    mgr7.resolve_tier()
    r8 = mgr7.check_limit("max_patterns", 9999)
    check("dev mode bypasses limits", r8["allowed"] is True)
    check("dev mode tier=dev", r8["tier"] == "dev")
    del os.environ["KIWI_DEV"]
    del os.environ["KIWI_TIER"]

    # === GROUP 6: Gate Check ===
    print("\n--- GROUP 6: Gate Check ---")
    from core.gating import gate_check, gate_tool, GateResult

    os.environ["KIWI_TIER"] = "free"
    tm_mod._instance = None

    gr1 = gate_check("max_patterns", 10)
    check("gate_check under limit: allowed", gr1.allowed is True)

    gr2 = gate_check("max_patterns", 35)
    check("gate_check over limit: blocked", gr2.allowed is False)
    check("gate_check has message", len(gr2.message) > 0)
    check("gate_check has upgrade_tier", gr2.upgrade_tier == "starter")

    gr3 = gate_check("code_generation", 0)
    check("gate_check bool feature: blocked", gr3.allowed is False)

    # gate_tool for free tools
    from core.tier_config import FREE_TOOLS
    gr4 = gate_tool("kiwi_check")
    check("free tool always allowed", gr4.allowed is True)

    gr5 = gate_tool("kiwi_context")
    check("kiwi_context always allowed", gr5.allowed is True)

    del os.environ["KIWI_TIER"]

    # === GROUP 7: Upgrade Prompts ===
    print("\n--- GROUP 7: Upgrade Prompts ---")
    from core.upgrade_prompts import get_upgrade_prompt, format_tier_status

    msg1 = get_upgrade_prompt("max_patterns", 30, 30, "starter")
    check("pattern prompt mentions limit", "30" in msg1)
    check("pattern prompt mentions Starter", "Starter" in msg1)
    check("pattern prompt mentions 200", "200" in msg1)

    msg2 = get_upgrade_prompt("max_scans_day", 20, 20, "starter")
    check("scan prompt mentions daily", "Daily" in msg2 or "daily" in msg2 or "20" in msg2)

    msg3 = get_upgrade_prompt("code_generation", 0, None, "starter")
    check("code_gen prompt mentions tier", "Starter" in msg3)

    status = format_tier_status("free", {"patterns_learned": 15, "conventions_learned": 3, "scans_today": 5}, TIER_LIMITS["free"])
    check("status shows FREE", "FREE" in status)
    check("status shows patterns", "15" in status)
    check("status shows conventions", "3" in status)
    check("status shows scans", "5" in status)

    # === GROUP 8: Gated Decorator ===
    print("\n--- GROUP 8: Gated Decorator ---")
    from core.gating import gated

    os.environ["KIWI_TIER"] = "pro"
    tm_mod._instance = None

    @gated("max_patterns")
    def dummy_mine():
        return {"patterns": [1, 2, 3]}

    result_pro = dummy_mine()
    check("pro tier: decorator passes through", result_pro == {"patterns": [1, 2, 3]})

    os.environ["KIWI_TIER"] = "free"
    os.environ.pop("KIWI_DEV", None)
    tm_mod._instance = None

    # Note: gated decorator uses get_usage_counts() which reads DB
    # With no DB data, counts are 0, so free tier with 0 patterns should pass
    result_free = dummy_mine()
    check("free tier under limit: passes", result_free == {"patterns": [1, 2, 3]})

    @gated("code_generation")
    def dummy_generate():
        return {"code": "hello"}

    result_gen = dummy_generate()
    check("free tier code_gen: blocked", isinstance(result_gen, dict) and result_gen.get("gated") is True)
    check("blocked result has message", "message" in result_gen)
    check("blocked result has upgrade_tier", result_gen.get("upgrade_tier") == "starter")

    del os.environ["KIWI_TIER"]

    # === GROUP 9: License Activation ===
    print("\n--- GROUP 9: License Activation ---")

    tmp_lic = Path(tempfile.mkdtemp()) / "license.json"
    tm_mod._LICENSE_PATH = tmp_lic
    tm_mod._instance = None

    mgr_act = TierManager()
    r_bad = mgr_act.activate_license("invalid-key", "starter")
    check("invalid key rejected", r_bad["success"] is False)
    check("error mentions format", "format" in r_bad["error"].lower() or "sk-kiwi" in r_bad["error"])

    r_bad2 = mgr_act.activate_license("sk-kiwi-test123", "nonexistent")
    check("invalid tier rejected", r_bad2["success"] is False)

    r_good = mgr_act.activate_license("sk-kiwi-test123", "starter")
    check("valid activation succeeds", r_good["success"] is True)
    check("activation returns tier", r_good["tier"] == "starter")
    check("license file created", tmp_lic.exists())

    data = json.loads(tmp_lic.read_text(encoding="utf-8"))
    check("license file has tier", data["tier"] == "starter")
    check("license file has key", data["key"] == "sk-kiwi-test123")

    tier_after = mgr_act.get_current_tier()
    check("tier resolved after activation", tier_after.name == "starter")

    tm_mod._LICENSE_PATH = old_license

    # === GROUP 10: MCP Integration ===
    print("\n--- GROUP 10: MCP Integration ---")

    # Check _check_tier_gate exists in mcp_server
    mcp_path = KIWI_DIR / "mcp_server.py"
    mcp_content = mcp_path.read_text(encoding="utf-8")
    check("_check_tier_gate in mcp_server", "_check_tier_gate" in mcp_content)
    check("gate_result check in dispatch", "gate_result" in mcp_content)
    check("kiwi_tier handler registered", '"kiwi_tier"' in mcp_content or "'kiwi_tier'" in mcp_content)
    check("_handle_tier defined", "_handle_tier" in mcp_content)

    # Check pattern_miner integration
    pm_path = KIWI_DIR / "plugins" / "generic" / "pattern_miner.py"
    pm_content = pm_path.read_text(encoding="utf-8")
    check("pattern_miner has gate_check", "gate_check" in pm_content)

    # Check convention_learner integration
    cl_path = KIWI_DIR / "plugins" / "generic" / "convention_learner.py"
    cl_content = cl_path.read_text(encoding="utf-8")
    check("convention_learner has gate_check", "gate_check" in cl_content)

    # === GROUP 11: Backward Compat (A4) ===
    print("\n--- GROUP 11: Backward Compat (A4) ---")

    try:
        from tracking.usage_tracker import UsageTracker, get_tracker
        check("A4 UsageTracker still importable", True)
    except Exception as e:
        check("A4 UsageTracker still importable", False, str(e))

    try:
        from tracking.baseline_estimator import estimate_baseline
        check("A4 baseline_estimator still importable", True)
    except Exception as e:
        check("A4 baseline_estimator still importable", False, str(e))

    try:
        from tracking.savings import get_savings
        check("A4 savings still importable", True)
    except Exception as e:
        check("A4 savings still importable", False, str(e))

    try:
        from tracking.dashboard import dashboard, format_compact
        check("A4 dashboard still importable", True)
    except Exception as e:
        check("A4 dashboard still importable", False, str(e))

    # A3 backward compat
    try:
        from plugins.generic.plugin import GenericPlugin
        gp = GenericPlugin()
        check("A3 GenericPlugin still works", gp.get_manifest().name == "generic")
    except Exception as e:
        check("A3 GenericPlugin still works", False, str(e))

    # === SUMMARY ===
    print("\n" + "=" * 60)
    total = passed + failed
    print(f"A5 QA RESULT: {passed}/{total} passed, {failed} failed")
    if failed == 0:
        print("ALL CHECKS PASSED")
    else:
        print("SOME CHECKS FAILED — review above")
    print("=" * 60)
    return failed


if __name__ == "__main__":
    sys.exit(main())
