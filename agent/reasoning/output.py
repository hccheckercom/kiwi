"""R1 — Output formatter: KiwiOutput dataclass for Claude consumption."""

from dataclasses import dataclass, field


@dataclass
class KiwiOutput:
    content: dict
    trust_score: float
    trust_breakdown: dict
    recommendation: str = "re_research"
    verify_hint: str = ""
    warnings: list = field(default_factory=list)
    transfer: dict | None = None
    brief_config: object = None
    graduated: object = None


def format_output(context, trust_score: float, trust_breakdown: dict) -> KiwiOutput:
    if trust_score >= 0.85:
        recommendation = "trust"
    elif trust_score >= 0.6:
        recommendation = "verify_partial"
    else:
        recommendation = "re_research"

    content = {
        'target': context.task_type,
        'files_needed': context.files_needed,
        'spec': context.spec,
        'lessons': context.lessons[:5],
        'data_bindings': context.bindings,
        'style_pattern': _summarize_style(context.theme.get('style_patterns', {})),
        'reference_pages': context.reference_pages[:3],
    }

    verify_hint = _generate_verify_hint(trust_breakdown)

    return KiwiOutput(
        content=content,
        trust_score=trust_score,
        trust_breakdown=trust_breakdown,
        recommendation=recommendation,
        verify_hint=verify_hint,
    )


def _summarize_style(patterns: dict) -> str:
    parts = []
    for key in ('spacing', 'radius', 'container', 'shadow', 'grid'):
        values = patterns.get(key, [])
        if not values:
            continue
        # Prefer Tailwind class format over DB format (db_key:value)
        for v in values:
            if ':' not in v or v.startswith(('py-', 'rounded-', 'max-w-', 'shadow-', 'grid-')):
                parts.append(v)
                break
        else:
            # Fallback: convert DB format to readable
            parts.append(values[0])
    return ', '.join(parts) if parts else 'unknown'


def _generate_verify_hint(breakdown: dict) -> str:
    if not breakdown:
        return ''
    lowest = min(breakdown, key=breakdown.get)
    hints = {
        'spec_found': 'No spec found — verify requirements with user',
        'theme_maturity': 'Theme is new — verify design choices',
        'bindings': 'No data bindings known — verify wz_* functions',
        'references': 'No reference pages — verify layout consistency',
        'lessons': 'Few relevant lessons — verify anti-patterns manually',
    }
    return hints.get(lowest, '')