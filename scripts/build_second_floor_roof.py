"""Finish the provisional second-floor room and roof geometry.

The user-authored objects in collection ``Roof`` remain the dimensional guides.
Unmeasured profiles are explicitly tagged provisional.  Generated finish pieces
live in ``Roof_Finishes`` so the operation is repeatable and easy to remove.
"""

from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
COLLECTION_NAME = "Roof_Finishes"
ROOT_NAME = "SECOND_FLOOR_ROOF_01"


def remove_collection(name: str) -> None:
    collection = bpy.data.collections.get(name)
    if collection is None:
        return
    for child in list(collection.children):
        remove_collection(child.name)
    for obj in list(collection.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.collections.remove(collection)


def ensure_collection(name: str, parent: bpy.types.Collection) -> bpy.types.Collection:
    collection = bpy.data.collections.new(name)
    parent.children.link(collection)
    return collection


def shader_input(shader, *names):
    for name in names:
        socket = shader.inputs.get(name)
        if socket is not None:
            return socket
    return None


def material(name, color, *, metallic=0.0, roughness=0.45, alpha=1.0,
             transmission=0.0, ior=1.45):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color, alpha)
    nodes = mat.node_tree.nodes
    shader = nodes.get("Principled BSDF")
    shader_input(shader, "Base Color").default_value = (*color, 1.0)
    shader_input(shader, "Metallic").default_value = metallic
    shader_input(shader, "Roughness").default_value = roughness
    alpha_socket = shader_input(shader, "Alpha")
    if alpha_socket:
        alpha_socket.default_value = alpha
    transmission_socket = shader_input(shader, "Transmission Weight", "Transmission")
    if transmission_socket:
        transmission_socket.default_value = transmission
    ior_socket = shader_input(shader, "IOR")
    if ior_socket:
        ior_socket.default_value = ior
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "DITHERED" if alpha < 1.0 else "DITHERED"
    elif hasattr(mat, "blend_method"):
        mat.blend_method = "BLEND" if alpha < 1.0 else "OPAQUE"
        mat.use_screen_refraction = transmission > 0.0
    mat.use_transparency_overlap = False if hasattr(mat, "use_transparency_overlap") else True
    return mat


def assign_material(obj, mat):
    if not hasattr(obj.data, "materials"):
        return
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def cube(name, location, dimensions, collection, mat, rotation_z=0.0, parent=None,
         bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(location=location, rotation=(0.0, 0.0, rotation_z))
    obj = bpy.context.object
    obj.name = name
    for existing in list(obj.users_collection):
        existing.objects.unlink(obj)
    collection.objects.link(obj)
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0.0:
        modifier = obj.modifiers.new("Soft_Edges", "BEVEL")
        modifier.width = bevel
        modifier.segments = 2
    assign_material(obj, mat)
    obj.parent = parent
    obj["generatedBy"] = Path(__file__).name
    obj["dimensionalStatus"] = "provisional_from_scene_guides"
    return obj


def curve_tube(name, points, collection, mat, radius=0.025, parent=None):
    data = bpy.data.curves.new(name + "_DATA", "CURVE")
    data.dimensions = "3D"
    data.resolution_u = 1
    data.bevel_depth = radius
    data.bevel_resolution = 2
    spline = data.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, co in zip(spline.points, points):
        point.co = (*co, 1.0)
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    assign_material(obj, mat)
    obj.parent = parent
    obj["generatedBy"] = Path(__file__).name
    obj["dimensionalStatus"] = "derived_from_existing_roof_geometry"
    return obj


def world_bounds(obj):
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return (
        Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points))),
        Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points))),
    )


def projected_opening(obj, origin, y_axis):
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    along = [(point - origin).dot(y_axis) for point in points]
    return min(along), max(along), min(p.z for p in points), max(p.z for p in points)


def local_point(origin, x_axis, y_axis, x, y, z):
    return origin + x_axis * x + y_axis * y + Vector((0.0, 0.0, z - origin.z))


def wall_piece(name, wall_origin, x_axis, y_axis, angle, u0, u1, z0, z1,
               thickness, collection, mat, parent):
    center = local_point(wall_origin, x_axis, y_axis, 0.0, (u0 + u1) * 0.5, (z0 + z1) * 0.5)
    return cube(
        name,
        center,
        (thickness, u1 - u0, z1 - z0),
        collection,
        mat,
        rotation_z=angle,
        parent=parent,
    )


def build():
    required = [
        "Cube", "Cube.011", "Cube.012", "Cube.013", "Cube.014", "Cube.015",
        "Cube.026", "Cube.028", "Cube.047", "Cube.048", "Cube.049", "Cube.050",
        "Cylinder.003",
    ]
    missing = [name for name in required if bpy.data.objects.get(name) is None]
    if missing:
        raise RuntimeError(f"Missing second-floor/roof guides: {missing}")

    scene_root = bpy.data.collections.get("Guadalajara") or bpy.context.scene.collection
    remove_collection(COLLECTION_NAME)
    finishes = ensure_collection(COLLECTION_NAME, scene_root)
    facade = ensure_collection("Second_Floor_Facade", finishes)
    roof_structure = ensure_collection("Patio_Roof_Structure", finishes)
    trim = ensure_collection("Roof_Trim", finishes)

    root = bpy.data.objects.new(ROOT_NAME, None)
    finishes.objects.link(root)
    root.empty_display_type = "PLAIN_AXES"
    root["generatedBy"] = Path(__file__).name
    root["sourceCollection"] = "Roof"
    root["evidenceStatus"] = "provisional_geometry_derived_from_user_guides"
    root["roofPhysics"] = "none"

    mat_gray = material(
        "MAT_Roof_Galvanized_Gray", (0.26, 0.29, 0.31), metallic=0.55, roughness=0.42
    )
    mat_poly = material(
        "MAT_Roof_Translucent_Polycarbonate", (0.63, 0.82, 0.86),
        metallic=0.0, roughness=0.27, alpha=0.43, transmission=0.62, ior=1.47,
    )
    mat_frame = material(
        "MAT_Roof_Frame_Dark", (0.075, 0.085, 0.09), metallic=0.75, roughness=0.34
    )
    mat_wall = material(
        "MAT_SecondFloor_Wall_White", (0.78, 0.77, 0.70), metallic=0.0, roughness=0.63
    )
    mat_concrete = material(
        "MAT_SecondFloor_Concrete", (0.34, 0.35, 0.35), metallic=0.0, roughness=0.78
    )
    mat_door = material(
        "MAT_SecondFloor_Door_Gray", (0.20, 0.24, 0.27), metallic=0.35, roughness=0.42
    )
    mat_glass = material(
        "MAT_SecondFloor_Window_Glass", (0.34, 0.55, 0.62),
        roughness=0.12, alpha=0.28, transmission=0.78, ior=1.45,
    )

    for name in ("Cube", "Cube.011", "Cube.013", "Cube.047", "Cube.048"):
        obj = bpy.data.objects[name]
        assign_material(obj, mat_gray)
        obj["finishRole"] = "gray_roof"
    assign_material(bpy.data.objects["Cube.012"], mat_concrete)
    bpy.data.objects["Cube.012"]["finishRole"] = "second_floor_slab"
    for name in ("Cube.014", "Cube.015", "Cube.026"):
        obj = bpy.data.objects[name]
        assign_material(obj, mat_wall)
        obj["finishRole"] = "second_floor_wall"

    canopy = bpy.data.objects["Cylinder.003"]
    assign_material(canopy, mat_poly)
    canopy["finishRole"] = "translucent_solar_patio_roof"
    canopy["materialDescription"] = "translucent corrugated-style polycarbonate approximation"
    if canopy.modifiers.get("Polycarbonate_Thickness") is None:
        solidify = canopy.modifiers.new("Polycarbonate_Thickness", "SOLIDIFY")
        solidify.thickness = 0.012
        solidify.offset = 0.0

    # Rebuild the long landing facade around the exact user-authored door/window guides.
    wall = bpy.data.objects["Cube.028"]
    door_guide = bpy.data.objects["Cube.049"]
    window_guide = bpy.data.objects["Cube.050"]
    angle = wall.rotation_euler.z
    x_axis = Vector((math.cos(angle), math.sin(angle), 0.0))
    y_axis = Vector((-math.sin(angle), math.cos(angle), 0.0))
    origin = wall.matrix_world.translation.copy()
    wall_min, wall_max = world_bounds(wall)
    half_length = abs(wall.scale.y)
    thickness = abs(wall.scale.x) * 2.0
    door_u0, door_u1, _, door_z1 = projected_opening(door_guide, origin, y_axis)
    win_u0, win_u1, win_z0, win_z1 = projected_opening(window_guide, origin, y_axis)
    z0, z1 = wall_min.z, wall_max.z

    spans = [
        ("A", -half_length, win_u0, z0, z1),
        ("B_SILL", win_u0, win_u1, z0, win_z0),
        ("B_HEAD", win_u0, win_u1, win_z1, z1),
        ("C", win_u1, door_u0, z0, z1),
        ("D_HEAD", door_u0, door_u1, door_z1, z1),
        ("E", door_u1, half_length, z0, z1),
    ]
    for suffix, u0, u1, low, high in spans:
        if u1 - u0 > 0.01 and high - low > 0.01:
            wall_piece(
                f"SECOND_FLOOR_FACADE_{suffix}", origin, x_axis, y_axis, angle,
                u0, u1, low, high, thickness, facade, mat_wall, root,
            )
    wall.hide_render = True
    wall.hide_set(True)
    wall["finishRole"] = "hidden_facade_envelope_guide"
    door_guide.hide_render = True
    door_guide.hide_set(True)
    window_guide.hide_render = True
    window_guide.hide_set(True)
    door_guide["finishRole"] = "hidden_door_opening_guide"
    window_guide["finishRole"] = "hidden_window_opening_guide"

    exterior_x = -thickness * 0.5 - 0.018
    door_center_u = (door_u0 + door_u1) * 0.5
    door_width = max(0.30, door_u1 - door_u0 - 0.07)
    door_bottom = z0 + 0.015
    door_top = door_z1 - 0.035
    door_center = local_point(origin, x_axis, y_axis, exterior_x, door_center_u, (door_bottom + door_top) * 0.5)
    cube(
        "SECOND_FLOOR_DOOR_PANEL", door_center, (0.045, door_width, door_top - door_bottom),
        facade, mat_door, angle, root, bevel=0.008,
    )
    frame_w = 0.05
    for suffix, u, height in (
        ("JAMB_L", door_u0 + frame_w * 0.5, door_z1 - z0),
        ("JAMB_R", door_u1 - frame_w * 0.5, door_z1 - z0),
    ):
        center = local_point(origin, x_axis, y_axis, exterior_x - 0.015, u, z0 + height * 0.5)
        cube(f"SECOND_FLOOR_DOOR_{suffix}", center, (0.07, frame_w, height), facade,
             mat_frame, angle, root)
    head = local_point(origin, x_axis, y_axis, exterior_x - 0.015, door_center_u, door_z1 - frame_w * 0.5)
    cube("SECOND_FLOOR_DOOR_HEAD", head, (0.07, door_u1 - door_u0, frame_w),
         facade, mat_frame, angle, root)
    threshold = local_point(origin, x_axis, y_axis, exterior_x - 0.03, door_center_u, z0 + 0.018)
    cube("SECOND_FLOOR_DOOR_THRESHOLD", threshold, (0.13, door_u1 - door_u0, 0.035),
         facade, mat_frame, angle, root, bevel=0.006)
    handle_u = door_center_u - door_width * 0.30
    handle_center = local_point(origin, x_axis, y_axis, exterior_x - 0.055, handle_u, z0 + 0.88)
    cube("SECOND_FLOOR_DOOR_HANDLE", handle_center, (0.035, 0.14, 0.025),
         facade, mat_frame, angle, root, bevel=0.008)

    window_center_u = (win_u0 + win_u1) * 0.5
    glass_center = local_point(origin, x_axis, y_axis, exterior_x, window_center_u, (win_z0 + win_z1) * 0.5)
    cube(
        "SECOND_FLOOR_WINDOW_GLASS", glass_center,
        (0.025, win_u1 - win_u0 - 0.09, win_z1 - win_z0 - 0.09),
        facade, mat_glass, angle, root,
    )
    for suffix, u in (("JAMB_L", win_u0 + frame_w * 0.5), ("JAMB_R", win_u1 - frame_w * 0.5)):
        center = local_point(origin, x_axis, y_axis, exterior_x - 0.012, u, (win_z0 + win_z1) * 0.5)
        cube(f"SECOND_FLOOR_WINDOW_{suffix}", center, (0.055, frame_w, win_z1 - win_z0),
             facade, mat_frame, angle, root)
    for suffix, z in (("SILL", win_z0 + frame_w * 0.5), ("HEAD", win_z1 - frame_w * 0.5)):
        center = local_point(origin, x_axis, y_axis, exterior_x - 0.012, window_center_u, z)
        cube(f"SECOND_FLOOR_WINDOW_{suffix}", center, (0.055, win_u1 - win_u0, frame_w),
             facade, mat_frame, angle, root)
    mullion = local_point(origin, x_axis, y_axis, exterior_x - 0.02, window_center_u, (win_z0 + win_z1) * 0.5)
    cube("SECOND_FLOOR_WINDOW_MULLION", mullion, (0.06, 0.035, win_z1 - win_z0 - 0.08),
         facade, mat_frame, angle, root)
    sill_cap = local_point(origin, x_axis, y_axis, exterior_x - 0.045, window_center_u, win_z0 - 0.015)
    cube("SECOND_FLOOR_WINDOW_SILL_CAP", sill_cap, (0.14, win_u1 - win_u0 + 0.10, 0.035),
         facade, mat_concrete, angle, root, bevel=0.006)

    # Cover small corner discrepancies without changing the user-authored wall guides.
    for index, u in enumerate((-half_length, half_length), start=1):
        center = local_point(origin, x_axis, y_axis, -thickness * 0.5 - 0.025, u, (z0 + z1) * 0.5)
        cube(f"SECOND_FLOOR_CORNER_CAP_{index:02d}", center, (0.10, 0.10, z1 - z0 + 0.06),
             facade, mat_frame, angle, root)

    # Frame the exact polycarbonate canopy surface using its existing paired vertices.
    vertices = [canopy.matrix_world @ vertex.co for vertex in canopy.data.vertices]
    front_ids = [0, 12, 10, 8, 6, 4, 2]
    back_ids = [1, 13, 11, 9, 7, 5, 3]
    front = [vertices[index] for index in front_ids]
    back = [vertices[index] for index in back_ids]
    for index, fraction in enumerate((0.0, 0.25, 0.5, 0.75, 1.0), start=1):
        points = [front_point.lerp(back_point, fraction) for front_point, back_point in zip(front, back)]
        curve_tube(f"PATIO_ROOF_RIB_{index:02d}", points, roof_structure, mat_frame, 0.028, root)
    for index, (front_point, back_point) in enumerate(zip(front, back), start=1):
        curve_tube(
            f"PATIO_ROOF_PURLIN_{index:02d}", [front_point, back_point], roof_structure,
            mat_frame, 0.022, root,
        )

    # Edge flashing follows the upper roof's exact four top perimeter edges.
    upper_roof = bpy.data.objects["Cube.047"]
    roof_vertices = [upper_roof.matrix_world @ vertex.co for vertex in upper_roof.data.vertices]
    top_indices = sorted(range(len(roof_vertices)), key=lambda i: roof_vertices[i].z)[-4:]
    top_points = [roof_vertices[i] for i in top_indices]
    center_xy = sum((Vector((p.x, p.y)) for p in top_points), Vector((0.0, 0.0))) / 4.0
    top_points.sort(key=lambda p: math.atan2(p.y - center_xy.y, p.x - center_xy.x))
    for index in range(4):
        curve_tube(
            f"UPPER_ROOF_EDGE_FLASHING_{index + 1:02d}",
            [top_points[index], top_points[(index + 1) % 4]], trim, mat_frame, 0.025, root,
        )

    # Slab fascia visually closes its thin exposed perimeter.
    slab = bpy.data.objects["Cube.012"]
    slab_vertices = [slab.matrix_world @ vertex.co for vertex in slab.data.vertices]
    slab_top_ids = sorted(range(len(slab_vertices)), key=lambda i: slab_vertices[i].z)[-4:]
    slab_points = [slab_vertices[i] for i in slab_top_ids]
    slab_center = sum((Vector((p.x, p.y)) for p in slab_points), Vector((0.0, 0.0))) / 4.0
    slab_points.sort(key=lambda p: math.atan2(p.y - slab_center.y, p.x - slab_center.x))
    for index in range(4):
        curve_tube(
            f"SECOND_FLOOR_SLAB_EDGE_{index + 1:02d}",
            [slab_points[index], slab_points[(index + 1) % 4]], trim, mat_concrete, 0.025, root,
        )

    root["generatedObjectCount"] = sum(1 for _ in finishes.all_objects)
    root["doorGuide"] = "Cube.049"
    root["windowGuide"] = "Cube.050"
    root["curvedCanopyGuide"] = "Cylinder.003"
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "blend" / "guadalajara_base.blend"))
    return root


if __name__ == "__main__":
    root = build()
    print("SECOND_FLOOR_ROOF_ROOT", root.name)
    print("SECOND_FLOOR_ROOF_OBJECTS", root.get("generatedObjectCount"))

