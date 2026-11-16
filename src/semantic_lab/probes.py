"""One probe per service. A probe takes plain arguments, never raises and never puts a
credential in its result."""

from dataclasses import dataclass

import httpx
import psycopg
from neo4j import GraphDatabase

from semantic_lab.semantic import token


@dataclass(frozen=True)
class Check:
    service: str
    ok: bool
    detail: str


def _failure(service: str, error: Exception) -> Check:
    lines = str(error).splitlines()
    first_line = lines[0] if lines else ""
    return Check(service, False, f"{type(error).__name__}: {first_line}".rstrip(": "))


def postgres(dsn: str, timeout: float = 5.0) -> Check:
    try:
        with psycopg.connect(dsn, connect_timeout=max(1, int(timeout))) as connection:
            connection.execute("select 1")
    except Exception as error:
        return _failure("postgres", error)
    return Check("postgres", True, "select 1")


def neo4j(uri: str, user: str, password: str, timeout: float = 5.0) -> Check:
    try:
        with GraphDatabase.driver(
            uri,
            auth=(user, password),
            connection_timeout=timeout,
            max_transaction_retry_time=0,
        ) as driver:
            driver.execute_query("RETURN 1")
    except Exception as error:
        return _failure("neo4j", error)
    return Check("neo4j", True, "RETURN 1")


def cube(url: str, secret: str, client: httpx.Client, now: int) -> Check:
    try:
        ready = client.get(f"{url}/readyz")
        if ready.status_code != 200:
            return Check("cube", False, f"readyz: HTTP {ready.status_code}")
        meta = client.get(
            f"{url}/cubejs-api/v1/meta",
            headers={"Authorization": token.sign(secret, now)},
        )
        if meta.status_code != 200:
            return Check("cube", False, f"meta: HTTP {meta.status_code}")
        body = meta.json()
        cubes = body.get("cubes") if isinstance(body, dict) else None
        if not isinstance(cubes, list):
            return Check("cube", False, "meta: no cubes in the response")
    except Exception as error:
        return _failure("cube", error)
    return Check("cube", True, f"{len(cubes)} cubes")


def ollama(url: str, model: str, client: httpx.Client) -> Check:
    try:
        response = client.get(f"{url}/api/tags")
        if response.status_code != 200:
            return Check("ollama", False, f"tags: HTTP {response.status_code}")
        names = {entry.get("name") for entry in response.json().get("models", [])}
    except Exception as error:
        return _failure("ollama", error)
    if model not in names:
        return Check("ollama", False, f"model not pulled: {model}")
    return Check("ollama", True, f"model present: {model}")
