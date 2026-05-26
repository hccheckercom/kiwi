"""Agent state management."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AgentState:
    mode: str
    path: str
    scan_count: int = 0
    fixes_applied: int = 0
    fixes_failed: int = 0
    violations_found: int = 0
    violations_remaining: int = 0
    history: list = field(default_factory=list)
    stashed: bool = False
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    tokens_used: int = 0
    session_id: str = ""
    should_summarize: bool = False

    def log(self, action: str, detail: str = ""):
        self.history.append({
            "action": action,
            "detail": detail,
            "scan": self.scan_count,
            "fixes": self.fixes_applied,
        })

    def track_tokens(self, tokens: int):
        """Track token usage and trigger summarization if needed."""
        self.tokens_used += tokens
        # Trigger summarization at 150K tokens (75% of 200K context)
        if self.tokens_used > 150000 and not self.should_summarize:
            self.should_summarize = True

    def to_report(self) -> dict:
        elapsed = (datetime.now() - datetime.fromisoformat(self.started_at)).total_seconds()
        return {
            "mode": self.mode,
            "path": self.path,
            "scans": self.scan_count,
            "fixes_applied": self.fixes_applied,
            "fixes_failed": self.fixes_failed,
            "violations_found": self.violations_found,
            "violations_remaining": self.violations_remaining,
            "elapsed_seconds": round(elapsed, 1),
            "tokens_used": self.tokens_used,
            "session_id": self.session_id,
            "history": self.history,
        }