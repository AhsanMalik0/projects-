import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, requests_per_minute: int = 60) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.rpm = requests_per_minute
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in ("/health", "/metrics"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = now - 60.0

        hits = self._hits[client_ip]
        self._hits[client_ip] = [t for t in hits if t > window]

        if len(self._hits[client_ip]) >= self.rpm:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
            )

        self._hits[client_ip].append(now)
        return await call_next(request)
