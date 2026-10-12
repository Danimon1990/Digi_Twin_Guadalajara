"""Upgrade the user-authored Sopas proxies into a reusable soup station.

The station envelope and pot bounds come from the existing Blender objects in
``blend/guadalajara_base.blend``.  IMG_5979.heic is used only as a visual
construction reference for the commercial range, open stockpots, loop handles,
ladles, and burner details.  No dimensions are inferred from the photograph.
"""

from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
BLEND_PATH = ROOT / "blend" / "guadalajara_base.blend"
PREVIEW_PATH = ROOT / "outputs" / "previews" / "soup_station.png"

SCRIPT_ID = "build_soup_station_v1"
SOURCE_REFERENCE = "IMG_5979.heic"
TARGET_COLLECTION = "Sopas"
DESPACHO_COLLECTION = "Equipment_Despacho"
ROOT_OBJECT = "SOUP_STATION_01"

CORE_ALIASES = {
    "body": ("SOUP_RANGE_BODY", "Cube.004"),
    "side_left": ("SOUP_RANGE_SIDE_LEFT", "Cube.008"),
    "side_right": ("SOUP_RANGE_SIDE_RIGHT", "Cube.023"),
    "lower_shelf": ("SOUP_RANGE_LOWER_SHELF", "Cube.025"),
}

POT_ALIASES = (
    ("SOUP_POT_01", "Cylinder.022"),
    ("SOUP_POT_02", "Cylinder.023"),
    ("SOUP_POT_03", "Cylinder.024"),
)

# Exact values read from the user's cylinder proxies before the first upgrade.
# These are used only to repair scenes written by the initial hierarchy pass.
AUTHORED_POT_BOUNDS = {
    "Cylinder.022": {
        "location": (-0.70044, -3.68644, 0.98792),
        "diameter": 0.35360,
        "height": 0.27295,
    },
    "Cylinder.023": {
        "location": (-1.08913, -3.68644, 0.98792),
        "diameter": 0.30270,
        "height": 0.23366,
    },
    "Cylinder.024": {
        "location": (-1.44133, -3.65540, 0.98792),
        "diameter": 0.30270,
        "height": 0.23366,
    },
}


def require_collection(name: str):
    result = bpy.data.collections.get(name)
    if result is None:
        raise RuntimeError(f"Required collection is missing: {name}")
    return result


def find_object(*aliases: str):
    for name in aliases:
        obj = bpy.data.objects.get(name)
        if obj is not None:
            return obj
    raise RuntimeError(f"Required object is missing; expected one of: {aliases}")


def collection_parents(child):
    parents = []
    if child.name in bpy.context.scene.collection.children:
        parents.append(bpy.context.scene.collection)
    for candidate in bpy.data.collections:
        if child.name in candidate.children:
            parents.append(candidate)
    return parents


def move_collection(child, parent):
    if child.name not in parent.children:
        parent.children.link(child)
    for current in collection_parents(child):
        if current != parent:
            current.children.unlink(child)


def move_object(obj, target):
    if target not in obj.users_collection:
        target.objects.link(obj)
    for current in list(obj.users_collection):
        if current != target:
            current.objects.unlink(obj)


def assign_material(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def set_parent_keep_world(obj, parent):
    bpy.context.view_layer.update()
    world = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_parent_inverse = parent.matrix_world.inverted()
    obj.matrix_world = world
    bpy.context.view_layer.update()


def repair_initial_hierarchy_if_needed():
    """Repair transforms saved by the first root-parenting implementation."""
    root = bpy.data.objects.get(ROOT_OBJECT)
    if root is None or root.get("hierarchy_version", 0) >= 2:
        return False

    # The core cubes retained their original world transform in matrix_basis.
    for aliases in CORE_ALIASES.values():
        obj = find_object(*aliases)
        if obj.parent == root:
            original = obj.matrix_basis.copy()
            obj.parent = None
            obj.matrix_parent_inverse.identity()
            obj.matrix_world = original

    # Restore the exact proxy centers and bounds captured before conversion.
    for aliases in POT_ALIASES:
        obj = find_object(*aliases)
        legacy_name = obj.get("legacy_proxy", aliases[1])
        authored = AUTHORED_POT_BOUNDS[legacy_name]
        obj.parent = None
        obj.matrix_parent_inverse.identity()
        obj.location = authored["location"]
        obj.rotation_euler = (0.0, 0.0, -0.10845)
        obj.scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()
    return True


def local_dimensions(obj):
    points = [Vector(corner) for corner in obj.bound_box]
    mins = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    maxs = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    size = maxs - mins
    return Vector((
        abs(size.x * obj.scale.x),
        abs(size.y * obj.scale.y),
        abs(size.z * obj.scale.z),
    ))


def ensure_principled_material(name, color, metallic, roughness):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color, 1.0)
    mat.metallic = metallic
    mat.roughness = roughness
    nodes = mat.node_tree.nodes
    shader = nodes.get("Principled BSDF")
    if shader is not None:
        shader.inputs["Base Color"].default_value = (*color, 1.0)
        shader.inputs["Metallic"].default_value = metallic
        shader.inputs["Roughness"].default_value = roughness
    return mat


def ensure_worn_aluminum():
    mat = ensure_principled_material(
        "MAT_Soup_Pot_Aluminum_Worn", (0.43, 0.45, 0.44), 0.94, 0.34
    )
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    shader = nodes.get("Principled BSDF")
    for node in list(nodes):
        if node.get("soup_station_node"):
            nodes.remove(node)
    noise = nodes.new("ShaderNodeTexNoise")
    noise.name = "SoupPot_Wear"
    noise.label = "Subtle aluminum wear"
    noise.inputs["Scale"].default_value = 7.5
    noise.inputs["Detail"].default_value = 4.0
    noise.inputs["Roughness"].default_value = 0.72
    noise["soup_station_node"] = True
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.name = "SoupPot_RoughnessVariation"
    ramp.color_ramp.elements[0].color = (0.20, 0.20, 0.20, 1.0)
    ramp.color_ramp.elements[1].color = (0.58, 0.58, 0.58, 1.0)
    ramp["soup_station_node"] = True
    bump = nodes.new("ShaderNodeBump")
    bump.name = "SoupPot_MicroDents"
    bump.inputs["Strength"].default_value = 0.08
    bump.inputs["Distance"].default_value = 0.0015
    bump["soup_station_node"] = True
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], shader.inputs["Roughness"])
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    return mat


def generated_object(obj, target, parent=None):
    obj["generated_by"] = SCRIPT_ID
    obj["source_reference"] = SOURCE_REFERENCE
    obj["dimensions_status"] = "Derived from user-authored Blender proxies"
    move_object(obj, target)
    if parent is not None:
        set_parent_keep_world(obj, parent)
    return obj


def remove_previous_generated():
    for obj in list(bpy.data.objects):
        if obj.get("generated_by") == SCRIPT_ID:
            bpy.data.objects.remove(obj, do_unlink=True)


def beveled_box(name, dimensions, location, rotation_z, mat, target, parent, bevel=0.006):
    bpy.ops.mesh.primitive_cube_add(location=location, rotation=(0.0, 0.0, rotation_z))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0.0:
        modifier = obj.modifiers.new("EDGE_RADIUS", "BEVEL")
        modifier.width = bevel
        modifier.segments = 3
        modifier.limit_method = "ANGLE"
    assign_material(obj, mat)
    return generated_object(obj, target, parent)


def cylinder_between(name, start, end, radius, mat, target, parent, vertices=24):
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
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return generated_object(obj, target, parent)


def world_point(origin, angle, x, y, z):
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return Vector((
        origin.x + cosine * x - sine * y,
        origin.y + sine * x + cosine * y,
        z,
    ))


def parent_world_origin(name, location, angle, target):
    obj = bpy.data.objects.get(name)
    if obj is None:
        obj = bpy.data.objects.new(name, None)
        target.objects.link(obj)
    else:
        move_object(obj, target)
    obj.empty_display_type = "CUBE"
    obj.empty_display_size = 0.20
    obj.location = location
    obj.rotation_euler = (0.0, 0.0, angle)
    obj["asset_id"] = "SOUP_STATION_01"
    obj["source_reference"] = SOURCE_REFERENCE
    obj["dimensions_status"] = "Derived from user-authored Blender proxies"
    return obj


def upgrade_core_object(obj, new_name, mat, root):
    obj.name = new_name
    move_object(obj, require_collection(TARGET_COLLECTION))
    assign_material(obj, mat)
    set_parent_keep_world(obj, root)
    obj["asset_id"] = "SOUP_STATION_01"
    obj["source_reference"] = SOURCE_REFERENCE
    obj["dimensions_status"] = "Existing user-authored proxy retained as station envelope"
    bevel = obj.modifiers.get("SOUP_EDGE_RADIUS")
    if bevel is None:
        bevel = obj.modifiers.new("SOUP_EDGE_RADIUS", "BEVEL")
    bevel.width = min(0.008, min(local_dimensions(obj)) * 0.20)
    bevel.segments = 3
    bevel.limit_method = "ANGLE"
    return obj


def lathe_stockpot_mesh(name, diameter, height, segments=64):
    rim_tube = min(0.007, diameter * 0.025)
    wall = min(0.005, diameter * 0.018)
    radius = diameter * 0.5 - rim_tube
    z0 = -height * 0.5
    z1 = height * 0.5
    bottom_curve = min(0.018, height * 0.09)
    profile = (
        (0.001, z0),
        (radius * 0.90, z0),
        (radius, z0 + bottom_curve),
        (radius, z1 - rim_tube * 1.4),
        (radius + rim_tube, z1 - rim_tube),
        (radius + rim_tube, z1),
        (radius - wall, z1),
        (radius - wall, z0 + bottom_curve + wall),
        (0.001, z0 + bottom_curve + wall),
    )
    vertices = []
    for segment in range(segments):
        theta = math.tau * segment / segments
        cosine = math.cos(theta)
        sine = math.sin(theta)
        for radius_value, z in profile:
            vertices.append((radius_value * cosine, radius_value * sine, z))
    count = len(profile)
    faces = []
    for segment in range(segments):
        next_segment = (segment + 1) % segments
        for index in range(count - 1):
            faces.append((
                segment * count + index,
                next_segment * count + index,
                next_segment * count + index + 1,
                segment * count + index + 1,
            ))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(verbose=False)
    mesh.update()
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    return mesh


def pot_handle(name, pot, side, radius, height, mat, target):
    curve = bpy.data.curves.new(name, type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = max(0.0045, radius * 0.025)
    curve.bevel_resolution = 3
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(4)
    z_top = height * 0.5
    points = (
        (side * (radius - 0.004), 0.0, z_top - height * 0.38),
        (side * (radius + 0.030), 0.0, z_top - height * 0.31),
        (side * (radius + 0.048), 0.0, z_top - height * 0.16),
        (side * (radius + 0.030), 0.0, z_top - height * 0.01),
        (side * (radius - 0.004), 0.0, z_top - height * 0.08),
    )
    for point, co in zip(spline.bezier_points, points):
        point.co = co
        point.handle_left_type = "AUTO"
        point.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, curve)
    target.objects.link(obj)
    assign_material(obj, mat)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target="MESH")
    obj = bpy.context.object
    obj.parent = pot
    obj.matrix_parent_inverse.identity()
    obj["generated_by"] = SCRIPT_ID
    obj["source_reference"] = SOURCE_REFERENCE
    return obj


def add_stockpot_details(pot, index, diameter, height, polished, materials, target, station_root):
    radius = diameter * 0.5
    handle_mat = materials["dark_metal"] if not polished else materials["stainless"]
    pot_handle(f"SOUP_POT_{index:02d}_HANDLE_L", pot, -1.0, radius, height, handle_mat, target)
    pot_handle(f"SOUP_POT_{index:02d}_HANDLE_R", pot, 1.0, radius, height, handle_mat, target)

    liquid_z = pot.location.z + height * 0.5 - min(0.022, height * 0.09)
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=64,
        radius=radius - max(0.012, diameter * 0.045),
        depth=0.004,
        location=(pot.location.x, pot.location.y, liquid_z),
        rotation=(0.0, 0.0, pot.rotation_euler.z),
    )
    liquid = bpy.context.object
    liquid.name = f"SOUP_POT_{index:02d}_CONTENTS"
    assign_material(liquid, materials["soup"])
    generated_object(liquid, target, station_root)

    direction = -1.0 if index == 2 else 1.0
    handle_start = Vector((pot.location.x, pot.location.y, liquid_z + 0.012))
    local_offset = Vector((direction * radius * 0.35, 0.015, height * 0.78))
    cosine = math.cos(pot.rotation_euler.z)
    sine = math.sin(pot.rotation_euler.z)
    handle_end = Vector((
        handle_start.x + cosine * local_offset.x - sine * local_offset.y,
        handle_start.y + sine * local_offset.x + cosine * local_offset.y,
        handle_start.z + local_offset.z,
    ))
    cylinder_between(
        f"SOUP_POT_{index:02d}_LADLE_HANDLE",
        handle_start,
        handle_end,
        0.006,
        materials["stainless"],
        target,
        station_root,
        vertices=18,
    )
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=24,
        ring_count=12,
        location=handle_start,
        scale=(0.040, 0.030, 0.012),
    )
    bowl = bpy.context.object
    bowl.name = f"SOUP_POT_{index:02d}_LADLE_BOWL"
    assign_material(bowl, materials["stainless"])
    generated_object(bowl, target, station_root)


def upgrade_pot(obj, index, name, mat, materials, target, root, angle, recovery=False):
    if recovery:
        authored = AUTHORED_POT_BOUNDS[POT_ALIASES[index - 1][1]]
        diameter = authored["diameter"]
        height = authored["height"]
        obj.location = authored["location"]
    else:
        dimensions = local_dimensions(obj)
        diameter = max(dimensions.x, dimensions.y)
        height = dimensions.z
    location = obj.matrix_world.translation.copy()
    old_mesh = obj.data
    obj.data = lathe_stockpot_mesh(f"{name}_MESH", diameter, height)
    if old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)
    obj.name = name
    obj.location = location
    obj.rotation_euler = (0.0, 0.0, angle)
    obj.scale = (1.0, 1.0, 1.0)
    move_object(obj, target)
    assign_material(obj, mat)
    set_parent_keep_world(obj, root)
    obj["asset_id"] = "SOUP_STATION_01"
    obj["legacy_proxy"] = POT_ALIASES[index - 1][1]
    obj["source_reference"] = SOURCE_REFERENCE
    obj["dimensions_status"] = "Exact bounds retained from user-authored cylinder proxy"
    add_stockpot_details(obj, index, diameter, height, index == 1, materials, target, root)
    return obj


def create_station_details(body, pot_objects, materials, target, root):
    dims = local_dimensions(body)
    center = body.matrix_world.translation.copy()
    angle = body.matrix_world.to_euler().z
    width, depth, body_height = dims
    body_bottom = center.z - body_height * 0.5
    body_top = center.z + body_height * 0.5

    def point(x, y, z):
        return world_point(center, angle, x, y, z)

    # Reinforced cooktop and front control panel.
    beveled_box(
        "SOUP_RANGE_COOKTOP",
        (width * 0.985, depth * 0.96, 0.020),
        point(0.0, 0.0, body_top - 0.006),
        angle,
        materials["stainless"],
        target,
        root,
        bevel=0.004,
    )
    beveled_box(
        "SOUP_RANGE_CONTROL_PANEL",
        (width * 0.90, 0.045, body_height * 0.58),
        point(0.0, -depth * 0.5 - 0.018, center.z - body_height * 0.03),
        angle,
        materials["stainless"],
        target,
        root,
        bevel=0.005,
    )

    # Burner/grate positions follow the authored pot centers.
    inverse_angle = -angle
    cosine = math.cos(inverse_angle)
    sine = math.sin(inverse_angle)
    for index, pot in enumerate(pot_objects, start=1):
        delta = pot.matrix_world.translation - center
        local_x = cosine * delta.x - sine * delta.y
        local_y = sine * delta.x + cosine * delta.y
        pot_radius = max(local_dimensions(pot).x, local_dimensions(pot).y) * 0.5
        burner_center = point(local_x, local_y, body_top + 0.004)
        bpy.ops.mesh.primitive_torus_add(
            major_radius=max(0.060, pot_radius * 0.55),
            minor_radius=0.010,
            major_segments=40,
            minor_segments=10,
            location=burner_center,
            rotation=(0.0, 0.0, angle),
        )
        ring = bpy.context.object
        ring.name = f"SOUP_RANGE_BURNER_{index:02d}"
        assign_material(ring, materials["cast_iron"])
        generated_object(ring, target, root)
        for cross_index, cross_angle in enumerate((0.0, math.pi * 0.5), start=1):
            length = pot_radius * 1.15
            direction = angle + cross_angle
            offset = Vector((math.cos(direction) * length, math.sin(direction) * length, 0.0))
            cylinder_between(
                f"SOUP_RANGE_GRATE_{index:02d}_{cross_index:02d}",
                burner_center - offset,
                burner_center + offset,
                0.008,
                materials["cast_iron"],
                target,
                root,
                vertices=12,
            )
        bpy.ops.mesh.primitive_torus_add(
            major_radius=max(0.045, pot_radius * 0.40),
            minor_radius=0.004,
            major_segments=32,
            minor_segments=8,
            location=(burner_center.x, burner_center.y, burner_center.z + 0.006),
            rotation=(0.0, 0.0, angle),
        )
        flame = bpy.context.object
        flame.name = f"SOUP_RANGE_FLAME_{index:02d}"
        assign_material(flame, materials["flame"])
        generated_object(flame, target, root)

        knob_center = point(
            local_x,
            -depth * 0.5 - 0.050,
            center.z - body_height * 0.04,
        )
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=24,
            radius=0.026,
            depth=0.032,
            location=knob_center,
            rotation=(math.pi * 0.5, 0.0, angle),
        )
        knob = bpy.context.object
        knob.name = f"SOUP_RANGE_KNOB_{index:02d}"
        assign_material(knob, materials["dark_metal"])
        generated_object(knob, target, root)

    # Open commercial-range base: square legs plus a low storage rail/shelf.
    floor_z = min(
        find_object(*CORE_ALIASES["lower_shelf"]).matrix_world.translation.z
        + local_dimensions(find_object(*CORE_ALIASES["lower_shelf"])).z * 0.5,
        body_bottom - 0.10,
    )
    leg_top = body_bottom + 0.015
    for x_sign in (-1.0, 1.0):
        for y_sign in (-1.0, 1.0):
            start = point(x_sign * width * 0.44, y_sign * depth * 0.39, floor_z)
            end = point(x_sign * width * 0.44, y_sign * depth * 0.39, leg_top)
            cylinder_between(
                f"SOUP_RANGE_LEG_{'L' if x_sign < 0 else 'R'}_{'F' if y_sign < 0 else 'B'}",
                start,
                end,
                0.020,
                materials["stainless"],
                target,
                root,
                vertices=12,
            )
    lower_z = floor_z + 0.075
    for y_sign in (-1.0, 1.0):
        cylinder_between(
            f"SOUP_RANGE_LOWER_RAIL_{'F' if y_sign < 0 else 'B'}",
            point(-width * 0.44, y_sign * depth * 0.39, lower_z),
            point(width * 0.44, y_sign * depth * 0.39, lower_z),
            0.016,
            materials["stainless"],
            target,
            root,
            vertices=12,
        )


def create_materials():
    return {
        "stainless": ensure_principled_material(
            "MAT_Soup_Station_Stainless", (0.42, 0.46, 0.48), 0.93, 0.23
        ),
        "aluminum": ensure_worn_aluminum(),
        "polished": ensure_principled_material(
            "MAT_Soup_Pot_Stainless_Polished", (0.52, 0.56, 0.58), 0.97, 0.16
        ),
        "cast_iron": ensure_principled_material(
            "MAT_Soup_Grate_Cast_Iron", (0.025, 0.028, 0.028), 0.72, 0.42
        ),
        "dark_metal": ensure_principled_material(
            "MAT_Soup_Handle_Dark_Metal", (0.035, 0.037, 0.036), 0.82, 0.38
        ),
        "soup": ensure_principled_material(
            "MAT_Soup_Contents_Warm", (0.26, 0.075, 0.020), 0.0, 0.24
        ),
        "flame": ensure_principled_material(
            "MAT_Soup_Flame_Blue", (0.015, 0.10, 0.68), 0.10, 0.18
        ),
    }


def build_station():
    target = require_collection(TARGET_COLLECTION)
    despacho = require_collection(DESPACHO_COLLECTION)
    move_collection(target, despacho)
    remove_previous_generated()
    recovery = repair_initial_hierarchy_if_needed()
    materials = create_materials()

    cores = {key: find_object(*aliases) for key, aliases in CORE_ALIASES.items()}
    body = cores["body"]
    body_center = body.matrix_world.translation.copy()
    angle = body.matrix_world.to_euler().z
    root = parent_world_origin(ROOT_OBJECT, (body_center.x, body_center.y, 0.0), angle, target)

    upgrade_core_object(body, "SOUP_RANGE_BODY", materials["stainless"], root)
    upgrade_core_object(cores["side_left"], "SOUP_RANGE_SIDE_LEFT", materials["stainless"], root)
    upgrade_core_object(cores["side_right"], "SOUP_RANGE_SIDE_RIGHT", materials["stainless"], root)
    upgrade_core_object(cores["lower_shelf"], "SOUP_RANGE_LOWER_SHELF", materials["stainless"], root)

    pots = []
    for index, aliases in enumerate(POT_ALIASES, start=1):
        obj = find_object(*aliases)
        pot_mat = materials["polished"] if index == 1 else materials["aluminum"]
        pots.append(upgrade_pot(
            obj, index, aliases[0], pot_mat, materials, target, root, angle, recovery=recovery
        ))

    create_station_details(body, pots, materials, target, root)
    target["asset_id"] = "SOUP_STATION_01"
    target["source_reference"] = SOURCE_REFERENCE
    target["dimensions_status"] = "User-authored station and pot proxies"
    target["scope_note"] = "Visual operational asset; equipment clearances remain unvalidated"
    root["hierarchy_version"] = 2
    return root, pots


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def render_preview(root):
    PREVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    target_collection = require_collection(TARGET_COLLECTION)
    visible = set(target_collection.all_objects)
    for obj in bpy.context.scene.objects:
        if obj not in visible:
            obj.hide_render = True

    body = find_object("SOUP_RANGE_BODY")
    center = body.matrix_world.translation.copy()
    angle = body.matrix_world.to_euler().z
    dims = local_dimensions(body)

    bpy.ops.mesh.primitive_plane_add(size=6.0, location=(center.x, center.y, -0.055))
    ground = bpy.context.object
    ground.name = "REVIEW_SOUP_GROUND"
    ground.data.materials.append(
        ensure_principled_material("MAT_Review_Soup_Ground", (0.11, 0.105, 0.095), 0.0, 0.72)
    )

    camera_data = bpy.data.cameras.new("CAM_SoupStationPreview_DATA")
    camera = bpy.data.objects.new("CAM_SoupStationPreview", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = world_point(center, angle, dims.x * 1.15, -2.25, 1.45)
    camera_data.lens = 55.0
    look_at(camera, (center.x, center.y, 0.60))
    bpy.context.scene.camera = camera

    for name, local, energy, size in (
        ("LIGHT_Soup_Key", (-1.0, -1.4, 2.7), 900.0, 2.2),
        ("LIGHT_Soup_Fill", (1.2, 0.8, 1.8), 550.0, 1.8),
    ):
        data = bpy.data.lights.new(f"{name}_DATA", type="AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        light = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(light)
        light.location = world_point(center, angle, local[0], local[1], local[2])
        look_at(light, (center.x, center.y, 0.55))

    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.035, 0.035, 0.035, 1.0)
    background.inputs["Strength"].default_value = 0.30

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 900
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
    root, pots = build_station()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    render_preview(root)
    print("SOUP_STATION_COLLECTION", TARGET_COLLECTION)
    print("SOUP_STATION_ROOT", root.name)
    print("SOUP_STATION_POTS", [pot.name for pot in pots])
    print("SOUP_STATION_PREVIEW", PREVIEW_PATH)


if __name__ == "__main__":
    main()
