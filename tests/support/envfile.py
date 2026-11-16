from pathlib import Path


def read(path: Path) -> dict[str, str]:
    """Parse a KEY=VALUE file, skipping blank lines and lines that start with #."""
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        values[key] = value
    return values
