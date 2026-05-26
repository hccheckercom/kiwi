"""Data models for Active Pattern Learning"""

from dataclasses import dataclass, field
from typing import List, Set, Optional


@dataclass
class SuggestedPattern:
    """Pattern candidate from mining"""
    pattern: str
    scope: str
    category: str
    severity: str
    example_file: str
    example_line: int
    example_code: str
    occurrence_count: int
    confidence: float
    files: List[str] = field(default_factory=list)


@dataclass
class PatternFingerprint:
    """Fingerprint of existing lesson for anomaly detection"""
    lesson_id: str
    pattern_hash: str
    category: str
    scope: str
    token_set: Set[str]


@dataclass
class Anomaly:
    """Detected anomaly in code"""
    pattern: str
    match_text: str
    files: List[str]
    occurrence_count: int
    confidence: float
    suggested_category: str
    suggested_severity: str
    example_file: str
    example_line: int


@dataclass
class LessonMetadata:
    """Metadata for generated lesson"""
    lesson_id: str
    severity: str
    category: str
    title: str
    pattern: str
    scope: str
    fix_type: Optional[str] = None
    fix_search: Optional[str] = None
    fix_replace: Optional[str] = None