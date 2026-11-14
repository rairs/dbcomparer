"""Cross-engine test: PostgreSQL vs SQLite. Runs only when DBCOMPARER_PG_URL is set."""

import os

import pytest
import sqlalchemy as sa

from dbcomparer import compare_databases

PG_URL = os.environ.get("DBCOMPARER_PG_URL")
pytestmark = pytest.mark.skipif(not PG_URL, reason="DBCOMPARER_PG_URL not set")

DDL = "CREATE TABLE xeng (id INTEGER PRIMARY KEY, name VARCHAR(20) NOT NULL, amt NUMERIC(10,2), ok BOOLEAN)"


def test_postgres_vs_sqlite(tmp_path):
    pg = sa.create_engine(PG_URL)
    lite = sa.create_engine(f"sqlite:///{tmp_path / 'x.db'}")
    with pg.begin() as c:
        c.exec_driver_sql("DROP TABLE IF EXISTS xeng")
    for e in (pg, lite):
        with e.begin() as c:
            c.exec_driver_sql(DDL)
            c.execute(
                sa.text("INSERT INTO xeng VALUES (:i, :n, :a, :o)"),
                [{"i": 1, "n": "a", "a": 1.5, "o": True}, {"i": 2, "n": "b", "a": 2.25, "o": False}],
            )
    try:
        res = compare_databases(pg, lite, include=["xeng"])
        assert not res.has_differences, res.to_dict()
        with lite.begin() as c:
            c.exec_driver_sql("UPDATE xeng SET amt = 9 WHERE id = 2")
        res = compare_databases(pg, lite, include=["xeng"], schema_only=False)
        assert res.data.tables[0].rows_changed[0]["key"] == {"id": 2}
    finally:
        with pg.begin() as c:
            c.exec_driver_sql("DROP TABLE IF EXISTS xeng")
