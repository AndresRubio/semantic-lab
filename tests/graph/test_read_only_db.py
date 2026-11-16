import pytest
from neo4j import GraphDatabase
from neo4j.exceptions import ClientError


@pytest.mark.db
def test_a_write_in_a_read_transaction_fails(stack):
    driver = GraphDatabase.driver(stack.neo4j_uri, auth=(stack.neo4j_user, stack.neo4j_password))
    try:
        with driver.session() as session:
            with pytest.raises(ClientError):
                session.execute_read(lambda tx: tx.run("CREATE (:Probe)").consume())
            count = session.execute_read(
                lambda tx: tx.run("MATCH (n:Probe) RETURN count(n) AS n").single()["n"]
            )
    finally:
        driver.close()

    assert count == 0
