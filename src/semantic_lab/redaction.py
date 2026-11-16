"""Turns an exception into one detail line that holds no credential."""

from collections.abc import Iterable

import psycopg
from psycopg.conninfo import conninfo_to_dict

HIDDEN = "***"


def detail(error: Exception, secrets: Iterable[str] = ()) -> str:
    """The class and the first line of the message, with every known secret blanked."""
    lines = str(error).splitlines()
    name = type(error).__name__
    text = f"{name}: {lines[0]}" if lines and lines[0] else name
    for secret in secrets:
        if secret:
            text = text.replace(secret, HIDDEN)
    return text


def unparsable_detail(error: Exception, what: str) -> str:
    """The detail for an address the driver could not parse. Those messages quote the
    address, which can hold a password, so the detail quotes nothing from them."""
    return f"{type(error).__name__}: invalid {what}"


def dsn_password(dsn: str) -> str:
    try:
        return str(conninfo_to_dict(dsn).get("password") or "")
    except psycopg.ProgrammingError:
        return ""
