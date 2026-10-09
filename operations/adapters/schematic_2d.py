from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class SchematicResult:
    output: Path
    run_id: str
    event_count: int
    stop_time_s: float


def export_schematic_2d(
    database: str | Path,
    run_id: str,
    layout_path: str | Path,
    output: str | Path,
) -> SchematicResult:
    """Create a self-contained, read-only HTML playback for one saved run."""
    database = Path(database)
    layout_path = Path(layout_path)
    output = Path(output)
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    if layout.get("schema_version") != "operations_schematic_2d_v1":
        raise ValueError("layout must use operations_schematic_2d_v1")
    if layout.get("evidence") != "schematic_not_measured":
        raise ValueError("2D layout must be explicitly marked schematic_not_measured")

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        run = connection.execute(
            "SELECT * FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if run is None:
            raise ValueError(f"unknown run {run_id!r}")
        rows = connection.execute(
            """SELECT recording_cursor,sim_time_s,activity,lifecycle,activity_id,
                      source_id,payload_json
               FROM events WHERE run_id=?
               ORDER BY sim_time_s,recording_cursor""",
            (run_id,),
        ).fetchall()
        if rows and any(row["sim_time_s"] is None for row in rows):
            raise ValueError("this first 2D viewer supports simulated logical time only")
        object_rows = connection.execute(
            """SELECT eo.recording_cursor,eo.object_type,eo.object_id,eo.qualifier
               FROM event_objects eo JOIN events e USING(recording_cursor)
               WHERE e.run_id=? ORDER BY eo.recording_cursor""",
            (run_id,),
        ).fetchall()
        objects: dict[int, list[dict[str, str]]] = {}
        for item in object_rows:
            objects.setdefault(int(item["recording_cursor"]), []).append({
                "type": item["object_type"],
                "id": item["object_id"],
                "qualifier": item["qualifier"],
            })
        workers = [{
            "worker_id": row["worker_id"],
            "display_code": row["display_code"],
            "eligible_roles": json.loads(row["eligible_roles_json"]),
        } for row in connection.execute(
            """SELECT DISTINCT w.worker_id,w.display_code,w.eligible_roles_json
               FROM workers w JOIN event_objects eo
                 ON eo.object_type='worker' AND eo.object_id=w.worker_id
               JOIN events e USING(recording_cursor)
               WHERE e.run_id=? ORDER BY w.worker_id""",
            (run_id,),
        ).fetchall()]
        resources = [dict(row) for row in connection.execute(
            """SELECT DISTINCT r.resource_id,r.resource_type,r.capacity
               FROM resources r JOIN event_objects eo
                 ON eo.object_type='resource' AND eo.object_id=r.resource_id
               JOIN events e USING(recording_cursor)
               WHERE e.run_id=? ORDER BY r.resource_id""",
            (run_id,),
        ).fetchall()]
        visits = [row[0] for row in connection.execute(
            "SELECT visit_id FROM visits WHERE run_id=? ORDER BY visit_id", (run_id,)
        ).fetchall()]
        orders = [row[0] for row in connection.execute(
            "SELECT order_id FROM orders WHERE run_id=? ORDER BY order_id", (run_id,)
        ).fetchall()]
    finally:
        connection.close()

    events = [{
        "cursor": int(row["recording_cursor"]),
        "time": float(row["sim_time_s"]),
        "activity": row["activity"],
        "lifecycle": row["lifecycle"],
        "activity_id": row["activity_id"],
        "source_id": row["source_id"],
        "payload": json.loads(row["payload_json"]),
        "objects": objects.get(int(row["recording_cursor"]), []),
    } for row in rows]
    maximum_event_time = max((event["time"] for event in events), default=0.0)
    analysis_cutoff = run["analysis_cutoff_s"]
    playback_end = maximum_event_time or float(analysis_cutoff or 0.0)
    data: dict[str, Any] = {
        "run": {
            "run_id": run_id,
            "kind": run["kind"],
            "status": run["status"],
            "scenario_id": run["scenario_id"],
            "stop_time_s": playback_end,
            "analysis_cutoff_s": (
                None if analysis_cutoff is None else float(analysis_cutoff)
            ),
        },
        "events": events,
        "workers": workers,
        "resources": resources,
        "visits": visits,
        "orders": orders,
    }
    template = Path(__file__).with_name("schematic_2d_template.html").read_text(
        encoding="utf-8"
    )
    html = template.replace(
        "__SIMULATION_DATA__", _safe_json(data)
    ).replace("__LAYOUT_DATA__", _safe_json(layout))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return SchematicResult(output, run_id, len(events), playback_end)


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":")).replace(
        "</", "<\\/"
    )
