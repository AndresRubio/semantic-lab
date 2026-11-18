from typing import Any

import psycopg
import pytest

from semantic_lab import pg

PASSWORD = "hunter2-secret"
DSN = f"postgresql://lab:{PASSWORD}@127.0.0.1:1/lab"


def test_the_default_timeout_is_5_seconds() -> None:
    assert pg.CONNECT_TIMEOUT_SECONDS == 5


@pytest.mark.parametrize(("asked", "passed"), [(None, 5), (2, 2), (0, 1), (-3, 1)])
def test_connect_passes_a_connect_timeout_of_at_least_one_second(
    monkeypatch: pytest.MonkeyPatch, asked: int | None, passed: int
) -> None:
    seen: list[dict[str, Any]] = []

    def fake(dsn: str, **kwargs: Any) -> str:
        seen.append({"dsn": dsn, **kwargs})
        return "connection"

    monkeypatch.setattr(psycopg, "connect", fake)
    result = pg.connect(DSN) if asked is None else pg.connect(DSN, asked)

    assert result == "connection"
    assert seen == [{"dsn": DSN, "connect_timeout": passed}]


def test_a_closed_port_raises_connect_error_without_the_password() -> None:
    with pytest.raises(pg.ConnectError) as raised:
        pg.connect(DSN, timeout=2)

    assert str(raised.value).startswith("OperationalError")
    assert "\n" not in str(raised.value)
    assert PASSWORD not in str(raised.value)
    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://lab:pa%zzword@127.0.0.1:1/lab",
        "postgresql://lab:pa ss@127.0.0.1:1/lab",
        "not a dsn hunter2-secret",
        "host=127.0.0.1 port=1 password=hunter2-secret bogus=1",
    ],
)
def test_an_unparsable_dsn_is_named_and_not_quoted(dsn: str) -> None:
    with pytest.raises(pg.ConnectError) as raised:
        pg.connect(dsn, timeout=2)

    assert str(raised.value) == "ProgrammingError: invalid DSN"


def test_another_driver_error_has_the_password_blanked(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(dsn: str, **kwargs: Any) -> None:
        raise psycopg.OperationalError(f"password {PASSWORD} refused\nsecond line")

    monkeypatch.setattr(psycopg, "connect", fail)
    with pytest.raises(pg.ConnectError) as raised:
        pg.connect(DSN)

    assert str(raised.value) == "OperationalError: password *** refused"


def test_connect_error_is_not_a_driver_error() -> None:
    assert not issubclass(pg.ConnectError, psycopg.Error)


def test_detail_blanks_the_password_of_the_dsn() -> None:
    error = psycopg.errors.UndefinedTable(f"relation of {PASSWORD} does not exist")
    assert pg.detail(error, DSN) == "UndefinedTable: relation of *** does not exist"


def test_detail_of_an_unparsable_dsn_still_gives_the_line() -> None:
    error = psycopg.errors.UndefinedTable("relation does not exist")
    assert pg.detail(error, "not a dsn") == "UndefinedTable: relation does not exist"
