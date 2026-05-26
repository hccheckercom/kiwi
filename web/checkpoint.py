"""Checkpoint system for agent approval workflows."""

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

KIWI_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(KIWI_DIR))

from memory import coordination as coord


@dataclass
class Checkpoint:
    """Represents a decision point requiring human approval."""
    checkpoint_id: str
    agent_run_id: int
    message: str
    options: list[dict]
    created_at: str
    resolved_at: Optional[str] = None
    decision: Optional[str] = None
    comment: Optional[str] = None


class CheckpointManager:
    """Manages approval checkpoints in agent workflows."""

    def __init__(self):
        self.checkpoints: dict[str, Checkpoint] = {}

    def create_checkpoint(
        self,
        agent_run_id: int,
        message: str,
        options: list[dict],
    ) -> Checkpoint:
        """
        Create a new checkpoint requiring human decision.

        Args:
            agent_run_id: Agent run ID
            message: Question or decision description
            options: List of choices, each with {id, label, description}

        Returns:
            Checkpoint object
        """
        checkpoint_id = f"cp_{agent_run_id}_{len(self.checkpoints)}"

        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            agent_run_id=agent_run_id,
            message=message,
            options=options,
            created_at=datetime.utcnow().isoformat(),
        )

        self.checkpoints[checkpoint_id] = checkpoint

        # Update agent run status to checkpoint_waiting
        coord.update_agent_run(
            agent_run_id,
            status="checkpoint_waiting",
            checkpoint_data={
                "checkpoint_id": checkpoint_id,
                "message": message,
                "options": [opt["id"] for opt in options],
            }
        )

        return checkpoint

    def resolve_checkpoint(
        self,
        checkpoint_id: str,
        decision: str,
        comment: Optional[str] = None,
    ) -> bool:
        """
        Resolve a checkpoint with human decision.

        Args:
            checkpoint_id: Checkpoint ID
            decision: Selected option ID
            comment: Optional comment from human

        Returns:
            True if resolved successfully
        """
        checkpoint = self.checkpoints.get(checkpoint_id)
        if not checkpoint:
            return False

        checkpoint.resolved_at = datetime.utcnow().isoformat()
        checkpoint.decision = decision
        checkpoint.comment = comment

        # Update agent run to continue
        coord.update_agent_run(
            checkpoint.agent_run_id,
            status="running",
            checkpoint_data={
                "checkpoint_id": checkpoint_id,
                "decision": decision,
                "comment": comment,
                "resolved_at": checkpoint.resolved_at,
            }
        )

        return True

    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Get checkpoint by ID."""
        return self.checkpoints.get(checkpoint_id)

    def get_pending_checkpoints(self, agent_run_id: Optional[int] = None) -> list[Checkpoint]:
        """Get all pending checkpoints, optionally filtered by agent run."""
        pending = [
            cp for cp in self.checkpoints.values()
            if cp.resolved_at is None
        ]

        if agent_run_id is not None:
            pending = [cp for cp in pending if cp.agent_run_id == agent_run_id]

        return pending

    def to_dict(self, checkpoint: Checkpoint) -> dict:
        """Convert checkpoint to dict for API response."""
        return {
            "checkpoint_id": checkpoint.checkpoint_id,
            "agent_run_id": checkpoint.agent_run_id,
            "message": checkpoint.message,
            "options": checkpoint.options,
            "created_at": checkpoint.created_at,
            "resolved_at": checkpoint.resolved_at,
            "decision": checkpoint.decision,
            "comment": checkpoint.comment,
        }


# Global checkpoint manager instance
_checkpoint_manager = CheckpointManager()


def create_checkpoint(agent_run_id: int, message: str, options: list[dict]) -> Checkpoint:
    """Create a checkpoint (convenience function)."""
    return _checkpoint_manager.create_checkpoint(agent_run_id, message, options)


def resolve_checkpoint(checkpoint_id: str, decision: str, comment: Optional[str] = None) -> bool:
    """Resolve a checkpoint (convenience function)."""
    return _checkpoint_manager.resolve_checkpoint(checkpoint_id, decision, comment)


def get_pending_checkpoints(agent_run_id: Optional[int] = None) -> list[Checkpoint]:
    """Get pending checkpoints (convenience function)."""
    return _checkpoint_manager.get_pending_checkpoints(agent_run_id)
