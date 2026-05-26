"""CI/CD integrations package."""

from .github_actions import GitHubActionsAdapter, CIReport

__all__ = ['GitHubActionsAdapter', 'CIReport']