"""Command-line interface: ``dbcomparer SOURCE_URL TARGET_URL [options]``.

Exit codes: 0 = identical, 1 = differences found, 2 = error.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .compare import compare_databases
from .report import FORMATS


def _parse_keys(items: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for item in items:
        table, sep, cols = item.partition("=")
        if not sep or not cols:
            raise argparse.ArgumentTypeError(f"--key must look like table=col1,col2 (got {item!r})")
        out[table] = [c.strip() for c in cols.split(",") if c.strip()]
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dbcomparer",
        description="Compare schema and data of two databases given as SQLAlchemy URLs.",
    )
    p.add_argument("source", help="source database URL, e.g. sqlite:///a.db or postgresql://u@h/db")
    p.add_argument("target", help="target database URL")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--schema-only", action="store_true", help="compare schema only")
    g.add_argument("--data-only", action="store_true", help="compare data only")
    p.add_argument("--db-schema", dest="schema", help="database schema/namespace to inspect")
    p.add_argument("-i", "--include", action="append", help="table glob to include (repeatable)")
    p.add_argument("-x", "--exclude", action="append", help="table glob to exclude (repeatable)")
    p.add_argument("-k", "--key", action="append", default=[], help="row key for a table: table=col1,col2")
    p.add_argument("--ignore-column", action="append", default=[], help="column name to ignore in data diff")
    p.add_argument("--strict-types", action="store_true", help="compare dialect-specific types exactly")
    p.add_argument("--ignore-indexes", action="store_true", help="skip index comparison")
    p.add_argument("--float-tolerance", type=float, default=0.0, help="absolute tolerance for floats")
    p.add_argument("--max-rows", type=int, default=100, help="max differing rows reported per table and kind")
    p.add_argument("-f", "--format", choices=sorted(FORMATS), default="text")
    p.add_argument("-o", "--output", help="write report to file instead of stdout")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = compare_databases(
            args.source,
            args.target,
            schema_only=args.schema_only,
            data_only=args.data_only,
            schema=args.schema,
            include=args.include,
            exclude=args.exclude,
            keys=_parse_keys(args.key),
            ignore_columns=args.ignore_column,
            strict_types=args.strict_types,
            ignore_indexes=args.ignore_indexes,
            float_tolerance=args.float_tolerance,
            max_rows=args.max_rows,
        )
    except Exception as exc:  # noqa: BLE001 - surface any driver error cleanly
        print(f"dbcomparer: error: {exc}", file=sys.stderr)
        return 2
    report = FORMATS[args.format](result)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(report)
    else:
        print(report)
    return 1 if result.has_differences else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
