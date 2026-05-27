"""Token merger — deep merge multiple token sources.

Handles merging tokens from multiple sources (DESIGN.md, HTML, overrides) with proper precedence.
"""

from typing import Dict, Any, List

try:
    from .schema import DesignTokens
except ImportError:
    from schema import DesignTokens


class TokenMerger:
    """Deep merge multiple token sources with precedence rules.

    Usage:
        merger = TokenMerger()
        merged = merger.merge([base_tokens, override_tokens])
    """

    def merge(self, token_sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge multiple token dicts with later sources taking precedence.

        Args:
            token_sources: List of token dicts (earlier = lower priority)

        Returns:
            Merged token dict
        """
        if not token_sources:
            return {}

        result = token_sources[0].copy()

        for source in token_sources[1:]:
            result = self._deep_merge(result, source)

        return result

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dicts (override wins on conflicts).

        Args:
            base: Base dict
            override: Override dict (takes precedence)

        Returns:
            Merged dict
        """
        result = base.copy()

        for key, value in override.items():
            if key in result:
                base_value = result[key]

                # Both are dicts and neither is a token leaf node
                if (isinstance(base_value, dict) and isinstance(value, dict) and
                    not self._is_token_leaf(base_value) and not self._is_token_leaf(value)):
                    result[key] = self._deep_merge(base_value, value)
                else:
                    # Override wins
                    result[key] = value
            else:
                result[key] = value

        return result

    def _is_token_leaf(self, d: Dict) -> bool:
        """Check if dict is a token leaf node (has value/fontSize/fontFamily).

        Args:
            d: Dict to check

        Returns:
            True if token leaf node
        """
        if not isinstance(d, dict):
            return False

        # Token leaf indicators
        leaf_keys = {"value", "fontSize", "fontFamily", "type", "comment"}
        return any(key in d for key in leaf_keys)


def merge_tokens(*token_sources: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function to merge tokens.

    Args:
        *token_sources: Variable number of token dicts (earlier = lower priority)

    Returns:
        Merged token dict

    Example:
        merged = merge_tokens(design_md_tokens, html_tokens, overrides)
    """
    merger = TokenMerger()
    return merger.merge(list(token_sources))