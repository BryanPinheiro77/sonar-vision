"""Single shared viewer credential for #73; never a device Bearer credential."""
import base64
import binascii
import hashlib
import hmac
import re
import secrets
import time

ITERATIONS = 600_000
USERNAME = b"sonar"
SESSION_SECONDS = 28800
_SESSION = re.compile(r"([0-9]{1,12})\.([0-9a-f]{32})\.([0-9a-f]{64})")
_VERIFIER = re.compile(r"pbkdf2-sha256\$600000\$([0-9a-f]{32})\$([0-9a-f]{64})")


def make_verifier(password):
    """Provision offline; return only a salted password verifier for the server."""
    if not isinstance(password, str) or not 12 <= len(password) <= 256:
        raise ValueError("viewer password must contain 12 to 256 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"pbkdf2-sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


class ViewerAuth:
    def __init__(self, verifier):
        match = _VERIFIER.fullmatch(verifier) if isinstance(verifier, str) else None
        if not match:
            raise ValueError("invalid viewer password verifier")
        self.salt, self.expected = (bytes.fromhex(v) for v in match.groups())
        # Constant-size cache of the one accepted header; no plaintext password.
        self._accepted_digest = None
        self._session_key = secrets.token_bytes(32)

    def cached(self, header):
        if not isinstance(header, str) or len(header) > 1024 or self._accepted_digest is None:
            return False
        digest = hashlib.sha256(header.encode("utf-8")).digest()
        return hmac.compare_digest(digest, self._accepted_digest)

    def authenticate(self, header):
        if not isinstance(header, str) or len(header) > 1024:
            return False
        if self.cached(header):
            return True
        scheme, _, raw = header.partition(" ")
        if scheme.lower() != "basic":
            return False
        try:
            decoded = base64.b64decode(raw, validate=True)
        except (ValueError, binascii.Error):
            return False
        username, separator, password = decoded.partition(b":")
        if not separator or username != USERNAME or not 1 <= len(password) <= 1024:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password, self.salt, ITERATIONS)
        if not hmac.compare_digest(digest, self.expected):
            return False
        self._accepted_digest = hashlib.sha256(header.encode("utf-8")).digest()
        return True

    def issue_session(self):
        payload = f"{int(time.time()) + SESSION_SECONDS}.{secrets.token_hex(16)}"
        signature = hmac.new(self._session_key, payload.encode(), hashlib.sha256).hexdigest()
        return payload + "." + signature

    def valid_session(self, cookie):
        if not isinstance(cookie, str) or len(cookie) > 160:
            return False
        match = _SESSION.fullmatch(cookie)
        if not match:
            return False
        expiry, nonce, signature = match.groups()
        payload = expiry + "." + nonce
        expected = hmac.new(self._session_key, payload.encode("ascii"), hashlib.sha256).hexdigest()
        now = int(time.time())
        return hmac.compare_digest(signature, expected) and now < int(expiry) <= now + SESSION_SECONDS
