"""Create provisional door and window openings in WALL_011.

The user-authored cubes are preserved as wireframe Boolean cutters and moved
from the temporary ``Levels`` collection into ``Door_Cutters``.
"""

from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
BLEND_PATH = ROOT / "blend" / "guadalajara_base.blend"
WALL_NAME = "WALL_011"
WINDOW_NAME = "OPENING_WINDOW_WALL_011_01"
DOOR_NAME = "OPENING_DOOR_WALL_011_01"


def resolve_marker(stable_name, fallback_name):
    marker = bpy.data.objects.get(stable_name)
    if marker:
        return marker
    marker = bpy.data.objects.get(fallback_name)
    if marker is None:
        raise RuntimeError(f"Missing opening marker: {stable_name} / {fallback_name}")
    marker.name = stable_name
    marker.data.name = f"{stable_name}_MESH"
    return marker


def move_to_cutters(marker, cutters):
    if marker.name not in cutters.objects:
        cutters.objects.link(marker)
    for collection in list(marker.users_collection):
        if collection != cutters:
            collection.objects.unlink(marker)
    marker.display_type = "WIRE"
    marker.hide_render = True
    marker.show_in_front = True


def add_boolean(wall, marker, modifier_name):
    old = wall.modifiers.get(modifier_name)
    if old:
        wall.modifiers.remove(old)
    modifier = wall.modifiers.new(modifier_name, "BOOLEAN")
    modifier.operation = "DIFFERENCE"
    modifier.solver = "EXACT"
    modifier.object = marker


def annotate(marker, opening_type):
    marker["phase"] = "Phase 1"
    marker["evidence_status"] = "Provisional"
    marker["opening_type"] = opening_type
    marker["host_wall"] = WALL_NAME
    marker["source"] = "User-authored cube in Blender, 2026-10-05"
    marker["notes"] = "Position and dimensions preserved from the user-authored marker; field measurement endpoints remain pending."


def main():
    wall = bpy.data.objects.get(WALL_NAME)
    cutters = bpy.data.collections.get("Door_Cutters")
    if wall is None or cutters is None:
        raise RuntimeError("Missing WALL_011 or Door_Cutters collection")

    window = resolve_marker(WINDOW_NAME, "Cube")
    door = resolve_marker(DOOR_NAME, "Cube.001")

    move_to_cutters(window, cutters)
    move_to_cutters(door, cutters)
    annotate(window, "window")
    annotate(door, "door")

    add_boolean(wall, window, "OPENING_WINDOW_WALL_011_01_BOOL")
    add_boolean(wall, door, "OPENING_DOOR_WALL_011_01_BOOL")

    bpy.context.scene["bebidas_wall_011_openings_status"] = "Provisional user-authored markers"
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))

    for marker in (window, door):
        bottom = marker.location.z - marker.dimensions.z / 2.0
        top = marker.location.z + marker.dimensions.z / 2.0
        print(
            "BEBIDAS_OPENING", marker.name,
            "WIDTH_ALONG_WALL", round(marker.dimensions.y, 4),
            "HEIGHT", round(marker.dimensions.z, 4),
            "BOTTOM_Z", round(bottom, 4),
            "TOP_Z", round(top, 4),
        )


if __name__ == "__main__":
    main()
