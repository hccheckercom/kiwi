"""Abstract base class for all Kiwi plugins."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class PluginManifest:
    name: str
    version: str
    languages: list = field(default_factory=list)
    frameworks: list = field(default_factory=list)
    platforms: list = field(default_factory=list)
    scope_types: list = field(default_factory=list)
    lessons_dir: str = ""  # str or Path, coerced to str in get_lessons_path()
    description: str = ""
    author: str = ""
    homepage: str = ""


class KiwiPlugin(ABC):

    @abstractmethod
    def get_manifest(self) -> PluginManifest:
        ...

    @abstractmethod
    def get_checkers(self) -> dict:
        """Return {type_name: checker_instance} registry."""
        ...

    @abstractmethod
    def get_quality_rules(self) -> list:
        ...

    @abstractmethod
    def get_context_map(self) -> dict:
        """Return {keyword: [categories]} for task routing."""
        ...

    def get_drafters(self) -> list:
        return []

    def get_excluded_dirs(self) -> set:
        return set()

    def get_excluded_files(self) -> set:
        return set()

    def get_lessons_path(self) -> str:
        return self.get_manifest().lessons_dir

    def detect_project(self, path: str) -> float:
        """Return confidence 0.0-1.0 that this plugin handles the given project."""
        return 0.0