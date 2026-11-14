"""Reproducible performance benchmark for dbcomparer.

Builds pairs of databases with N rows that differ in ~1% of rows
(0.5% changed, 0.25% added, 0.25% removed), then times compare_data()
and records peak resident memory. Each measurement runs in a fresh
subprocess so peak RSS is not polluted by earlier runs.

Usage:
    python benchmarks/run.py --sizes 10000 100000 1000000 --repeats 3 \
        [--pg postgresql+psycopg://user@host/db] --out results.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import statistics
import subprocess
import sys
import tempfile

import sqlalchemy as sa

DDL = (
    "CREATE TABLE obs (id BIGINT PRIMARY KEY, station INTEGER NOT NULL, "
    "value DOUBLE PRECISION, label VARCHAR(32), ts TIMESTAMP)"
)


def _rows(n: int, seed: int):
    rnd = random.Random(seed)
    for i in range(n):
        yield {
            "id": i,
            "station": rnd.randint(1, 500),
            "value": rnd.random() * 100,
            "label": f"s{rnd.randint(0, 99999):05d}",
            "ts": f"2026-01-{1 + i % 28:02d} {i % 24:02d}:{i % 60:02d}:00",
        }


def build(url: str, n: int, mutate: bool) -> None:
    eng = sa.create_engine(url)
    with eng.begin() as c:
        c.exec_driver_sql("DROP TABLE IF EXISTS obs")
        c.exec_driver_sql(DDL.replace("DOUBLE PRECISION", "REAL") if url.startswith("sqlite") else DDL)
    rnd = random.Random(42)
    rows = list(_rows(n, 7))
    if mutate:
        k = max(1, n // 400)  # 0.25%
        idx = rnd.sample(range(n), 4 * k)
        changed, removed = idx[: 2 * k], set(idx[2 * k : 3 * k])
        for i in changed:
            rows[i]["value"] += 1.0
        rows = [r for i, r in enumerate(rows) if i not in removed]
        rows += [dict(r, id=n + j) for j, r in enumerate(_rows(k, 99))]
    stmt = sa.text("INSERT INTO obs VALUES (:id, :station, :value, :label, :ts)")
    with eng.begin() as c:
        for s in range(0, len(rows), 50_000):
            c.execute(stmt, rows[s : s + 50_000])
    eng.dispose()


def measure(src: str, tgt: str) -> dict:
    """Run one comparison in a fresh interpreter; return time and peak RSS."""
    code = (
        "import json,resource,sys,time;from dbcomparer import compare_data;"
        "t=time.perf_counter();d=compare_data(sys.argv[1],sys.argv[2],max_rows=10**9);"
        "e=time.perf_counter()-t;t0=d.tables[0];"
        "print(json.dumps({'seconds':e,'peak_mb':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,"
        "'added':len(t0.rows_added),'removed':len(t0.rows_removed),'changed':len(t0.rows_changed)}))"
    )
    out = subprocess.run([sys.executable, "-c", code, src, tgt], check=True, capture_output=True, text=True)
    return json.loads(out.stdout)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="+", default=[10_000, 100_000, 1_000_000])
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--pg", help="PostgreSQL URL for cross-engine runs")
    ap.add_argument("--out", default="results.csv")
    a = ap.parse_args()
    tmp = tempfile.mkdtemp()
    results = []
    for n in a.sizes:
        s_url, t_url = f"sqlite:///{tmp}/s{n}.db", f"sqlite:///{tmp}/t{n}.db"
        build(s_url, n, False)
        build(t_url, n, True)
        pairs = [("sqlite-sqlite", s_url, t_url)]
        if a.pg:
            build(a.pg, n, False)
            pairs.append(("postgres-sqlite", a.pg, t_url))
        for name, s, t in pairs:
            runs = [measure(s, t) for _ in range(a.repeats)]
            row = {
                "pair": name,
                "rows": n,
                "median_s": round(statistics.median(r["seconds"] for r in runs), 3),
                "min_s": round(min(r["seconds"] for r in runs), 3),
                "peak_mb": round(max(r["peak_mb"] for r in runs), 1),
                "added": runs[0]["added"],
                "removed": runs[0]["removed"],
                "changed": runs[0]["changed"],
            }
            row["rows_per_s"] = int(2 * n / row["median_s"])
            print(row, flush=True)
            results.append(row)
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(results[0]))
        w.writeheader()
        w.writerows(results)
    print("python", sys.version.split()[0], "sqlalchemy", sa.__version__, "cpus", os.cpu_count())


if __name__ == "__main__":
    main()
