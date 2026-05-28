"""Core scanner — language-agnostic scan engine."""

from .models import Violation, Report
from .engine import scan, scan_multi

__all__ = ["Violation", "Report", "scan", "scan_multi"]