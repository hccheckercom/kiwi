"""Abstract base class for Kiwi code drafters."""

from abc import ABC, abstractmethod


class BaseDrafter(ABC):

    @abstractmethod
    def generate(self, brief: dict, target_path: str, level: str = "skeleton") -> str:
        """Generate code at given completeness level.

        Levels: skeleton, draft, complete
        """
        ...

    def supported_levels(self) -> list:
        return ["skeleton", "draft", "complete"]