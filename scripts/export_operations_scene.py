"""Export selected operations geometry from the open Blender file without editing it.

Run from the repository root:

  /Applications/Blender.app/Contents/MacOS/Blender --background \
    blend/guadalajara_base.blend --python scripts/export_operations_scene.py -- \
    --mapping config/operations/blender_scene_mapping.json \
    --out config/operations/despacho_geometry_from_blender.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]


def _portable_path(path: Path) -> str:
    """Store repository-relative POSIX paths when the file belongs to the repo."""
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _arguments() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--out", required=True)
    return parser.parse_args(argv)


def _objects_for(spec: dict) -> list[bpy.types.Object]:
    selector = spec["selector"]
    names = spec["names"]
    if selector in {"object", "objects"}:
        return [bpy.data.objects[name] for name in names]
    if selector == "collection":
        result: dict[str, bpy.types.Object] = {}
        for name in names:
            for obj in bpy.data.collections[name].all_objects:
                result[obj.name] = obj
        return list(result.values())
    if selector == "hierarchy":
        result = []
        for name in names:
            root = bpy.data.objects[name]
            result.append(root)
            result.extend(root.children_recursive)
        return result
    raise ValueError(f"unsupported selector {selector!r}")


def _bounds(objects: list[bpy.types.Object]) -> dict[str, list[float]]:
    points = [
        obj.matrix_world @ Vector(corner)
        for obj in objects if obj.type != "EMPTY"
        for corner in obj.bound_box
    ]
    if not points:
        points = [obj.matrix_world.translation.copy() for obj in objects]
    minimum = [min(point[index] for point in points) for index in range(3)]
    maximum = [max(point[index] for point in points) for index in range(3)]
    return {
        "min": [round(value, 4) for value in minimum],
        "max": [round(value, 4) for value in maximum],
        "size": [round(maximum[i] - minimum[i], 4) for i in range(3)],
        "center": [round((maximum[i] + minimum[i]) / 2, 4) for i in range(3)],
    }


def main() -> None:
    args = _arguments()
    mapping_path = Path(args.mapping).resolve()
    output_path = Path(args.out).resolve()
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    entities = []
    for spec in mapping["entities"]:
        objects = _objects_for(spec)
        entity = {
            "entity_id": spec["entity_id"],
            "selector": spec["selector"],
            "source_names": spec["names"],
            "bounds_m": _bounds(objects),
        }
        for key in ("semantic_status", "note"):
            if key in spec:
                entity[key] = spec[key]
        entities.append(entity)
    blend_path = Path(bpy.data.filepath).resolve()
    payload = {
        "schema_version": "operations_blender_geometry_v1",
        "source_blend": _portable_path(blend_path),
        "source_sha256": hashlib.sha256(blend_path.read_bytes()).hexdigest(),
        "unit_system": bpy.context.scene.unit_settings.system,
        "scale_length": bpy.context.scene.unit_settings.scale_length,
        "mapping_file": _portable_path(mapping_path),
        "entities": entities,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Exported {len(entities)} operations entities to {output_path}")


if __name__ == "__main__":
    main()
