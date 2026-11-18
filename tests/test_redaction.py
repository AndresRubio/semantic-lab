import psycopg

from semantic_lab import redaction


def test_detail_is_the_class_and_the_first_line_with_secrets_blanked() -> None:
    error = RuntimeError("login failed for hunter2\nsecond line")
    assert redaction.detail(error, ["hunter2"]) == "RuntimeError: login failed for ***"


def test_detail_of_an_error_without_a_message_is_the_class_alone() -> None:
    assert redaction.detail(RuntimeError()) == "RuntimeError"


def test_an_empty_secret_blanks_nothing() -> None:
    assert redaction.detail(RuntimeError("x"), [""]) == "RuntimeError: x"


def test_unparsable_detail_quotes_nothing_from_the_error() -> None:
    error = psycopg.ProgrammingError("invalid dsn: pa%zzword")
    assert redaction.unparsable_detail(error, "DSN") == "ProgrammingError: invalid DSN"


def test_dsn_password_reads_it_from_a_url_and_a_key_value_dsn() -> None:
    assert redaction.dsn_password("postgresql://lab:s3cret@127.0.0.1:1/lab") == "s3cret"
    assert redaction.dsn_password("host=h password=s3cret") == "s3cret"


def test_dsn_password_of_an_unparsable_dsn_is_empty() -> None:
    assert redaction.dsn_password("postgresql://lab:pa%zzword@127.0.0.1:1/lab") == ""
