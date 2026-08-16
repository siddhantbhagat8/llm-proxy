import math
import time

from app import errors
from app.models.user import User
from app.services.usage_service import UsageService

MINUTE_SECONDS = 60
DAY_SECONDS = 86400


class LimitService:
    """Sliding-window pre-checks over recorded usage (optimistic enforcement, DESIGN.md 3.5)."""

    def __init__(self, usage_service: UsageService) -> None:
        self.usage_service = usage_service

    @staticmethod
    def _retry_after_seconds(
        oldest_created_at: float | None, window_seconds: int
    ) -> int:
        if oldest_created_at is None:
            return 1
        return max(1, math.ceil(oldest_created_at + window_seconds - time.time()))

    def check(self, user: User) -> None:
        if user.requests_per_minute is not None:
            count, oldest = self.usage_service.requests_in_window(
                user.id, MINUTE_SECONDS
            )
            if count >= user.requests_per_minute:
                raise errors.rate_limit_exceeded(
                    f"Rate limit reached: {count} requests in the last minute"
                    f" (limit {user.requests_per_minute}/min).",
                    self._retry_after_seconds(oldest, MINUTE_SECONDS),
                )
        if user.tokens_per_day is not None:
            tokens, oldest = self.usage_service.tokens_in_window(user.id, DAY_SECONDS)
            if tokens >= user.tokens_per_day:
                raise errors.rate_limit_exceeded(
                    f"Daily token limit reached: {tokens} tokens in the last 24 hours"
                    f" (limit {user.tokens_per_day}/day).",
                    self._retry_after_seconds(oldest, DAY_SECONDS),
                )
        if user.lifetime_spend_dollars is not None:
            spend = self.usage_service.lifetime_spend_dollars(user.id)
            if spend >= user.lifetime_spend_dollars:
                raise errors.insufficient_quota(
                    f"You exceeded your lifetime spend cap of"
                    f" ${user.lifetime_spend_dollars:g}. Contact an admin to raise it."
                )
