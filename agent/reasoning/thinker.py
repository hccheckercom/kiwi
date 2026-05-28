"""R8 — Selective Thinking: LLM reasoning for edge cases only. 95% deterministic, 5% Haiku."""

import importlib.util
import json
import hashlib
import time
from dataclasses import dataclass, field

from .session_logger import _get_conn, get_session_id
from .think_prompts import get_prompt
from .think_cache import get_cached, save_cached

_HAS_ANTHROPIC = importlib.util.find_spec("anthropic") is not None

THINK_TRIGGERS = {
    'pattern_conflict',
    'borderline_trust',
    'novel_validation',
    'style_ambiguity',
}

MAX_THINK_TOKENS = 300
MAX_THINKS_PER_SESSION = 3
THINK_COOLDOWN_SEC = 10.0

_last_think_ts: float = 0.0


@dataclass
class ThinkResult:
    trigger: str
    decision: str
    reasoning: str
    confidence: float
    tokens_used: int
    cached: bool = False
    extra: dict = field(default_factory=dict)


def _get_session_think_count(session_id: str) -> int:
    conn = _get_conn()
    if not conn:
        return 0
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM think_events WHERE session_id = ? AND cached = 0",
            (session_id,),
        ).fetchone()
        return row[0] if row else 0
    except Exception:
        return 0


def should_think(trigger: str, context: dict) -> bool:
    global _last_think_ts

    if not _HAS_ANTHROPIC:
        return False

    if trigger not in THINK_TRIGGERS:
        return False

    session_id = get_session_id()
    if _get_session_think_count(session_id) >= MAX_THINKS_PER_SESSION:
        return False

    if (time.time() - _last_think_ts) < THINK_COOLDOWN_SEC:
        return False

    if trigger == 'pattern_conflict':
        patterns = context.get('patterns', [])
        if len(patterns) < 2:
            return False
        rates = sorted([p.get('confidence', 0) for p in patterns], reverse=True)
        return (rates[0] - rates[1]) < 0.15

    elif trigger == 'borderline_trust':
        trust = context.get('trust_score', 0)
        threshold = context.get('threshold', 0.6)
        return abs(trust - threshold) < 0.05

    elif trigger == 'novel_validation':
        return context.get('times_seen', 0) >= 3

    elif trigger == 'style_ambiguity':
        return context.get('style_knowledge_count', 0) == 0

    return False


def think(trigger: str, context: dict) -> ThinkResult | None:
    global _last_think_ts

    if not _HAS_ANTHROPIC:
        return None
    if trigger not in THINK_TRIGGERS:
        return None

    cache_key = _make_cache_key(trigger, context)
    task_type = context.get('task_type', '')
    theme = context.get('theme', '')

    cached = get_cached(cache_key, trigger)
    if cached:
        result = ThinkResult(
            trigger=trigger,
            decision=cached['decision'],
            reasoning=cached.get('reasoning', ''),
            confidence=cached.get('confidence', 0.5),
            tokens_used=0,
            cached=True,
            extra=cached.get('extra', {}),
        )
        _log_think_event(trigger, context, result)
        return result

    if not should_think(trigger, context):
        return None

    prompt = get_prompt(trigger, context)
    if not prompt:
        return None

    try:
        response, tokens_used = _call_haiku(prompt)
    except Exception:
        return None

    _last_think_ts = time.time()

    result = _parse_response(trigger, response, tokens_used)
    if result:
        save_cached(cache_key, trigger, task_type, theme, {
            'decision': result.decision,
            'reasoning': result.reasoning,
            'confidence': result.confidence,
            'extra': result.extra,
        })
        _log_think_event(trigger, context, result)

    return result


def _call_haiku(prompt: str) -> tuple[str, int]:
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=MAX_THINK_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text
    tokens_used = response.usage.output_tokens
    return text, tokens_used


def _parse_response(trigger: str, response: str, tokens_used: int) -> ThinkResult | None:
    try:
        data = json.loads(response)
        if not isinstance(data, dict):
            raise ValueError("not a dict")

        extra = {}
        if trigger == 'style_ambiguity' and 'tokens' in data:
            extra = {'tokens': data['tokens']}

        raw_conf = data.get('confidence')
        confidence = float(raw_conf) if raw_conf is not None else 0.5

        raw_decision = data.get('decision')
        raw_reasoning = data.get('reasoning')

        return ThinkResult(
            trigger=trigger,
            decision=str(raw_decision) if raw_decision is not None else '',
            reasoning=str(raw_reasoning) if raw_reasoning is not None else '',
            confidence=confidence,
            tokens_used=tokens_used,
            extra=extra,
        )
    except (json.JSONDecodeError, ValueError, TypeError):
        lines = response.strip().split('\n')
        return ThinkResult(
            trigger=trigger,
            decision=lines[0][:100] if lines else '',
            reasoning=response[:300],
            confidence=0.3,
            tokens_used=tokens_used,
        )


def _make_cache_key(trigger: str, context: dict) -> str:
    if trigger == 'pattern_conflict':
        content = json.dumps(context.get('patterns', []), sort_keys=True)
    elif trigger == 'borderline_trust':
        content = str(round(context.get('trust_score', 0), 2))
    elif trigger == 'novel_validation':
        content = context.get('pattern', '')
    elif trigger == 'style_ambiguity':
        content = f"{context.get('theme', '')}:{context.get('industry', '')}"
    else:
        content = json.dumps(context, sort_keys=True, default=str)

    raw = f"{trigger}:{content}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def _log_think_event(trigger: str, context: dict, result: ThinkResult):
    conn = _get_conn()
    if not conn:
        return
    try:
        session_id = get_session_id()
        conn.execute(
            "INSERT INTO think_events "
            "(session_id, trigger, task_type, theme, decision, confidence, "
            "tokens_used, cached, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                trigger,
                context.get('task_type', ''),
                context.get('theme', ''),
                result.decision,
                result.confidence,
                result.tokens_used,
                1 if result.cached else 0,
                time.time(),
            ),
        )
        conn.commit()
    except Exception:
        pass
