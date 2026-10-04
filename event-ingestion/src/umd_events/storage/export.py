"""Write load-ready files for every Snowflake table.

- ``<TABLE>.jsonl``   one JSON object per row; what ``umd-events load-snowflake`` stages and COPYs
- ``<TABLE>.parquet`` typed columns, for Snowsight's "Load Data" UI or other tools
- ``<TABLE>.csv``     arrays/objects as JSON strings, for quick inspection in a spreadsheet
- ``frontend_events.json`` upcoming events in the shape the swipe UI uses
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .local import LocalStore
from .schema import EXPORTED_TABLES

log = logging.getLogger(__name__)


def _jsonable(value: Any, sf_type: str) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if sf_type == "VARIANT" and isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    if isinstance(value, tuple):
        return list(value)
    return value


def export_all(store: LocalStore, out_dir: Path) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for table in EXPORTED_TABLES:
        types = dict(table.columns)
        columns = [c for c, _ in table.columns]
        rows = store.query(f"SELECT {', '.join(columns)} FROM {table.name} ORDER BY {', '.join(table.key)}")
        counts[table.name] = len(rows)
        records = [{c: _jsonable(r[c], types[c]) for c in columns} for r in rows]

        with open(out_dir / f"{table.name}.jsonl", "w", encoding="utf-8", newline="\n") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        with open(out_dir / f"{table.name}.csv", "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            for record in records:
                writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                                 for k, v in record.items()})

        parquet = (out_dir / f"{table.name}.parquet").as_posix().replace("'", "''")
        store.con.execute(f"COPY (SELECT * FROM {table.name} ORDER BY {', '.join(table.key)}) "
                          f"TO '{parquet}' (FORMAT PARQUET)")

    frontend = frontend_events(store)
    with open(out_dir / "frontend_events.json", "w", encoding="utf-8") as f:
        json.dump(frontend, f, ensure_ascii=False, indent=1, default=str)
    counts["frontend_events"] = len(frontend)
    log.info("exported to %s: %s", out_dir, ", ".join(f"{k}={v}" for k, v in counts.items()))
    return counts


def frontend_events(store: LocalStore) -> list[dict[str, Any]]:
    from ..query import row_to_frontend

    rows = store.query("SELECT * FROM EVENTS WHERE COALESCE(end_time, start_time) >= now() ORDER BY start_time")
    return [row_to_frontend(r) for r in rows]
