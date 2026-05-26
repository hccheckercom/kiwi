"""Kiwi Scanner v3 — Modular theme scanner with grouped output and compiled-file exclusion."""

from .models import Violation, Report
from .loader import load_patterns
from .resolver import resolve_scope, is_compiled_file

__all__ = ["Violation", "Report", "load_patterns", "resolve_scope", "is_compiled_file"]