"""Demo Theme Generator Orchestrator — Generate theme from demo HTML/screenshot"""

import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    from .parsers import DesignTokenExtractor, ComponentDetector
    from .converters import StoreConfigGenerator, HTMLToPHPConverter
    from .converters.g0_foundation_generator import G0FoundationGenerator
    from .converters.g1_pages_generator import G1PagesGenerator
except ImportError:
    from parsers import DesignTokenExtractor, ComponentDetector
    from converters import StoreConfigGenerator, HTMLToPHPConverter
    from converters.g0_foundation_generator import G0FoundationGenerator
    from converters.g1_pages_generator import G1PagesGenerator


class DemoThemeGenerator:
    """
    Generate WordPress theme from demo HTML + DESIGN.md + screenshot.

    Usage:
        generator = DemoThemeGenerator()
        report = generator.generate_from_demo(
            demo_path="themes/sfvn/demos/demo3",
            theme_name="sfvn-institutional",
            mode="foundation"
        )
    """

    def __init__(self):
        self.token_extractor = DesignTokenExtractor()
        self.component_detector = ComponentDetector()
        self.html_to_php = HTMLToPHPConverter()

        # Token pipeline components
        try:
            from .tokens import normalize_tokens, validate_design_tokens, create_default_pipeline
            from .exporters import CSSExporter, SCSSExporter, PHPExporter, TailwindExporter
            self.use_new_pipeline = True
        except ImportError:
            self.use_new_pipeline = False

    def generate_from_demo(
        self,
        demo_path: str,
        theme_name: str,
        mode: str = "tokens-only",
        confidence_threshold: float = 0.7
    ) -> Dict[str, Any]:
        """
        Generate theme from demo folder.

        Args:
            demo_path: Path to demo folder (contains code.html, DESIGN.md)
            theme_name: Target theme name (e.g., "sfvn-institutional")
            mode: Generation mode
                - "tokens-only": Extract tokens only
                - "foundation": Tokens + G0 Foundation
                - "full": Tokens + G0 + G1 Pages
            confidence_threshold: Min confidence to auto-apply components

        Returns:
            Generation report with files created, components detected, violations
        """
        try:
            from .error_handler import Validator, ValidationError
        except ImportError:
            from error_handler import Validator, ValidationError

        # Validate inputs
        demo_validation = Validator.validate_demo_folder(demo_path)
        if not demo_validation["valid"]:
            return {
                "error": "Demo folder validation failed",
                "validation": demo_validation
            }

        theme_validation = Validator.validate_theme_name(theme_name)
        if not theme_validation["valid"]:
            return {
                "error": "Theme name validation failed",
                "validation": theme_validation
            }

        demo_dir = Path(demo_path)
        theme_dir = Path("themes") / theme_name

        gen_id = str(uuid.uuid4())[:8]

        # Create backup before generation
        backup_path = None
        try:
            try:
                from .rollback import GenerationRollback
            except ImportError:
                from rollback import GenerationRollback
            rollback_manager = GenerationRollback()
            backup_path = rollback_manager.create_backup(gen_id, str(theme_dir))
            if backup_path:
                print(f"  Created backup: {backup_path}")
        except Exception as e:
            print(f"Warning: Failed to create backup: {e}")

        report = {
            "gen_id": gen_id,
            "demo_path": demo_path,
            "theme_name": theme_name,
            "theme_path": str(theme_dir),
            "mode": mode,
            "confidence_threshold": confidence_threshold,
            "files_created": [],
            "components_detected": 0,
            "components_applied": 0,
            "components_manual_review": 0,
            "violations": [],
            "validation": {
                "demo": demo_validation,
                "theme": theme_validation
            }
        }

        # Step 1: Extract tokens
        print(f"[1/3] Extracting design tokens from {demo_path}...")
        try:
            legacy_tokens = self.token_extractor.extract_from_demo(demo_path)

            # Use new pipeline if available
            if self.use_new_pipeline:
                from .tokens import normalize_tokens, validate_design_tokens, create_default_pipeline
                from .exporters import CSSExporter, SCSSExporter, PHPExporter, TailwindExporter

                # Normalize to schema
                tokens = normalize_tokens(legacy_tokens)

                # Validate with new validator
                token_validation = validate_design_tokens(tokens.model_dump())
                report["validation"]["tokens"] = token_validation

                if not token_validation["valid"]:
                    report["error"] = "Design token validation failed"
                    return report

                # Transform (px→rem, sort)
                transformer = create_default_pipeline()
                transformed_tokens = transformer.apply(tokens)

                # Export to all formats
                css_exporter = CSSExporter()
                scss_exporter = SCSSExporter()
                php_exporter = PHPExporter()
                tailwind_exporter = TailwindExporter()

                # Save exports
                theme_dir.mkdir(parents=True, exist_ok=True)
                css_file = theme_dir / "assets" / "css" / "tokens.css"
                scss_file = theme_dir / "assets" / "scss" / "_tokens.scss"
                php_file = theme_dir / "inc" / "store-config.php"
                tailwind_file = theme_dir / "tailwind.config.js"

                css_file.parent.mkdir(parents=True, exist_ok=True)
                scss_file.parent.mkdir(parents=True, exist_ok=True)
                php_file.parent.mkdir(parents=True, exist_ok=True)

                css_exporter.export_to_file(transformed_tokens, str(css_file))
                scss_exporter.export_to_file(transformed_tokens, str(scss_file))
                php_exporter.export_to_file(transformed_tokens, str(php_file))
                tailwind_exporter.export_to_file(transformed_tokens, str(tailwind_file))

                report["files_created"].extend([
                    str(css_file),
                    str(scss_file),
                    str(php_file),
                    str(tailwind_file)
                ])

                print(f"  OK Exported to 4 formats (CSS, SCSS, PHP, Tailwind)")
            else:
                # Fallback to old system
                tokens = legacy_tokens

                # Validate tokens (old validator)
                try:
                    from .error_handler import Validator
                except ImportError:
                    from error_handler import Validator
                token_validation = Validator.validate_design_tokens(tokens)
                report["validation"]["tokens"] = token_validation

                if not token_validation["valid"]:
                    report["error"] = "Design token validation failed"
                    return report

                # Generate config files (old way)
                config_generator = StoreConfigGenerator(tokens)
                config_files = config_generator.save_to_theme(str(theme_dir))
                report["files_created"].extend(config_files.values())

        except Exception as e:
            report["error"] = f"Token extraction failed: {e}"
            return report

        if mode == "tokens-only":
            print(f"[2/3] Done (tokens-only mode)")
            return report

        # Step 3: Detect components
        html_path = demo_dir / "code.html"
        if not html_path.exists():
            report["error"] = f"code.html not found in {demo_path}"
            return report

        print(f"[3/3] Detecting components...")
        html_content = html_path.read_text(encoding="utf-8")
        components = self.component_detector.detect_components(html_content)

        report["components_detected"] = len(components)

        # Filter by confidence
        auto_apply = [c for c in components if c["confidence"] >= confidence_threshold]
        manual_review = [c for c in components if c["confidence"] < confidence_threshold]

        report["components_applied"] = len(auto_apply)
        report["components_manual_review"] = len(manual_review)

        # Generate PHP templates for auto-apply components
        if mode in ["foundation", "full"]:
            templates_dir = theme_dir / "templates"
            templates_dir.mkdir(parents=True, exist_ok=True)

            for i, component in enumerate(auto_apply[:10], 1):  # Limit to 10 for now
                php_code = self.html_to_php.convert_component(component)
                template_file = templates_dir / f"{component['type']}-{i}.php"
                template_file.write_text(php_code, encoding="utf-8")
                report["files_created"].append(str(template_file))

        # Step 4: Generate G0 Foundation (foundation and full modes)
        if mode in ["foundation", "full"]:
            print(f"[4/5] Generating G0 Foundation (16 files)...")
            try:
                g0_generator = G0FoundationGenerator(tokens, theme_name)
                g0_files = g0_generator.generate_all(theme_dir)
                report["files_created"].extend(g0_files)
                print(f"  Created {len(g0_files)} G0 Foundation files")
            except Exception as e:
                report["error"] = f"G0 Foundation generation failed: {e}"
                return report

        # Step 5: Generate G1 Pages (full mode only)
        if mode == "full":
            print(f"[5/5] Generating G1 Pages (11 files)...")
            try:
                g1_generator = G1PagesGenerator(tokens, components)
                g1_files = g1_generator.generate_all(theme_dir)
                report["files_created"].extend(g1_files)
                print(f"  Created {len(g1_files)} G1 Pages files")
            except Exception as e:
                report["error"] = f"G1 Pages generation failed: {e}"
                return report

        print(f"\nGeneration complete:")
        print(f"  Gen ID: {gen_id}")
        print(f"  Files created: {len(report['files_created'])}")
        print(f"  Components detected: {report['components_detected']}")
        print(f"  Auto-applied: {report['components_applied']}")
        print(f"  Manual review: {report['components_manual_review']}")

        # Validate generated PHP files
        php_files = [f for f in report['files_created'] if f.endswith('.php')]
        if php_files and mode in ["foundation", "full"]:
            try:
                try:
                    from .validators import PHPValidator
                except ImportError:
                    from validators import PHPValidator
                validator = PHPValidator()
                validation_results = validator.validate_batch(php_files)

                invalid_files = [f for f, (valid, _) in validation_results.items() if not valid]
                if invalid_files:
                    report['validation']['php'] = {
                        'valid': False,
                        'errors': [f"{f}: {err}" for f, (_, err) in validation_results.items() if not valid]
                    }
                    print(f"Warning: {len(invalid_files)} PHP files have syntax errors")
                else:
                    report['validation']['php'] = {'valid': True, 'errors': []}
            except Exception as e:
                print(f"Warning: PHP validation failed: {e}")

        # Log to feedback database
        try:
            try:
                from ..memory.db import log_generator_feedback, log_component_pattern
            except ImportError:
                import sys
                from pathlib import Path as PathLib
                sys.path.insert(0, str(PathLib(__file__).parent.parent))
                from memory.db import log_generator_feedback, log_component_pattern
            log_generator_feedback(
                gen_id=gen_id,
                demo_path=demo_path,
                theme_name=theme_name,
                mode=mode,
                confidence_threshold=confidence_threshold,
                components_detected=report['components_detected'],
                components_applied=report['components_applied']
            )

            # Log each detected component
            for comp in components:
                # Ensure 'html' key exists in component dict
                html_snippet = comp.get('html', comp.get('code', ''))[:500]
                log_component_pattern(
                    gen_id=gen_id,
                    component_type=comp['type'],
                    html_snippet=html_snippet,
                    confidence=comp['confidence'],
                    auto_applied=comp['confidence'] >= confidence_threshold
                )
        except Exception as e:
            print(f"Warning: Failed to log feedback: {e}")

        # Cleanup backup on success
        if backup_path:
            try:
                try:
                    from .rollback import GenerationRollback
                except ImportError:
                    from rollback import GenerationRollback
                rollback_manager = GenerationRollback()
                rollback_manager.cleanup_backup(backup_path)
            except Exception as e:
                print(f"Warning: Failed to cleanup backup: {e}")

        return report


def format_generation_report(report: Dict[str, Any]) -> str:
    """Format generation report for MCP tool output."""
    # Handle error case
    if "error" in report:
        lines = [
            f"Kiwi UI Generator V2 — Generation Failed",
            f"",
            f"Gen ID: {report.get('gen_id', 'N/A')}",
            f"Demo: {report.get('demo_path', 'N/A')}",
            f"Theme: {report.get('theme_name', 'N/A')}",
            f"Mode: {report.get('mode', 'N/A')}",
            f"",
            f"Error: {report['error']}",
        ]
        return "\n".join(lines)

    lines = [
        f"Kiwi UI Generator V2 — Generation Report",
        f"",
        f"Gen ID: {report.get('gen_id', 'N/A')}",
        f"Demo: {report.get('demo_path', 'N/A')}",
        f"Theme: {report.get('theme_name', 'N/A')} ({report.get('theme_path', 'N/A')})",
        f"Mode: {report.get('mode', 'N/A')}",
        f"",
        f"Files created: {len(report.get('files_created', []))}",
    ]

    for filepath in report.get("files_created", [])[:10]:  # Show first 10
        lines.append(f"  - {filepath}")

    if len(report.get("files_created", [])) > 10:
        lines.append(f"  ... and {len(report['files_created']) - 10} more")

    lines.append("")
    lines.append(f"Components detected: {report.get('components_detected', 0)}")
    lines.append(f"  Auto-applied (confidence >= {report.get('confidence_threshold', 0.7)}): {report.get('components_applied', 0)}")
    lines.append(f"  Manual review needed: {report.get('components_manual_review', 0)}")

    lines.append("")
    lines.append(f"To provide feedback: kiwi_feedback(gen_id='{report.get('gen_id', 'N/A')}', accepted=True/False, corrections='...')")

    if report.get("error"):
        lines.append("")
        lines.append(f"ERROR: {report['error']}")

    return "\n".join(lines)