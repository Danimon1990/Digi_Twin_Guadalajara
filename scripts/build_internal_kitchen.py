"""Detail the internal production kitchen from user-authored proxy envelopes.

Authoritative placement/size envelopes:

* ``Cube.011`` central built-in island.
* ``Cube.012`` sink and long wall counter.
* ``Cube.015`` auxiliary bank of two double stoves (four burners).
* ``Cube.014`` refrigerator.
* ``Cube.013`` short side counter.
* ``WALL_009`` alignment for one large-burner module and three double-burner
  modules (seven burners total).

IMG_6068.heic and IMG_6067.heic are used only for visual construction details.
Unmeasured clearances and equipment profiles remain explicitly provisional.
"""

from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


ROOT = Path(__file__).resolve().parents[1]
BLEND_PATH = ROOT / "blend" / "guadalajara_base.blend"

SCRIPT_ID = "build_internal_kitchen_v1"
SOURCE_REFERENCE = "IMG_6068.heic; IMG_6067.heic"
COLLECTION_NAME = "Equipment_Cocina"
PARENT_COLLECTION_NAME = "Existing_Unclassified"
ROOT_NAME = "KITCHEN_INTERNAL_01"

CORE_ALIASES = {
    "island": ("KITCHEN_ISLAND_CORE", "Cube.011"),
    "sink_counter": ("KITCHEN_SINK_COUNTER_CORE", "Cube.012"),
    "aux_range": ("KITCHEN_RANGE_AUX_CORE", "Cube.015"),
    "fridge": ("KITCHEN_FRIDGE_CORE", "Cube.014"),
    "side_counter": ("KITCHEN_SIDE_COUNTER_CORE", "Cube.013"),
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


def object_local_dimensions(obj):
    corners = [Vector(corner) for corner in obj.bound_box]
    minimum = Vector(tuple(min(point[index] for point in corners) for index in range(3)))
    maximum = Vector(tuple(max(point[index] for point in corners) for index in range(3)))
    return maximum - minimum


def world_z_bounds(obj):
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return min(point.z for point in points), max(point.z for point in points)


def normalized_frame(obj, location=None):
    world_location, rotation, _scale = obj.matrix_world.decompose()
    return Matrix.Translation(location or world_location) @ rotation.to_matrix().to_4x4()


def world_axis_dimensions(obj):
    local = object_local_dimensions(obj)
    scale = obj.matrix_world.to_scale()
    return Vector((local.x * abs(scale.x), local.y * abs(scale.y), local.z * abs(scale.z)))


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
    tile = bpy.data.materials.get("MAT_Wall_WhiteTile")
    if tile is None:
        tile = material("MAT_Kitchen_WhiteTile", (0.72, 0.72, 0.68), 0.0, 0.28)
    return {
        "tile": tile,
        "stainless": material("MAT_Kitchen_Stainless", (0.40, 0.44, 0.46), 0.92, 0.25),
        "stainless_dark": material("MAT_Kitchen_Stainless_Dark", (0.16, 0.18, 0.19), 0.86, 0.32),
        "cast_iron": material("MAT_Kitchen_CastIron", (0.018, 0.020, 0.021), 0.55, 0.38),
        "basin": material("MAT_Kitchen_SinkBasin", (0.22, 0.25, 0.27), 0.93, 0.20),
        "control": material("MAT_Kitchen_ControlMarker", (0.52, 0.045, 0.025), 0.05, 0.32),
        "rubber": material("MAT_Kitchen_Rubber", (0.012, 0.013, 0.014), 0.0, 0.62),
    }


def assign_material(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def generated(obj, target, root, role, status="Detail derived from authored proxy or named wall"):
    obj["generated_by"] = SCRIPT_ID
    obj["asset_id"] = ROOT_NAME
    obj["equipment_role"] = role
    obj["source_reference"] = SOURCE_REFERENCE
    obj["dimensions_status"] = status
    move_object(obj, target)
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
    root.matrix_world = Matrix.Identity(4)
    root.empty_display_type = "CUBE"
    root.empty_display_size = 0.30
    root["asset_id"] = ROOT_NAME
    root["source_reference"] = SOURCE_REFERENCE
    root["dimensions_status"] = "User-authored proxies and explicit burner counts"
    root["scope_note"] = "Kitchen equipment only; no people generated"
    return root


def upgrade_core(obj, name, mat, target, root, role, bevel=0.008):
    world = obj.matrix_world.copy()
    obj.parent = None
    obj.matrix_parent_inverse.identity()
    obj.matrix_world = world
    activate(obj)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.name = name
    assign_material(obj, mat)
    move_object(obj, target)
    modifier = obj.modifiers.get("KITCHEN_EDGE_RADIUS")
    if modifier is None:
        modifier = obj.modifiers.new("KITCHEN_EDGE_RADIUS", "BEVEL")
    modifier.width = bevel
    modifier.segments = 3
    modifier.limit_method = "ANGLE"
    set_parent_keep_world(obj, root)
    obj["asset_id"] = ROOT_NAME
    obj["equipment_role"] = role
    obj["source_reference"] = SOURCE_REFERENCE
    obj["dimensions_status"] = "Exact envelope retained from user-authored proxy"
    return obj


def box_world(name, dimensions, matrix, mat, target, root, role, bevel=0.002, status=None):
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
    return generated(obj, target, root, role, status or "Detail derived from authored proxy or named wall")


def box_relative(name, reference, local_location, dimensions, mat, target, root, role, bevel=0.002, rotation_z=0.0):
    matrix = reference.matrix_world @ Matrix.Translation(Vector(local_location))
    if rotation_z:
        matrix = matrix @ Matrix.Rotation(rotation_z, 4, "Z")
    return box_world(name, dimensions, matrix, mat, target, root, role, bevel)


def cylinder_world(name, radius, depth, matrix, mat, target, root, role, vertices=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth)
    obj = bpy.context.object
    obj.name = name
    obj.matrix_world = matrix
    assign_material(obj, mat)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return generated(obj, target, root, role)


def cylinder_between(name, start, end, radius, mat, target, root, role, vertices=18):
    start = Vector(start)
    end = Vector(end)
    delta = end - start
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=delta.length, location=(start + end) * 0.5)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector((0.0, 0.0, 1.0)).rotation_difference(delta.normalized())
    obj.rotation_mode = "XYZ"
    assign_material(obj, mat)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return generated(obj, target, root, role)


def torus_world(name, matrix, major_radius, minor_radius, mat, target, root, role):
    bpy.ops.mesh.primitive_torus_add(
        align="WORLD",
        major_segments=32,
        minor_segments=8,
        location=(0.0, 0.0, 0.0),
        major_radius=major_radius,
        minor_radius=minor_radius,
    )
    obj = bpy.context.object
    obj.name = name
    obj.matrix_world = matrix
    assign_material(obj, mat)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return generated(obj, target, root, role)


def sphere_world(name, location, radius, mat, target, root, role):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=10, radius=radius, location=location)
    obj = bpy.context.object
    obj.name = name
    assign_material(obj, mat)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return generated(obj, target, root, role)


def guide_centroid(name):
    guide = bpy.data.objects.get(name)
    if guide is None or guide.type != "MESH":
        raise RuntimeError(f"Required guide is missing: {name}")
    points = [guide.matrix_world @ vertex.co for vertex in guide.data.vertices]
    return sum(points, Vector()) / len(points)


def local_y_side_toward(reference, world_point):
    y_axis = reference.matrix_world.to_3x3() @ Vector((0.0, 1.0, 0.0))
    direction = Vector(world_point) - reference.matrix_world.translation
    return 1.0 if direction.dot(y_axis) >= 0.0 else -1.0


def detail_counter_top(core, name, mats, target, root, role="stainless work surface"):
    width, depth, height = object_local_dimensions(core)
    return box_relative(
        name,
        core,
        (0.0, 0.0, height * 0.5 + 0.022),
        (width + 0.035, depth + 0.035, 0.044),
        mats["stainless"], target, root, role, bevel=0.008,
    )


def detail_island(island, mats, target, root):
    width, depth, height = object_local_dimensions(island)
    detail_counter_top(island, "KITCHEN_ISLAND_STAINLESS_TOP", mats, target, root)
    for side in (-1.0, 1.0):
        box_relative(
            f"KITCHEN_ISLAND_SERVICE_PANEL_{'A' if side < 0 else 'B'}",
            island,
            (0.0, side * (depth * 0.5 + 0.007), -height * 0.12),
            (width * 0.72, 0.014, height * 0.50),
            mats["stainless_dark"], target, root, "island recessed service panel", bevel=0.006,
        )


def sink_mesh(name, width, depth, basin_depth, matrix, mat, target, root):
    outer_x, outer_y = width * 0.5, depth * 0.5
    inner_x, inner_y = width * 0.42, depth * 0.39
    vertices = [
        (-outer_x, -outer_y, 0.0), (outer_x, -outer_y, 0.0),
        (outer_x, outer_y, 0.0), (-outer_x, outer_y, 0.0),
        (-inner_x, -inner_y, -0.015), (inner_x, -inner_y, -0.015),
        (inner_x, inner_y, -0.015), (-inner_x, inner_y, -0.015),
        (-inner_x * 0.86, -inner_y * 0.86, -basin_depth),
        (inner_x * 0.86, -inner_y * 0.86, -basin_depth),
        (inner_x * 0.86, inner_y * 0.86, -basin_depth),
        (-inner_x * 0.86, inner_y * 0.86, -basin_depth),
    ]
    faces = [
        (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7),
        (4, 5, 9, 8), (5, 6, 10, 9), (6, 7, 11, 10), (7, 4, 8, 11),
        (8, 9, 10, 11),
    ]
    mesh = bpy.data.meshes.new(f"{name}_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    target.objects.link(obj)
    obj.matrix_world = matrix
    assign_material(obj, mat)
    bevel = obj.modifiers.new("SINK_EDGE_RADIUS", "BEVEL")
    bevel.width = 0.010
    bevel.segments = 3
    return generated(obj, target, root, "stainless sink basin")


def detail_sink_counter(counter, kitchen_center, mats, target, root):
    width, depth, height = object_local_dimensions(counter)
    detail_counter_top(counter, "KITCHEN_SINK_COUNTER_TOP", mats, target, root)
    front_sign = local_y_side_toward(counter, kitchen_center)
    sink_x = -width * 0.22
    top_z = height * 0.5 + 0.050
    sink_width = min(0.72, width * 0.19)
    sink_depth = min(0.52, depth * 0.66)
    sink = sink_mesh(
        "KITCHEN_SINK_BASIN",
        sink_width,
        sink_depth,
        0.16,
        counter.matrix_world @ Matrix.Translation((sink_x, 0.0, top_z)),
        mats["basin"], target, root,
    )
    sink["host_proxy"] = counter.name
    box_relative(
        "KITCHEN_SINK_INNER_SHADOW", counter,
        (sink_x, 0.0, top_z + 0.002),
        (sink_width * 0.76, sink_depth * 0.72, 0.010),
        mats["cast_iron"], target, root, "sink interior shadow", bevel=0.018,
    )

    back_y = -front_sign * depth * 0.28
    local_points = [
        Vector((sink_x + sink_width * 0.30, back_y, top_z + 0.01)),
        Vector((sink_x + sink_width * 0.30, back_y, top_z + 0.29)),
        Vector((sink_x, back_y, top_z + 0.29)),
        Vector((sink_x, back_y + front_sign * 0.15, top_z + 0.23)),
    ]
    world_points = [counter.matrix_world @ point for point in local_points]
    for index, (start, end) in enumerate(zip(world_points, world_points[1:]), start=1):
        cylinder_between(
            f"KITCHEN_SINK_FAUCET_SEG_{index:02d}", start, end, 0.015,
            mats["stainless"], target, root, "sink faucet", vertices=24,
        )
    for index, point in enumerate(world_points[1:-1], start=1):
        sphere_world(
            f"KITCHEN_SINK_FAUCET_JOINT_{index:02d}", point, 0.015,
            mats["stainless"], target, root, "sink faucet joint",
        )

    # Drainboard ribs on the remaining work surface.
    for index in range(7):
        x = sink_x + sink_width * 0.65 + index * 0.055
        if x > width * 0.43:
            break
        box_relative(
            f"KITCHEN_SINK_DRAINBOARD_RIB_{index + 1:02d}", counter,
            (x, 0.0, top_z + 0.006),
            (0.018, sink_depth * 0.88, 0.010),
            mats["stainless_dark"], target, root, "sink drainboard rib", bevel=0.003,
        )


def create_wall_shelves(counter, prefix, kitchen_center, tiers, sections, mats, target, root):
    width, depth, height = object_local_dimensions(counter)
    front_sign = local_y_side_toward(counter, kitchen_center)
    back_sign = -front_sign
    gap = 0.04
    section_width = (width - gap * (sections - 1)) / sections
    for tier in range(tiers):
        z = height * 0.5 + 0.48 + tier * 0.38
        for section in range(sections):
            x = -width * 0.5 + section_width * 0.5 + section * (section_width + gap)
            box_relative(
                f"{prefix}_SHELF_{tier + 1:02d}_{section + 1:02d}", counter,
                (x, back_sign * (depth * 0.5 - 0.10), z),
                (section_width * 0.94, 0.28, 0.025),
                mats["stainless"], target, root, "wall-mounted storage shelf", bevel=0.004,
            )
            for bracket_sign in (-1.0, 1.0):
                bracket_x = x + bracket_sign * section_width * 0.36
                start = counter.matrix_world @ Vector((bracket_x, back_sign * (depth * 0.5 - 0.10), z - 0.015))
                end = counter.matrix_world @ Vector((bracket_x, back_sign * (depth * 0.5 + 0.02), z - 0.22))
                cylinder_between(
                    f"{prefix}_BRACKET_{tier + 1:02d}_{section + 1:02d}_{'L' if bracket_sign < 0 else 'R'}",
                    start, end, 0.010, mats["stainless_dark"], target, root,
                    "shelf support bracket", vertices=14,
                )


def burner_details(prefix, frame, module_width, depth, height, burner_positions, front_sign, mats, target, root):
    top_z = height * 0.5 + 0.030
    radius = min(depth * 0.22, module_width * 0.15)
    for index, (x, y, size_scale) in enumerate(burner_positions, start=1):
        center_matrix = frame @ Matrix.Translation((x, y, top_z))
        torus_world(
            f"{prefix}_BURNER_{index:02d}", center_matrix,
            radius * size_scale, 0.008, mats["cast_iron"], target, root, "gas burner",
        )
        for arm_index, angle in enumerate((0.0, math.pi * 0.5), start=1):
            box_world(
                f"{prefix}_GRATE_{index:02d}_{arm_index:02d}",
                (radius * size_scale * 2.4, 0.018, 0.014),
                center_matrix @ Matrix.Rotation(angle, 4, "Z"),
                mats["cast_iron"], target, root, "cast-iron burner grate", bevel=0.003,
            )
        knob_x = x
        knob_y = front_sign * (depth * 0.5 + 0.018)
        knob_z = -height * 0.18
        cylinder_world(
            f"{prefix}_CONTROL_{index:02d}", 0.027, 0.025,
            frame @ Matrix.Translation((knob_x, knob_y, knob_z)) @ Matrix.Rotation(math.pi * 0.5, 4, "X"),
            mats["stainless_dark"], target, root, "stove control knob", vertices=20,
        )


def detail_aux_range(aux_range, kitchen_center, mats, target, root):
    width, depth, height = object_local_dimensions(aux_range)
    front_sign = local_y_side_toward(aux_range, kitchen_center)
    box_relative(
        "KITCHEN_RANGE_AUX_COOKTOP", aux_range,
        (0.0, 0.0, height * 0.5 + 0.018),
        (width + 0.025, depth + 0.025, 0.036),
        mats["stainless"], target, root, "four-burner cooktop", bevel=0.006,
    )
    spacing = width / 5.0
    burners = [(-width * 0.5 + spacing * (index + 1), 0.0, 1.0) for index in range(4)]
    burner_details(
        "KITCHEN_RANGE_AUX", aux_range.matrix_world, width, depth, height,
        burners, front_sign, mats, target, root,
    )
    aux_range["burner_count"] = 4
    aux_range["configuration"] = "two double stoves"


def wall_row_frame(wall, kitchen_center, depth, height, floor_z):
    location, rotation, _scale = wall.matrix_world.decompose()
    frame = Matrix.Translation(location) @ rotation.to_matrix().to_4x4()
    dimensions = world_axis_dimensions(wall)
    normal = frame.to_3x3() @ Vector((0.0, 1.0, 0.0))
    side = 1.0 if (Vector(kitchen_center) - location).dot(normal) >= 0.0 else -1.0
    center = location + normal * side * (dimensions.y * 0.5 + depth * 0.5 + 0.035)
    center.z = floor_z + height * 0.5
    return Matrix.Translation(center) @ rotation.to_matrix().to_4x4(), dimensions.x, side


def build_wall009_range(wall, kitchen_center, depth, height, floor_z, mats, target, root):
    row_frame, wall_length, front_sign = wall_row_frame(wall, kitchen_center, depth, height, floor_z)
    row_width = wall_length * 0.92
    gap = 0.025
    module_width = (row_width - gap * 3.0) / 4.0
    start_x = -row_width * 0.5 + module_width * 0.5
    modules = []
    for module_index in range(4):
        x = start_x + module_index * (module_width + gap)
        module_frame = row_frame @ Matrix.Translation((x, 0.0, 0.0))
        module = box_world(
            f"KITCHEN_RANGE_W009_MODULE_{module_index + 1:02d}",
            (module_width, depth, height), module_frame,
            mats["stainless_dark"], target, root, "wall-aligned stove module", bevel=0.008,
            status="Width distributed along WALL_009; depth and height derived from Cube.015",
        )
        modules.append(module)
        box_world(
            f"KITCHEN_RANGE_W009_COOKTOP_{module_index + 1:02d}",
            (module_width + 0.018, depth + 0.018, 0.036),
            module_frame @ Matrix.Translation((0.0, 0.0, height * 0.5 + 0.018)),
            mats["stainless"], target, root, "stove cooktop", bevel=0.005,
        )
        if module_index == 0:
            positions = [(0.0, 0.0, 1.35)]
            configuration = "one large burner"
        else:
            positions = [(-module_width * 0.24, 0.0, 0.88), (module_width * 0.24, 0.0, 0.88)]
            configuration = "double burner"
        burner_details(
            f"KITCHEN_RANGE_W009_M{module_index + 1:02d}", module_frame,
            module_width, depth, height, positions, front_sign, mats, target, root,
        )
        module["configuration"] = configuration
        module["host_wall"] = "WALL_009"
    root["wall009_burner_count"] = 7
    root["wall009_configuration"] = "one large burner plus three double burners"
    return row_frame, row_width, front_sign


def hood_mesh(name, frame, width, depth, bottom_z, top_z, mats, target, root):
    height = top_z - bottom_z
    bottom_width = width
    bottom_depth = depth
    top_width = width * 0.72
    top_depth = depth * 0.56
    z0 = -height * 0.5
    z1 = height * 0.5
    vertices = [
        (-bottom_width * 0.5, -bottom_depth * 0.5, z0),
        (bottom_width * 0.5, -bottom_depth * 0.5, z0),
        (bottom_width * 0.5, bottom_depth * 0.5, z0),
        (-bottom_width * 0.5, bottom_depth * 0.5, z0),
        (-top_width * 0.5, -top_depth * 0.5, z1),
        (top_width * 0.5, -top_depth * 0.5, z1),
        (top_width * 0.5, top_depth * 0.5, z1),
        (-top_width * 0.5, top_depth * 0.5, z1),
    ]
    faces = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)]
    mesh = bpy.data.meshes.new(f"{name}_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    target.objects.link(obj)
    center = frame.translation.copy()
    center.z = (bottom_z + top_z) * 0.5
    _location, rotation, _scale = frame.decompose()
    obj.matrix_world = Matrix.Translation(center) @ rotation.to_matrix().to_4x4()
    assign_material(obj, mats["stainless_dark"])
    bevel = obj.modifiers.new("HOOD_EDGE_RADIUS", "BEVEL")
    bevel.width = 0.010
    bevel.segments = 2
    generated(obj, target, root, "heat extraction canopy", "Visual profile from reference; plan span tied to stove envelope")

    filter_count = max(2, int(round(width / 0.75)))
    filter_width = width * 0.86 / filter_count
    for index in range(filter_count):
        x = -width * 0.43 + filter_width * (index + 0.5)
        box_world(
            f"{name}_FILTER_{index + 1:02d}",
            (filter_width * 0.88, depth * 0.68, 0.024),
            (Matrix.Translation(center) @ rotation.to_matrix().to_4x4())
            @ Matrix.Translation((x, 0.0, -height * 0.5 + 0.010)),
            mats["cast_iron"], target, root, "hood grease filter", bevel=0.003,
        )
    box_world(
        f"{name}_DUCT",
        (top_width * 0.30, top_depth * 0.55, 0.22),
        (Matrix.Translation(center) @ rotation.to_matrix().to_4x4())
        @ Matrix.Translation((0.0, 0.0, height * 0.5 + 0.11)),
        mats["stainless_dark"], target, root, "extractor duct", bevel=0.006,
    )
    return obj


def detail_fridge(fridge, kitchen_center, mats, target, root):
    width, depth, height = object_local_dimensions(fridge)
    front_sign = local_y_side_toward(fridge, kitchen_center)
    face_y = front_sign * (depth * 0.5 + 0.010)
    box_relative(
        "KITCHEN_FRIDGE_DOOR", fridge,
        (0.0, face_y, 0.0),
        (width * 0.93, 0.020, height * 0.92),
        mats["stainless"], target, root, "refrigerator door", bevel=0.012,
    )
    handle_x = width * 0.34
    start = fridge.matrix_world @ Vector((handle_x, face_y + front_sign * 0.025, -height * 0.25))
    end = fridge.matrix_world @ Vector((handle_x, face_y + front_sign * 0.025, height * 0.26))
    cylinder_between(
        "KITCHEN_FRIDGE_HANDLE", start, end, 0.018,
        mats["stainless_dark"], target, root, "refrigerator handle", vertices=22,
    )
    for index in range(6):
        box_relative(
            f"KITCHEN_FRIDGE_GRILLE_{index + 1:02d}", fridge,
            ((index - 2.5) * width * 0.105, face_y + front_sign * 0.014, height * 0.39),
            (width * 0.075, 0.010, 0.018),
            mats["stainless_dark"], target, root, "refrigerator ventilation grille", bevel=0.002,
        )


def detail_side_counter(counter, kitchen_center, mats, target, root):
    detail_counter_top(counter, "KITCHEN_SIDE_COUNTER_TOP", mats, target, root)
    create_wall_shelves(counter, "KITCHEN_SIDE", kitchen_center, 2, 1, mats, target, root)


def build():
    if Path(bpy.data.filepath).resolve() != BLEND_PATH.resolve():
        raise RuntimeError(f"Run this script with the canonical scene: {BLEND_PATH}")
    target = ensure_collection()
    remove_generated()
    root = ensure_root(target)
    mats = create_materials()
    kitchen_center = guide_centroid("FLOOR_COCINA")
    cores = {key: find_object(*aliases) for key, aliases in CORE_ALIASES.items()}

    island = upgrade_core(
        cores["island"], CORE_ALIASES["island"][0], mats["tile"], target, root,
        "built-in central island", 0.010,
    )
    sink_counter = upgrade_core(
        cores["sink_counter"], CORE_ALIASES["sink_counter"][0], mats["tile"], target, root,
        "built-in sink counter", 0.008,
    )
    aux_range = upgrade_core(
        cores["aux_range"], CORE_ALIASES["aux_range"][0], mats["stainless_dark"], target, root,
        "two double-stove bank", 0.008,
    )
    fridge = upgrade_core(
        cores["fridge"], CORE_ALIASES["fridge"][0], mats["stainless_dark"], target, root,
        "upright refrigerator", 0.012,
    )
    side_counter = upgrade_core(
        cores["side_counter"], CORE_ALIASES["side_counter"][0], mats["tile"], target, root,
        "side preparation counter", 0.008,
    )

    detail_island(island, mats, target, root)
    detail_sink_counter(sink_counter, kitchen_center, mats, target, root)
    create_wall_shelves(sink_counter, "KITCHEN_SINK", kitchen_center, 2, 3, mats, target, root)
    detail_aux_range(aux_range, kitchen_center, mats, target, root)
    detail_fridge(fridge, kitchen_center, mats, target, root)
    detail_side_counter(side_counter, kitchen_center, mats, target, root)

    _floor_min, _floor_max = world_z_bounds(island)
    floor_z = _floor_min
    _aux_width, aux_depth, aux_height = object_local_dimensions(aux_range)
    wall = bpy.data.objects.get("WALL_009")
    if wall is None:
        raise RuntimeError("Required host wall is missing: WALL_009")
    row_frame, row_width, _front_sign = build_wall009_range(
        wall, kitchen_center, aux_depth, aux_height, floor_z, mats, target, root,
    )

    hood_bottom = floor_z + 1.66
    hood_top = floor_z + 2.08
    hood_mesh(
        "KITCHEN_HOOD_WALL009", row_frame, row_width + 0.18, aux_depth + 0.28,
        hood_bottom, hood_top, mats, target, root,
    )
    aux_frame = normalized_frame(aux_range)
    aux_location = aux_range.matrix_world.translation.copy()
    aux_frame.translation = aux_location
    hood_mesh(
        "KITCHEN_HOOD_AUX", aux_frame, object_local_dimensions(aux_range).x + 0.18, aux_depth + 0.28,
        hood_bottom, hood_top, mats, target, root,
    )

    aux_range["burner_count"] = 4
    root["total_burner_count"] = 11
    root["people_generated"] = False
    root["host_wall"] = "WALL_009"
    target["asset_id"] = ROOT_NAME
    target["source_reference"] = SOURCE_REFERENCE
    target["dimensions_status"] = "Proxy envelopes retained; unmeasured equipment profiles provisional"
    target["scope_note"] = "Internal production kitchen equipment; no people"
    return root


def main():
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    root = build()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    print("KITCHEN_COLLECTION", COLLECTION_NAME)
    print("KITCHEN_ROOT", root.name)
    print("KITCHEN_TOTAL_BURNERS", root["total_burner_count"])


if __name__ == "__main__":
    main()
