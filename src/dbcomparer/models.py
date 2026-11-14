"""Result data structures. All are plain dataclasses and serialise to JSON."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ColumnDiff:
    name: str
    kind: str  # "added" | "removed" | "changed"
    source: dict[str, Any] | None = None
    target: dict[str, Any] | None = None


@dataclass
class TableSchemaDiff:
    table: str
    columns: list[ColumnDiff] = field(default_factory=list)
    primary_key: tuple[list[str], list[str]] | None = None
    indexes_added: list[str] = field(default_factory=list)
    indexes_removed: list[str] = field(default_factory=list)
    foreign_keys_added: list[str] = field(default_factory=list)
    foreign_keys_removed: list[str] = field(default_factory=list)

    @property
    def has_differences(self) -> bool:
        return bool(
            self.columns
            or self.primary_key
            or self.indexes_added
            or self.indexes_removed
            or self.foreign_keys_added
            or self.foreign_keys_removed
        )


@dataclass
class SchemaDiff:
    tables_added: list[str] = field(default_factory=list)
    tables_removed: list[str] = field(default_factory=list)
    tables_changed: list[TableSchemaDiff] = field(default_factory=list)

    @property
    def has_differences(self) -> bool:
        return bool(self.tables_added or self.tables_removed or self.tables_changed)


@dataclass
class TableDataDiff:
    table: str
    key_columns: list[str]
    source_rows: int
    target_rows: int
    rows_added: list[dict[str, Any]] = field(default_factory=list)
    rows_removed: list[dict[str, Any]] = field(default_factory=list)
    rows_changed: list[dict[str, Any]] = field(default_factory=list)
    truncated: bool = False
    note: str | None = None

    @property
    def has_differences(self) -> bool:
        return bool(self.rows_added or self.rows_removed or self.rows_changed or self.source_rows != self.target_rows)


@dataclass
class DataDiff:
    tables: list[TableDataDiff] = field(default_factory=list)

    @property
    def has_differences(self) -> bool:
        return any(t.has_differences for t in self.tables)


@dataclass
class ComparisonResult:
    source: str
    target: str
    schema: SchemaDiff | None = None
    data: DataDiff | None = None

    @property
    def has_differences(self) -> bool:
        return bool((self.schema and self.schema.has_differences) or (self.data and self.data.has_differences))

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["has_differences"] = self.has_differences
        return d
