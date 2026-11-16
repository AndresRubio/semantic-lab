"""The signed token Cube's API expects in the Authorization header."""

import base64
import hashlib
import hmac
import json


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _part(value: dict[str, object]) -> str:
    return _b64url(json.dumps(value, separators=(",", ":")).encode())


def sign(secret: str, now: int, ttl: int = 300) -> str:
    """An HS256 JWT that is valid from `now` for `ttl` seconds."""
    header = _part({"alg": "HS256", "typ": "JWT"})
    payload = _part({"iat": now, "exp": now + ttl})
    signing_input = f"{header}.{payload}"
    signature = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(signature)}"
