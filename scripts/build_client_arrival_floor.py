"""Extend the lowered despacho level into the client-arrival footprint."""

from collections import Counter, defaultdict
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
BLEND_PATH = ROOT / "blend" / "guadalajara_base.blend"
GUIDE_NAME = "FLOOR_CLIENT_ARRIVAL_GUIDE"
FLOOR_NAME = "FLOOR_CLIENT_ARRIVAL_LOWER"
CUTTER_NAME = "CUTTER_FLOOR_CLIENT_ARRIVAL_LOWER"
BOOLEAN_NAME = "LEVEL_CUT_CLIENT_ARRIVAL_LOWER"
TOP_Z = -0.09
SLAB_THICKNESS = 0.08


def resolve_guide():
    guide = bpy.data.objects.get(GUIDE_NAME) or bpy.data.objects.get("Plane")
    if guide is None:
        raise RuntimeError("Missing user-authored client-arrival Plane")
    guide.name = GUIDE_NAME
    guide.data.name = f"{GUIDE_NAME}_MESH"
    return guide


def ordered_boundary_world_xy(guide):
    edge_counts = Counter()
    for polygon in guide.data.polygons:
        vertices = list(polygon.vertices)
        for index, start in enumerate(vertices):
            end = vertices[(index + 1) % len(vertices)]
            edge_counts[tuple(sorted((start, end)))] += 1
    boundary_edges = [edge for edge, count in edge_counts.items() if count == 1]
    adjacency = defaultdict(list)
    for start, end in boundary_edges:
        adjacency[start].append(end)
        adjacency[end].append(start)
    if any(len(neighbors) != 2 for neighbors in adjacency.values()):
        raise RuntimeError("Client-arrival Plane does not have one closed perimeter")

    start = min(adjacency)
    ordered = [start]
    previous = None
    current = start
    while True:
        candidates = [item for item in adjacency[current] if item != previous]
        next_index = candidates[0]
        if next_index == start:
            break
        ordered.append(next_index)
        previous, current = current, next_index
        if len(ordered) > len(adjacency):
            raise RuntimeError("Could not order client-arrival perimeter")
    return [(guide.matrix_world @ guide.data.vertices[index].co).xy for index in ordered]


def prism(name, points, bottom_z, top_z, collection, material=None):
    count = len(points)
    vertices = [(point.x, point.y, bottom_z) for point in points]
    vertices += [(point.x, point.y, top_z) for point in points]
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
    return obj


def main():
    guide = resolve_guide()
    guides = bpy.data.collections.get("Zone_Guides_NotForExport")
    floors = bpy.data.collections.get("Floors")
    cutters = bpy.data.collections.get("Floor_Level_Cutters_NotForExport")
    common = bpy.data.objects.get("FLOOR_PROPERTY_COMMON")
    if not all((guides, floors, cutters, common)):
        raise RuntimeError("Missing required floor or guide collections")

    if guide.name not in guides.objects:
        guides.objects.link(guide)
    for collection in list(guide.users_collection):
        if collection != guides:
            collection.objects.unlink(guide)
    guide.display_type = "WIRE"
    guide.hide_render = True
    guide["zone_guide_only"] = True
    guide["not_for_export"] = True
    guide["guide_status"] = "User-authored closed arrival footprint"
    guide["target_floor_top_z_m"] = TOP_Z

    points = ordered_boundary_world_xy(guide)
    for name in (FLOOR_NAME, CUTTER_NAME):
        old = bpy.data.objects.get(name)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
    old_modifier = common.modifiers.get(BOOLEAN_NAME)
    if old_modifier:
        common.modifiers.remove(old_modifier)

    floor = prism(
        FLOOR_NAME, points, TOP_Z - SLAB_THICKNESS, TOP_Z, floors,
        bpy.data.materials.get("MAT_Floor_MaroonTile"),
    )
    floor["phase"] = "Phase 1"
    floor["evidence_status"] = "Provisional"
    floor["level_offset_m"] = TOP_Z
    floor["source_guide"] = GUIDE_NAME
    floor["notes"] = "Client-arrival area set to the same provisional level as despacho."

    cutter = prism(CUTTER_NAME, points, -0.12, 0.03, cutters)
    cutter.display_type = "WIRE"
    cutter.hide_render = True
    cutter["not_for_export"] = True
    cutter["source_guide"] = GUIDE_NAME

    modifier = common.modifiers.new(BOOLEAN_NAME, "BOOLEAN")
    modifier.operation = "DIFFERENCE"
    modifier.solver = "EXACT"
    modifier.object = cutter

    bpy.context.scene["client_arrival_floor_offset_m"] = TOP_Z
    bpy.context.scene["outside_lower_floor_outline_status"] = "Provisional closed user-authored guide"
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    print("CLIENT_ARRIVAL_FLOOR_TOP_Z", TOP_Z)
    print("CLIENT_ARRIVAL_BOUNDARY_VERTICES", len(points))
    print("CLIENT_ARRIVAL_GUIDE", GUIDE_NAME)


if __name__ == "__main__":
    main()
