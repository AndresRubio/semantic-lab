import httpx
import pytest

from semantic_lab import probes
from semantic_lab.config import Settings
from semantic_lab.semantic import token

SECRET = "cube-secret-value"
NOW = 1_700_000_000


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _cube(readyz: httpx.Response, meta: httpx.Response | None = None):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/readyz":
            return readyz
        assert meta is not None
        return meta

    return _client(handler), seen


def _raise_connect_error(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused", request=request)


def test_postgres_on_a_closed_port_fails_without_the_password():
    check = probes.postgres("postgresql://lab:hunter2-secret@127.0.0.1:1/lab", timeout=2)
    assert (check.service, check.ok) == ("postgres", False)
    assert "hunter2-secret" not in check.detail


@pytest.mark.parametrize(
    ("dsn", "secret"),
    [
        ("postgresql://lab:pa%zzword@127.0.0.1:1/lab", "pa%zzword"),
        ("postgresql://lab:pa ss@127.0.0.1:1/lab", "pa ss"),
        ("postgresql://lab:hunter2-secret@127.0.0.1:1/lab", "hunter2-secret"),
        ("not a dsn hunter2-secret", "hunter2-secret"),
        ("hunter2-secret", "hunter2-secret"),
        ("nonsense://topsecret", "topsecret"),
        ("postgresql://lab:topsecret@[::1/lab", "topsecret"),
        ("host=127.0.0.1 port=1 password=topsecret bogus=1", "topsecret"),
    ],
)
def test_postgres_never_puts_the_address_in_the_detail(dsn: str, secret: str) -> None:
    check = probes.postgres(dsn, timeout=2)
    assert (check.service, check.ok) == ("postgres", False)
    assert secret not in check.detail


def test_postgres_with_a_malformed_dsn_names_the_class_and_quotes_nothing() -> None:
    check = probes.postgres("postgresql://lab:pa%zzword@127.0.0.1:1/lab", timeout=2)
    assert check.detail == "ProgrammingError: invalid DSN"


@pytest.mark.parametrize(
    ("uri", "secret"),
    [
        ("bolt://neo4j:topsecret@127.0.0.1:1", "topsecret"),
        ("neo4j://neo4j:topsecret@127.0.0.1:1", "topsecret"),
        ("nonsense://topsecret", "topsecret"),
        ("topsecret", "topsecret"),
        ("bolt://[topsecret", "topsecret"),
    ],
)
def test_neo4j_never_puts_the_address_in_the_detail(uri: str, secret: str) -> None:
    check = probes.neo4j(uri, "neo4j", "topsecret", timeout=2)
    assert (check.service, check.ok) == ("neo4j", False)
    assert secret not in check.detail


def test_neo4j_with_a_malformed_uri_names_the_class_and_quotes_nothing() -> None:
    check = probes.neo4j("bolt://neo4j:topsecret@127.0.0.1:1", "neo4j", "topsecret", timeout=2)
    assert check.detail == "ConfigurationError: invalid URI"


def test_neo4j_on_a_closed_port_fails_without_the_password():
    check = probes.neo4j("bolt://127.0.0.1:1", "neo4j", "hunter2-secret", timeout=2)
    assert (check.service, check.ok) == ("neo4j", False)
    assert "hunter2-secret" not in check.detail


def test_cube_ok_counts_the_cubes():
    client, _ = _cube(httpx.Response(200), httpx.Response(200, json={"cubes": [{}, {}]}))
    check = probes.cube("http://cube", SECRET, client, NOW)
    assert check == probes.Check("cube", True, "2 cubes")


def test_cube_with_one_cube_reads_singular():
    client, _ = _cube(httpx.Response(200), httpx.Response(200, json={"cubes": [{}]}))
    check = probes.cube("http://cube", SECRET, client, NOW)
    assert check == probes.Check("cube", True, "1 cube")


def test_cube_with_no_cubes_reads_plural():
    client, _ = _cube(httpx.Response(200), httpx.Response(200, json={"cubes": []}))
    check = probes.cube("http://cube", SECRET, client, NOW)
    assert check == probes.Check("cube", True, "0 cubes")


def test_cube_sends_a_signed_token():
    client, seen = _cube(httpx.Response(200), httpx.Response(200, json={"cubes": []}))
    probes.cube("http://cube", SECRET, client, NOW)
    meta = [r for r in seen if r.url.path == "/cubejs-api/v1/meta"]
    assert len(meta) == 1
    assert meta[0].headers["Authorization"] == token.sign(SECRET, NOW)


def test_cube_not_ready():
    client, seen = _cube(httpx.Response(500))
    check = probes.cube("http://cube", SECRET, client, NOW)
    assert check == probes.Check("cube", False, "readyz: HTTP 500")
    assert [r.url.path for r in seen] == ["/readyz"]


def test_cube_meta_refused():
    client, _ = _cube(httpx.Response(200), httpx.Response(403))
    check = probes.cube("http://cube", SECRET, client, NOW)
    assert check == probes.Check("cube", False, "meta: HTTP 403")


def test_cube_meta_without_cubes():
    client, _ = _cube(httpx.Response(200), httpx.Response(200, json={"error": "x"}))
    check = probes.cube("http://cube", SECRET, client, NOW)
    assert check == probes.Check("cube", False, "meta: no cubes in the response")


def test_cube_unreachable_keeps_the_secret_out():
    check = probes.cube("http://cube", SECRET, _client(_raise_connect_error), NOW)
    assert (check.service, check.ok) == ("cube", False)
    assert check.detail.startswith("ConnectError")
    assert SECRET not in check.detail


def test_a_failure_blanks_the_secret_wherever_the_message_holds_it():
    def leaky(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"refused for {SECRET}", request=request)

    check = probes.cube("http://cube", SECRET, _client(leaky), NOW)
    assert check.ok is False
    assert SECRET not in check.detail
    assert check.detail.startswith("ConnectError: refused for ")


def test_a_failure_keeps_a_trailing_colon_in_the_message():
    def colon(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused:", request=request)

    check = probes.cube("http://cube", SECRET, _client(colon), NOW)
    assert check.detail == "ConnectError: refused:"


def test_a_failure_with_an_empty_message_is_the_class_name_alone():
    def silent(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("", request=request)

    check = probes.cube("http://cube", SECRET, _client(silent), NOW)
    assert check.detail == "ConnectError"


def test_ollama_ok_names_the_model():
    client = _client(
        lambda request: httpx.Response(200, json={"models": [{"name": "qwen2.5-coder:7b"}]})
    )
    check = probes.ollama("http://ollama", "qwen2.5-coder:7b", client)
    assert (check.service, check.ok) == ("ollama", True)
    assert "qwen2.5-coder:7b" in check.detail


def test_ollama_model_named_without_a_tag_matches_the_latest_tag():
    client = _client(
        lambda request: httpx.Response(200, json={"models": [{"name": "gemma4:latest"}]})
    )
    check = probes.ollama("http://ollama", "gemma4", client)
    assert (check.service, check.ok) == ("ollama", True)
    assert "gemma4" in check.detail


def test_ollama_model_named_without_a_tag_does_not_match_another_tag():
    client = _client(lambda request: httpx.Response(200, json={"models": [{"name": "gemma4:2b"}]}))
    check = probes.ollama("http://ollama", "gemma4", client)
    assert check == probes.Check("ollama", False, "model not pulled: gemma4")


def test_ollama_model_not_pulled():
    client = _client(lambda request: httpx.Response(200, json={"models": [{"name": "other:1b"}]}))
    check = probes.ollama("http://ollama", "qwen2.5-coder:7b", client)
    assert check == probes.Check("ollama", False, "model not pulled: qwen2.5-coder:7b")


def test_ollama_unreachable():
    check = probes.ollama("http://ollama", "m", _client(_raise_connect_error))
    assert (check.service, check.ok) == ("ollama", False)
    assert check.detail.startswith("ConnectError")


def _closed_settings() -> Settings:
    return Settings(
        postgres_dsn="postgresql://lab:secret@127.0.0.1:1/lab",
        neo4j_uri="bolt://127.0.0.1:1",
        neo4j_user="neo4j",
        neo4j_password="secret",
        cube_url="http://127.0.0.1:1",
        cube_secret=SECRET,
        ollama_url="http://127.0.0.1:1",
        model="m",
    )


def test_run_returns_the_service_checks_in_order_and_the_model_check_last():
    with httpx.Client(timeout=2.0) as client:
        without = probes.run(_closed_settings(), client, NOW, with_model=False)
        with_model = probes.run(_closed_settings(), client, NOW, with_model=True)
    assert [check.service for check in without] == ["postgres", "neo4j", "cube"]
    assert [check.service for check in with_model] == ["postgres", "neo4j", "cube", "ollama"]
    assert not any(check.ok for check in with_model)
