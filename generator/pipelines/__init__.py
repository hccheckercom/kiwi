"""Pipelines — Jinja2-only generation pipelines for Kiwi Generator."""

from .base import BasePipeline, PipelineResult
from .new_theme import NewThemePipeline
from .clone_theme import CloneThemePipeline

__all__ = [
    'BasePipeline',
    'PipelineResult',
    'NewThemePipeline',
    'CloneThemePipeline',
]