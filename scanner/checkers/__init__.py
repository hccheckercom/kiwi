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

try:
    from .semgrep import SemgrepChecker
    REGISTRY["semgrep"] = SemgrepChecker()
except ImportError:
    pass


def get_checker(type_name: str, use_semgrep: bool = False):
    """Get checker instance by type name.

    Args:
        type_name: Checker type (presence, absence, cross-check, etc.)
        use_semgrep: If True and type is 'presence', use Semgrep checker

    Returns:
        Checker instance or None if not found
    """
    if use_semgrep and type_name == "presence" and "semgrep" in REGISTRY:
        return REGISTRY["semgrep"]
    return REGISTRY.get(type_name)