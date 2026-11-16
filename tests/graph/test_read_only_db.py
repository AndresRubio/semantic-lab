import pytest
from neo4j import GraphDatabase, ManagedTransaction
from neo4j.exceptions import ClientError


def _count_probes(tx: ManagedTransaction) -> int:
    record = tx.run("MATCH (n:Probe) RETURN count(n) AS n").single()
    assert record is not None
    return int(record["n"])


@pytest.mark.db
def test_a_write_in_a_read_transaction_fails(stack):
    driver = GraphDatabase.driver(stack.neo4j_uri, auth=(stack.neo4j_user, stack.neo4j_password))
    try:
        with driver.session() as session:
            with pytest.raises(ClientError):
                session.execute_read(lambda tx: tx.run("CREATE (:Probe)").consume())
            count = session.execute_read(_count_probes)
    finally:
        driver.close()

    assert count == 0
