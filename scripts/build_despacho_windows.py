"""Create two provisional despacho window openings from user cubes."""

from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
BLEND_PATH = ROOT / "blend" / "guadalajara_base.blend"

WINDOWS = (
    {
        "name": "OPENING_WINDOW_WALL_004.001_01",
        "fallback": "Cube.010",
        "wall": "WALL_004.001",
    },
    {
        "name": "OPENING_WINDOW_WALL_001_01",
        "fallback": "Cube.011",
        "wall": "WALL_001",
    },
)


def resolve_marker(stable_name, fallback_name):
    marker = bpy.data.objects.get(stable_name)
    if marker:
        return marker
    marker = bpy.data.objects.get(fallback_name)
    if marker is None:
        raise RuntimeError(f"Missing despacho window marker: {stable_name} / {fallback_name}")
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


def main():
    cutters = bpy.data.collections.get("Door_Cutters")
    if cutters is None:
        raise RuntimeError("Missing Door_Cutters collection")

    for spec in WINDOWS:
        wall = bpy.data.objects.get(spec["wall"])
        if wall is None:
            raise RuntimeError(f"Missing host wall: {spec['wall']}")
        marker = resolve_marker(spec["name"], spec["fallback"])
        move_to_cutters(marker, cutters)
        marker["phase"] = "Phase 1"
        marker["evidence_status"] = "Provisional"
        marker["opening_type"] = "window"
        marker["host_wall"] = spec["wall"]
        marker["source"] = "User-authored cube in Blender, 2026-10-05"
        marker["notes"] = "Position and dimensions preserved from the user-authored marker; field endpoints remain pending."

        modifier_name = f"{spec['name']}_BOOL"
        old = wall.modifiers.get(modifier_name)
        if old:
            wall.modifiers.remove(old)
        modifier = wall.modifiers.new(modifier_name, "BOOLEAN")
        modifier.operation = "DIFFERENCE"
        modifier.solver = "EXACT"
        modifier.object = marker

        bottom = marker.location.z - marker.dimensions.z / 2.0
        top = marker.location.z + marker.dimensions.z / 2.0
        print(
            "DESPACHO_WINDOW", marker.name, "HOST", spec["wall"],
            "WIDTH_ALONG_WALL", round(marker.dimensions.y, 4),
            "HEIGHT", round(marker.dimensions.z, 4),
            "BOTTOM_Z", round(bottom, 4), "TOP_Z", round(top, 4),
        )

    bpy.context.scene["despacho_windows_status"] = "Provisional user-authored markers"
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))


if __name__ == "__main__":
    main()
