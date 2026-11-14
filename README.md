# dbcomparer

[![CI](https://github.com/rairs/dbcomparer/actions/workflows/ci.yml/badge.svg)](https://github.com/rairs/dbcomparer/actions/workflows/ci.yml)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24213701.svg)](https://doi.org/10.5281/zenodo.24213701)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**dbcomparer** compares the *schema* and *data* of any two SQL databases that
[SQLAlchemy](https://www.sqlalchemy.org/) can connect to: SQLite, PostgreSQL,
MySQL/MariaDB, SQL Server, Oracle, DuckDB, and more. The two databases do not
need to use the same engine, so you can check that a PostgreSQL production
database and its SQLite snapshot really hold the same thing.

It was written for researchers and data engineers who need to show that a
dataset is unchanged after a migration, an ETL re-run, a software upgrade, or a
hand-off between collaborators.

## Features

- **Schema diff:** tables, columns, types, nullability, primary keys, indexes and foreign keys.
- **Cross-engine type matching:** types are compared by their generic SQLAlchemy
  type by default (`VARCHAR(10)` ≈ `TEXT`); use `--strict-types` for exact matching.
- **Row-level data diff:** rows added, removed and changed (with per-column before/after
  values), matched by primary key or by key columns you choose.
- **Keyless tables:** compared as multisets, so duplicates are counted correctly.
- **Value normalisation** across drivers (Decimal/float, bool/int, bytes, timezone-aware
  datetimes), plus an optional absolute float tolerance.
- **Reports** in text, Markdown, JSON or HTML. Exit codes (0 = same, 1 = different,
  2 = error) make it easy to use in CI.
- **Python API** returning plain dataclasses.

## Installation

```bash
pip install dbcomparer                 # SQLite works out of the box
pip install "dbcomparer[postgres]"     # + PostgreSQL driver
pip install "dbcomparer[mysql]"        # + MySQL/MariaDB driver
pip install "dbcomparer[duckdb]"       # + DuckDB
```

From source:

```bash
git clone https://github.com/rairs/dbcomparer && cd dbcomparer
pip install -e ".[dev]"
```

## Command-line usage

```bash
dbcomparer sqlite:///before.db sqlite:///after.db
dbcomparer postgresql://user@host/prod sqlite:///snapshot.db --format markdown -o report.md
dbcomparer A_URL B_URL --schema-only
dbcomparer A_URL B_URL --data-only -i "obs_*" -x "obs_tmp" \
    --key measurements=station_id,ts --ignore-column updated_at --float-tolerance 1e-9
```

Run `dbcomparer --help` for every option.

## Python usage

```python
from dbcomparer import compare_databases
from dbcomparer.report import to_markdown

result = compare_databases(
    "sqlite:///before.db",
    "sqlite:///after.db",
    keys={"measurements": ["station_id", "ts"]},
    float_tolerance=1e-9,
)
if result.has_differences:
    print(to_markdown(result))
```

`compare_schema()` and `compare_data()` are also available separately, and they
accept SQLAlchemy `Engine` objects as well as URL strings.

## How it works

The schema is read with SQLAlchemy's runtime inspector. For data, the source
table is streamed in chunks into a hash map keyed on the row key, then the
target is streamed and matched against it. This takes one pass over each table
and memory proportional to the source table. Counts are always exact; the
number of example rows recorded per table is capped by `--max-rows`.

## Limitations

- Memory scales with the size of the largest compared table, so very large
  tables (hundreds of millions of rows) should be filtered or compared by key range.
- Views, triggers, stored procedures and check constraints are not compared yet.
- Float tolerance is absolute, not relative.

## Testing

```bash
pip install -e ".[test]"
pytest
```

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and the
[Code of Conduct](CODE_OF_CONDUCT.md).

## Citation

If you use dbcomparer in research, please cite it using [CITATION.cff](CITATION.cff)
(and the JOSS paper once it is published). The underlying approach is described in:

> Rai, R. S. (2026). Universal Database Comparison Framework. *International Journal
> of Creative Research Thoughts*, 14(3), e436–e441. https://doi.org/10.56975/ijcrt.v14i3.303410

## License

MIT. See [LICENSE](LICENSE).
