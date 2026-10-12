"""Detail the user-authored DOmicilios station in the canonical Blender scene.

Existing meshes define the authoritative position and size envelopes.  The
attached IMG_5984.heic photograph is used only as a visual reference for the
stainless waste cabinet, folding cashier table, POS terminal, and acrylic guard.
"""

from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


ROOT = Path(__file__).resolve().parents[1]
BLEND_PATH = ROOT / "blend" / "guadalajara_base.blend"
PREVIEW_PATH = ROOT / "outputs" / "previews" / "domicilios_station.png"

SCRIPT_ID = "build_domicilios_station_v1"
SOURCE_REFERENCE = "IMG_5984.heic"
COLLECTION_NAME = "DOmicilios"
ROOT_NAME = "DOMICILIOS_STATION_01"

CORE_ALIASES = {
    "waste": ("DOMICILIOS_WASTE_CABINET", "Basuras"),
    "table": ("DOMICILIOS_POS_TABLE_TOP", "Mesa"),
    "drawer": ("DOMICILIOS_CASH_DRAWER", "CM_holder"),
    "pos_base": ("DOMICILIOS_POS_BASE", "Cash_Machine_base"),
    "pos_display": ("DOMICILIOS_POS_DISPLAY", "Cash_Machine_top"),
    "support_1": ("DOMICILIOS_GUARD_POST_01", "Glass_support1"),
    "support_2": ("DOMICILIOS_GUARD_POST_02", "Glass_support2"),
    "support_3": ("DOMICILIOS_GUARD_POST_03", "Glass_support3"),
    "support_4": ("DOMICILIOS_GUARD_POST_04", "Glass_support4"),
}


def collection():
    result = bpy.data.collections.get(COLLECTION_NAME)
    if result is None:
        raise RuntimeError(f"Required collection is missing: {COLLECTION_NAME}")
    return result


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


def assign_material(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def material(name, color, metallic=0.0, roughness=0.4, alpha=1.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color, alpha)
    mat.metallic = metallic
    mat.roughness = roughness
    shader = mat.node_tree.nodes.get("Principled BSDF")
    if shader is not None:
        shader.inputs["Base Color"].default_value = (*color, 1.0)
        shader.inputs["Metallic"].default_value = metallic
        shader.inputs["Roughness"].default_value = roughness
        if "Alpha" in shader.inputs:
            shader.inputs["Alpha"].default_value = alpha
    if alpha < 1.0:
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "DITHERED"
        if hasattr(mat, "use_transparency_overlap"):
            mat.use_transparency_overlap = False
    return mat


def glass_material():
    mat = material("MAT_Domicilios_Clear_Acrylic", (0.68, 0.86, 0.88), 0.0, 0.08, 0.20)
    shader = mat.node_tree.nodes.get("Principled BSDF")
    if shader is not None:
        if "Transmission Weight" in shader.inputs:
            shader.inputs["Transmission Weight"].default_value = 0.90
        if "IOR" in shader.inputs:
            shader.inputs["IOR"].default_value = 1.46
    return mat


def create_materials():
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
        "green": material(
            "MAT_Domicilios_Recycling_Green", (0.025, 0.36, 0.13), metallic=0.05, roughness=0.30
        ),
        "white": material(
            "MAT_Domicilios_Label_White", (0.88, 0.87, 0.80), metallic=0.0, roughness=0.48
        ),
        "red": material(
            "MAT_Domicilios_POS_Key_Red", (0.55, 0.035, 0.025), metallic=0.0, roughness=0.30
        ),
        "paper": material(
            "MAT_Domicilios_Receipt_Paper", (0.93, 0.91, 0.84), metallic=0.0, roughness=0.58
        ),
        "glass": glass_material(),
    }


def generated(obj, target, root=None):
    obj["generated_by"] = SCRIPT_ID
    obj["asset_id"] = ROOT_NAME
    obj["source_reference"] = SOURCE_REFERENCE
    obj["dimensions_status"] = "Detail derived from user-authored proxy envelope"
    move_object(obj, target)
    if root is not None:
        set_parent_keep_world(obj, root)
    return obj


def remove_generated():
    for obj in list(bpy.data.objects):
        if obj.get("generated_by") == SCRIPT_ID:
            bpy.data.objects.remove(obj, do_unlink=True)


def ensure_root(target):
    root = bpy.data.objects.get(ROOT_NAME)
    if root is None:
        root = bpy.data.objects.new(ROOT_NAME, None)
    move_object(root, target)
    root.location = (0.0, 0.0, 0.0)
    root.rotation_euler = (0.0, 0.0, 0.0)
    root.scale = (1.0, 1.0, 1.0)
    root.empty_display_type = "CUBE"
    root.empty_display_size = 0.18
    root["asset_id"] = ROOT_NAME
    root["source_reference"] = SOURCE_REFERENCE
    root["dimensions_status"] = "Existing user-authored proxies"
    return root


def upgrade_core(obj, name, mat, target, root, bevel=0.006):
    world = obj.matrix_world.copy()
    obj.parent = None
    obj.matrix_parent_inverse.identity()
    obj.matrix_world = world
    activate(obj)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.name = name
    assign_material(obj, mat)
    move_object(obj, target)
    modifier = obj.modifiers.get("DOMICILIOS_EDGE_RADIUS")
    if modifier is None:
        modifier = obj.modifiers.new("DOMICILIOS_EDGE_RADIUS", "BEVEL")
    modifier.width = bevel
    modifier.segments = 3
    modifier.limit_method = "ANGLE"
    set_parent_keep_world(obj, root)
    obj["asset_id"] = ROOT_NAME
    obj["source_reference"] = SOURCE_REFERENCE
    obj["dimensions_status"] = "Exact bounds retained from user-authored proxy"
    return obj


def object_local_dimensions(obj):
    corners = [Vector(corner) for corner in obj.bound_box]
    mins = Vector((min(v.x for v in corners), min(v.y for v in corners), min(v.z for v in corners)))
    maxs = Vector((max(v.x for v in corners), max(v.y for v in corners), max(v.z for v in corners)))
    return maxs - mins


def box_world(name, dimensions, matrix, mat, target, root, bevel=0.002):
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    activate(obj)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.matrix_world = matrix
    if bevel > 0.0:
        modifier = obj.modifiers.new("EDGE_RADIUS", "BEVEL")
        modifier.width = bevel
        modifier.segments = 2
        modifier.limit_method = "ANGLE"
    assign_material(obj, mat)
    return generated(obj, target, root)


def box_relative(name, reference, local_location, dimensions, mat, target, root, bevel=0.002):
    matrix = reference.matrix_world @ Matrix.Translation(Vector(local_location))
    return box_world(name, dimensions, matrix, mat, target, root, bevel)


def cylinder_world(name, radius, depth, matrix, mat, target, root, vertices=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth)
    obj = bpy.context.object
    obj.name = name
    obj.matrix_world = matrix
    assign_material(obj, mat)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return generated(obj, target, root)


def cylinder_between(name, start, end, radius, mat, target, root, vertices=18):
    start = Vector(start)
    end = Vector(end)
    delta = end - start
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=radius,
        depth=delta.length,
        location=(start + end) * 0.5,
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector((0.0, 0.0, 1.0)).rotation_difference(delta.normalized())
    obj.rotation_mode = "XYZ"
    assign_material(obj, mat)
    return generated(obj, target, root)


def create_text(name, body, reference, local_location, size, mat, target, root):
    curve = bpy.data.curves.new(f"{name}_CURVE", type="FONT")
    curve.body = body
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.size = size
    curve.extrude = 0.0015
    obj = bpy.data.objects.new(name, curve)
    target.objects.link(obj)
    obj.matrix_world = (
        reference.matrix_world
        @ Matrix.Translation(Vector(local_location))
        @ Matrix.Rotation(math.pi * 0.5, 4, "X")
    )
    assign_material(obj, mat)
    activate(obj)
    bpy.ops.object.convert(target="MESH")
    obj = bpy.context.object
    return generated(obj, target, root)


def detail_waste_cabinet(waste, mats, target, root):
    width, depth, height = object_local_dimensions(waste)
    front_y = -depth * 0.5 - 0.010

    # Recessed top opening and raised stainless perimeter.
    box_relative(
        "DOMICILIOS_WASTE_OPENING_TRIM",
        waste,
        (0.0, 0.0, height * 0.5 + 0.009),
        (width * 0.62, depth * 0.50, 0.018),
        mats["green"], target, root, bevel=0.008,
    )
    box_relative(
        "DOMICILIOS_WASTE_OPENING",
        waste,
        (0.0, 0.0, height * 0.5 + 0.020),
        (width * 0.54, depth * 0.41, 0.010),
        mats["plastic"], target, root, bevel=0.010,
    )
    for axis, sign in (("X", -1.0), ("X", 1.0)):
        box_relative(
            f"DOMICILIOS_WASTE_TOP_RAIL_{axis}_{'N' if sign < 0 else 'P'}",
            waste,
            (sign * width * 0.485, 0.0, height * 0.5 + 0.020),
            (0.018, depth * 0.96, 0.040), mats["stainless"], target, root, bevel=0.004,
        )
    for sign in (-1.0, 1.0):
        box_relative(
            f"DOMICILIOS_WASTE_TOP_RAIL_Y_{'N' if sign < 0 else 'P'}",
            waste,
            (0.0, sign * depth * 0.485, height * 0.5 + 0.020),
            (width * 0.96, 0.018, 0.040), mats["stainless"], target, root, bevel=0.004,
        )

    # Front hatch, label, lower service door, handles and hinges.
    box_relative(
        "DOMICILIOS_WASTE_HATCH",
        waste,
        (0.0, front_y, height * 0.18),
        (width * 0.78, 0.022, height * 0.25), mats["stainless"], target, root, bevel=0.008,
    )
    box_relative(
        "DOMICILIOS_WASTE_LABEL",
        waste,
        (0.0, front_y - 0.014, height * 0.20),
        (width * 0.56, 0.010, height * 0.13), mats["white"], target, root, bevel=0.004,
    )
    create_text(
        "DOMICILIOS_WASTE_LABEL_TEXT", "RECICLABLE", waste,
        (0.0, front_y - 0.021, height * 0.20), min(0.070, width * 0.075),
        mats["green"], target, root,
    )
    box_relative(
        "DOMICILIOS_WASTE_ACCESS_DOOR",
        waste,
        (0.0, front_y, -height * 0.23),
        (width * 0.82, 0.022, height * 0.43), mats["stainless"], target, root, bevel=0.006,
    )
    box_relative(
        "DOMICILIOS_WASTE_DOOR_HANDLE",
        waste,
        (width * 0.30, front_y - 0.025, -height * 0.20),
        (width * 0.16, 0.020, 0.024), mats["dark"], target, root, bevel=0.006,
    )
    for sign in (-1.0, 1.0):
        cylinder_world(
            f"DOMICILIOS_WASTE_HINGE_{'L' if sign < 0 else 'R'}",
            0.010, height * 0.12,
            waste.matrix_world
            @ Matrix.Translation((sign * width * 0.39, front_y - 0.016, -height * 0.34)),
            mats["dark"], target, root, vertices=18,
        )


def detail_table(table, mats, target, root):
    width, depth, thickness = object_local_dimensions(table)
    top_world_z = table.matrix_world.translation.z - thickness * 0.5
    floor_z = -0.050

    # Stainless edge band around the authored tabletop.
    for sign in (-1.0, 1.0):
        box_relative(
            f"DOMICILIOS_TABLE_EDGE_X_{'L' if sign < 0 else 'R'}",
            table, (sign * width * 0.49, 0.0, 0.0),
            (0.014, depth, thickness * 1.14), mats["stainless"], target, root, bevel=0.004,
        )
        box_relative(
            f"DOMICILIOS_TABLE_EDGE_Y_{'F' if sign < 0 else 'B'}",
            table, (0.0, sign * depth * 0.49, 0.0),
            (width, 0.014, thickness * 1.14), mats["stainless"], target, root, bevel=0.004,
        )

    # Two X-shaped folding frames, one on each side of the table.
    for y_sign in (-1.0, 1.0):
        y = y_sign * depth * 0.38
        lower_left = table.matrix_world @ Vector((-width * 0.39, y, floor_z - table.location.z + 0.025))
        lower_right = table.matrix_world @ Vector((width * 0.39, y, floor_z - table.location.z + 0.025))
        upper_left = table.matrix_world @ Vector((-width * 0.38, y, -thickness * 0.65))
        upper_right = table.matrix_world @ Vector((width * 0.38, y, -thickness * 0.65))
        side = "F" if y_sign < 0 else "B"
        cylinder_between(
            f"DOMICILIOS_TABLE_XFRAME_{side}_01", lower_left, upper_right,
            0.012, mats["dark"], target, root,
        )
        cylinder_between(
            f"DOMICILIOS_TABLE_XFRAME_{side}_02", lower_right, upper_left,
            0.012, mats["dark"], target, root,
        )
        center = (lower_left + lower_right + upper_left + upper_right) * 0.25
        cylinder_world(
            f"DOMICILIOS_TABLE_XFRAME_{side}_PIVOT", 0.020, 0.030,
            Matrix.Translation(center) @ Matrix.Rotation(math.pi * 0.5, 4, "X"),
            mats["stainless"], target, root, vertices=20,
        )

    # Front/back floor rails and rubber feet.
    for x_sign in (-1.0, 1.0):
        a = table.matrix_world @ Vector((x_sign * width * 0.39, -depth * 0.43, floor_z - table.location.z + 0.025))
        b = table.matrix_world @ Vector((x_sign * width * 0.39, depth * 0.43, floor_z - table.location.z + 0.025))
        cylinder_between(
            f"DOMICILIOS_TABLE_FOOT_RAIL_{'L' if x_sign < 0 else 'R'}",
            a, b, 0.014, mats["dark"], target, root,
        )


def detail_cash_drawer(drawer, mats, target, root):
    width, depth, height = object_local_dimensions(drawer)
    front_y = -depth * 0.5 - 0.010
    box_relative(
        "DOMICILIOS_CASH_DRAWER_FACE", drawer,
        (0.0, front_y, 0.0), (width * 0.86, 0.022, height * 0.56),
        mats["stainless"], target, root, bevel=0.006,
    )
    box_relative(
        "DOMICILIOS_CASH_DRAWER_PULL", drawer,
        (0.0, front_y - 0.018, -height * 0.05), (width * 0.24, 0.018, 0.025),
        mats["dark"], target, root, bevel=0.006,
    )
    cylinder_world(
        "DOMICILIOS_CASH_DRAWER_KEY", 0.012, 0.016,
        drawer.matrix_world
        @ Matrix.Translation((width * 0.31, front_y - 0.018, height * 0.12))
        @ Matrix.Rotation(math.pi * 0.5, 4, "X"),
        mats["dark"], target, root, vertices=20,
    )


def detail_pos(base, display, mats, target, root):
    width, depth, height = object_local_dimensions(base)
    box_relative(
        "DOMICILIOS_POS_RECEIPT_SLOT", base,
        (0.0, depth * 0.31, height * 0.5 + 0.006),
        (width * 0.50, depth * 0.08, 0.012), mats["dark"], target, root, bevel=0.003,
    )
    box_relative(
        "DOMICILIOS_POS_RECEIPT", base,
        (0.0, depth * 0.37, height * 0.5 + 0.022),
        (width * 0.42, depth * 0.16, 0.004), mats["paper"], target, root, bevel=0.001,
    )

    display_width, display_depth, display_height = object_local_dimensions(display)
    # The sloped user-authored top is the main keypad surface.
    columns = 5
    rows = 4
    key_w = display_width * 0.115
    key_d = display_depth * 0.105
    start_x = -key_w * (columns - 1) * 0.68
    start_y = -display_depth * 0.29
    for row in range(rows):
        for column in range(columns):
            key_mat = mats["red"] if (column == columns - 1 and row in {0, rows - 1}) else mats["stainless"]
            box_relative(
                f"DOMICILIOS_POS_KEY_{row + 1:02d}_{column + 1:02d}",
                display,
                (start_x + column * key_w * 1.36, start_y + row * key_d * 1.42, display_height * 0.5 + 0.005),
                (key_w, key_d, 0.010), key_mat, target, root, bevel=0.002,
            )

    box_relative(
        "DOMICILIOS_POS_SCREEN", display,
        (0.0, display_depth * 0.32, display_height * 0.5 + 0.006),
        (display_width * 0.58, display_depth * 0.18, 0.006),
        mats["screen"], target, root, bevel=0.004,
    )
    box_relative(
        "DOMICILIOS_POS_SCREEN_FRAME", display,
        (0.0, display_depth * 0.32, display_height * 0.5 + 0.003),
        (display_width * 0.68, display_depth * 0.25, 0.004),
        mats["plastic"], target, root, bevel=0.005,
    )

    # Short power/data cable routed behind the table.
    p0 = base.matrix_world @ Vector((width * 0.45, depth * 0.45, -height * 0.35))
    p1 = p0 + Vector((0.05, 0.03, -0.10))
    p2 = p1 + Vector((0.02, 0.02, -0.23))
    cylinder_between("DOMICILIOS_POS_CABLE_01", p0, p1, 0.006, mats["dark"], target, root, 12)
    cylinder_between("DOMICILIOS_POS_CABLE_02", p1, p2, 0.006, mats["dark"], target, root, 12)


def detail_guard(supports, mats, target, root):
    for index, support in enumerate(supports, start=1):
        height = object_local_dimensions(support).z
        radius = max(object_local_dimensions(support).x, object_local_dimensions(support).y) * 0.5
        cylinder_world(
            f"DOMICILIOS_GUARD_POST_{index:02d}_CAP",
            radius * 1.20, 0.012,
            Matrix.Translation((
                support.matrix_world.translation.x,
                support.matrix_world.translation.y,
                support.matrix_world.translation.z + height * 0.5 + 0.006,
            )),
            mats["stainless"], target, root, vertices=24,
        )

    # U-shaped acrylic guard; the edge between posts 4 and 1 remains open.
    for panel_index, (first, second) in enumerate(zip(supports[:3], supports[1:]), start=1):
        start = first.matrix_world.translation
        end = second.matrix_world.translation
        delta = end - start
        height = min(object_local_dimensions(first).z, object_local_dimensions(second).z) - 0.025
        midpoint = (start + end) * 0.5
        angle = math.atan2(delta.y, delta.x)
        box_world(
            f"DOMICILIOS_GUARD_PANEL_{panel_index:02d}",
            (math.hypot(delta.x, delta.y) - 0.018, 0.006, height),
            Matrix.Translation(midpoint) @ Matrix.Rotation(angle, 4, "Z"),
            mats["glass"], target, root, bevel=0.002,
        )


def build():
    target = collection()
    remove_generated()
    root = ensure_root(target)
    mats = create_materials()
    cores = {key: find_object(*aliases) for key, aliases in CORE_ALIASES.items()}

    waste = upgrade_core(cores["waste"], CORE_ALIASES["waste"][0], mats["stainless"], target, root, 0.010)
    table = upgrade_core(cores["table"], CORE_ALIASES["table"][0], mats["dark"], target, root, 0.007)
    drawer = upgrade_core(cores["drawer"], CORE_ALIASES["drawer"][0], mats["stainless"], target, root, 0.008)
    base = upgrade_core(cores["pos_base"], CORE_ALIASES["pos_base"][0], mats["plastic"], target, root, 0.005)
    display = upgrade_core(cores["pos_display"], CORE_ALIASES["pos_display"][0], mats["plastic"], target, root, 0.004)
    supports = []
    for index in range(1, 5):
        key = f"support_{index}"
        supports.append(upgrade_core(
            cores[key], CORE_ALIASES[key][0], mats["stainless"], target, root, 0.003
        ))

    detail_waste_cabinet(waste, mats, target, root)
    detail_table(table, mats, target, root)
    detail_cash_drawer(drawer, mats, target, root)
    detail_pos(base, display, mats, target, root)
    detail_guard(supports, mats, target, root)

    target["asset_id"] = ROOT_NAME
    target["source_reference"] = SOURCE_REFERENCE
    target["dimensions_status"] = "Existing proxy envelopes retained; added details provisional"
    target["scope_note"] = "Visual operational asset; working clearances remain unvalidated"
    return root


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def render_preview():
    PREVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    target = collection()
    visible = set(target.all_objects)
    for obj in bpy.context.scene.objects:
        if obj not in visible:
            obj.hide_render = True

    objects = [obj for obj in target.all_objects if obj.type == "MESH"]
    corners = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    minimum = Vector((min(p.x for p in corners), min(p.y for p in corners), min(p.z for p in corners)))
    maximum = Vector((max(p.x for p in corners), max(p.y for p in corners), max(p.z for p in corners)))
    center = (minimum + maximum) * 0.5
    span = maximum - minimum

    bpy.ops.mesh.primitive_plane_add(size=max(5.0, span.x * 3.0), location=(center.x, center.y, -0.055))
    ground = bpy.context.object
    ground.name = "REVIEW_DOMICILIOS_GROUND"
    ground.data.materials.append(material("MAT_Review_Domicilios_Ground", (0.12, 0.105, 0.085), 0.0, 0.72))

    camera_data = bpy.data.cameras.new("CAM_DomiciliosPreview_DATA")
    camera = bpy.data.objects.new("CAM_DomiciliosPreview", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = (center.x + span.x * 1.00, center.y - span.y * 2.80, center.z + span.z * 0.85)
    camera_data.lens = 55.0
    look_at(camera, (center.x, center.y, center.z * 0.88))
    bpy.context.scene.camera = camera

    for name, location, energy, size in (
        ("LIGHT_Domicilios_Key", (center.x + 1.8, center.y - 1.5, 2.8), 1000.0, 2.4),
        ("LIGHT_Domicilios_Fill", (center.x - 1.4, center.y + 0.8, 1.9), 550.0, 2.0),
    ):
        data = bpy.data.lights.new(f"{name}_DATA", type="AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        light = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(light)
        light.location = location
        look_at(light, center)

    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.035, 0.035, 0.035, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.32

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1000
    scene.render.resolution_y = 760
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(PREVIEW_PATH)
    scene.render.film_transparent = False
    bpy.ops.render.render(write_still=True)


def main():
    if Path(bpy.data.filepath).resolve() != BLEND_PATH.resolve():
        raise RuntimeError(f"Run this script with the canonical scene: {BLEND_PATH}")
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    root = build()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    render_preview()
    print("DOMICILIOS_COLLECTION", COLLECTION_NAME)
    print("DOMICILIOS_ROOT", root.name)
    print("DOMICILIOS_PREVIEW", PREVIEW_PATH)


if __name__ == "__main__":
    main()
