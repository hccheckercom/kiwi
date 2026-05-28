"""
CloneTheme Pipeline — generate theme from demo HTML + DESIGN.md.

Extracts design tokens from demo, then applies them onto blueprint templates.
Replaces the old DemoThemeGenerator/demo_orchestrator.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
import time

from .base import BasePipeline, PipelineResult
from .new_theme import G0_FILES, G1_PAGES


class CloneThemePipeline(BasePipeline):
    """
    Generate theme by extracting tokens from demo HTML and applying to templates.

    Flow: demo HTML → token extraction → context building → template rendering
    """

    PIPELINE_NAME = "clone_theme"

    def __init__(self, dry_run: bool = False, auto_fix: bool = True):
        super().__init__(dry_run=dry_run, auto_fix=auto_fix)

    def run(
        self,
        demo_path: str,
        theme_name: str,
        mode: str = "foundation",
        confidence_threshold: float = 0.7,
        output_base: Optional[Path] = None,
    ) -> PipelineResult:
        """
        Generate theme from demo folder.

        Args:
            demo_path: Path to demo folder (contains code.html, DESIGN.md, screen.png)
            theme_name: Target theme slug (e.g., "sfvn-institutional")
            mode: "tokens-only" | "foundation" | "full"
            confidence_threshold: Min confidence for auto-applying detected components
            output_base: Base directory for output (default: themes/)
        """
        theme_slug = theme_name.lower().replace(" ", "-").replace("_", "-")
        output_dir = (output_base or Path("themes")) / theme_slug
        result = PipelineResult(theme_slug=theme_slug)
        start = time.time()

        try:
            demo = Path(demo_path)
            if not demo.exists():
                raise FileNotFoundError(f"Demo path not found: {demo_path}")

            tokens = self._extract_tokens(demo)
            context = self._build_context(tokens, theme_slug, theme_name)

            if not self.dry_run:
                output_dir.mkdir(parents=True, exist_ok=True)

            if mode in ("foundation", "full"):
                self._generate_g0(output_dir, theme_slug, context, result)

            if mode == "full":
                self._generate_g1(output_dir, theme_slug, context, result)

            result.success = len(result.files_failed) == 0

        except Exception as e:
            result.success = False
            result.error = str(e)

        result.duration_seconds = time.time() - start
        return result

    def _extract_tokens(self, demo_path: Path) -> Dict[str, Any]:
        """Extract design tokens from demo HTML + DESIGN.md."""
        from ..parsers import DesignTokenExtractor

        extractor = DesignTokenExtractor()

        html_file = demo_path / "code.html"
        if not html_file.exists():
            for candidate in ("index.html", "demo.html"):
                alt = demo_path / candidate
                if alt.exists():
                    html_file = alt
                    break

        tokens = {}
        if html_file.exists():
            html_content = html_file.read_text(encoding="utf-8")
            tokens = extractor.extract(html_content)

        design_md = demo_path / "DESIGN.md"
        if design_md.exists():
            design_content = design_md.read_text(encoding="utf-8")
            design_tokens = self._parse_design_md(design_content)
            tokens = self._merge_tokens(tokens, design_tokens)

        return tokens

    def _parse_design_md(self, content: str) -> Dict[str, Any]:
        """Parse DESIGN.md for explicit token definitions."""
        import re

        tokens = {}

        color_match = re.search(r'primary[:\s]+([#\w]+)', content, re.IGNORECASE)
        if color_match:
            tokens["primary_color"] = color_match.group(1)

        secondary_match = re.search(r'secondary[:\s]+([#\w]+)', content, re.IGNORECASE)
        if secondary_match:
            tokens["secondary_color"] = secondary_match.group(1)

        font_match = re.search(r'font[:\s]+([^\n,]+)', content, re.IGNORECASE)
        if font_match:
            tokens["font_family"] = font_match.group(1).strip()

        name_match = re.search(r'shop[_ ]?name[:\s]+([^\n]+)', content, re.IGNORECASE)
        if name_match:
            tokens["shop_name"] = name_match.group(1).strip()

        return tokens

    def _merge_tokens(self, extracted: Dict, design_md: Dict) -> Dict:
        """Merge tokens — DESIGN.md overrides extracted values."""
        merged = {**extracted}
        for key, value in design_md.items():
            if value:
                merged[key] = value
        return merged

    def _build_context(
        self, tokens: Dict[str, Any], theme_slug: str, theme_name: str
    ) -> Dict[str, Any]:
        """Build Jinja2 context from extracted tokens."""
        from ..data_bindings import COMPONENT_BINDINGS

        return {
            "theme_slug": theme_slug,
            "theme_name": theme_name,
            "shop_name": tokens.get("shop_name", theme_name),
            "primary_color": tokens.get("primary_color", "#3b82f6"),
            "secondary_color": tokens.get("secondary_color", "#8b5cf6"),
            "font_family": tokens.get("font_family", "Inter, sans-serif"),
            "bindings": COMPONENT_BINDINGS,
            "tokens": tokens,
        }

    def _generate_g0(
        self,
        output_dir: Path,
        theme_slug: str,
        context: Dict[str, Any],
        result: PipelineResult,
    ):
        """Generate G0 Foundation."""
        for tier, files in G0_FILES.items():
            for template_name, output_name in files:
                out = self.generate_file(
                    output_dir=output_dir,
                    theme_slug=theme_slug,
                    template_subdir="foundation",
                    template_name=template_name,
                    output_name=output_name,
                    context=context,
                    phase="G0",
                    pipeline_name=self.PIPELINE_NAME,
                )
                if out:
                    result.files_created.append(out)
                else:
                    result.files_failed.append(
                        {"file": output_name, "template": template_name, "tier": tier}
                    )

    def _generate_g1(
        self,
        output_dir: Path,
        theme_slug: str,
        context: Dict[str, Any],
        result: PipelineResult,
    ):
        """Generate G1 Pages."""
        for group, files in G1_PAGES.items():
            for template_name, output_name in files:
                out = self.generate_file(
                    output_dir=output_dir,
                    theme_slug=theme_slug,
                    template_subdir="pages",
                    template_name=template_name,
                    output_name=output_name,
                    context=context,
                    phase="G1",
                    pipeline_name=self.PIPELINE_NAME,
                )
                if out:
                    result.files_created.append(out)
                else:
                    result.files_failed.append(
                        {"file": output_name, "template": template_name, "group": group}
                    )
