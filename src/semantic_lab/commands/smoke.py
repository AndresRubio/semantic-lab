"""The smoke command: one probe per service, one line per probe."""

import argparse
import os
import sys
import time
from collections.abc import Mapping, Sequence
from typing import TextIO

import httpx

from semantic_lab import config, probes
from semantic_lab.probes import Check


def report(checks: Sequence[Check], out: TextIO) -> int:
    for check in checks:
        status = "ok   " if check.ok else "FAIL "
        out.write(f"{status} {check.service}  {check.detail}\n")
    return 0 if all(check.ok for check in checks) else 1


def main(argv: Sequence[str], env: Mapping[str, str], out: TextIO, err: TextIO) -> int:
    parser = argparse.ArgumentParser(prog="smoke", description="Probe each service once.")
    parser.add_argument("--no-model", action="store_true", help="skip the Ollama probe")
    args = parser.parse_args(argv)
    try:
        settings = config.load(env)
    except config.MissingSetting as missing:
        err.write(f"missing setting: {missing.name}\n")
        return 2
    with httpx.Client(timeout=5.0) as client:
        checks = [
            probes.postgres(settings.postgres_dsn),
            probes.neo4j(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password),
            probes.cube(settings.cube_url, settings.cube_secret, client, int(time.time())),
        ]
        if not args.no_model:
            checks.append(probes.ollama(settings.ollama_url, settings.model, client))
    return report(checks, out)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], os.environ, sys.stdout, sys.stderr))
