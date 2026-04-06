"""
Rate limiting middleware using in-memory sliding window.
Replace with Upstash Redis for production multi-instance deployments.
"""
import time
from collections import defaultdict, deque
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding window rate limiter per IP address.
    Limits:
      - /api/v1/extract:     10 requests / 60s
      - /api/v1/ai-command:  20 requests / 60s
      - /api/auth:            5 requests / 60s  (brute-force protection)
      - Everything else:    100 requests / 60s
    """

    LIMITS = {
        "/api/v1/extract": (10, 60),
        "/api/v1/ai-command": (20, 60),
        "/api/auth": (5, 60),
    }
    DEFAULT_LIMIT = (100, 60)

    def __init__(self, app):
        super().__init__(app)
        # { (ip, path_prefix): deque of timestamps }
        self._windows: dict = defaultdict(deque)

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _get_limit(self, path: str):
        for prefix, limit in self.LIMITS.items():
            if path.startswith(prefix):
                return limit
        return self.DEFAULT_LIMIT

    async def dispatch(self, request: Request, call_next):
        ip = self._get_client_ip(request)
        path = request.url.path
        max_requests, window_seconds = self._get_limit(path)

        key = (ip, tuple(path.split("/")[1:3]))  # group by top 2 path segments
        now = time.time()
        window = self._windows[key]

        # Remove timestamps outside the window
        while window and window[0] < now - window_seconds:
            window.popleft()

        if len(window) >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests. Limit: {max_requests}/{window_seconds}s per IP.",
                headers={"Retry-After": str(window_seconds)},
            )

        window.append(now)
        return await call_next(request)
