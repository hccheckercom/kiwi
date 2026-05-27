"""Base exporter interface for design tokens.

All exporters inherit from BaseExporter and implement the export() method.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tokens.schema import DesignTokens


class BaseExporter(ABC):
    """Base class for token exporters.

    Subclasses must implement export() to generate output in their target format.
    """

    def __init__(self, options: Dict[str, Any] = None):
        """Initialize exporter with options.

        Args:
            options: Format-specific options (e.g., indent size, prefix)
        """
        self.options = options or {}

    @abstractmethod
    def export(self, tokens: DesignTokens) -> str:
        """Export tokens to target format.

        Args:
            tokens: Validated DesignTokens schema

        Returns:
            Formatted output string
        """
        pass

    def export_to_file(self, tokens: DesignTokens, file_path: str) -> None:
        """Export tokens to file.

        Args:
            tokens: Validated DesignTokens schema
            file_path: Output file path
        """
        output = self.export(tokens)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(output)

    def _format_comment(self, comment: str, prefix: str = "//") -> str:
        """Format comment with prefix.

        Args:
            comment: Comment text
            prefix: Comment prefix (default: "//")

        Returns:
            Formatted comment line
        """
        if not comment:
            return ""
        return f"{prefix} {comment}"