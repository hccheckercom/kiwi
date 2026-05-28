"""R8 — Prompt templates for selective thinking. 4 triggers."""


PROMPTS = {
    'pattern_conflict': """Choose between {n} layout patterns for a {task_type} page.

Patterns:
{patterns_desc}

Target theme: {theme} (industry: {industry})
Style: {style_summary}

Which pattern fits best? Reply JSON only:
{{"decision": "0-based index", "reasoning": "one sentence", "confidence": 0.0-1.0}}""",

    'borderline_trust': """Task: {task_type} for theme {theme}.
Trust score: {trust_score} (threshold: {threshold}).
Signals: {signals}

Should Kiwi attempt code generation (skeleton level) or stay brief-only?
Consider: task complexity, available data, risk of bad output.

Reply JSON only:
{{"decision": "generate" or "brief_only", "reasoning": "one sentence", "confidence": 0.0-1.0}}""",

    'novel_validation': """Pattern detected {times_seen} times across sessions:
Pattern: {pattern}
Type: {pattern_type}
Context: used in {task_type} for theme {theme}

Is this a good practice worth promoting to a Kiwi lesson?
Consider: security, performance, maintainability, WordPress conventions.

Reply JSON only:
{{"decision": "promote" or "skip", "reasoning": "one sentence", "confidence": 0.0-1.0}}""",

    'style_ambiguity': """New theme "{theme}" has no style data yet.
Industry: {industry}
Available industry DNA: {dna_summary}

Suggest Tailwind style tokens for this theme.
Reply JSON only:
{{"decision": "inferred", "reasoning": "based on industry", "confidence": 0.0-1.0, "tokens": {{"radius": "...", "spacing_base": "...", "container": "...", "shadow": "..."}}}}""",
}


def get_prompt(trigger: str, context: dict) -> str | None:
    template = PROMPTS.get(trigger)
    if not template:
        return None
    try:
        return template.format(**context)
    except KeyError:
        return None