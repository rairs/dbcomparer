"""dbcomparer: compare the schema and data of any two SQLAlchemy-supported databases."""

from .compare import compare_data, compare_databases, compare_schema
from .models import (
    ColumnDiff,
    ComparisonResult,
    DataDiff,
    SchemaDiff,
    TableDataDiff,
    TableSchemaDiff,
)

__all__ = [
    "compare_databases",
    "compare_schema",
    "compare_data",
    "ColumnDiff",
    "ComparisonResult",
    "DataDiff",
    "SchemaDiff",
    "TableDataDiff",
    "TableSchemaDiff",
]

__version__ = "0.1.0"
