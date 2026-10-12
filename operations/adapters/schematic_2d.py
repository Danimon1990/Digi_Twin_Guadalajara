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
    layout = _load_layout(layout_path)
    if layout.get("schema_version") not in {
        "operations_schematic_2d_v1", "operations_layout_2d_v2"
    }:
        raise ValueError("unsupported 2D operations layout schema")
    if layout.get("evidence") not in {
        "schematic_not_measured", "blender_scene_geometry"
    }:
        raise ValueError("2D layout must declare its geometry evidence")
    _validate_worker_access(layout)
    layout = _project_world_layout(layout)

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
        effective_config = json.loads(run["effective_config_json"])
        worker_config = {
            item["worker_id"]: item for item in effective_config.get("workers", [])
        }
        workers = [{
            "worker_id": row["worker_id"],
            "display_code": row["display_code"],
            "eligible_roles": json.loads(row["eligible_roles_json"]),
            "primary_role": worker_config[row["worker_id"]].get("primary_role"),
            "default_activity": worker_config[row["worker_id"]].get(
                "default_activity", "idle"
            ),
        } for row in connection.execute(
            "SELECT worker_id,display_code,eligible_roles_json FROM workers ORDER BY worker_id"
        ).fetchall() if row["worker_id"] in worker_config]
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
        order_rows = connection.execute(
            """SELECT o.order_id,o.visit_id,o.channel,o.fulfillment_mode,
                      ol.product_id,p.name AS product_name,ol.quantity,ol.unit,
                      ol.unit_price_cop
               FROM orders o
               LEFT JOIN order_lines ol ON ol.order_id=o.order_id
               LEFT JOIN products p ON p.product_id=ol.product_id
               WHERE o.run_id=? ORDER BY o.order_id,ol.line_id""",
            (run_id,),
        ).fetchall()
    finally:
        connection.close()

    orders_by_id: dict[str, dict[str, Any]] = {}
    for row in order_rows:
        order = orders_by_id.setdefault(row["order_id"], {
            "order_id": row["order_id"],
            "visit_id": row["visit_id"],
            "channel": row["channel"],
            "fulfillment_mode": row["fulfillment_mode"],
            "lines": [],
            "total_cop": 0,
            "price_known": True,
        })
        if row["product_id"] is not None:
            order["lines"].append({
                "product_id": row["product_id"],
                "product_name": row["product_name"],
                "quantity": row["quantity"],
                "unit": row["unit"],
                "unit_price_cop": row["unit_price_cop"],
            })
            if row["unit_price_cop"] is None:
                order["price_known"] = False
                order["total_cop"] = None
            elif order["price_known"]:
                order["total_cop"] += int(row["quantity"] * row["unit_price_cop"])

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
    order_sizes = {
        object_item["id"]: event["payload"].get("order_size")
        for event in events if event["activity"] == "order_created"
        for object_item in event["objects"] if object_item["type"] == "order"
    }
    for order_id, order in orders_by_id.items():
        order["size_label"] = order_sizes.get(order_id)
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
        "orders": list(orders_by_id.values()),
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


def _load_layout(layout_path: Path) -> dict[str, Any]:
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    snapshot_name = layout.get("geometry_snapshot_file")
    if not snapshot_name:
        return layout
    snapshot_path = layout_path.parent / snapshot_name
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if snapshot.get("schema_version") != "operations_blender_geometry_v1":
        raise ValueError("unsupported Blender geometry snapshot schema")
    entities = {item["entity_id"]: item for item in snapshot["entities"]}
    fixtures = []
    for spec in layout.get("geometry_fixtures", []):
        if spec["entity_id"] not in entities:
            raise ValueError(f"unknown geometry entity {spec['entity_id']!r}")
        bounds = entities[spec["entity_id"]]["bounds_m"]
        fixtures.append({
            "shape": "rect",
            "x": bounds["min"][0],
            "y": bounds["min"][1],
            "width": bounds["size"][0],
            "height": bounds["size"][1],
            "label": spec["label"],
            "class": spec["class"],
            "entity_id": spec["entity_id"],
        })
    layout["fixtures"] = fixtures
    layout["geometry_snapshot"] = {
        "source_blend": snapshot["source_blend"],
        "source_sha256": snapshot["source_sha256"],
        "unit_system": snapshot["unit_system"],
        "scale_length": snapshot["scale_length"],
    }
    return layout


def _validate_worker_access(layout: dict[str, Any]) -> None:
    locations = layout.get("locations", {})
    room = next(
        (item for item in layout.get("fixtures", []) if item.get("class") == "room"),
        None,
    )
    if room is None:
        raise ValueError("layout requires one room fixture")
    blocked = [
        item for item in layout.get("fixtures", [])
        if item.get("class") != "room" and item.get("shape") == "rect"
    ]
    for location_id in layout.get("worker_access_locations", []):
        point = locations.get(location_id)
        if point is None:
            raise ValueError(f"unknown worker access location {location_id!r}")
        inside_room = (
            room["x"] < point["x"] < room["x"] + room["width"]
            and room["y"] < point["y"] < room["y"] + room["height"]
        )
        if not inside_room:
            raise ValueError(f"worker access {location_id!r} is outside the service area")
        for fixture in blocked:
            inside_fixture = (
                fixture["x"] <= point["x"] <= fixture["x"] + fixture["width"]
                and fixture["y"] <= point["y"] <= fixture["y"] + fixture["height"]
            )
            if inside_fixture:
                raise ValueError(
                    f"worker access {location_id!r} overlaps fixture {fixture['label']!r}"
                )


def _project_world_layout(layout: dict[str, Any]) -> dict[str, Any]:
    """Project Blender XY meter coordinates into the self-contained SVG canvas."""
    if layout.get("coordinate_space") != "world_meters":
        return layout
    projected = json.loads(json.dumps(layout))
    canvas = layout["canvas"]
    bounds = layout["world_bounds"]
    padding = float(layout.get("canvas_padding", 28))
    span_x = float(bounds["max_x"] - bounds["min_x"])
    span_y = float(bounds["max_y"] - bounds["min_y"])
    scale = min(
        (float(canvas["width"]) - 2 * padding) / span_x,
        (float(canvas["height"]) - 2 * padding) / span_y,
    )
    offset_x = (float(canvas["width"]) - span_x * scale) / 2
    offset_y = (float(canvas["height"]) - span_y * scale) / 2

    def point(x: float, y: float) -> tuple[float, float]:
        return (
            offset_x + (float(x) - float(bounds["min_x"])) * scale,
            offset_y + (float(bounds["max_y"]) - float(y)) * scale,
        )

    for fixture in projected["fixtures"]:
        x0, y0 = point(fixture["x"], fixture["y"] + fixture["height"])
        fixture["x"] = round(x0, 3)
        fixture["y"] = round(y0, 3)
        fixture["width"] = round(float(fixture["width"]) * scale, 3)
        fixture["height"] = round(float(fixture["height"]) * scale, 3)
    for location in projected["locations"].values():
        location["x"], location["y"] = (
            round(value, 3) for value in point(location["x"], location["y"])
        )
    projected["meters_per_pixel"] = 1 / scale
    projected["projection_scale_px_per_m"] = scale
    geometry = projected.get("agent_geometry")
    if geometry:
        geometry["worker_radius_px"] = (
            float(geometry["worker_body_diameter_m"]) * scale / 2
        )
        geometry["customer_radius_px"] = (
            float(geometry["customer_body_diameter_m"]) * scale / 2
        )
        geometry["worker_min_distance_px"] = (
            float(geometry["worker_body_diameter_m"])
            + float(geometry["worker_clearance_m"])
        ) * scale
    return projected
