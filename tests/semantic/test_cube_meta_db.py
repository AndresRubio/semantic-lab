import time

import httpx
import pytest

from semantic_lab.semantic import token


@pytest.mark.db
def test_meta_returns_each_members_meta(stack):
    response = httpx.get(
        f"{stack.cube_url}/cubejs-api/v1/meta",
        headers={"Authorization": token.sign(stack.cube_secret, int(time.time()))},
        timeout=10.0,
    )

    assert response.status_code == 200
    cubes = {cube["name"]: cube for cube in response.json()["cubes"]}
    measures = {m["name"]: m for m in cubes["healthcheck"]["measures"]}
    assert measures["healthcheck.rows"]["meta"] == {"iri": "urn:semantic-lab:healthcheck"}


@pytest.mark.db
def test_a_token_signed_with_another_secret_is_refused(stack):
    response = httpx.get(
        f"{stack.cube_url}/cubejs-api/v1/meta",
        headers={"Authorization": token.sign("another-secret", int(time.time()))},
        timeout=10.0,
    )

    assert response.status_code in (401, 403)
