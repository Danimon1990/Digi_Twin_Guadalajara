"""Build the provisional Phase 1 floor-level changes.

The user-authored objects in ``Levels`` remain untouched as placement markers.
Physical slabs and risers are added to ``Floors``. A non-rendering cutter keeps
the lowered despacho from being covered by the common floor.
"""

from pathlib import Path
from math import atan2

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
BLEND_PATH = ROOT / "blend" / "guadalajara_base.blend"

DESPACHO_TOP_Z = -0.09
COMEDOR_TOP_Z = 0.08
SLAB_THICKNESS = 0.08

GENERATED_NAMES = {
    "FLOOR_DESPACHO_LOWER",
    "FLOOR_COMEDOR_RAISED",
    "STEP_DESPACHO_CUBE002",
    "STEP_OUTSIDE_CUBE001",
    "STEP_COMEDOR_CUBE005",
}
CUTTER_COLLECTION_NAME = "Floor_Level_Cutters_NotForExport"
CUTTER_NAME = "CUTTER_FLOOR_DESPACHO_LOWER"
BOOLEAN_NAME = "LEVEL_CUT_DESPACHO_LOWER"


def polygon_world_xy(source, polygon_index):
    polygon = source.data.polygons[polygon_index]
    return [(source.matrix_world @ source.data.vertices[index].co).xy for index in polygon.vertices]


def prism_mesh(name, xy_points, bottom_z, top_z, material, collection, status_note):
    count = len(xy_points)
    vertices = [(point.x, point.y, bottom_z) for point in xy_points]
    vertices += [(point.x, point.y, top_z) for point in xy_points]
    faces = [tuple(range(count - 1, -1, -1)), tuple(range(count, 2 * count))]
    for index in range(count):
        next_index = (index + 1) % count
        faces.append((index, next_index, count + next_index, count + index))

    mesh = bpy.data.meshes.new(f"{name}_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    if material:
        obj.data.materials.append(material)
    obj["phase"] = "Phase 1"
    obj["evidence_status"] = "Provisional"
    obj["notes"] = status_note
    return obj


def footprint_world_xy(source):
    unique = {}
    for vertex in source.data.vertices:
        point = (source.matrix_world @ vertex.co).xy
        unique[(round(point.x, 6), round(point.y, 6))] = point
    points = list(unique.values())
    center = sum(points, Vector((0.0, 0.0))) / len(points)
    return sorted(points, key=lambda point: atan2(point.y - center.y, point.x - center.x))


def step_from_footprint(name, footprint, source_name, bottom_z, top_z, material, collection, note):
    obj = prism_mesh(name, footprint, bottom_z, top_z, material, collection, note)
    obj["placement_reference"] = source_name
    return obj


def clear_previous(common_floor):
    for name in GENERATED_NAMES:
        obj = bpy.data.objects.get(name)
        if obj:
            bpy.data.objects.remove(obj, do_unlink=True)
    modifier = common_floor.modifiers.get(BOOLEAN_NAME)
    if modifier:
        common_floor.modifiers.remove(modifier)
    old_cutter = bpy.data.objects.get(CUTTER_NAME)
    if old_cutter:
        bpy.data.objects.remove(old_cutter, do_unlink=True)


def main():
    floors = bpy.data.collections.get("Floors")
    common_floor = bpy.data.objects.get("FLOOR_PROPERTY_COMMON")
    despacho_guide = bpy.data.objects.get("FLOOR_DESPACHO")
    comedores_guide = bpy.data.objects.get("FLOOR_COMEDORES")
    if not all((floors, common_floor, despacho_guide, comedores_guide)):
        raise RuntimeError("Missing required floor collection, common floor, or zone guides")

    step_sources = {
        "despacho": bpy.data.objects.get("Cube.002") or bpy.data.objects.get("STEP_DESPACHO_CUBE002"),
        "outside": bpy.data.objects.get("STEP_OUTSIDE_CUBE001") or bpy.data.objects.get("Cube.001"),
        "comedor": bpy.data.objects.get("Cube.005") or bpy.data.objects.get("STEP_COMEDOR_CUBE005"),
    }
    if not all(step_sources.values()):
        missing = [name for name, source in step_sources.items() if source is None]
        raise RuntimeError(f"Missing level marker or preserved riser for: {', '.join(missing)}")
    step_footprints = {name: footprint_world_xy(source) for name, source in step_sources.items()}
    step_source_names = {name: source.name for name, source in step_sources.items()}

    floor_material = bpy.data.materials.get("MAT_Floor_MaroonTile")
    clear_previous(common_floor)

    despacho_xy = polygon_world_xy(despacho_guide, 0)
    lower_floor = prism_mesh(
        "FLOOR_DESPACHO_LOWER", despacho_xy,
        DESPACHO_TOP_Z - SLAB_THICKNESS, DESPACHO_TOP_Z,
        floor_material, floors,
        "Top set to -0.09 m, midpoint of the user-reported 8-10 cm lower range.",
    )
    lower_floor["level_offset_m"] = DESPACHO_TOP_Z
    lower_floor["source_guide"] = "FLOOR_DESPACHO"

    # Polygon 0 is the rear comedor whose west edge follows Cube.005.
    comedor_xy = polygon_world_xy(comedores_guide, 0)
    raised_floor = prism_mesh(
        "FLOOR_COMEDOR_RAISED", comedor_xy, 0.0, COMEDOR_TOP_Z,
        floor_material, floors,
        "Top set to +0.08 m from the user-reported approximate dining-floor rise.",
    )
    raised_floor["level_offset_m"] = COMEDOR_TOP_Z
    raised_floor["source_guide"] = "FLOOR_COMEDORES polygon 0"

    step_from_footprint(
        "STEP_DESPACHO_CUBE002", step_footprints["despacho"], step_source_names["despacho"], DESPACHO_TOP_Z, 0.0,
        floor_material, floors, "Riser between the lowered despacho and the common floor.",
    )
    step_from_footprint(
        "STEP_OUTSIDE_CUBE001", step_footprints["outside"], step_source_names["outside"], DESPACHO_TOP_Z, 0.0,
        floor_material, floors,
        "Exterior riser only; the closed exterior lowered-floor perimeter is unresolved.",
    )
    step_from_footprint(
        "STEP_COMEDOR_CUBE005", step_footprints["comedor"], step_source_names["comedor"], 0.0, COMEDOR_TOP_Z,
        floor_material, floors, "Riser at the raised rear comedor boundary.",
    )

    cutter_collection = bpy.data.collections.get(CUTTER_COLLECTION_NAME)
    if cutter_collection is None:
        cutter_collection = bpy.data.collections.new(CUTTER_COLLECTION_NAME)
        bpy.context.scene.collection.children.link(cutter_collection)
    cutter_collection.hide_render = True
    cutter = prism_mesh(
        CUTTER_NAME, despacho_xy, -0.12, 0.03, None, cutter_collection,
        "Non-rendering Boolean cutter for the lowered despacho slab.",
    )
    cutter.display_type = "WIRE"
    cutter.hide_render = True

    boolean = common_floor.modifiers.new(BOOLEAN_NAME, "BOOLEAN")
    boolean.operation = "DIFFERENCE"
    boolean.solver = "EXACT"
    boolean.object = cutter

    bpy.context.scene["floor_levels_status"] = "Provisional Phase 1 geometry"
    bpy.context.scene["despacho_floor_offset_m"] = DESPACHO_TOP_Z
    bpy.context.scene["raised_comedor_floor_offset_m"] = COMEDOR_TOP_Z
    if bpy.data.objects.get("FLOOR_CLIENT_ARRIVAL_GUIDE"):
        bpy.context.scene["outside_lower_floor_outline_status"] = "Provisional closed user-authored guide"
    else:
        bpy.context.scene["outside_lower_floor_outline_status"] = "Unknown; Cube.001 riser only"

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    print("FLOOR_LEVEL_DESPACHO_TOP_Z", DESPACHO_TOP_Z)
    print("FLOOR_LEVEL_COMEDOR_TOP_Z", COMEDOR_TOP_Z)
    print("FLOOR_LEVEL_PHYSICAL_OBJECTS", len(floors.objects))
    print("FLOOR_LEVEL_EXTERIOR_OUTLINE", "UNRESOLVED")


if __name__ == "__main__":
    main()
