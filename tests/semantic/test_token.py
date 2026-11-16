import base64
import hashlib
import hmac
import json

from semantic_lab.semantic import token


def _decode(part: str) -> dict[str, object]:
    padded = part + "=" * (-len(part) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


def test_token_has_three_parts_and_a_valid_signature():
    parts = token.sign("s3cret", now=1000).split(".")
    assert len(parts) == 3
    expected = hmac.new(b"s3cret", f"{parts[0]}.{parts[1]}".encode(), hashlib.sha256).digest()
    expected_part = base64.urlsafe_b64encode(expected).rstrip(b"=").decode()
    assert parts[2] == expected_part


def test_payload_carries_iat_and_exp():
    payload = token.sign("s", now=1000, ttl=300).split(".")[1]
    assert _decode(payload) == {"iat": 1000, "exp": 1300}


def test_default_ttl_is_five_minutes():
    payload = token.sign("s", now=1000).split(".")[1]
    assert _decode(payload) == {"iat": 1000, "exp": 1300}


def test_header_is_hs256_jwt():
    header = token.sign("s", now=1000).split(".")[0]
    assert _decode(header) == {"alg": "HS256", "typ": "JWT"}
