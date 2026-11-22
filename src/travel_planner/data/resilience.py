"""Retries, timeouts, a session circuit breaker, and call budgets.

A breaker stays open for the rest of the planner run after repeated failures.
The per-run budget stops further live calls. Daily quotas are session counters,
and a persistent cache keeps them across runs when CACHE_STORE_URL is set.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from travel_planner.data.cache import Cache


class ProviderHTTPError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = status in {408, 500, 502, 503}


class CircuitOpen(Exception):
    pass


class RateLimited(Exception):
    pass


class QuotaExceeded(Exception):
    pass


class BudgetExhausted(Exception):
    pass


@dataclass
class CircuitBreaker:
    name: str
    threshold: int = 3
    failures: int = 0
    opened: bool = False

    def allow(self) -> bool:
        return not self.opened

    def success(self) -> None:
        self.failures = 0

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened = True


class SlidingWindowLimiter:
    """Allows at most ``per_minute`` acquisitions in a rolling 60 seconds."""

    def __init__(self, per_minute: int, clock: Callable[[], float] | None = None) -> None:
        self.per_minute = per_minute
        self._clock = clock or time.monotonic
        self._hits: deque[float] = deque()

    def allow(self) -> bool:
        now = self._clock()
        while self._hits and now - self._hits[0] >= 60:
            self._hits.popleft()
        if len(self._hits) >= self.per_minute:
            return False
        self._hits.append(now)
        return True


@dataclass
class DailyQuota:
    limit: int
    used: int = 0

    def allow(self) -> bool:
        return self.used < self.limit

    def record(self) -> None:
        self.used += 1


@dataclass
class SessionGuard:
    budget_limit: int = 40
    failure_threshold: int = 3
    attempts: int = 3
    backoff_seconds: float = 0.05
    used: int = 0
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    today: Callable[[], date] = date.today
    breakers: dict[str, CircuitBreaker] = field(default_factory=dict)
    limiters: dict[str, SlidingWindowLimiter] = field(default_factory=dict)
    quotas: dict[str, DailyQuota] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def breaker(self, name: str) -> CircuitBreaker:
        found = self.breakers.get(name)
        if found is None:
            found = CircuitBreaker(name, threshold=self.failure_threshold)
            self.breakers[name] = found
        return found

    def limiter(self, name: str, per_minute: int) -> SlidingWindowLimiter:
        found = self.limiters.get(name)
        if found is None:
            found = SlidingWindowLimiter(per_minute, clock=self.clock)
            self.limiters[name] = found
        return found

    def quota(self, name: str, limit: int) -> DailyQuota:
        found = self.quotas.get(name)
        if found is None:
            found = DailyQuota(limit)
            self.quotas[name] = found
        return found

    def try_spend(self) -> bool:
        with self._lock:
            if self.used >= self.budget_limit:
                return False
            self.used += 1
            return True


def call_with_retry[T](guard: SessionGuard, fn: Callable[[], T]) -> T:
    last: ProviderHTTPError | None = None
    for attempt in range(guard.attempts):
        try:
            return fn()
        except ProviderHTTPError as exc:
            last = exc
            if not exc.retryable or attempt == guard.attempts - 1:
                raise
            guard.sleep(guard.backoff_seconds * (2**attempt))
    if last is None:
        raise ProviderHTTPError(500, "retry produced no result")
    raise last


def guarded_call[T](
    guard: SessionGuard,
    cache: Cache,
    *,
    provider: str,
    per_minute: int,
    quota: str,
    quota_limit: int,
    fn: Callable[[], T],
) -> T:
    """Run ``fn`` once the breaker, limiter, daily quota, and budget allow it."""

    breaker = guard.breaker(provider)
    if not breaker.allow():
        raise CircuitOpen(f"{provider} is disabled for this run")
    bucket = guard.quota(quota, quota_limit)
    persisted = _persisted_used(cache, quota, guard.today())
    if not bucket.allow() or persisted >= quota_limit:
        raise QuotaExceeded(f"{quota} daily limit of {quota_limit} is reached")
    if not guard.limiter(provider, per_minute).allow():
        raise RateLimited(f"{provider} is at {per_minute} calls per minute")
    try:
        result = call_with_retry(guard, fn)
    except ProviderHTTPError:
        breaker.failure()
        raise
    breaker.success()
    bucket.record()
    _persist_used(cache, quota, guard.today(), max(bucket.used, persisted + 1))
    return result


def _quota_key(name: str, day: date) -> str:
    return f"quota:{name}:{day.isoformat()}"


def _persisted_used(cache: Cache, name: str, day: date) -> int:
    if not cache.persistent:
        return 0
    raw = cache.get(_quota_key(name, day))
    if not raw:
        return 0
    try:
        return int(raw)
    except ValueError:
        return 0


def _persist_used(cache: Cache, name: str, day: date, used: int) -> None:
    if cache.persistent:
        cache.set(_quota_key(name, day), str(used), 86400)
