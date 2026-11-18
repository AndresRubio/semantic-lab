"""The one way to open a Postgres connection: with a timeout, and with an error line that holds
no credential."""

from typing import Any

import psycopg

from semantic_lab import redaction

CONNECT_TIMEOUT_SECONDS = 5


class ConnectError(Exception):
    """Why a connection could not be opened, as one line that holds no credential."""


def connect(dsn: str, timeout: int = CONNECT_TIMEOUT_SECONDS) -> psycopg.Connection[Any]:
    """Open a connection or raise `ConnectError`.

    Only this step can fail on an address the driver cannot parse, and that failure is a
    `ProgrammingError` whose message quotes the address, so its detail quotes nothing. Any other
    driver error has the DSN's password blanked. The cause is dropped from the chain for the same
    reason: a traceback would print the quoted address.
    """
    try:
        # libpq reads a timeout of 0 as no timeout, so the least that is passed is 1 second.
        return psycopg.connect(dsn, connect_timeout=max(1, timeout))
    except psycopg.ProgrammingError as error:
        raise ConnectError(redaction.unparsable_detail(error, "DSN")) from None
    except psycopg.Error as error:
        raise ConnectError(detail(error, dsn)) from None


def detail(error: Exception, dsn: str) -> str:
    """The detail line of an error raised after the connection was open, with the DSN's password
    blanked."""
    return redaction.detail(error, [redaction.dsn_password(dsn)])
