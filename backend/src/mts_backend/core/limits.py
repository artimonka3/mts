"""Limit multipart before Starlette spools bodies; enforce chunked uploads too."""

import json
from uuid import uuid4

from starlette.exceptions import HTTPException


class BodyTooLarge(HTTPException):
    def __init__(self):
        # FastAPI preserves HTTPException while its body parser otherwise turns
        # arbitrary receive() errors into a generic 400 response.
        super().__init__(status_code=413)


class BodyLimitMiddleware:
    def __init__(self, app, upload_max_bytes):
        self.app = app
        self.upload_max_bytes = upload_max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        limit = self.upload_max_bytes + 1048576 if scope["path"] == "/api/v1/calls" else 1048576
        headers = dict(scope.get("headers", []))
        size = 0
        started = False

        async def limited_receive():
            nonlocal size
            message = await receive()
            if message["type"] == "http.request":
                size += len(message.get("body", b""))
                if size > limit:
                    raise BodyTooLarge
            return message

        async def track_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            length = int(headers.get(b"content-length", b"0"))
            if length > limit:
                raise BodyTooLarge
            await self.app(scope, limited_receive, track_send)
        except BodyTooLarge:
            if started:
                raise
            request_id = uuid4().hex
            body = json.dumps(
                {
                    "error": {
                        "code": "payload_too_large",
                        "message": "Request exceeds size limit.",
                        "request_id": request_id,
                        "details": [],
                    }
                }
            ).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 413,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"x-request-id", request_id.encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
