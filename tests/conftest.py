import os
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from semantic_lab import config, probes
from semantic_lab.config import Settings
from tests.support import envfile
from tests.support.compose_env import without_lab_settings

ROOT = Path(__file__).resolve().parent.parent
STACK_ENV = ROOT / "tests" / "stack.env"
PROJECT = "semantic-lab-test"
READY_TIMEOUT_SECONDS = 180


def _compose(*args: str) -> subprocess.CompletedProcess[str]:
    # -f stops a COMPOSE_FILE in the shell from swapping the file. The environment loses its
    # SEMANTIC_LAB_* keys so that tests/stack.env alone decides the ports and credentials.
    return subprocess.run(
        [
            "docker",
            "compose",
            "-p",
            PROJECT,
            "-f",
            "compose.yaml",
            "--env-file",
            str(STACK_ENV),
            *args,
        ],
        cwd=ROOT,
        env=without_lab_settings(os.environ),
        capture_output=True,
        text=True,
        check=False,
    )


def _failed_checks(settings: Settings) -> list[probes.Check]:
    with httpx.Client(timeout=5.0) as client:
        checks = probes.run(settings, client, int(time.time()), with_model=False)
    return [check for check in checks if not check.ok]


@pytest.fixture(scope="session")
def stack() -> Iterator[Settings]:
    """The test stack, started once per session and removed with its volumes at the end."""
    settings = config.load(envfile.read(STACK_ENV))
    try:
        started = _compose("up", "-d")
        if started.returncode != 0:
            pytest.fail(f"docker compose up failed:\n{started.stdout}{started.stderr}")
        deadline = time.monotonic() + READY_TIMEOUT_SECONDS
        while True:
            failed = _failed_checks(settings)
            if not failed:
                break
            if time.monotonic() >= deadline:
                details = "; ".join(f"{check.service}: {check.detail}" for check in failed)
                logs = _compose("logs", "--tail", "50")
                pytest.fail(
                    f"stack not ready after {READY_TIMEOUT_SECONDS}s: {details}\n"
                    f"{logs.stdout}{logs.stderr}"
                )
            time.sleep(1)
        yield settings
    finally:
        _compose("down", "-v")
