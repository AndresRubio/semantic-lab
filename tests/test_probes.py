import httpx

from semantic_lab import probes
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


def test_neo4j_on_a_closed_port_fails_without_the_password():
    check = probes.neo4j("bolt://127.0.0.1:1", "neo4j", "hunter2-secret", timeout=2)
    assert (check.service, check.ok) == ("neo4j", False)
    assert "hunter2-secret" not in check.detail


def test_cube_ok_counts_the_cubes():
    client, _ = _cube(httpx.Response(200), httpx.Response(200, json={"cubes": [{}, {}]}))
    check = probes.cube("http://cube", SECRET, client, NOW)
    assert check == probes.Check("cube", True, "2 cubes")


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


def test_ollama_ok_names_the_model():
    client = _client(
        lambda request: httpx.Response(200, json={"models": [{"name": "qwen2.5-coder:7b"}]})
    )
    check = probes.ollama("http://ollama", "qwen2.5-coder:7b", client)
    assert (check.service, check.ok) == ("ollama", True)
    assert "qwen2.5-coder:7b" in check.detail


def test_ollama_model_not_pulled():
    client = _client(lambda request: httpx.Response(200, json={"models": [{"name": "other:1b"}]}))
    check = probes.ollama("http://ollama", "qwen2.5-coder:7b", client)
    assert check == probes.Check("ollama", False, "model not pulled: qwen2.5-coder:7b")


def test_ollama_unreachable():
    check = probes.ollama("http://ollama", "m", _client(_raise_connect_error))
    assert (check.service, check.ok) == ("ollama", False)
    assert check.detail.startswith("ConnectError")
