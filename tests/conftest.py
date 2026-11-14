import pytest
import sqlalchemy as sa


def _make(path, ddl, rows):
    eng = sa.create_engine(f"sqlite:///{path}")
    with eng.begin() as c:
        for stmt in ddl:
            c.exec_driver_sql(stmt)
        for stmt, params in rows:
            c.exec_driver_sql(stmt, params)
    return eng


BASE_DDL = [
    "CREATE TABLE users (id INTEGER PRIMARY KEY, name VARCHAR(50) NOT NULL, score FLOAT)",
    "CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id), total NUMERIC(10,2))",
    "CREATE INDEX ix_orders_user ON orders(user_id)",
    "CREATE TABLE tags (label TEXT)",
]
BASE_ROWS = [
    ("INSERT INTO users VALUES (?,?,?)", (1, "ada", 1.0)),
    ("INSERT INTO users VALUES (?,?,?)", (2, "bob", 2.0)),
    ("INSERT INTO users VALUES (?,?,?)", (3, "cy", 3.0)),
    ("INSERT INTO orders VALUES (?,?,?)", (10, 1, 9.99)),
    ("INSERT INTO tags VALUES (?)", ("x",)),
    ("INSERT INTO tags VALUES (?)", ("x",)),
]


@pytest.fixture
def same_pair(tmp_path):
    return _make(tmp_path / "same_a.db", BASE_DDL, BASE_ROWS), _make(tmp_path / "same_b.db", BASE_DDL, BASE_ROWS)


@pytest.fixture
def diff_pair(tmp_path):
    a = _make(tmp_path / "a.db", BASE_DDL + ["CREATE TABLE legacy (id INTEGER PRIMARY KEY)"], BASE_ROWS)
    ddl_b = [
        "CREATE TABLE users (id INTEGER PRIMARY KEY, name VARCHAR(50), score FLOAT, email TEXT)",
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id), total NUMERIC(10,2))",
        "CREATE TABLE tags (label TEXT)",
        "CREATE TABLE audit (id INTEGER PRIMARY KEY)",
    ]
    rows_b = [
        ("INSERT INTO users VALUES (?,?,?,?)", (1, "ada", 1.0, None)),
        ("INSERT INTO users VALUES (?,?,?,?)", (2, "bobby", 2.0, None)),  # changed
        ("INSERT INTO users VALUES (?,?,?,?)", (4, "dee", 4.0, None)),  # added; id 3 removed
        ("INSERT INTO orders VALUES (?,?,?)", (10, 1, 9.99)),
        ("INSERT INTO tags VALUES (?)", ("x",)),
        ("INSERT INTO tags VALUES (?)", ("y",)),
    ]
    return a, _make(tmp_path / "b.db", ddl_b, rows_b)
