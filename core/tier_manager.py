"""TierManager — singleton that resolves and enforces tier limits."""

import json
import os
import time
from pathlib import Path
from typing import Optional

from .tier_config import (
    TIER_LIMITS,
    TIER_ORDER,
    GRACE_PERIOD_DAYS,
    TierConfig,
    get_tier_config,
)

_KIWI_DIR = Path(__file__).parent.parent
_LICENSE_PATH = _KIWI_DIR / ".kiwi" / "license.json"
_TRIAL_PATH = _KIWI_DIR / ".kiwi" / "trial.json"

_instance: Optional["TierManager"] = None


def get_tier_manager() -> "TierManager":
    global _instance
    if _instance is None:
        _instance = TierManager()
    return _instance


class TierManager:

    def __init__(self):
        self._tier: Optional[TierConfig] = None

    def resolve_tier(self) -> TierConfig:
        """Resolve tier: ENV > license file > trial/free."""
        # 1. ENV override
        env_tier = os.environ.get("KIWI_TIER", "").lower().strip()
        if env_tier in TIER_LIMITS:
            cfg = get_tier_config(env_tier)
            cfg.resolved_from = "env"
            self._tier = cfg
            return cfg

        # 2. License file
        if _LICENSE_PATH.exists():
            try:
                data = json.loads(_LICENSE_PATH.read_text(encoding="utf-8"))
                tier_name = data.get("tier", "free")
                if tier_name in TIER_LIMITS:
                    cfg = get_tier_config(tier_name)
                    cfg.resolved_from = "license"
                    self._tier = cfg
                    return cfg
            except (json.JSONDecodeError, OSError):
                pass

        # 3. Trial grace period
        if self._in_grace_period():
            cfg = get_tier_config("pro")
            cfg.resolved_from = "trial"
            self._tier = cfg
            return cfg

        # 4. Default free
        cfg = get_tier_config("free")
        cfg.resolved_from = "default"
        self._tier = cfg
        return cfg

    def get_current_tier(self) -> TierConfig:
        if self._tier is None:
            self.resolve_tier()
        return self._tier

    def is_dev_mode(self) -> bool:
        return os.environ.get("KIWI_DEV", "").strip() == "1"

    def check_limit(self, feature: str, current_count: int = 0) -> dict:
        """Check if a feature is within tier limits.

        Returns:
            dict with keys: allowed, remaining, limit, tier, feature
        """
        if self.is_dev_mode():
            return {"allowed": True, "remaining": None, "limit": None,
                    "tier": "dev", "feature": feature}

        tier = self.get_current_tier()
        limit = tier.get_limit(feature)

        # Boolean features
        if isinstance(limit, bool):
            return {"allowed": limit, "remaining": None, "limit": limit,
                    "tier": tier.name, "feature": feature}

        # String features (e.g., "skeleton", "review")
        if isinstance(limit, str):
            return {"allowed": True, "remaining": None, "limit": limit,
                    "tier": tier.name, "feature": feature}

        # None = unlimited
        if limit is None:
            return {"allowed": True, "remaining": None, "limit": None,
                    "tier": tier.name, "feature": feature}

        # Numeric limits
        remaining = max(0, limit - current_count)
        return {
            "allowed": current_count < limit,
            "remaining": remaining,
            "limit": limit,
            "tier": tier.name,
            "feature": feature,
        }

    def get_usage_counts(self) -> dict:
        """Get current usage counts from tracking DB."""
        try:
            from tracking.usage_tracker import DB_PATH
            import sqlite3

            if not DB_PATH.exists():
                return self._empty_counts()

            conn = sqlite3.connect(str(DB_PATH), timeout=5)
            conn.row_factory = sqlite3.Row

            today_start = int(time.time()) - (int(time.time()) % 86400)

            scans_today = conn.execute(
                "SELECT COUNT(*) as cnt FROM usage_events "
                "WHERE operation='scan' AND timestamp >= ?",
                (today_start,)
            ).fetchone()["cnt"]

            patterns_learned = conn.execute(
                "SELECT COUNT(*) as cnt FROM usage_events "
                "WHERE operation IN ('learn_from_folder', 'mine_patterns')"
            ).fetchone()["cnt"]

            conventions_learned = conn.execute(
                "SELECT COUNT(*) as cnt FROM usage_events "
                "WHERE operation='convention_learn'"
            ).fetchone()["cnt"]

            conn.close()

            return {
                "scans_today": scans_today,
                "patterns_learned": patterns_learned,
                "conventions_learned": conventions_learned,
            }
        except Exception:
            return self._empty_counts()

    def activate_license(self, key: str, tier: str = "starter") -> dict:
        """Write license file. Returns success/error."""
        if tier not in TIER_LIMITS:
            return {"success": False, "error": f"Unknown tier: {tier}"}

        if not key or not key.startswith("sk-kiwi-"):
            return {"success": False, "error": "Invalid key format (expected sk-kiwi-...)"}

        _LICENSE_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {"tier": tier, "key": key, "activated_at": time.time()}
        _LICENSE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")

        # Re-resolve
        self._tier = None
        self.resolve_tier()

        return {"success": True, "tier": tier}

    def _in_grace_period(self) -> bool:
        """Check if within 7-day trial grace period."""
        if not _TRIAL_PATH.exists():
            _TRIAL_PATH.parent.mkdir(parents=True, exist_ok=True)
            _TRIAL_PATH.write_text(
                json.dumps({"started_at": time.time()}), encoding="utf-8"
            )
            return True

        try:
            data = json.loads(_TRIAL_PATH.read_text(encoding="utf-8"))
            started = data.get("started_at", 0)
            elapsed_days = (time.time() - started) / 86400
            return elapsed_days < GRACE_PERIOD_DAYS
        except (json.JSONDecodeError, OSError):
            return False

    @staticmethod
    def _empty_counts() -> dict:
        return {
            "scans_today": 0,
            "patterns_learned": 0,
            "conventions_learned": 0,
        }