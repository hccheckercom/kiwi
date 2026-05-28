"""Abstract base class for all Kiwi checkers."""

from abc import ABC, abstractmethod


class BaseChecker(ABC):

    @abstractmethod
    def check(self, pattern_def: dict, files: list, root_path: str) -> list:
        """Run check against files, return list of Violation objects."""
        ...