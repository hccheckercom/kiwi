"""Design Token Extractor — Extract design tokens from demo HTML + DESIGN.md"""

import json
import re
from pathlib import Path
from typing import Dict, Any, Optional

import yaml


class DesignTokenExtractor:
    """
    Extract design tokens from demo HTML (embedded tailwind.config) and DESIGN.md (YAML frontmatter).

    Usage:
        extractor = DesignTokenExtractor()
        tokens = extractor.extract_from_demo("themes/sfvn/demos/demo3")
    """

    def __init__(self):
        self.tokens = {}

    def extract_from_demo(self, demo_path: str) -> Dict[str, Any]:
        """
        Extract tokens from demo folder.

        Args:
            demo_path: Path to demo folder (contains code.html, DESIGN.md)

        Returns:
            Normalized token dict with keys: colors, typography, spacing, borderRadius
        """
        demo_dir = Path(demo_path)

        if not demo_dir.exists():
            raise FileNotFoundError(f"Demo folder not found: {demo_path}")

        html_path = demo_dir / "code.html"
        design_path = demo_dir / "DESIGN.md"

        tokens = {}

        # Extract from DESIGN.md first (base tokens)
        if design_path.exists():
            design_tokens = self.extract_from_design_md(str(design_path))
            tokens.update(design_tokens)

        # Extract from HTML (overrides DESIGN.md)
        if html_path.exists():
            html_tokens = self.extract_from_html(str(html_path))
            tokens = self._merge_tokens(tokens, html_tokens)

        # Validate completeness
        self._validate_tokens(tokens)

        return tokens

    def extract_from_html(self, html_path: str) -> Dict[str, Any]:
        """
        Parse embedded tailwind.config from HTML <script> tag.

        Args:
            html_path: Path to code.html

        Returns:
            Token dict extracted from tailwind.config
        """
        html_content = Path(html_path).read_text(encoding="utf-8")

        # Find <script id="tailwind-config">
        script_match = re.search(
            r'<script[^>]*id=["\']tailwind-config["\'][^>]*>(.*?)</script>',
            html_content,
            re.DOTALL
        )

        if not script_match:
            return {}

        script_content = script_match.group(1)

        # Extract tailwind.config = {...}
        # Use a simple approach: find the opening brace and match to the closing brace
        config_start = re.search(r'tailwind\.config\s*=\s*\{', script_content)
        if not config_start:
            return {}

        # Find matching closing brace by counting braces
        start_pos = config_start.end() - 1  # Position of opening {
        brace_count = 0
        end_pos = start_pos

        for i in range(start_pos, len(script_content)):
            if script_content[i] == '{':
                brace_count += 1
            elif script_content[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_pos = i + 1
                    break

        config_str = script_content[start_pos:end_pos]

        if not config_str or config_str == '{}':
            return {}

        # Parse as JSON (with some cleanup for JS object notation)
        config_str = self._normalize_js_object(config_str)

        try:
            config = json.loads(config_str)
        except json.JSONDecodeError as e:
            print(f"WARNING: Failed to parse tailwind.config: {e}")
            return {}

        # Extract theme.extend
        theme_extend = config.get("theme", {}).get("extend", {})

        return {
            "colors": theme_extend.get("colors", {}),
            "typography": self._extract_typography(theme_extend),
            "spacing": theme_extend.get("spacing", {}),
            "borderRadius": theme_extend.get("borderRadius", {}),
        }

    def extract_from_design_md(self, md_path: str) -> Dict[str, Any]:
        """
        Parse YAML frontmatter from DESIGN.md.

        Args:
            md_path: Path to DESIGN.md

        Returns:
            Token dict from YAML frontmatter
        """
        content = Path(md_path).read_text(encoding="utf-8")

        # Extract YAML frontmatter
        match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)

        if not match:
            return {}

        yaml_str = match.group(1)

        try:
            data = yaml.safe_load(yaml_str)
        except yaml.YAMLError as e:
            print(f"WARNING: Failed to parse DESIGN.md YAML: {e}")
            return {}

        return {
            "colors": data.get("colors", {}),
            "typography": data.get("typography", {}),
            "spacing": data.get("spacing", {}),
            "borderRadius": data.get("rounded", {}),
        }

    def _extract_typography(self, theme_extend: Dict) -> Dict[str, Any]:
        """Extract typography tokens from theme.extend (fontFamily + fontSize)."""
        typography = {}

        font_family = theme_extend.get("fontFamily", {})
        font_size = theme_extend.get("fontSize", {})

        # Merge fontFamily and fontSize by scale name
        for scale_name in set(list(font_family.keys()) + list(font_size.keys())):
            scale = {}

            if scale_name in font_family:
                family_value = font_family[scale_name]
                scale["fontFamily"] = family_value[0] if isinstance(family_value, list) else family_value

            if scale_name in font_size:
                size_config = font_size[scale_name]
                if isinstance(size_config, str):
                    # Simple string value like '0.75rem'
                    scale["fontSize"] = size_config
                elif isinstance(size_config, list) and len(size_config) == 2:
                    # Tuple format: ['1rem', {lineHeight: '1.5'}]
                    scale["fontSize"] = size_config[0]
                    if isinstance(size_config[1], dict):
                        scale.update(size_config[1])
                elif isinstance(size_config, dict):
                    # Already a dict with fontSize + other props
                    scale.update(size_config)
                else:
                    scale["fontSize"] = str(size_config)

            if scale:
                typography[scale_name] = scale

        return typography

    def _merge_tokens(self, base: Dict, override: Dict) -> Dict:
        """Merge two token dicts (override wins)."""
        merged = base.copy()

        for key, value in override.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value

        return merged

    def _validate_tokens(self, tokens: Dict) -> None:
        """Validate token completeness (warn if missing critical tokens)."""
        # Only colors and typography are required
        # spacing and borderRadius are optional (can use Tailwind defaults)
        required_keys = ["colors", "typography"]
        optional_keys = ["spacing", "borderRadius"]

        for key in required_keys:
            if key not in tokens or not tokens[key]:
                print(f"WARNING: Missing or empty token category: {key}")

        for key in optional_keys:
            if key not in tokens or not tokens[key]:
                print(f"INFO: Optional token category '{key}' not found, will use Tailwind defaults")

        # Check color count (should have 30+ colors for Material Design)
        if "colors" in tokens and len(tokens["colors"]) < 10:
            print(f"WARNING: Only {len(tokens['colors'])} colors found (expected 30+)")

        # Check typography scales (should have 5+ scales)
        if "typography" in tokens and len(tokens["typography"]) < 5:
            print(f"WARNING: Only {len(tokens['typography'])} typography scales found (expected 5+)")

    def _normalize_js_object(self, js_str: str) -> str:
        """
        Normalize JavaScript object notation to valid JSON.

        Handles:
        - Unquoted keys: {foo: "bar"} → {"foo": "bar"}
        - Single quotes: {'foo': 'bar'} → {"foo": "bar"}
        - Trailing commas: {foo: "bar",} → {foo: "bar"}
        """
        # Replace single quotes with double quotes
        js_str = js_str.replace("'", '"')

        # Quote unquoted keys (simple heuristic: word followed by colon)
        js_str = re.sub(r'(\w+):', r'"\1":', js_str)

        # Remove trailing commas before closing braces/brackets
        js_str = re.sub(r',(\s*[}\]])', r'\1', js_str)

        return js_str


def main():
    """CLI for testing token extraction."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python token_extractor.py <demo_path>")
        sys.exit(1)

    demo_path = sys.argv[1]

    extractor = DesignTokenExtractor()
    tokens = extractor.extract_from_demo(demo_path)

    print(json.dumps(tokens, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()