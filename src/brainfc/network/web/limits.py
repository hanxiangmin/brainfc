"""Bound request bodies as they arrive, including chunked local uploads."""
from __future__ import annotations

from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestBodyLimitMiddleware:
    """Stop receiving oversized bodies before multipart/JSON parsing.

    Content-Length is only an early rejection opportunity. The authoritative
    bound counts every ASGI body chunk, so absent or inaccurate headers cannot
    bypass it. HTTPException preserves the 413 status through FastAPI's body
    parser and allows the multipart parser to clean up temporary files.
    """

    def __init__(self, app: ASGIApp, max_bytes: int):
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
            raise ValueError("max_bytes must be a positive integer.")
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        message = "Request is too large; upload smaller batches."
        length = dict(scope.get("headers", [])).get(b"content-length")
        if length and length.isdigit() and int(length) > self.max_bytes:
            response = JSONResponse({"detail": message}, status_code=413)
            await response(scope, receive, send)
            return
        received = 0

        async def bounded_receive() -> Message:
            nonlocal received
            event = await receive()
            if event["type"] == "http.request":
                received += len(event.get("body", b""))
                if received > self.max_bytes:
                    raise HTTPException(status_code=413, detail=message)
            return event

        await self.app(scope, bounded_receive, send)
