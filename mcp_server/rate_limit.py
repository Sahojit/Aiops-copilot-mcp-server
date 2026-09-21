"""
In-memory token-bucket rate limiter, keyed per caller_id.

This state lives in process memory only — it resets on restart and is not
shared across multiple server instances. Fine for a single local process;
call out the persistent-store gap in the README's "what I'd do next" section.
"""
import time
from dataclasses import dataclass, field

from mcp.shared.exceptions import MCPError
from mcp.types import INVALID_REQUEST

DEFAULT_CAPACITY = 30  # max calls per window
DEFAULT_WINDOW_SECONDS = 60.0


@dataclass
class _Bucket:
    tokens: float
    last_refill: float


@dataclass
class TokenBucketRateLimiter:
    capacity: int = DEFAULT_CAPACITY
    window_seconds: float = DEFAULT_WINDOW_SECONDS
    _buckets: dict[str, _Bucket] = field(default_factory=dict)

    def _refill_rate(self) -> float:
        return self.capacity / self.window_seconds

    def check(self, caller_id: str) -> None:
        """Consume one token for `caller_id`. Raises MCPError if none are left."""
        now = time.monotonic()
        bucket = self._buckets.get(caller_id)

        if bucket is None:
            bucket = _Bucket(tokens=float(self.capacity), last_refill=now)
            self._buckets[caller_id] = bucket

        elapsed = now - bucket.last_refill
        bucket.tokens = min(self.capacity, bucket.tokens + elapsed * self._refill_rate())
        bucket.last_refill = now

        if bucket.tokens < 1:
            raise MCPError(
                INVALID_REQUEST,
                f"Rate limit exceeded for caller '{caller_id}': "
                f"max {self.capacity} calls per {int(self.window_seconds)}s. Try again shortly.",
            )

        bucket.tokens -= 1


# Shared limiter instance for the whole server process.
rate_limiter = TokenBucketRateLimiter()
