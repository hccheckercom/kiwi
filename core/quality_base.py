"""Abstract base class for quality rules applied during code generation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class QualityViolation:
    rule_name: str
    message: str
    severity: str
    line: int = 0
    suggestion: str = ""


class BaseQualityRule(ABC):

    @abstractmethod
    def check(self, content: str, file_path: str) -> list:
        """Check generated content against quality rule. Return list of QualityViolation."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def severity(self) -> str:
        ...
