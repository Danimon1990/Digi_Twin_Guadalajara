"""Detail the interior cash station above ``Cutting table``.

The user-authored meshes are the dimensional authority:

* ``Cach_machine`` is the cash drawer envelope.
* ``Cube.026`` is the upright monitor envelope.
* ``Cube.028`` is the sloped keyboard-console envelope.

``IMG_5973.heic`` is used only as a visual reference for materials and small
features.  No scale geometry is generated because the scene does not yet
contain a measured or user-authored scale envelope.
"""

from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


ROOT = Path(__file__).resolve().parents[1]
BLEND_PATH = ROOT / "blend" / "guadalajara_base.blend"

SCRIPT_ID = "build_internal_cash_station_v1"
SOURCE_REFERENCE = "IMG_5973.heic"
COLLECTION_NAME = "Cash_Station_Interior"
PARENT_COLLECTION_NAME = "Equipment_Despacho"
ROOT_NAME = "CASH_INTERIOR_STATION_01"

CORE_ALIASES = {
    "drawer": ("CASH_INTERIOR_DRAWER", "Cach_machine"),
    "monitor": ("CASH_INTERIOR_MONITOR", "Cube.026"),
    "console": ("CASH_INTERIOR_KEYBOARD_CONSOLE", "Cube.028"),
}


def ensure_collection():
    parent = bpy.data.collections.get(PARENT_COLLECTION_NAME)
    if parent is None:
        raise RuntimeError(f"Required collection is missing: {PARENT_COLLECTION_NAME}")
    target = bpy.data.collections.get(COLLECTION_NAME)
    if target is None:
        target = bpy.data.collections.new(COLLECTION_NAME)
    if target.name not in parent.children:
        parent.children.link(target)
    return target


def find_object(*aliases):
    for name in aliases:
        obj = bpy.data.objects.get(name)
        if obj is not None:
            return obj
    raise RuntimeError(f"Required object is missing; expected one of {aliases}")


def move_object(obj, target):
    if target not in obj.users_collection:
        target.objects.link(obj)
    for current in list(obj.users_collection):
        if current != target:
            current.objects.unlink(obj)


def activate(obj):
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def set_parent_keep_world(obj, parent):
    bpy.context.view_layer.update()
    world = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_parent_inverse = parent.matrix_world.inverted()
    obj.matrix_world = world
    bpy.context.view_layer.update()


def material(name, color, metallic=0.0, roughness=0.4):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color, 1.0)
    mat.metallic = metallic
    mat.roughness = roughness
    shader = mat.node_tree.nodes.get("Principled BSDF")
    if shader is not None:
        shader.inputs["Base Color"].default_value = (*color, 1.0)
        shader.inputs["Metallic"].default_value = metallic
        shader.inputs["Roughness"].default_value = roughness
    return mat


def create_materials():
    # Reuse the established Domicilios palette so both cashier stations read as
    # one equipment family in Blender and OpenUSD.
    return {
        "stainless": material(
            "MAT_Domicilios_Stainless", (0.45, 0.49, 0.51), metallic=0.94, roughness=0.24
        ),
        "dark": material(
            "MAT_Domicilios_Dark_Steel", (0.025, 0.027, 0.028), metallic=0.78, roughness=0.34
        ),
        "plastic": material(
            "MAT_Domicilios_POS_Black_Plastic", (0.025, 0.028, 0.030), metallic=0.05, roughness=0.30
        ),
        "screen": material(
            "MAT_Domicilios_POS_Screen", (0.035, 0.18, 0.23), metallic=0.08, roughness=0.16
        ),
        "key": material(
            "MAT_CashInterior_Keycap", (0.17, 0.18, 0.18), metallic=0.0, roughness=0.38
        ),
        "accent": material(
            "MAT_CashInterior_Indicator_Green", (0.02, 0.55, 0.12), metallic=0.0, roughness=0.25
        ),
    }


def assign_material(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def object_local_dimensions(obj):
    corners = [Vector(corner) for corner in obj.bound_box]
    minimum = Vector(tuple(min(v[i] for v in corners) for i in range(3)))
    maximum = Vector(tuple(max(v[i] for v in corners) for i in range(3)))
    return maximum - minimum


def world_z_bounds(obj):
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return min(point.z for point in points), max(point.z for point in points)


def place_monitor_above_console(monitor, console):
    """Expose the screen without changing either authored size envelope."""
    monitor_bottom, _ = world_z_bounds(monitor)
    _, console_top = world_z_bounds(console)
    clearance = 0.015
    lift = max(0.0, console_top + clearance - monitor_bottom)
    monitor.location.z += lift
    bpy.context.view_layer.update()
    monitor["placement_status"] = (
        "Vertically cleared above keyboard console; authored dimensions retained"
    )


def ensure_root(target):
    root = bpy.data.objects.get(ROOT_NAME)
    if root is None:
        root = bpy.data.objects.new(ROOT_NAME, None)
    move_object(root, target)
    root.matrix_world = Matrix.Identity(4)
    root.empty_display_type = "CUBE"
    root.empty_display_size = 0.12
    root["asset_id"] = ROOT_NAME
    root["source_reference"] = SOURCE_REFERENCE
    root["dimensions_status"] = "Existing user-authored proxy envelopes"
    root["host_table"] = "Cutting table"
    root["adjacent_opening"] = "OPENING_WINDOW_WALL_004.001_01"
    root["scale_status"] = "Pending measured or user-authored envelope"
    return root


def remove_generated():
    for obj in list(bpy.data.objects):
        if obj.get("generated_by") == SCRIPT_ID:
            bpy.data.objects.remove(obj, do_unlink=True)


def generated(obj, target, root):
    obj["generated_by"] = SCRIPT_ID
    obj["asset_id"] = ROOT_NAME
    obj["source_reference"] = SOURCE_REFERENCE
    obj["dimensions_status"] = "Detail derived from user-authored proxy envelope"
    move_object(obj, target)
    set_parent_keep_world(obj, root)
    return obj


def upgrade_core(obj, name, mat, target, root, bevel):
    world = obj.matrix_world.copy()
    obj.parent = None
    obj.matrix_parent_inverse.identity()
    obj.matrix_world = world
    activate(obj)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.name = name
    assign_material(obj, mat)
    move_object(obj, target)
    modifier = obj.modifiers.get("CASH_INTERIOR_EDGE_RADIUS")
    if modifier is None:
        modifier = obj.modifiers.new("CASH_INTERIOR_EDGE_RADIUS", "BEVEL")
    modifier.width = bevel
    modifier.segments = 3
    modifier.limit_method = "ANGLE"
    set_parent_keep_world(obj, root)
    obj["asset_id"] = ROOT_NAME
    obj["source_reference"] = SOURCE_REFERENCE
    obj["dimensions_status"] = "Exact bounds retained from user-authored proxy"
    return obj


def box_relative(name, reference, local_location, dimensions, mat, target, root, bevel=0.002):
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    activate(obj)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.matrix_world = reference.matrix_world @ Matrix.Translation(Vector(local_location))
    if bevel > 0.0:
        modifier = obj.modifiers.new("EDGE_RADIUS", "BEVEL")
        modifier.width = bevel
        modifier.segments = 2
        modifier.limit_method = "ANGLE"
    assign_material(obj, mat)
    return generated(obj, target, root)


def cylinder_relative(name, reference, local_location, radius, depth, axis, mat, target, root):
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=radius, depth=depth)
    obj = bpy.context.object
    obj.name = name
    rotation = Matrix.Identity(4)
    if axis == "X":
        rotation = Matrix.Rotation(math.pi * 0.5, 4, "Y")
    elif axis == "Y":
        rotation = Matrix.Rotation(math.pi * 0.5, 4, "X")
    obj.matrix_world = reference.matrix_world @ Matrix.Translation(Vector(local_location)) @ rotation
    assign_material(obj, mat)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return generated(obj, target, root)


def detail_drawer(drawer, mats, target, root):
    depth, width, height = object_local_dimensions(drawer)
    # The authored objects carry their former negative scale in the mesh.  Once
    # normalized, local -X faces the worker and local +X faces the window.
    front_x = -depth * 0.5 - 0.006
    box_relative(
        "CASH_INTERIOR_DRAWER_FACE", drawer,
        (front_x, 0.0, 0.0), (0.012, width * 0.88, height * 0.66),
        mats["stainless"], target, root, bevel=0.005,
    )
    box_relative(
        "CASH_INTERIOR_DRAWER_SLOT", drawer,
        (front_x - 0.008, 0.0, height * 0.12), (0.008, width * 0.48, 0.018),
        mats["dark"], target, root, bevel=0.003,
    )
    box_relative(
        "CASH_INTERIOR_DRAWER_PULL", drawer,
        (front_x - 0.014, 0.0, -height * 0.13), (0.020, width * 0.24, 0.028),
        mats["plastic"], target, root, bevel=0.006,
    )
    cylinder_relative(
        "CASH_INTERIOR_DRAWER_LOCK", drawer,
        (front_x - 0.016, width * 0.32, height * 0.14), 0.012, 0.018, "X",
        mats["dark"], target, root,
    )


def detail_monitor(monitor, mats, target, root):
    depth, width, height = object_local_dimensions(monitor)
    front_x = -depth * 0.5 - 0.004
    # The proxy remains the bezel/body; the inset panel is the luminous screen.
    box_relative(
        "CASH_INTERIOR_MONITOR_SCREEN", monitor,
        (front_x, 0.0, height * 0.015),
        (0.008, width * 0.82, height * 0.70),
        mats["screen"], target, root, bevel=0.006,
    )
    box_relative(
        "CASH_INTERIOR_MONITOR_LOWER_BEZEL", monitor,
        (front_x - 0.001, 0.0, -height * 0.405),
        (0.010, width * 0.88, height * 0.10),
        mats["plastic"], target, root, bevel=0.003,
    )
    cylinder_relative(
        "CASH_INTERIOR_MONITOR_POWER_LED", monitor,
        (front_x - 0.008, -width * 0.37, -height * 0.405),
        min(0.005, height * 0.03), 0.010, "X", mats["accent"], target, root,
    )
    # Shallow rear vents read in close-up without altering the monitor envelope.
    for index in range(5):
        box_relative(
            f"CASH_INTERIOR_MONITOR_VENT_{index + 1:02d}", monitor,
            (depth * 0.5 + 0.003, (-2 + index) * width * 0.095, height * 0.14),
            (0.006, width * 0.055, height * 0.26),
            mats["dark"], target, root, bevel=0.001,
        )


def detail_console(console, mats, target, root):
    depth, width, height = object_local_dimensions(console)
    top_x = -depth * 0.5 - 0.004
    panel = box_relative(
        "CASH_INTERIOR_KEYBOARD_PANEL", console,
        (top_x, 0.0, height * 0.02),
        (0.008, width * 0.88, height * 0.72),
        mats["dark"], target, root, bevel=0.004,
    )

    # Compact keyboard.  Key positions are proportional to the authored console
    # envelope, so the overall physical bounds remain authoritative.
    rows = 4
    columns = 10
    key_width = width * 0.065
    key_height = height * 0.105
    for row in range(rows):
        for column in range(columns):
            y = (column - (columns - 1) * 0.5) * width * 0.082
            z = (row - (rows - 1) * 0.5) * height * 0.145 + height * 0.04
            box_relative(
                f"CASH_INTERIOR_KEY_{row + 1:02d}_{column + 1:02d}", console,
                (top_x - 0.008, y, z),
                (0.008, key_width, key_height),
                mats["key"], target, root, bevel=0.0015,
            )

    box_relative(
        "CASH_INTERIOR_KEYBOARD_SPACEBAR", console,
        (top_x - 0.009, 0.0, -height * 0.30),
        (0.009, width * 0.34, key_height),
        mats["key"], target, root, bevel=0.0015,
    )
    panel["equipment_role"] = "keyboard_surface"


def build():
    if bpy.data.objects.get("Cutting table") is None:
        raise RuntimeError("Required host object is missing: Cutting table")
    if bpy.data.objects.get("OPENING_WINDOW_WALL_004.001_01") is None:
        raise RuntimeError("Required adjacent opening is missing: OPENING_WINDOW_WALL_004.001_01")

    target = ensure_collection()
    remove_generated()
    root = ensure_root(target)
    mats = create_materials()
    cores = {key: find_object(*aliases) for key, aliases in CORE_ALIASES.items()}

    drawer = upgrade_core(
        cores["drawer"], CORE_ALIASES["drawer"][0], mats["plastic"], target, root, 0.008
    )
    monitor = upgrade_core(
        cores["monitor"], CORE_ALIASES["monitor"][0], mats["plastic"], target, root, 0.006
    )
    console = upgrade_core(
        cores["console"], CORE_ALIASES["console"][0], mats["plastic"], target, root, 0.005
    )

    place_monitor_above_console(monitor, console)

    detail_drawer(drawer, mats, target, root)
    detail_monitor(monitor, mats, target, root)
    detail_console(console, mats, target, root)

    target["asset_id"] = ROOT_NAME
    target["source_reference"] = SOURCE_REFERENCE
    target["host_table"] = "Cutting table"
    target["adjacent_opening"] = "OPENING_WINDOW_WALL_004.001_01"
    target["dimensions_status"] = "Existing proxy envelopes retained; added details proportional"
    target["scale_status"] = "Not modeled: measured or user-authored envelope required"
    target["scope_note"] = "Visual operational asset; working clearances remain unvalidated"
    return root


def main():
    if Path(bpy.data.filepath).resolve() != BLEND_PATH.resolve():
        raise RuntimeError(f"Run this script with the canonical scene: {BLEND_PATH}")
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    root = build()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    print("CASH_INTERIOR_COLLECTION", COLLECTION_NAME)
    print("CASH_INTERIOR_ROOT", root.name)


if __name__ == "__main__":
    main()
