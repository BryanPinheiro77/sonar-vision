"""Structured errors limited to the codes of contract 0.1."""

CODES = {400: "invalid_request", 401: "unauthorized", 403: "forbidden",
         413: "payload_too_large", 415: "unsupported_media_type", 429: "busy",
         500: "internal_error", 503: "unavailable"}


class ApiError(Exception):
    """`reason` is a short internal label for logs; it is never sent to clients."""

    def __init__(self, status: int, reason: str):
        if status not in CODES:
            raise ValueError("status outside contract 0.1")
        super().__init__(reason)
        self.status, self.code, self.reason = status, CODES[status], reason

    def body(self) -> dict:
        return {"error": {"code": self.code}}
