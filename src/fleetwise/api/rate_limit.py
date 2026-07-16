"""Per-client fixed-window rate limiting for the chat endpoints.

The chat routes proxy every request to a paid LLM API and are publicly
reachable -- CORS only gates browsers, not curl. A small fixed window per
client IP bounds how fast one caller can burn tokens without adding a
dependency or external store (single-process uvicorn means an in-memory
counter is the honest scope; a shared store only matters with replicas).

Implemented as pure ASGI rather than `BaseHTTPMiddleware` so the SSE
streaming response passes through untouched -- `BaseHTTPMiddleware`
wraps the response body and has a history of buffering surprises with
long-lived streams.

Client identity: first hop of `X-Forwarded-For` when present (Render's
proxy sets it; direct connections can't usefully spoof it because
everything arrives through that proxy), else the transport client host.
"""

from __future__ import annotations

import time

from starlette.types import ASGIApp, Receive, Scope, Send

_WINDOW_SECONDS = 60.0

# Cap the counter table so a scan across many spoofed IPs can't grow it
# without bound; expired windows are pruned once the table passes this.
_MAX_TRACKED_CLIENTS = 1024

_RETRY_BODY = b'{"detail":"Rate limit exceeded. Try again in a minute."}'


class ChatRateLimitMiddleware:
    """Fixed window: at most `limit_per_minute` chat requests per client IP."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        limit_per_minute: int,
        path_prefix: str = "/api/chat",
    ) -> None:
        self.app = app
        self.limit = limit_per_minute
        self.path_prefix = path_prefix
        # client key -> (window start, requests seen in window)
        self._hits: dict[str, tuple[float, int]] = {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(self.path_prefix):
            await self.app(scope, receive, send)
            return

        now = time.monotonic()
        key = self._client_key(scope)
        window_start, count = self._hits.get(key, (now, 0))
        if now - window_start >= _WINDOW_SECONDS:
            window_start, count = now, 0
        count += 1

        if len(self._hits) >= _MAX_TRACKED_CLIENTS:
            self._prune(now)
        self._hits[key] = (window_start, count)

        if count > self.limit:
            await self._reject(send)
            return

        await self.app(scope, receive, send)

    @staticmethod
    def _client_key(scope: Scope) -> str:
        headers: list[tuple[bytes, bytes]] = scope.get("headers", [])
        for name, value in headers:
            if name == b"x-forwarded-for":
                first_hop = value.split(b",", 1)[0].strip()
                if first_hop:
                    return first_hop.decode("latin-1")
        client = scope.get("client")
        if client:
            return str(client[0])
        return "unknown"

    def _prune(self, now: float) -> None:
        expired = [k for k, (start, _) in self._hits.items() if now - start >= _WINDOW_SECONDS]
        for k in expired:
            del self._hits[k]

    @staticmethod
    async def _reject(send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"retry-after", b"60"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": _RETRY_BODY})
