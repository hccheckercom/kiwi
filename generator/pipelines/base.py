"""
Base Pipeline — shared render + validate + write logic.

All generation pipelines inherit from this. Handles:
- Jinja2 template rendering via FileBuilder
- Multi-layer validation via Validator
- File writing with dry-run support
- Generation history tracking in SQLite
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
import time


@dataclass
class PipelineResult:
    """Result of a pipeline run."""
    theme_slug: str
    files_created: List[str] = field(default_factory=list)
    files_failed: List[Dict[str, str]] = field(default_factory=list)
    violations_found: int = 0
    violations_fixed: int = 0
    duration_seconds: float = 0.0
    success: bool = False
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "theme_slug": self.theme_slug,
            "files_created": self.files_created,
            "files_failed": self.files_failed,
            "violations_found": self.violations_found,
            "violations_fixed": self.violations_fixed,
            "duration_seconds": round(self.duration_seconds, 2),
            "success": self.success,
            "error": self.error,
        }


class BasePipeline:
    """
    Shared generation pipeline.

    Subclasses implement `build_context()` to provide template variables.
    Base handles rendering, validation, writing, and history tracking.
    """

    def __init__(self, dry_run: bool = False, auto_fix: bool = True):
        self.dry_run = dry_run
        self.auto_fix = auto_fix

        self.kiwi_dir = Path(__file__).parent.parent.parent
        self.generator_dir = Path(__file__).parent.parent
        self.templates_dir = self.generator_dir / "templates"

        from ..file_builder import FileBuilder
        from ..validator import Validator

        self.validator = Validator(self.kiwi_dir)
        self._builders: Dict[str, FileBuilder] = {}
        self._high_risk_cache: Optional[Dict[str, Any]] = None  # cached per pipeline run

    def _get_builder(self, template_subdir: str) -> "FileBuilder":
        """Get or create FileBuilder for a template subdirectory."""
        if template_subdir not in self._builders:
            from ..file_builder import FileBuilder
            self._builders[template_subdir] = FileBuilder(
                self.templates_dir / template_subdir
            )
        return self._builders[template_subdir]

    def render_file(
        self,
        template_subdir: str,
        template_name: str,
        context: Dict[str, Any],
    ) -> str:
        """Render a single template with context."""
        builder = self._get_builder(template_subdir)
        return builder.build_file(template_name, context)

    def validate_file(self, content: str, file_path: str) -> List[str]:
        """Run all validation layers on generated content. Returns list of issues."""
        issues = []

        # Layer 2: Content validation
        result = self.validator.validate_content(content, file_path)
        if not result:
            issues.append(result.message)

        # Layer 3: Kiwi scan (per-file, written to temp path)
        issues.extend(self.validate_with_kiwi(Path(file_path)))

        # Layer 4: GATE compliance
        result = self.validator.validate_gate_compliance(content, file_path)
        if not result:
            issues.append(result.message)

        return issues

    def validate_with_kiwi(self, file_path: Path) -> List[str]:
        """Layer 3: Kiwi scan. Returns list of issues."""
        try:
            result = self.validator.validate_with_kiwi(file_path)
            if not result:
                return [result.message]
        except Exception:
            pass
        return []

    def write_file(self, output_dir: Path, relative_path: str, content: str) -> bool:
        """Write file to disk. Returns True on success."""
        if self.dry_run:
            return True

        target = output_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return True

    def record_generation(
        self,
        theme_slug: str,
        file_path: str,
        template_used: str,
        violations: int = 0,
        fix_count: int = 0,
        quality_score: float = 1.0,
        pipeline: str = "",
        phase: str = "",
        duration_ms: int = 0,
    ):
        """Record generation in history table."""
        try:
            import sys
            sys.path.insert(0, str(self.kiwi_dir))
            from memory.db import get_connection

            conn = get_connection()
            conn.execute(
                """INSERT INTO generation_history
                   (theme_slug, file_path, template_used, generated_at,
                    violations_at_gen, fix_count, quality_score, pipeline, phase, duration_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    theme_slug, file_path, template_used,
                    datetime.now(timezone.utc).isoformat(),
                    violations, fix_count, quality_score, pipeline, phase, duration_ms,
                ),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _get_high_risk_context(self, theme_slug: str, template_name: str) -> Dict[str, Any]:
        """Query generation history for high-risk sections to inject into template context.
        Result is cached per pipeline instance to avoid N DB queries for N files."""
        if self._high_risk_cache is None:
            try:
                import sys
                sys.path.insert(0, str(self.kiwi_dir))
                from memory.db import get_high_risk_sections
                high_risk = get_high_risk_sections(theme_slug=theme_slug, top_n=5)
                self._high_risk_cache = {
                    "names": [r["template_used"] for r in high_risk if r["total_fixes"] > 0]
                }
            except Exception:
                self._high_risk_cache = {"names": []}
        names = self._high_risk_cache["names"]
        return {
            "high_risk_sections": names,
            "is_high_risk": template_name in names,
        }

    def _maybe_trigger_retrain(self, theme_slug: str):
        """Trigger kiwi_retrain_classifier after every 10 generations."""
        try:
            import sys
            sys.path.insert(0, str(self.kiwi_dir))
            from memory.db import get_generation_count
            count = get_generation_count()
            if count > 0 and count % 10 == 0:
                from generator.ml_retrain import MLRetrainer
                retrainer = MLRetrainer(self.kiwi_dir)
                retrainer.retrain(force=False)
        except Exception:
            pass

    def generate_file(
        self,
        output_dir: Path,
        theme_slug: str,
        template_subdir: str,
        template_name: str,
        output_name: str,
        context: Dict[str, Any],
        phase: str = "",
        pipeline_name: str = "",
    ) -> Optional[str]:
        """
        Full pipeline for a single file: render → validate → write → record.

        Layer 3 (Kiwi scan) is skipped per-file for performance.
        Use `scan_output()` after all files are generated.

        Returns output_name on success, None on failure.
        """
        start = time.time()

        # Inject high-risk section context for extra validation awareness
        risk_ctx = self._get_high_risk_context(theme_slug, template_name)
        context = {**context, **risk_ctx}

        # Render
        try:
            content = self.render_file(template_subdir, template_name, context)
        except Exception as e:
            return None

        # Validate (Layer 2 + Layer 4 only — fast checks)
        issues = self.validate_file(content, output_name)
        violations = len(issues)

        # Write
        if not self.write_file(output_dir, output_name, content):
            return None

        duration_ms = int((time.time() - start) * 1000)
        quality = 1.0 if violations == 0 else max(0.0, 1.0 - (violations * 0.1))

        # Record
        self.record_generation(
            theme_slug=theme_slug,
            file_path=output_name,
            template_used=template_name,
            violations=violations,
            quality_score=quality,
            pipeline=pipeline_name,
            phase=phase,
            duration_ms=duration_ms,
        )

        # Trigger retrain every 10 generations
        self._maybe_trigger_retrain(theme_slug)

        return output_name

    def scan_output(self, output_dir: Path) -> List[str]:
        """Run Kiwi scan (Layer 3) once on the entire output directory."""
        return self.validate_with_kiwi(output_dir)

    def run(self, **kwargs) -> PipelineResult:
        """Override in subclasses."""
        raise NotImplementedError
