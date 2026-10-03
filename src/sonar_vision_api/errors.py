"""Structured errors limited to the codes of contract 0.1 and the catalog routes (#26)."""

CODES = {400: "invalid_request", 401: "unauthorized", 403: "forbidden",
         413: "payload_too_large", 415: "unsupported_media_type", 429: "busy",
         500: "internal_error", 503: "unavailable"}
# Catalog distribution (#26): codes outside the inference contract.
CATALOG_CODES = {"catalog_unavailable": 404, "not_found": 404}


class ApiError(Exception):
    """`reason` is a short internal label for logs; it is never sent to clients."""

    def __init__(self, status: int, reason: str, code: str | None = None):
        if code is None:
            if status not in CODES:
                raise ValueError("status outside contract 0.1")
            code = CODES[status]
        elif CATALOG_CODES.get(code) != status:
            raise ValueError("unknown catalog error code")
        super().__init__(reason)
        self.status, self.code, self.reason = status, code, reason

    def body(self) -> dict:
        return {"error": {"code": self.code}}
