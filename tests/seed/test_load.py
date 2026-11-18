import re
from dataclasses import fields
from importlib.resources import files

from semantic_lab.domain.records import Dataset
from semantic_lab.seed import load


def _schema() -> str:
    return files("semantic_lab.seed").joinpath("schema.sql").read_text(encoding="utf-8")


def test_every_table_is_created_by_the_schema() -> None:
    created = re.findall(r"^create table (\w+) \(", _schema(), flags=re.MULTILINE)
    assert tuple(created) == load.TABLES
    assert len(load.TABLES) == 17


def test_every_table_is_dropped_by_the_schema() -> None:
    dropped = _schema().split("drop table if exists", 1)[1].split(";", 1)[0]
    assert set(re.findall(r"\w+", dropped)) - {"cascade"} == set(load.TABLES)


def test_the_data_tables_map_one_to_one_onto_the_dataset() -> None:
    attributes = [attribute for _, attribute in load.DATA_TABLES]
    assert attributes == [field.name for field in fields(Dataset)]
    assert tuple(table for table, _ in load.DATA_TABLES) == load.TABLES[3:]


def test_every_record_column_is_declared_in_the_schema() -> None:
    schema = _schema()
    for table, _ in load.DATA_TABLES:
        body = schema.split(f"create table {table} (", 1)[1].split("\n);", 1)[0]
        declared = {line.split()[0] for line in body.splitlines() if line.strip()}
        assert set(load._columns(table)) <= declared, table
