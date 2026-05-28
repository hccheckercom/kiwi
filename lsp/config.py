"""LSP server configuration."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LspConfig:
    severity_filter: str = "ALL"
    max_diagnostics_per_file: int = 50
    scan_on_open: bool = True
    scan_on_save: bool = True
    scan_on_change: bool = False
    debounce_ms: int = 500
    platform: Optional[str] = None
    scope_type: Optional[str] = None
    lessons_dir: Optional[str] = None
    excluded_patterns: list = field(default_factory=lambda: [
        "**/node_modules/**",
        "**/.git/**",
        "**/vendor/**",
        "**/dist/**",
        "**/build/**",
    ])