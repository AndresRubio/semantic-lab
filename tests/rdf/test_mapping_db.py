import psycopg
import pytest

from semantic_lab.config import Settings
from semantic_lab.domain.mapping import Mapping

pytestmark = pytest.mark.db


def test_every_mapped_column_is_a_column_of_the_database(seeded: Settings, mapping: Mapping) -> None:
    with psycopg.connect(seeded.postgres_dsn) as connection:
        rows = connection.execute(
            "select table_name, column_name from information_schema.columns "
            "where table_schema = 'public'"
        ).fetchall()
    assert mapping.postgres_columns() <= {(table, column) for table, column in rows}
