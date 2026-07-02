"""Shared error taxonomy and retry helper for API-touching subsystems."""
from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


class ApiError(Exception):
    """Base class for external-API failures."""


class TransientError(ApiError):
    """A retryable failure (network blip, 5xx, non-quota rate limit)."""


class QuotaExceeded(ApiError):
    """Billing/quota exhausted. Terminal for the run — never retried."""


class RefusedByPolicy(ApiError):
    """The provider refused the request on content-policy grounds. Per-item, not retried."""


def retry_on_transient(
    fn: Callable[[], T], *, retries: int = 3, base_delay: float = 1.0
) -> T:
    """Call fn(), retrying only on TransientError with exponential backoff.

    Any non-TransientError propagates immediately. After exhausting retries,
    the last TransientError is re-raised.
    """
    last: TransientError | None = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except TransientError as e:
            if attempt >= retries:
                raise
            last = e
            time.sleep(base_delay * (3**attempt))
    raise last if last else RuntimeError("unreachable")
