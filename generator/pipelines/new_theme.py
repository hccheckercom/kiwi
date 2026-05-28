"""
NewTheme Pipeline — generate theme from input_spec + optional industry DNA.

Replaces the old ThemeGenerator orchestrator with a Jinja2-only approach.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
import time

from .base import BasePipeline, PipelineResult


# G0 Foundation file manifest (template → output)
G0_FILES = {
    "T1-Config": [
        ("store-config.php.j2", "store-config.php"),
        ("design-tokens.json.j2", "design-tokens.json"),
        ("tailwind.config.js.j2", "tailwind.config.js"),
        ("package.json.j2", "package.json"),
        ("src/main.css.j2", "src/main.css"),
    ],
    "T2-Bootstrap": [
        ("style.css.j2", "style.css"),
        ("index.php.j2", "index.php"),
        ("functions.php.j2", "functions.php"),
        ("inc/helpers.php.j2", "inc/helpers.php"),
        ("inc/security.php.j2", "inc/security.php"),
        ("inc/setup.php.j2", "inc/setup.php"),
        ("inc/seo.php.j2", "inc/seo.php"),
    ],
    "T3-Layout": [
        ("header.php.j2", "header.php"),
        ("footer.php.j2", "footer.php"),
        ("inc/cart.php.j2", "inc/cart.php"),
        ("assets/js/main.js.j2", "assets/js/main.js"),
    ],
}

# G1 Page templates (template → output)
G1_PAGES = {
    "cap1-shop": [
        ("front-page.php.j2", "front-page.php"),
        ("archive-wz_product.php.j2", "archive-wz_product.php"),
        ("single-wz_product.php.j2", "single-wz_product.php"),
        ("page-search.php.j2", "page-search.php"),
        ("page-cart.php.j2", "page-cart.php"),
        ("page-checkout.php.j2", "page-checkout.php"),
        ("page-thank-you.php.j2", "page-thank-you.php"),
        ("page-order-failed.php.j2", "page-order-failed.php"),
    ],
    "cap1-account": [
        ("page-register.php.j2", "page-register.php"),
        ("page-login.php.j2", "page-login.php"),
        ("page-verify-email.php.j2", "page-verify-email.php"),
        ("page-forgot-password.php.j2", "page-forgot-password.php"),
        ("404.php.j2", "404.php"),
        ("page-maintenance.php.j2", "page-maintenance.php"),
    ],
    "cap1-gmc": [
        ("page-chinh-sach-van-chuyen.php.j2", "page-chinh-sach-van-chuyen.php"),
        ("page-chinh-sach-doi-tra.php.j2", "page-chinh-sach-doi-tra.php"),
        ("page-chinh-sach-bao-mat.php.j2", "page-chinh-sach-bao-mat.php"),
        ("page-dieu-khoan.php.j2", "page-dieu-khoan.php"),
        ("page-lien-he.php.j2", "page-lien-he.php"),
    ],
    "cap2": [
        ("wezone-templates/account/dashboard.php.j2", "wezone-templates/account/dashboard.php"),
        ("wezone-templates/account/profile.php.j2", "wezone-templates/account/profile.php"),
        ("wezone-templates/account/addresses.php.j2", "wezone-templates/account/addresses.php"),
        ("wezone-templates/account/change-password.php.j2", "wezone-templates/account/change-password.php"),
        ("wezone-templates/account/notifications.php.j2", "wezone-templates/account/notifications.php"),
        ("wezone-templates/account/vouchers.php.j2", "wezone-templates/account/vouchers.php"),
        ("wezone-templates/account/orders.php.j2", "wezone-templates/account/orders.php"),
        ("wezone-templates/account/order-detail.php.j2", "wezone-templates/account/order-detail.php"),
        ("wezone-templates/account/tracking.php.j2", "wezone-templates/account/tracking.php"),
        ("wezone-templates/account/returns.php.j2", "wezone-templates/account/returns.php"),
        ("wezone-templates/account/wishlist.php.j2", "wezone-templates/account/wishlist.php"),
        ("wezone-templates/account/compare.php.j2", "wezone-templates/account/compare.php"),
        ("page-huong-dan-chuyen-khoan.php.j2", "page-huong-dan-chuyen-khoan.php"),
        ("page-huong-dan-thanh-toan.php.j2", "page-huong-dan-thanh-toan.php"),
        ("page-huong-dan-mua-hang.php.j2", "page-huong-dan-mua-hang.php"),
        ("page-gioi-thieu.php.j2", "page-gioi-thieu.php"),
        ("page-faq.php.j2", "page-faq.php"),
        ("403.php.j2", "403.php"),
        ("500.php.j2", "500.php"),
        ("page-sitemap.php.j2", "page-sitemap.php"),
    ],
    "cap3": [
        ("wezone-templates/account/wallet.php.j2", "wezone-templates/account/wallet.php"),
        ("wezone-templates/account/loyalty-points.php.j2", "wezone-templates/account/loyalty-points.php"),
        ("page-flash-sale.php.j2", "page-flash-sale.php"),
        ("page-landing.php.j2", "page-landing.php"),
        ("home.php.j2", "home.php"),
        ("single.php.j2", "single.php"),
        ("page-thuong-hieu.php.j2", "page-thuong-hieu.php"),
        ("page-khach-than-thiet.php.j2", "page-khach-than-thiet.php"),
        ("page-gioi-thieu-ban.php.j2", "page-gioi-thieu-ban.php"),
        ("page-danh-gia.php.j2", "page-danh-gia.php"),
    ],
}


class NewThemePipeline(BasePipeline):
    """
    Generate a new theme from input_spec (colors, fonts, shop name).

    Optionally uses industry DNA for design suggestions.
    """

    PIPELINE_NAME = "new_theme"

    def __init__(self, dry_run: bool = False, auto_fix: bool = True):
        super().__init__(dry_run=dry_run, auto_fix=auto_fix)

    def run(
        self,
        theme_name: str,
        input_spec: Dict[str, Any],
        phases: Optional[List[str]] = None,
        industry: Optional[str] = None,
        output_base: Optional[Path] = None,
    ) -> PipelineResult:
        """
        Generate theme.

        Args:
            theme_name: Human-readable name (e.g., "My Beauty Shop")
            input_spec: Required keys: shop_name, primary_color, secondary_color, font_family
            phases: Which phases to generate (default: ['G0', 'G1'])
            industry: Optional industry for DNA suggestions
            output_base: Base directory for output (default: themes/)
        """
        if phases is None:
            phases = ["G0", "G1"]

        theme_slug = self._slugify(theme_name)
        output_dir = (output_base or Path("themes")) / theme_slug
        result = PipelineResult(theme_slug=theme_slug)
        start = time.time()

        try:
            self._validate_input_spec(input_spec)

            context = self._build_context(input_spec, theme_slug, industry)

            if not self.dry_run:
                output_dir.mkdir(parents=True, exist_ok=True)

            if "G0" in phases:
                self._generate_g0(output_dir, theme_slug, context, result)

            if "G1" in phases:
                self._generate_g1(output_dir, theme_slug, context, result, phases)

            result.success = len(result.files_failed) == 0

        except Exception as e:
            result.success = False
            result.error = str(e)

        result.duration_seconds = time.time() - start
        return result

    def _slugify(self, name: str) -> str:
        return name.lower().replace(" ", "-").replace("_", "-")

    def _validate_input_spec(self, spec: Dict[str, Any]):
        required = ["shop_name", "primary_color", "secondary_color", "font_family"]
        missing = [f for f in required if f not in spec]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

    def _build_context(
        self, input_spec: Dict[str, Any], theme_slug: str, industry: Optional[str]
    ) -> Dict[str, Any]:
        """Build Jinja2 template context from input spec + industry DNA."""
        from ..data_bindings import COMPONENT_BINDINGS

        context = {
            "theme_slug": theme_slug,
            "theme_name": input_spec["shop_name"],
            "shop_name": input_spec["shop_name"],
            "primary_color": input_spec["primary_color"],
            "secondary_color": input_spec["secondary_color"],
            "font_family": input_spec["font_family"],
            "bindings": COMPONENT_BINDINGS,
        }

        if industry:
            context["industry"] = industry
            dna = self._load_industry_dna(industry)
            if dna:
                context["dna"] = dna

        return context

    def _load_industry_dna(self, industry: str) -> Optional[Dict[str, Any]]:
        """Load industry DNA profile from variations."""
        dna_path = self.kiwi_dir.parent / "blueprint" / "variations" / "dna" / f"{industry}.md"
        if not dna_path.exists():
            return None
        try:
            content = dna_path.read_text(encoding="utf-8")
            return {"raw": content, "industry": industry}
        except Exception:
            return None

    def _generate_g0(
        self,
        output_dir: Path,
        theme_slug: str,
        context: Dict[str, Any],
        result: PipelineResult,
    ):
        """Generate G0 Foundation (16 files)."""
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
        phases: List[str],
    ):
        """Generate G1 Pages."""
        page_filter = None
        for p in phases:
            if p.startswith("G1:"):
                page_filter = p.split(":")[1]

        for group, files in G1_PAGES.items():
            if page_filter and group != page_filter:
                continue

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
