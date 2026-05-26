"""Retry utilities for Kiwi Agent — exponential backoff with jitter."""

import time
import random
from typing import Callable, Any, Optional


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter


class RetryableError(Exception):
    """Base class for errors that should trigger retry."""
    pass


class NonRetryableError(Exception):
    """Base class for errors that should NOT trigger retry."""
    pass


def calculate_backoff(attempt: int, config: RetryConfig) -> float:
    """Calculate backoff delay for given attempt number.

    Args:
        attempt: Current attempt number (0-indexed)
        config: Retry configuration

    Returns:
        Delay in seconds
    """
    delay = config.initial_delay * (config.exponential_base ** attempt)
    delay = min(delay, config.max_delay)

    if config.jitter:
        # Add random jitter (±25%)
        jitter_range = delay * 0.25
        delay += random.uniform(-jitter_range, jitter_range)

    return max(0, delay)


def retry_with_backoff(
    func: Callable,
    config: RetryConfig,
    error_callback: Optional[Callable[[Exception, int], None]] = None,
    retryable_exceptions: tuple = (Exception,),
    non_retryable_exceptions: tuple = (NonRetryableError,),
) -> Any:
    """Execute function with exponential backoff retry.

    Args:
        func: Function to execute
        config: Retry configuration
        error_callback: Optional callback called on each error (error, attempt_num)
        retryable_exceptions: Tuple of exception types that should trigger retry
        non_retryable_exceptions: Tuple of exception types that should NOT retry

    Returns:
        Result of func()

    Raises:
        Last exception if all retries exhausted
    """
    last_exception = None

    for attempt in range(config.max_retries + 1):
        try:
            return func()
        except non_retryable_exceptions as e:
            # Don't retry these
            raise
        except retryable_exceptions as e:
            last_exception = e

            if error_callback:
                error_callback(e, attempt)

            if attempt < config.max_retries:
                delay = calculate_backoff(attempt, config)
                time.sleep(delay)
            else:
                # Last attempt failed, raise
                raise last_exception from e


def is_retryable_api_error(error: Exception) -> bool:
    """Check if API error should trigger retry.

    Retryable errors:
    - Rate limit (429)
    - Server errors (500, 502, 503, 504)
    - Timeout errors
    - Connection errors

    Non-retryable errors:
    - Authentication errors (401, 403)
    - Invalid request (400)
    - Not found (404)
    """
    error_str = str(error).lower()

    # Rate limit
    if "429" in error_str or "rate limit" in error_str:
        return True

    # Server errors
    if any(code in error_str for code in ["500", "502", "503", "504"]):
        return True

    # Timeout
    if "timeout" in error_str or "timed out" in error_str:
        return True

    # Connection errors
    if any(term in error_str for term in ["connection", "network", "unreachable"]):
        return True

    # Authentication/client errors - don't retry
    if any(code in error_str for code in ["400", "401", "403", "404"]):
        return False

    # Default: retry
    return True