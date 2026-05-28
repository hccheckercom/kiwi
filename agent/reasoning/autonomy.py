"""R6 — Graduated Autonomy: trust score -> output level -> code generation."""

from dataclasses import dataclass, field
from pathlib import Path

from .output import KiwiOutput


@dataclass
class GraduatedOutput:
    brief: KiwiOutput
    level: str
    code: str | None = None
    confidence: float = 0.0
    apply_instruction: str = ""
    changes_from_reference: list = field(default_factory=list)


COMPLEXITY_PENALTY = {
    'checkout_page': 0.05,
    'account_page': 0.05,
    'product_page': 0.03,
    'cart_page': 0.03,
    'order_page': 0.03,
    'fix_css': 0.0,
    'add_component': 0.0,
    'hero_component': 0.0,
    'header_component': 0.0,
    'footer_component': 0.0,
}


def determine_output_level(trust_score: float, task_type: str, theme: str = '') -> str:
    penalty = COMPLEXITY_PENALTY.get(task_type, 0.02)
    effective_trust = trust_score - penalty

    if 0.55 <= effective_trust <= 0.65:
        try:
            from .thinker import think
            result = think('borderline_trust', {
                'trust_score': effective_trust,
                'threshold': 0.6,
                'task_type': task_type,
                'theme': theme,
                'signals': f'penalty={penalty}',
            })
            if result and result.confidence >= 0.7 and result.decision == 'generate':
                return "skeleton"
            elif result and result.confidence >= 0.7 and result.decision == 'brief_only':
                return "brief_only"
        except Exception:
            pass

    if effective_trust >= 0.95:
        return "ready"
    elif effective_trust >= 0.85:
        return "draft"
    elif effective_trust >= 0.6:
        return "skeleton"
    return "brief_only"


def generate_graduated_output(brief: KiwiOutput, theme_path: str) -> GraduatedOutput:
    task_type = brief.content.get('target', 'generic')
    theme_name = Path(theme_path).name
    level = determine_output_level(brief.trust_score, task_type, theme_name)

    if level in ("draft", "ready"):
        from .approval_tracker import should_attempt_level
        if not should_attempt_level(task_type, level):
            level = "skeleton" if level == "draft" else "draft"

    output = GraduatedOutput(brief=brief, level=level)

    if level == "brief_only":
        return output

    from .code_drafter import generate_skeleton, generate_draft, generate_final

    if level == "skeleton":
        output.code = generate_skeleton(brief, theme_path)
        output.confidence = brief.trust_score * 0.7
    elif level == "draft":
        draft = generate_draft(brief, theme_path)
        output.code = draft['code']
        output.confidence = brief.trust_score * 0.9
        output.changes_from_reference = draft.get('changes', [])
    elif level == "ready":
        final = generate_final(brief, theme_path)
        output.code = final['code']
        output.confidence = brief.trust_score
        output.apply_instruction = f"Write to: {final['target_path']}"
        output.changes_from_reference = final.get('changes', [])

    if output.code:
        from .code_drafter import check_code_quality
        if not check_code_quality(output.code):
            output.level = "brief_only"
            output.code = None
            output.confidence = 0.0

    return output
