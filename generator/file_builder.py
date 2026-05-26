"""
File Builder

Jinja2 template rendering engine for code generation.
Merges input context + Kiwi rules + Blueprint specs.
"""

from pathlib import Path
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader, Template, TemplateNotFound
import re


class FileBuilder:
    """
    Generate file content from Jinja2 templates.

    Workflow:
    1. Load template from templates/ directory
    2. Inject Kiwi context (rules, anti-patterns)
    3. Merge with Blueprint specs
    4. Render template with full context
    5. Post-process (format, validate)
    """

    def __init__(self, templates_dir: Path):
        self.templates_dir = templates_dir
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True
        )

        # Add custom filters
        self.env.filters['json_encode'] = self._json_encode_filter
        self.env.filters['php_array'] = self._php_array_filter
        self.env.filters['css_var'] = self._css_var_filter

    def _json_encode_filter(self, value: Any) -> str:
        """Jinja2 filter: Convert Python value to JSON."""
        import json
        return json.dumps(value, ensure_ascii=False, indent=2)

    def _php_array_filter(self, value: Dict) -> str:
        """Jinja2 filter: Convert Python dict to PHP array syntax."""
        return self._dict_to_php_array(value, indent=1)

    def _dict_to_php_array(self, d: Dict, indent: int = 0) -> str:
        """Recursively convert dict to PHP array string."""
        if not d:
            return "[]"

        lines = ["["]
        tab = "\t" * indent

        for key, value in d.items():
            if isinstance(value, dict):
                value_str = self._dict_to_php_array(value, indent + 1)
            elif isinstance(value, list):
                value_str = self._list_to_php_array(value, indent + 1)
            elif isinstance(value, str):
                value_str = f"'{value}'"
            elif isinstance(value, bool):
                value_str = "true" if value else "false"
            elif value is None:
                value_str = "null"
            else:
                value_str = str(value)

            lines.append(f"{tab}\t'{key}' => {value_str},")

        lines.append(f"{tab}]")
        return "\n".join(lines)

    def _list_to_php_array(self, lst: list, indent: int = 0) -> str:
        """Convert list to PHP array string."""
        if not lst:
            return "[]"

        tab = "\t" * indent
        items = []

        for item in lst:
            if isinstance(item, dict):
                items.append(self._dict_to_php_array(item, indent + 1))
            elif isinstance(item, str):
                items.append(f"'{item}'")
            else:
                items.append(str(item))

        return "[\n" + tab + "\t" + f",\n{tab}\t".join(items) + f"\n{tab}]"

    def _css_var_filter(self, value: str) -> str:
        """Jinja2 filter: Wrap color value in CSS var() if not already."""
        if value.startswith('var('):
            return value
        if value.startswith('#') or value.startswith('rgb'):
            # Hardcoded color - should use CSS var
            return f"var(--wz-{value})"
        return f"var(--wz-{value})"

    def build_file(
        self,
        template_name: str,
        context: Dict[str, Any],
        kiwi_rules: Optional[list] = None,
        blueprint_spec: Optional[Dict] = None
    ) -> str:
        """
        Generate file content from template.

        Args:
            template_name: Template filename (e.g., 'store-config.php.j2')
            context: Input variables (shop_name, colors, etc.)
            kiwi_rules: Kiwi rules to enforce
            blueprint_spec: Blueprint specification

        Returns:
            Generated file content
        """
        try:
            template = self.env.get_template(template_name)
        except TemplateNotFound:
            raise FileNotFoundError(f"Template not found: {template_name}")

        # Merge contexts
        full_context = {
            **context,
            'kiwi_rules': kiwi_rules or [],
            'blueprint_spec': blueprint_spec or {},
        }

        # Render template
        content = template.render(**full_context)

        # Post-process
        content = self._post_process(content, template_name)

        return content

    def _post_process(self, content: str, template_name: str) -> str:
        """
        Post-process generated content.

        - Remove extra blank lines
        - Ensure single trailing newline
        - Format PHP if applicable
        """
        # Remove multiple consecutive blank lines
        content = re.sub(r'\n{3,}', '\n\n', content)

        # Ensure single trailing newline
        content = content.rstrip() + '\n'

        # PHP-specific formatting
        if template_name.endswith('.php.j2'):
            content = self._format_php(content)

        return content

    def _format_php(self, content: str) -> str:
        """Basic PHP formatting."""
        # Only add <?php tag if content doesn't start with HTML or existing PHP tag
        # Template files (header.php, footer.php) start with HTML tags
        stripped = content.lstrip()
        if not stripped.startswith('<?php') and not stripped.startswith('<'):
            content = '<?php\n' + content

        # Remove spaces before semicolons
        content = re.sub(r'\s+;', ';', content)

        return content

    def validate_template(self, template_name: str) -> bool:
        """
        Validate template syntax.

        Returns:
            True if template is valid
        """
        try:
            self.env.get_template(template_name)
            return True
        except Exception as e:
            import sys
            print(f"[kiwi] validate_template error: {e}", file=sys.stderr)
            return False

    def list_templates(self, category: Optional[str] = None) -> list:
        """
        List available templates.

        Args:
            category: Filter by category (e.g., 'foundation', 'pages')

        Returns:
            List of template filenames
        """
        templates = []

        if category:
            category_dir = self.templates_dir / category
            if category_dir.exists():
                templates = [
                    f"{category}/{f.name}"
                    for f in category_dir.glob('*.j2')
                ]
        else:
            templates = [
                str(f.relative_to(self.templates_dir))
                for f in self.templates_dir.rglob('*.j2')
            ]

        return sorted(templates)


def render_template_string(template_str: str, context: Dict[str, Any]) -> str:
    """
    Render template from string (for testing).

    Args:
        template_str: Template content as string
        context: Variables to render

    Returns:
        Rendered content
    """
    env = Environment(trim_blocks=True, lstrip_blocks=True)
    template = env.from_string(template_str)
    return template.render(**context)