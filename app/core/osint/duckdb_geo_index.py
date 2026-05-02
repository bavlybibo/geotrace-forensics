from __future__ import annotations

"""Optional DuckDB helper for large local GeoNames indexes."""

from pathlib import Path
from typing import Any


def duckdb_status(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root)
    try:
        import duckdb  # type: ignore
    except Exception:
        return {"available": False, "database": str(root / "data" / "geo" / "processed" / "geotrace_geo.duckdb"), "warning": "duckdb is not installed."}
    db = root / "data" / "geo" / "processed" / "geotrace_geo.duckdb"
    return {"available": True, "database": str(db), "exists": db.exists(), "version": getattr(duckdb, "__version__", "discoverable")}
