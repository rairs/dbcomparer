import json

import pytest
import sqlalchemy as sa

from dbcomparer import compare_data, compare_databases, compare_schema
from dbcomparer.cli import main
from dbcomparer.report import FORMATS


def test_identical_databases(same_pair):
    res = compare_databases(*same_pair)
    assert not res.has_differences
    assert {t.table for t in res.data.tables} == {"users", "orders", "tags"}


def test_schema_tables(diff_pair):
    s = compare_schema(*diff_pair)
    assert s.tables_added == ["audit"]
    assert s.tables_removed == ["legacy"]


def test_schema_columns_and_indexes(diff_pair):
    s = compare_schema(*diff_pair)
    by = {t.table: t for t in s.tables_changed}
    users = by["users"]
    kinds = {(c.name, c.kind) for c in users.columns}
    assert ("email", "added") in kinds
    assert ("name", "changed") in kinds  # NOT NULL dropped
    assert by["orders"].indexes_removed == ["(user_id)"]
    assert "tags" not in by


def test_ignore_indexes(diff_pair):
    s = compare_schema(*diff_pair, ignore_indexes=True)
    assert "orders" not in {t.table for t in s.tables_changed}


def test_data_keyed(diff_pair):
    d = compare_data(*diff_pair)
    users = next(t for t in d.tables if t.table == "users")
    assert users.key_columns == ["id"]
    assert [r["id"] for r in users.rows_added] == [4]
    assert [r["id"] for r in users.rows_removed] == [3]
    assert users.rows_changed == [{"key": {"id": 2}, "changes": {"name": {"source": "bob", "target": "bobby"}}}]
    orders = next(t for t in d.tables if t.table == "orders")
    assert not orders.has_differences


def test_data_multiset_without_key(diff_pair):
    d = compare_data(*diff_pair, include=["tags"])
    tags = d.tables[0]
    assert tags.note
    assert tags.rows_added == [{"label": "y"}]
    assert tags.rows_removed == [{"label": "x"}]


def test_custom_key_and_ignore_columns(diff_pair):
    d = compare_data(*diff_pair, include=["users"], keys={"users": ["name"]}, ignore_columns=["score"])
    u = d.tables[0]
    assert u.key_columns == ["name"]
    assert {r["name"] for r in u.rows_added} == {"bobby", "dee"}
    assert "score" not in u.rows_added[0]


def test_include_exclude(diff_pair):
    s = compare_schema(*diff_pair, exclude=["leg*", "aud*"])
    assert not s.tables_added and not s.tables_removed


def test_float_tolerance(tmp_path):
    def mk(name, v):
        e = sa.create_engine(f"sqlite:///{tmp_path / name}")
        with e.begin() as c:
            c.exec_driver_sql("CREATE TABLE m (id INTEGER PRIMARY KEY, v FLOAT)")
            c.exec_driver_sql("INSERT INTO m VALUES (1, ?)", (v,))
        return e

    a, b = mk("a.db", 1.0000001), mk("b.db", 1.0000002)
    assert compare_data(a, b).has_differences
    assert not compare_data(a, b, float_tolerance=1e-3).has_differences


def test_max_rows_truncation(tmp_path):
    a = sa.create_engine(f"sqlite:///{tmp_path / 'a.db'}")
    b = sa.create_engine(f"sqlite:///{tmp_path / 'b.db'}")
    for e in (a, b):
        with e.begin() as c:
            c.exec_driver_sql("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    with b.begin() as c:
        for i in range(20):
            c.exec_driver_sql("INSERT INTO t VALUES (?)", (i,))
    t = compare_data(a, b, max_rows=5).tables[0]
    assert len(t.rows_added) == 5 and t.truncated and t.target_rows == 20


def test_cross_type_generic_vs_strict(tmp_path):
    a = sa.create_engine(f"sqlite:///{tmp_path / 'a.db'}")
    b = sa.create_engine(f"sqlite:///{tmp_path / 'b.db'}")
    with a.begin() as c:
        c.exec_driver_sql("CREATE TABLE t (id INTEGER PRIMARY KEY, s VARCHAR(10))")
    with b.begin() as c:
        c.exec_driver_sql("CREATE TABLE t (id INTEGER PRIMARY KEY, s VARCHAR(20))")
    assert not compare_schema(a, b).has_differences
    assert compare_schema(a, b, strict_types=True).has_differences


def test_unknown_kwarg(same_pair):
    with pytest.raises(TypeError):
        compare_databases(*same_pair, bogus=1)


@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_reports_render(diff_pair, fmt):
    out = FORMATS[fmt](compare_databases(*diff_pair))
    assert "users" in out
    if fmt == "json":
        assert json.loads(out)["has_differences"] is True


def test_cli_exit_codes(diff_pair, same_pair, tmp_path, capsys):
    a, b = (str(e.url) for e in diff_pair)
    assert main([a, b]) == 1
    sa_, sb = (str(e.url) for e in same_pair)
    assert main([sa_, sb, "--schema-only"]) == 0
    out = tmp_path / "r.json"
    assert main([a, b, "-f", "json", "-o", str(out), "-k", "users=id"]) == 1
    assert json.loads(out.read_text())["data"]["tables"]
    assert main(["notadialect://x", b]) == 2
    assert "error" in capsys.readouterr().err
