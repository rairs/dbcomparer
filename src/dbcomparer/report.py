"""Render a ComparisonResult as text, Markdown, JSON or HTML."""

from __future__ import annotations

import html
import json

from .models import ComparisonResult


def to_json(result: ComparisonResult, indent: int = 2) -> str:
    return json.dumps(result.to_dict(), indent=indent, default=str)


def to_markdown(result: ComparisonResult) -> str:
    L: list[str] = [
        "# Database comparison",
        "",
        f"- **Source:** `{result.source}`",
        f"- **Target:** `{result.target}`",
        f"- **Differences found:** {'yes' if result.has_differences else 'no'}",
        "",
    ]
    s = result.schema
    if s is not None:
        L += ["## Schema", ""]
        if not s.has_differences:
            L += ["No schema differences.", ""]
        for t in s.tables_added:
            L.append(f"- Table `{t}` only in target")
        for t in s.tables_removed:
            L.append(f"- Table `{t}` only in source")
        for td in s.tables_changed:
            L.append(f"- Table `{td.table}` differs:")
            for c in td.columns:
                if c.kind == "added":
                    L.append(f"  - column `{c.name}` added ({c.target['type']})")
                elif c.kind == "removed":
                    L.append(f"  - column `{c.name}` removed ({c.source['type']})")
                else:
                    L.append(f"  - column `{c.name}` changed: {c.source} -> {c.target}")
            if td.primary_key:
                L.append(f"  - primary key {td.primary_key[0]} -> {td.primary_key[1]}")
            for i in td.indexes_added:
                L.append(f"  - index added {i}")
            for i in td.indexes_removed:
                L.append(f"  - index removed {i}")
            for f in td.foreign_keys_added:
                L.append(f"  - foreign key added {f}")
            for f in td.foreign_keys_removed:
                L.append(f"  - foreign key removed {f}")
        L.append("")
    d = result.data
    if d is not None:
        L += [
            "## Data",
            "",
            "| Table | Source rows | Target rows | Added | Removed | Changed |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for t in d.tables:
            more = "+" if t.truncated else ""
            L.append(
                f"| `{t.table}` | {t.source_rows} | {t.target_rows} | "
                f"{len(t.rows_added)}{more} | {len(t.rows_removed)}{more} | {len(t.rows_changed)}{more} |"
            )
        L.append("")
        for t in d.tables:
            if not t.has_differences:
                continue
            L += [f"### `{t.table}`", ""]
            if t.note:
                L += [f"_{t.note}_", ""]
            for r in t.rows_added:
                L.append(f"- added: `{json.dumps(r, default=str)}`")
            for r in t.rows_removed:
                L.append(f"- removed: `{json.dumps(r, default=str)}`")
            for r in t.rows_changed:
                L.append(f"- changed {json.dumps(r['key'], default=str)}: `{json.dumps(r['changes'], default=str)}`")
            L.append("")
    return "\n".join(L)


def to_text(result: ComparisonResult) -> str:
    return to_markdown(result).replace("`", "").replace("**", "")


def to_html(result: ComparisonResult) -> str:
    body = html.escape(to_markdown(result))
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>dbcomparer report</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem}"
        "pre{white-space:pre-wrap}</style></head><body><pre>"
        f"{body}</pre></body></html>"
    )


FORMATS = {"text": to_text, "markdown": to_markdown, "json": to_json, "html": to_html}
