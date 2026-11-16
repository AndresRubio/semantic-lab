from collections.abc import Mapping

LAB_PREFIX = "SEMANTIC_LAB_"


def without_lab_settings(environ: Mapping[str, str]) -> dict[str, str]:
    """A copy of environ with every SEMANTIC_LAB_* key removed.

    Docker Compose lets a variable of the calling shell win over --env-file, so the test
    stack would take the development ports from a shell that exported them.
    """
    return {key: value for key, value in environ.items() if not key.startswith(LAB_PREFIX)}
