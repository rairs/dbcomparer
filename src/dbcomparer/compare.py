"""Core comparison logic.

Schema comparison uses SQLAlchemy's runtime inspector, so it works with any
dialect SQLAlchemy supports (SQLite, PostgreSQL, MySQL/MariaDB, SQL Server,
Oracle, DuckDB, ...). Column types are compared by their *generic* SQLAlchemy
type by default, which lets you compare, for example, a PostgreSQL database
with its SQLite export without spurious ``VARCHAR`` vs ``TEXT`` noise.

Data comparison matches rows by primary key (or user-supplied key columns).
Tables without any key are compared as multisets of rows.
"""

from __future__ import annotations

import datetime as _dt
import decimal
import fnmatch
import math
from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Any, Union

import sqlalchemy as sa
from sqlalchemy.engine import Engine

from .models import (
    ColumnDiff,
    ComparisonResult,
    DataDiff,
    SchemaDiff,
    TableDataDiff,
    TableSchemaDiff,
)

EngineLike = Union[Engine, str]


def _engine(e: EngineLike) -> Engine:
    return sa.create_engine(e) if isinstance(e, str) else e


def _dispose_owned(*pairs: Any) -> None:
    """Dispose engines that dbcomparer created from URL strings."""
    for given, eng in zip(pairs[::2], pairs[1::2]):
        if isinstance(given, str):
            eng.dispose()


def _safe_url(e: Engine) -> str:
    return e.url.render_as_string(hide_password=True)


def _filter_tables(
    names: Iterable[str],
    include: Sequence[str] | None,
    exclude: Sequence[str] | None,
) -> set[str]:
    out = set()
    for n in names:
        if include and not any(fnmatch.fnmatch(n, p) for p in include):
            continue
        if exclude and any(fnmatch.fnmatch(n, p) for p in exclude):
            continue
        out.add(n)
    return out


def _type_name(t: sa.types.TypeEngine, strict: bool) -> str:
    if strict:
        return str(t.compile()) if not isinstance(t, sa.types.NullType) else "NULL"
    try:
        g = t.as_generic()
    except NotImplementedError:
        g = t
    return type(g).__name__.upper()


def _column_info(col: dict[str, Any], strict: bool) -> dict[str, Any]:
    return {
        "type": _type_name(col["type"], strict),
        "nullable": bool(col.get("nullable", True)),
    }


def _fk_sig(fk: dict[str, Any]) -> str:
    return "({}) -> {}({})".format(
        ",".join(fk["constrained_columns"]),
        fk["referred_table"],
        ",".join(fk["referred_columns"]),
    )


def _idx_sig(ix: dict[str, Any]) -> str:
    cols = ",".join(c or "<expr>" for c in ix.get("column_names") or [])
    return f"{'UNIQUE ' if ix.get('unique') else ''}({cols})"


def compare_schema(
    source: EngineLike,
    target: EngineLike,
    *,
    schema: str | None = None,
    include: Sequence[str] | None = None,
    exclude: Sequence[str] | None = None,
    strict_types: bool = False,
    ignore_indexes: bool = False,
) -> SchemaDiff:
    """Compare tables, columns, primary keys, indexes and foreign keys."""
    s_eng, t_eng = _engine(source), _engine(target)
    try:
        return _compare_schema(s_eng, t_eng, schema, include, exclude, strict_types, ignore_indexes)
    finally:
        _dispose_owned(source, s_eng, target, t_eng)


def _compare_schema(s_eng, t_eng, schema, include, exclude, strict_types, ignore_indexes) -> SchemaDiff:
    si, ti = sa.inspect(s_eng), sa.inspect(t_eng)
    s_tables = _filter_tables(si.get_table_names(schema=schema), include, exclude)
    t_tables = _filter_tables(ti.get_table_names(schema=schema), include, exclude)

    diff = SchemaDiff(
        tables_added=sorted(t_tables - s_tables),
        tables_removed=sorted(s_tables - t_tables),
    )

    for table in sorted(s_tables & t_tables):
        td = TableSchemaDiff(table=table)
        s_pk = si.get_pk_constraint(table, schema=schema).get("constrained_columns") or []
        t_pk = ti.get_pk_constraint(table, schema=schema).get("constrained_columns") or []
        s_cols = {c["name"]: _column_info(c, strict_types) for c in si.get_columns(table, schema=schema)}
        t_cols = {c["name"]: _column_info(c, strict_types) for c in ti.get_columns(table, schema=schema)}
        # Primary-key columns are NOT NULL by definition; some dialects (SQLite) report otherwise.
        for cols, pk in ((s_cols, s_pk), (t_cols, t_pk)):
            for name in pk:
                if name in cols:
                    cols[name]["nullable"] = False
        for name in sorted(t_cols.keys() - s_cols.keys()):
            td.columns.append(ColumnDiff(name, "added", target=t_cols[name]))
        for name in sorted(s_cols.keys() - t_cols.keys()):
            td.columns.append(ColumnDiff(name, "removed", source=s_cols[name]))
        for name in sorted(s_cols.keys() & t_cols.keys()):
            if s_cols[name] != t_cols[name]:
                td.columns.append(ColumnDiff(name, "changed", s_cols[name], t_cols[name]))

        if list(s_pk) != list(t_pk):
            td.primary_key = (list(s_pk), list(t_pk))

        if not ignore_indexes:
            s_ix = {_idx_sig(i) for i in si.get_indexes(table, schema=schema)}
            t_ix = {_idx_sig(i) for i in ti.get_indexes(table, schema=schema)}
            td.indexes_added = sorted(t_ix - s_ix)
            td.indexes_removed = sorted(s_ix - t_ix)

        s_fk = {_fk_sig(f) for f in si.get_foreign_keys(table, schema=schema)}
        t_fk = {_fk_sig(f) for f in ti.get_foreign_keys(table, schema=schema)}
        td.foreign_keys_added = sorted(t_fk - s_fk)
        td.foreign_keys_removed = sorted(s_fk - t_fk)

        if td.has_differences:
            diff.tables_changed.append(td)
    return diff


def _normalize(v: Any, float_tol: float) -> Any:
    """Make values from different drivers comparable."""
    if isinstance(v, decimal.Decimal):
        v = float(v)
    if isinstance(v, float):
        if math.isnan(v):
            return "NaN"
        if float_tol > 0:
            return round(v / float_tol) * float_tol
        return v
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (bytes, bytearray, memoryview)):
        return bytes(v).hex()
    if isinstance(v, _dt.datetime) and v.tzinfo is not None:
        return v.astimezone(_dt.timezone.utc).replace(tzinfo=None).isoformat()
    if isinstance(v, (_dt.date, _dt.time, _dt.datetime)):
        return v.isoformat()
    return v


def _jsonable(v: Any) -> Any:
    v = _normalize(v, 0)
    if isinstance(v, (str, int, float)) or v is None:
        return v
    return str(v)


def _rows(eng: Engine, table: sa.Table, cols: list[str], chunk: int) -> Iterable[tuple]:
    stmt = sa.select(*[table.c[c] for c in cols])
    with eng.connect() as conn:
        res = conn.execution_options(stream_results=True).execute(stmt)
        while batch := res.fetchmany(chunk):
            yield from (tuple(r) for r in batch)


def _compare_table_data(
    s_eng: Engine,
    t_eng: Engine,
    table: str,
    *,
    schema: str | None,
    key_columns: Sequence[str] | None,
    float_tol: float,
    max_rows: int,
    chunk: int,
    ignore_columns: Sequence[str],
) -> TableDataDiff:
    s_tab = sa.Table(table, sa.MetaData(), autoload_with=s_eng, schema=schema)
    t_tab = sa.Table(table, sa.MetaData(), autoload_with=t_eng, schema=schema)
    shared = [c.name for c in s_tab.columns if c.name in t_tab.c and c.name not in ignore_columns]

    keys = list(key_columns) if key_columns else [c.name for c in s_tab.primary_key.columns]
    keys = [k for k in keys if k in shared]
    note = None
    if not keys:
        note = "no key columns: compared as a multiset of rows"
    values = [c for c in shared if c not in keys]
    cols = keys + values
    nk = len(keys)

    def norm(row: tuple) -> tuple:
        return tuple(_normalize(v, float_tol) for v in row)

    def as_dict(row: tuple) -> dict[str, Any]:
        return {c: _jsonable(v) for c, v in zip(cols, row)}

    out = TableDataDiff(table=table, key_columns=keys, source_rows=0, target_rows=0, note=note)

    def record(lst: list, item: dict) -> None:
        if len(lst) < max_rows:
            lst.append(item)
        else:
            out.truncated = True

    if nk == 0:
        s_count: Counter = Counter()
        raw: dict[tuple, tuple] = {}
        for r in _rows(s_eng, s_tab, cols, chunk):
            n = norm(r)
            s_count[n] += 1
            raw.setdefault(n, r)
            out.source_rows += 1
        t_count: Counter = Counter()
        for r in _rows(t_eng, t_tab, cols, chunk):
            n = norm(r)
            t_count[n] += 1
            raw.setdefault(n, r)
            out.target_rows += 1
        for n, c in (t_count - s_count).items():
            for _ in range(c):
                record(out.rows_added, as_dict(raw[n]))
        for n, c in (s_count - t_count).items():
            for _ in range(c):
                record(out.rows_removed, as_dict(raw[n]))
        return out

    src: dict[tuple, tuple] = {}
    for r in _rows(s_eng, s_tab, cols, chunk):
        src[norm(r[:nk])] = r
        out.source_rows += 1
    for r in _rows(t_eng, t_tab, cols, chunk):
        out.target_rows += 1
        k = norm(r[:nk])
        s_row = src.pop(k, None)
        if s_row is None:
            record(out.rows_added, as_dict(r))
            continue
        if norm(s_row[nk:]) != norm(r[nk:]):
            changes = {
                cols[i]: {"source": _jsonable(s_row[i]), "target": _jsonable(r[i])}
                for i in range(nk, len(cols))
                if _normalize(s_row[i], float_tol) != _normalize(r[i], float_tol)
            }
            record(
                out.rows_changed,
                {"key": {c: _jsonable(v) for c, v in zip(keys, r[:nk])}, "changes": changes},
            )
    for r in src.values():
        record(out.rows_removed, as_dict(r))
    return out


def compare_data(
    source: EngineLike,
    target: EngineLike,
    *,
    schema: str | None = None,
    include: Sequence[str] | None = None,
    exclude: Sequence[str] | None = None,
    keys: dict[str, Sequence[str]] | None = None,
    ignore_columns: Sequence[str] = (),
    float_tolerance: float = 0.0,
    max_rows: int = 100,
    chunk_size: int = 10_000,
) -> DataDiff:
    """Compare row contents of every table present in both databases.

    ``keys`` maps a table name to the columns used to match rows; tables not
    listed use their primary key. ``max_rows`` caps how many differing rows of
    each kind are recorded per table (counts are always exact).
    """
    s_eng, t_eng = _engine(source), _engine(target)
    try:
        return _compare_data(
            s_eng, t_eng, schema, include, exclude, keys, ignore_columns, float_tolerance, max_rows, chunk_size
        )
    finally:
        _dispose_owned(source, s_eng, target, t_eng)


def _compare_data(
    s_eng, t_eng, schema, include, exclude, keys, ignore_columns, float_tolerance, max_rows, chunk_size
) -> DataDiff:
    s_tables = _filter_tables(sa.inspect(s_eng).get_table_names(schema=schema), include, exclude)
    t_tables = _filter_tables(sa.inspect(t_eng).get_table_names(schema=schema), include, exclude)
    keys = keys or {}
    result = DataDiff()
    for table in sorted(s_tables & t_tables):
        result.tables.append(
            _compare_table_data(
                s_eng,
                t_eng,
                table,
                schema=schema,
                key_columns=keys.get(table),
                float_tol=float_tolerance,
                max_rows=max_rows,
                chunk=chunk_size,
                ignore_columns=ignore_columns,
            )
        )
    return result


def compare_databases(
    source: EngineLike,
    target: EngineLike,
    *,
    schema_only: bool = False,
    data_only: bool = False,
    **kwargs: Any,
) -> ComparisonResult:
    """Compare schema and/or data. Extra keyword arguments are routed to
    :func:`compare_schema` and :func:`compare_data` as appropriate."""
    s_eng, t_eng = _engine(source), _engine(target)
    schema_keys = ("schema", "include", "exclude", "strict_types", "ignore_indexes")
    schema_kw = {k: kwargs[k] for k in schema_keys if k in kwargs}
    data_kw = {
        k: kwargs[k]
        for k in ("schema", "include", "exclude", "keys", "ignore_columns", "float_tolerance", "max_rows", "chunk_size")
        if k in kwargs
    }
    unknown = set(kwargs) - set(schema_kw) - set(data_kw)
    if unknown:
        raise TypeError(f"unexpected arguments: {sorted(unknown)}")
    res = ComparisonResult(source=_safe_url(s_eng), target=_safe_url(t_eng))
    try:
        if not data_only:
            res.schema = compare_schema(s_eng, t_eng, **schema_kw)
        if not schema_only:
            res.data = compare_data(s_eng, t_eng, **data_kw)
    finally:
        _dispose_owned(source, s_eng, target, t_eng)
    return res
