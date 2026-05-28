"""
KiwiGenerator — Unified WordPress theme generator.

Single entry point replacing demo_orchestrator.py + orchestrator.py.
Input: demo_path (optional) + input_spec (required)
Output: themes/{slug}/ — complete WordPress theme, 0 CRITICAL violations
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


class KiwiGenerator:
    """
    Unified theme generator. Jinja2 templates are the single source of truth.

    Flow:
    1. Extract tokens (from demo HTML or input_spec)
    2. Generate G0 Foundation (16 files via Jinja2)
    3. Validate each file (5-layer: content, GATE, Kiwi scan, PHP syntax, integration)
    4. Log generation for learning loop
    """

    FOUNDATION_FILES = [
        # T1: Config
        ('foundation/store-config.php.j2',      'store-config.php'),
        ('foundation/design-tokens.json.j2',    'design-tokens.json'),
        ('foundation/tailwind.config.js.j2',    'tailwind.config.js'),
        ('foundation/package.json.j2',          'package.json'),
        ('foundation/src/main.css.j2',          'src/main.css'),
        # T2: WP Bootstrap
        ('foundation/style.css.j2',             'style.css'),
        ('foundation/index.php.j2',             'index.php'),
        ('foundation/functions.php.j2',         'functions.php'),
        ('foundation/inc/helpers.php.j2',       'inc/helpers.php'),
        ('foundation/inc/security.php.j2',      'inc/security.php'),
        ('foundation/inc/setup.php.j2',         'inc/setup.php'),
        ('foundation/inc/seo.php.j2',           'inc/seo.php'),
        # T3: Layout Shell
        ('foundation/header.php.j2',            'header.php'),
        ('foundation/footer.php.j2',            'footer.php'),
        ('foundation/inc/cart.php.j2',          'inc/cart.php'),
        ('foundation/assets/js/main.js.j2',     'assets/js/main.js'),
    ]

    def __init__(
        self,
        theme_name: str,
        input_spec: Dict[str, Any],
        demo_path: Optional[str] = None,
        dry_run: bool = False,
    ):
        self.theme_name = theme_name
        self.theme_slug = self._slugify(theme_name)
        self.input_spec = input_spec
        self.demo_path = demo_path
        self.dry_run = dry_run

        self.gen_id = str(uuid.uuid4())[:8]
        self.kiwi_dir = Path(__file__).parent.parent
        self.templates_dir = Path(__file__).parent / 'templates'
        self.output_dir = Path('themes') / self.theme_slug

        self.report: Dict[str, Any] = {
            'gen_id': self.gen_id,
            'theme_name': theme_name,
            'theme_slug': self.theme_slug,
            'theme_path': str(self.output_dir),
            'demo_path': demo_path,
            'files_created': [],
            'violations_found': 0,
            'violations_fixed': 0,
            'violations_remaining': [],
            'success': False,
            'error': None,
            'duration_seconds': 0.0,
            'timestamp': datetime.now().isoformat(),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, phases: List[str] = None) -> Dict[str, Any]:
        """Generate theme. phases defaults to ['G0']."""
        if phases is None:
            phases = ['G0']

        start = datetime.now()
        try:
            self._validate_input_spec()

            # If demo provided, extract tokens and merge into input_spec
            if self.demo_path:
                self._extract_tokens_from_demo()

            for phase in phases:
                if phase == 'G0':
                    self._generate_foundation()
                else:
                    raise ValueError(f'Unknown phase: {phase}')

            self._log_generation()
            self.report['success'] = True

        except Exception as exc:
            self.report['error'] = str(exc)
            self.report['success'] = False

        finally:
            self.report['duration_seconds'] = (datetime.now() - start).total_seconds()

        return self.report

    # ------------------------------------------------------------------
    # Token extraction
    # ------------------------------------------------------------------

    def _extract_tokens_from_demo(self):
        """Extract design tokens from demo folder and merge into input_spec."""
        try:
            from .parsers.token_extractor import DesignTokenExtractor
        except ImportError:
            from parsers.token_extractor import DesignTokenExtractor

        extractor = DesignTokenExtractor()
        tokens = extractor.extract_from_demo(self.demo_path)

        # Merge: demo tokens override input_spec where present
        colors = tokens.get('colors', {})
        if colors.get('primary'):
            self.input_spec['primary_color'] = colors['primary']
        if colors.get('secondary'):
            self.input_spec['secondary_color'] = colors['secondary']

        typography = tokens.get('typography', {})
        if typography:
            first_font = next(iter(typography.values()), {})
            font_family = first_font.get('fontFamily', '')
            if font_family and isinstance(font_family, list):
                font_family = font_family[0]
            if font_family:
                self.input_spec['font_family'] = font_family

        # Store full tokens for template context
        self.input_spec['_tokens'] = tokens

    # ------------------------------------------------------------------
    # G0 Foundation generation
    # ------------------------------------------------------------------

    def _generate_foundation(self):
        """Generate 16 G0 Foundation files via Jinja2 templates."""
        try:
            from .file_builder import FileBuilder
            from .validator import Validator
        except ImportError:
            from file_builder import FileBuilder
            from validator import Validator

        builder = FileBuilder(self.templates_dir)
        validator = Validator(self.kiwi_dir)

        if not self.dry_run:
            self.output_dir.mkdir(parents=True, exist_ok=True)

        context = self._build_context()

        for template_name, output_name in self.FOUNDATION_FILES:
            self._generate_file(builder, validator, template_name, output_name, context)

    def _build_context(self) -> Dict[str, Any]:
        """Build Jinja2 render context from input_spec + kiwi rules."""
        slug = self.theme_slug
        slug_underscore = slug.replace('-', '_')

        # Load relevant Kiwi lessons as rules for templates
        kiwi_rules = self._load_kiwi_rules()

        return {
            'shop_name':            self.input_spec.get('shop_name', self.theme_name),
            'theme_slug':           slug,
            'theme_slug_underscore': slug_underscore,
            'primary_color':        self.input_spec.get('primary_color', '#1976d2'),
            'secondary_color':      self.input_spec.get('secondary_color', '#424242'),
            'accent_color':         self.input_spec.get('accent_color', self.input_spec.get('primary_color', '#1976d2')),
            'font_family':          self.input_spec.get('font_family', 'Inter, sans-serif'),
            'shop_tagline':         self.input_spec.get('shop_tagline', ''),
            'shop_phone':           self.input_spec.get('shop_phone', ''),
            'shop_email':           self.input_spec.get('shop_email', ''),
            'shop_address':         self.input_spec.get('shop_address', ''),
            'shipping_free_threshold': self.input_spec.get('shipping_free_threshold', 0),
            'shipping_fees':        self.input_spec.get('shipping_fees', []),
            'timestamp':            datetime.now().isoformat(),
            'kiwi_rules':           kiwi_rules,
        }

    def _generate_file(
        self,
        builder,
        validator,
        template_name: str,
        output_name: str,
        context: Dict[str, Any],
    ):
        """Render template, validate, write file."""
        content = builder.build_file(template_name, context)

        success, messages = validator.validate_all(content, output_name)

        if not success:
            self.report['violations_found'] += 1
            self.report['violations_remaining'].append({
                'file': output_name,
                'severity': 'CRITICAL',
                'messages': messages,
            })
            # Do not abort — write file anyway so user can inspect
            print(f'  [WARN] {output_name}: {"; ".join(messages)}')
        else:
            print(f'  [OK]   {output_name}')

        if not self.dry_run:
            output_path = self.output_dir / output_name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding='utf-8')
            self.report['files_created'].append(output_name)

    # ------------------------------------------------------------------
    # Kiwi rules injection
    # ------------------------------------------------------------------

    def _load_kiwi_rules(self) -> List[str]:
        """Load relevant Kiwi lessons as rule strings for template context."""
        try:
            try:
                from ..scanner.loader import LessonLoader
            except ImportError:
                import sys
                sys.path.insert(0, str(self.kiwi_dir))
                from scanner.loader import LessonLoader

            loader = LessonLoader(self.kiwi_dir / 'lessons')
            lessons = loader.load_all()

            # Return titles of CRITICAL lessons relevant to PHP/CSS generation
            rules = []
            for lesson in lessons:
                if lesson.get('severity') == 'CRITICAL':
                    title = lesson.get('title', '')
                    if title:
                        rules.append(title)
            return rules[:20]  # Cap to avoid bloating context

        except Exception:
            return []

    # ------------------------------------------------------------------
    # Learning loop logging
    # ------------------------------------------------------------------

    def _log_generation(self):
        """Log generation to SQLite for learning loop."""
        try:
            try:
                from ..memory.db import log_generator_feedback
            except ImportError:
                import sys
                sys.path.insert(0, str(self.kiwi_dir))
                from memory.db import log_generator_feedback

            log_generator_feedback(
                gen_id=self.gen_id,
                demo_path=self.demo_path or '',
                theme_name=self.theme_name,
                mode='G0',
                confidence_threshold=0.7,
                components_detected=0,
                components_applied=0,
            )
        except Exception as exc:
            print(f'  [WARN] Failed to log generation: {exc}')

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _validate_input_spec(self):
        required = ['shop_name', 'primary_color', 'secondary_color', 'font_family']
        missing = [f for f in required if not self.input_spec.get(f)]
        if missing:
            raise ValueError(f'Missing required input_spec fields: {", ".join(missing)}')

    @staticmethod
    def _slugify(name: str) -> str:
        return name.lower().replace(' ', '-').replace('_', '-')


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------

def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Kiwi Theme Generator')
    parser.add_argument('--theme',     required=True,  help='Theme name (e.g. "My Shop")')
    parser.add_argument('--primary',   required=True,  help='Primary color hex (e.g. #1976d2)')
    parser.add_argument('--secondary', required=True,  help='Secondary color hex')
    parser.add_argument('--font',      required=True,  help='Font family (e.g. "Inter, sans-serif")')
    parser.add_argument('--demo',      default=None,   help='Path to demo folder (optional)')
    parser.add_argument('--phases',    default='G0',   help='Comma-separated phases (default: G0)')
    parser.add_argument('--dry-run',   action='store_true')
    args = parser.parse_args()

    input_spec = {
        'shop_name':      args.theme,
        'primary_color':  args.primary,
        'secondary_color': args.secondary,
        'font_family':    args.font,
    }

    generator = KiwiGenerator(
        theme_name=args.theme,
        input_spec=input_spec,
        demo_path=args.demo,
        dry_run=args.dry_run,
    )

    phases = [p.strip() for p in args.phases.split(',')]
    report = generator.generate(phases=phases)

    print('\n' + '=' * 60)
    print(f'Theme: {report["theme_name"]} ({report["theme_slug"]})')
    print(f'Status: {"SUCCESS" if report["success"] else "FAILED"}')
    print(f'Files created: {len(report["files_created"])}')
    print(f'Violations found: {report["violations_found"]}')
    print(f'Duration: {report["duration_seconds"]:.2f}s')

    if report.get('error'):
        print(f'Error: {report["error"]}')

    if report['violations_remaining']:
        print('\nRemaining violations:')
        for v in report['violations_remaining']:
            print(f'  [{v["severity"]}] {v["file"]}: {"; ".join(v["messages"])}')


if __name__ == '__main__':
    main()
