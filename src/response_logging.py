"""Log the serialized JSON body that is sent to the API client."""

from src.logger import logger


class JSONResponseLoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        is_json = False
        body_parts = []

        async def log_response(message):
            nonlocal is_json
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                content_type = headers.get(b"content-type", b"").split(b";", 1)[0].lower()
                is_json = content_type == b"application/json" or content_type.endswith(b"+json")
            elif message["type"] == "http.response.body" and is_json:
                body_parts.append(message.get("body", b""))
                if not message.get("more_body", False):
                    logger.info(
                        "%s", b"".join(body_parts).decode("utf-8"),
                        extra={"id": scope.get("state", {}).get("log_request_id", "")},
                    )
            await send(message)

        await self.app(scope, receive, log_response)
