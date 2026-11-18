from collections.abc import Sequence
from pathlib import Path

from rdflib import Graph


def read(files: Sequence[Path], error: type[Exception]) -> Graph:
    """Parse each Turtle file into one graph. A file that cannot be read raises `error`."""
    graph = Graph()
    for file in files:
        try:
            graph.parse(file, format="turtle")
        except (SyntaxError, ValueError, IndexError) as cause:
            # rdflib's Turtle parser raises BadSyntax (a SyntaxError) for bad syntax, a
            # UnicodeDecodeError (a ValueError) for bytes that are not UTF-8, and a bare
            # IndexError when the text stops in the middle of a statement.
            reason = " ".join(str(cause).split()) or type(cause).__name__
            raise error(f"{file.name}: not valid Turtle: {reason}") from cause
        except OSError as cause:
            reason = cause.strerror or type(cause).__name__
            raise error(f"{file.name}: {reason}") from cause
    return graph
