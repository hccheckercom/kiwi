"""Checker registry — maps type → checker class."""

from .presence import PresenceChecker
from .absence import AbsenceChecker
from .cross_check import CrossChecker
from .bom import BomChecker

REGISTRY = {
    "presence": PresenceChecker(),
    "absence": AbsenceChecker(),
    "cross-check": CrossChecker(),
    "bom-check": BomChecker(),
}

try:
    from .ast_checker import AstChecker
    REGISTRY["ast"] = AstChecker()
except ImportError:
    pass


def get_checker(type_name: str):
    """Get checker instance by type name."""
    return REGISTRY.get(type_name)