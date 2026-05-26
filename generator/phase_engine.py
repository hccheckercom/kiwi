"""
Phase Engine

Orchestrates theme generation phases (G0 → G1 → G2).
Manages dependencies, parallel execution, and phase verification.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from enum import Enum


class PhaseStatus(Enum):
    """Phase execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PhaseLayer:
    """Single layer within a phase."""
    id: str  # e.g., "G0-T1", "G1-P1"
    name: str  # e.g., "Config Layer", "Home Page"
    files: List[Tuple[str, str]]  # [(template_name, output_name), ...]
    dependencies: List[str] = field(default_factory=list)  # Layer IDs this depends on
    verification: Optional[str] = None  # Verification method name
    status: PhaseStatus = PhaseStatus.PENDING


@dataclass
class Phase:
    """Theme generation phase."""
    id: str  # "G0", "G1", "G2"
    name: str  # "Foundation", "Pages", "Quality"
    layers: List[PhaseLayer]
    status: PhaseStatus = PhaseStatus.PENDING


class PhaseEngine:
    """
    Orchestrates multi-phase theme generation.

    Phases:
    - G0: Foundation (config, tokens, WP bootstrap, layout shell)
    - G1: Pages (19 core page templates)
    - G2: Quality (performance, SEO, a11y, dark mode)
    """

    def __init__(self):
        self.phases = self._define_phases()
        self.current_phase: Optional[str] = None
        self.current_layer: Optional[str] = None

    def _define_phases(self) -> Dict[str, Phase]:
        """Define all phases and their layers."""
        return {
            "G0": self._define_g0_foundation(),
            "G1": self._define_g1_pages(),
            "G2": self._define_g2_quality(),
        }

    def _define_g0_foundation(self) -> Phase:
        """
        G0: Foundation Phase

        Layers:
        - T1: Config (5 files)
        - T2: WP Bootstrap (8 files)
        - T3: Layout Shell (3 files)
        - T4: Integration (verification only)
        """
        return Phase(
            id="G0",
            name="Foundation",
            layers=[
                PhaseLayer(
                    id="G0-T1",
                    name="Config Layer",
                    files=[
                        ('store-config.php.j2', 'store-config.php'),
                        ('design-tokens.json.j2', 'design-tokens.json'),
                        ('tailwind.config.js.j2', 'tailwind.config.js'),
                        ('package.json.j2', 'package.json'),
                        ('src/main.css.j2', 'src/main.css'),
                    ],
                    verification="verify_tailwind_build"
                ),
                PhaseLayer(
                    id="G0-T2",
                    name="WP Bootstrap",
                    files=[
                        ('style.css.j2', 'style.css'),
                        ('index.php.j2', 'index.php'),
                        ('functions.php.j2', 'functions.php'),
                        ('inc/helpers.php.j2', 'inc/helpers.php'),
                        ('inc/security.php.j2', 'inc/security.php'),
                        ('inc/setup.php.j2', 'inc/setup.php'),
                        ('inc/seo.php.j2', 'inc/seo.php'),
                        ('inc/cart.php.j2', 'inc/cart.php'),
                    ],
                    dependencies=["G0-T1"],
                    verification="verify_theme_activation"
                ),
                PhaseLayer(
                    id="G0-T3",
                    name="Layout Shell",
                    files=[
                        ('header.php.j2', 'header.php'),
                        ('footer.php.j2', 'footer.php'),
                        ('assets/js/main.js.j2', 'assets/js/main.js'),
                    ],
                    dependencies=["G0-T2"],
                    verification="verify_responsive"
                ),
            ]
        )

    def _define_g1_pages(self) -> Phase:
        """
        G1: Pages Phase

        19 core page templates in priority order.
        """
        return Phase(
            id="G1",
            name="Pages",
            layers=[
                PhaseLayer(
                    id="G1-P1",
                    name="Home Page",
                    files=[
                        ('pages/front-page.php.j2', 'front-page.php'),
                        ('template-parts/hero/default.php.j2', 'template-parts/hero/default.php'),
                        ('template-parts/categories/grid.php.j2', 'template-parts/categories/grid.php'),
                        ('template-parts/flash-sale/banner.php.j2', 'template-parts/flash-sale/banner.php'),
                    ],
                    dependencies=["G0-T3"],
                ),
                PhaseLayer(
                    id="G1-P2",
                    name="Product Archive",
                    files=[
                        ('pages/archive-wz_product.php.j2', 'archive-wz_product.php'),
                        ('template-parts/product/card.php.j2', 'template-parts/product/card.php'),
                        ('template-parts/product/filters.php.j2', 'template-parts/product/filters.php'),
                    ],
                    dependencies=["G0-T3"],
                ),
                PhaseLayer(
                    id="G1-P3",
                    name="Product Detail",
                    files=[
                        ('pages/single-wz_product.php.j2', 'single-wz_product.php'),
                        ('template-parts/product/gallery.php.j2', 'template-parts/product/gallery.php'),
                        ('template-parts/product/tabs.php.j2', 'template-parts/product/tabs.php'),
                        ('template-parts/product/related.php.j2', 'template-parts/product/related.php'),
                    ],
                    dependencies=["G1-P2"],
                ),
                PhaseLayer(
                    id="G1-P4",
                    name="Checkout",
                    files=[
                        ('pages/page-checkout.php.j2', 'page-checkout.php'),
                        ('template-parts/checkout/progress-steps.php.j2', 'template-parts/checkout/progress-steps.php'),
                    ],
                    dependencies=["G1-P1"],
                ),
                PhaseLayer(
                    id="G1-P5",
                    name="Account Pages",
                    files=[
                        ('pages/page-register.php.j2', 'page-register.php'),
                    ],
                    dependencies=["G1-P1"],
                ),
                # More pages will be added in subsequent iterations
            ]
        )

    def _define_g2_quality(self) -> Phase:
        """
        G2: Quality Phase

        8 quality layers for production readiness.
        """
        return Phase(
            id="G2",
            name="Quality",
            layers=[
                PhaseLayer(
                    id="G2-Q1",
                    name="Design System",
                    files=[
                        ('quality/design-system.php.j2', 'inc/design-system.php'),
                    ],
                    dependencies=["G1-P1"],
                ),
                # Mock data removed - themes must use real Wezone Core
            ]
        )

    def get_phase(self, phase_id: str) -> Optional[Phase]:
        """Get phase by ID."""
        return self.phases.get(phase_id)

    def get_layer(self, layer_id: str) -> Optional[PhaseLayer]:
        """Get layer by ID (e.g., 'G0-T1')."""
        phase_id = layer_id.split('-')[0]
        phase = self.get_phase(phase_id)
        if not phase:
            return None

        for layer in phase.layers:
            if layer.id == layer_id:
                return layer
        return None

    def get_executable_layers(self, phase_id: str) -> List[PhaseLayer]:
        """
        Get layers that can be executed now (dependencies met).

        Returns layers in execution order.
        """
        phase = self.get_phase(phase_id)
        if not phase:
            return []

        executable = []
        for layer in phase.layers:
            if layer.status != PhaseStatus.PENDING:
                continue

            # Check if all dependencies are completed
            deps_met = all(
                self.get_layer(dep_id).status == PhaseStatus.COMPLETED
                for dep_id in layer.dependencies
            )

            if deps_met:
                executable.append(layer)

        return executable

    def mark_layer_status(self, layer_id: str, status: PhaseStatus):
        """Update layer status."""
        layer = self.get_layer(layer_id)
        if layer:
            layer.status = status

    def is_phase_complete(self, phase_id: str) -> bool:
        """Check if all layers in phase are completed."""
        phase = self.get_phase(phase_id)
        if not phase:
            return False

        return all(
            layer.status == PhaseStatus.COMPLETED
            for layer in phase.layers
        )

    def get_next_phase(self, current_phase_id: str) -> Optional[str]:
        """Get next phase ID after current phase completes."""
        phase_order = ["G0", "G1", "G2"]
        try:
            current_idx = phase_order.index(current_phase_id)
            if current_idx < len(phase_order) - 1:
                return phase_order[current_idx + 1]
        except ValueError:
            pass
        return None

    def reset_phase(self, phase_id: str):
        """Reset all layers in phase to PENDING."""
        phase = self.get_phase(phase_id)
        if phase:
            for layer in phase.layers:
                layer.status = PhaseStatus.PENDING
            phase.status = PhaseStatus.PENDING