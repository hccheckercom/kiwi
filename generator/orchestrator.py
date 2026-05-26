"""
Theme Generation Orchestrator

Main coordinator for WordPress theme generation.
Orchestrates phases, loads input specs, generates reports.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
import json
from datetime import datetime


@dataclass
class GenerationContext:
    """Context for theme generation."""
    theme_name: str
    theme_slug: str
    input_spec: Dict
    blueprint_dir: Path
    output_dir: Path
    platform: str = "wp"
    scope_type: str = "theme"
    auto_fix: bool = True
    dry_run: bool = False


@dataclass
class GenerationReport:
    """Report of theme generation."""
    theme_name: str
    phases_completed: List[str] = field(default_factory=list)
    files_created: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    violations_found: int = 0
    violations_fixed: int = 0
    violations_remaining: List[Dict] = field(default_factory=list)
    duration_seconds: float = 0.0
    success: bool = False
    error_message: str = ""

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "theme_name": self.theme_name,
            "phases_completed": self.phases_completed,
            "files_created": self.files_created,
            "files_modified": self.files_modified,
            "violations_found": self.violations_found,
            "violations_fixed": self.violations_fixed,
            "violations_remaining": self.violations_remaining,
            "duration_seconds": self.duration_seconds,
            "success": self.success,
            "error_message": self.error_message,
            "timestamp": datetime.now().isoformat()
        }


class ThemeGenerator:
    """
    Main theme generation orchestrator.

    Phase 1 (MVP): Foundation Generator (G0)
    - Generate config, design tokens, Tailwind pipeline, WP bootstrap
    - 15 foundation files with zero CRITICAL violations
    """

    def __init__(
        self,
        theme_name: str,
        input_spec: Dict,
        auto_fix: bool = True,
        dry_run: bool = False
    ):
        self.theme_name = theme_name
        self.theme_slug = self._slugify(theme_name)
        self.input_spec = input_spec
        self.auto_fix = auto_fix
        self.dry_run = dry_run

        # Paths
        self.kiwi_dir = Path(__file__).parent.parent
        self.blueprint_dir = self.kiwi_dir.parent / "blueprint"
        self.output_dir = Path("themes") / self.theme_slug

        # Context
        self.context = GenerationContext(
            theme_name=theme_name,
            theme_slug=self.theme_slug,
            input_spec=input_spec,
            blueprint_dir=self.blueprint_dir,
            output_dir=self.output_dir,
            auto_fix=auto_fix,
            dry_run=dry_run
        )

        # Report
        self.report = GenerationReport(theme_name=theme_name)

    def _slugify(self, name: str) -> str:
        """Convert theme name to slug."""
        return name.lower().replace(" ", "-").replace("_", "-")

    def generate(self, phases: List[str] = None) -> GenerationReport:
        """
        Generate theme for specified phases.

        Args:
            phases: List of phases to generate (default: ['G0'])

        Returns:
            GenerationReport with results
        """
        if phases is None:
            phases = ['G0']  # Phase 1 MVP: Foundation only

        start_time = datetime.now()

        try:
            # Validate input spec
            self._validate_input_spec()

            # Initialize phase engine (shared across all phases)
            from .phase_engine import PhaseEngine
            engine = PhaseEngine()

            # Generate phases
            for phase_id in phases:
                if phase_id == 'G0':
                    self._generate_foundation(engine)
                elif phase_id == 'G1':
                    self._generate_pages(engine)
                elif phase_id == 'G2':
                    self._generate_quality(engine)
                else:
                    raise ValueError(f"Unknown phase: {phase_id}")

                self.report.phases_completed.append(phase_id)

            self.report.success = True

        except Exception as e:
            self.report.success = False
            self.report.error_message = str(e)

        finally:
            end_time = datetime.now()
            self.report.duration_seconds = (end_time - start_time).total_seconds()

        return self.report

    def _validate_input_spec(self):
        """Validate input spec has required fields."""
        required_fields = [
            'shop_name',
            'primary_color',
            'secondary_color',
            'font_family'
        ]

        missing = [f for f in required_fields if f not in self.input_spec]
        if missing:
            raise ValueError(f"Missing required fields in input_spec: {', '.join(missing)}")

    def _generate_foundation(self, engine):
        """
        Generate G0 (Foundation) phase.

        Phase 1 MVP implementation:
        - T1: Config (store-config.php, design-tokens.json, tailwind.config.js)
        - T2: WP Bootstrap (style.css, functions.php, inc/*.php)
        - T3: Layout Shell (header.php, footer.php, inc/cart.php)
        - T4: Integration (verify CSS vars, wzTheme object)
        """
        from .file_builder import FileBuilder
        from .blueprint_reader import BlueprintReader
        from .validator import Validator
        from .phase_engine import PhaseStatus

        # Initialize components
        templates_dir = Path(__file__).parent / "templates" / "foundation"
        builder = FileBuilder(templates_dir)
        reader = BlueprintReader(self.blueprint_dir)
        validator = Validator(self.kiwi_dir)

        # Create output directory
        if not self.dry_run:
            self.output_dir.mkdir(parents=True, exist_ok=True)

        # T1: Config layer - 5 files
        t1_files = [
            ('store-config.php.j2', 'store-config.php'),
            ('design-tokens.json.j2', 'design-tokens.json'),
            ('tailwind.config.js.j2', 'tailwind.config.js'),
            ('package.json.j2', 'package.json'),
            ('src/main.css.j2', 'src/main.css'),
        ]

        for template_name, output_name in t1_files:
            self._generate_file(builder, validator, template_name, output_name)
        engine.mark_layer_status('G0-T1', PhaseStatus.COMPLETED)

        # T2: WP Bootstrap - 7 files
        t2_files = [
            ('style.css.j2', 'style.css'),
            ('index.php.j2', 'index.php'),
            ('functions.php.j2', 'functions.php'),
            ('inc/helpers.php.j2', 'inc/helpers.php'),
            ('inc/security.php.j2', 'inc/security.php'),
            ('inc/setup.php.j2', 'inc/setup.php'),
            ('inc/seo.php.j2', 'inc/seo.php'),
        ]

        for template_name, output_name in t2_files:
            self._generate_file(builder, validator, template_name, output_name)
        engine.mark_layer_status('G0-T2', PhaseStatus.COMPLETED)

        # T3: Layout Shell - 4 files
        t3_files = [
            ('header.php.j2', 'header.php'),
            ('footer.php.j2', 'footer.php'),
            ('inc/cart.php.j2', 'inc/cart.php'),
            ('assets/js/main.js.j2', 'assets/js/main.js'),
        ]

        for template_name, output_name in t3_files:
            self._generate_file(builder, validator, template_name, output_name)
        engine.mark_layer_status('G0-T3', PhaseStatus.COMPLETED)

        # Phase 1 MVP: T1 + T2 + T3 implemented (15 files total)
        # T4 (Integration verification) will be implemented next

    def _generate_pages(self, engine):
        """
        Generate G1 (Pages) phase using phase engine.

        Uses PhaseEngine to orchestrate page generation with dependency tracking.
        Each layer generates multiple files (page template + template-parts).
        """
        from .file_builder import FileBuilder
        from .validator import Validator
        from .phase_engine import PhaseStatus

        # Initialize components
        templates_dir = Path(__file__).parent / "templates"
        builder = FileBuilder(templates_dir)
        validator = Validator(self.kiwi_dir)

        # Get G1 phase
        g1_phase = engine.get_phase('G1')
        if not g1_phase:
            raise ValueError("G1 phase not found in engine")

        # Execute layers in dependency order
        while not engine.is_phase_complete('G1'):
            executable_layers = engine.get_executable_layers('G1')

            if not executable_layers:
                # No more executable layers but phase not complete = dependency deadlock
                pending = [l for l in g1_phase.layers if l.status == PhaseStatus.PENDING]
                if pending:
                    raise RuntimeError(
                        f"Dependency deadlock in G1: {len(pending)} layers pending but none executable"
                    )
                break

            for layer in executable_layers:
                print(f"\n=== Generating {layer.name} ({layer.id}) ===")
                engine.mark_layer_status(layer.id, PhaseStatus.IN_PROGRESS)

                try:
                    # Generate all files in this layer
                    for template_name, output_name in layer.files:
                        self._generate_file(builder, validator, template_name, output_name)

                    engine.mark_layer_status(layer.id, PhaseStatus.COMPLETED)
                    print(f"[OK] {layer.name} complete")

                except Exception as e:
                    engine.mark_layer_status(layer.id, PhaseStatus.FAILED)
                    raise RuntimeError(f"Failed to generate {layer.name}: {e}")

    def _generate_quality(self, engine):
        """
        Generate G2 (Quality) phase using phase engine.

        Adds quality layers: design system, performance, SEO, a11y.
        """
        from .file_builder import FileBuilder
        from .validator import Validator
        from .phase_engine import PhaseStatus

        # Initialize components
        templates_dir = Path(__file__).parent / "templates"
        builder = FileBuilder(templates_dir)
        validator = Validator(self.kiwi_dir)

        # Get G2 phase
        g2_phase = engine.get_phase('G2')
        if not g2_phase:
            raise ValueError("G2 phase not found in engine")

        # Execute layers in dependency order
        while not engine.is_phase_complete('G2'):
            executable_layers = engine.get_executable_layers('G2')

            if not executable_layers:
                # No more executable layers but phase not complete = dependency deadlock
                pending = [l for l in g2_phase.layers if l.status == PhaseStatus.PENDING]
                if pending:
                    raise RuntimeError(
                        f"Dependency deadlock in G2: {len(pending)} layers pending but none executable"
                    )
                break

            for layer in executable_layers:
                print(f"\n=== Generating {layer.name} ({layer.id}) ===")
                engine.mark_layer_status(layer.id, PhaseStatus.IN_PROGRESS)

                try:
                    # Generate all files in this layer
                    for template_name, output_name in layer.files:
                        self._generate_file(builder, validator, template_name, output_name)

                    engine.mark_layer_status(layer.id, PhaseStatus.COMPLETED)
                    print(f"[OK] {layer.name} complete")

                except Exception as e:
                    engine.mark_layer_status(layer.id, PhaseStatus.FAILED)
                    raise RuntimeError(f"Failed to generate {layer.name}: {e}") from e

    def _generate_file(
        self,
        builder,
        validator,
        template_name: str,
        output_name: str
    ):
        """Generate single file from template."""
        from datetime import datetime

        # Prepare context
        context = {
            **self.input_spec,
            'theme_slug': self.theme_slug,
            'theme_slug_underscore': self.theme_slug.replace('-', '_'),
            'timestamp': datetime.now().isoformat()
        }

        # Generate content
        content = builder.build_file(template_name, context)

        # Validate content
        success, messages = validator.validate_all(content, output_name)

        # Debug: print validation result
        print(f"  Validating {output_name}: {'PASS' if success else 'FAIL'}")
        if messages:
            for msg in messages:
                print(f"    - {msg}")

        if not success:
            self.report.violations_found += 1
            self.report.violations_remaining.append({
                'file': output_name,
                'severity': 'CRITICAL',
                'lesson_id': 'VALIDATION',
                'message': '; '.join(messages)
            })
            if not self.auto_fix:
                raise ValueError(f"Validation failed for {output_name}: {messages}")

        # Write file
        if not self.dry_run:
            output_path = self.output_dir / output_name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding='utf-8')
            self.report.files_created.append(output_name)


def format_generation_report(report: GenerationReport) -> str:
    """Format generation report for display."""
    lines = [
        f"# Theme Generation Report: {report.theme_name}",
        "",
        f"**Status:** {'SUCCESS' if report.success else 'FAILED'}",
        f"**Duration:** {report.duration_seconds:.2f}s",
        "",
        "## Phases Completed",
        ""
    ]

    if report.phases_completed:
        for phase in report.phases_completed:
            lines.append(f"- {phase}")
    else:
        lines.append("- None")

    lines.extend([
        "",
        "## Files",
        "",
        f"**Created:** {len(report.files_created)}",
        f"**Modified:** {len(report.files_modified)}",
        ""
    ])

    if report.files_created:
        lines.append("### Created Files")
        for f in report.files_created[:10]:  # Limit to 10
            lines.append(f"- {f}")
        if len(report.files_created) > 10:
            lines.append(f"- ... and {len(report.files_created) - 10} more")
        lines.append("")

    lines.extend([
        "## Violations",
        "",
        f"**Found:** {report.violations_found}",
        f"**Fixed:** {report.violations_fixed}",
        f"**Remaining:** {len(report.violations_remaining)}",
        ""
    ])

    if report.violations_remaining:
        lines.append("### Remaining Violations")
        for v in report.violations_remaining[:5]:  # Limit to 5
            lines.append(f"- [{v.get('severity')}] {v.get('lesson_id')}: {v.get('file')}")
        if len(report.violations_remaining) > 5:
            lines.append(f"- ... and {len(report.violations_remaining) - 5} more")
        lines.append("")

    if not report.success:
        lines.extend([
            "## Error",
            "",
            f"```\n{report.error_message}\n```"
        ])

    return "\n".join(lines)