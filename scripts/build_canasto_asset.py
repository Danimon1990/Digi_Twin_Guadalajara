"""Build the reusable woven-fiber canasto and optional paper liner.

The overall envelope is based on the user's approximate field dimensions:
0.45 m outside diameter and 0.08 m total height.  IMG_6072.heic and
IMG_6070.heic are visual references for the shallow profile, radial base,
concentric weave, and reinforced braided rim.  The unmeasured interior profile
remains provisional and is controlled by constants in this file.
"""

from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Vector
from pxr import Kind, Sdf, Usd, UsdGeom, UsdUtils


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_BLEND = ROOT / "blend" / "guadalajara_base.blend"
BLEND_PATH = ROOT / "blend" / "assets" / "serving" / "canasto.blend"
USD_PATH = ROOT / "usd" / "assets" / "serving" / "canasto" / "canasto.usdc"
PREVIEW_BASKET = ROOT / "outputs" / "previews" / "canasto_asset.png"
PREVIEW_LINER = ROOT / "outputs" / "previews" / "canasto_with_liner.png"

ASSET_COLLECTION = "ASSET_CANASTO"
ROOT_NAME = "CANASTO_01"
SCRIPT_ID = "build_canasto_asset_v1"
SOURCE_REFERENCE = "IMG_6072.heic; IMG_6070.heic"

# Approximate dimensions reported by the user, in meters.
OUTER_DIAMETER = 0.45
TOTAL_HEIGHT = 0.08

# Unmeasured profile/detail parameters.  These are intentionally isolated so
# they can be updated after field measurement without remodeling the asset.
RIM_CENTER_RADIUS = 0.218
RIM_STRAND_RADIUS = 0.0043
RIM_CENTER_HEIGHT = 0.073
WEAVE_OUTER_RADIUS = 0.208
WEAVE_BASE_HEIGHT = 0.006
WEAVE_WALL_RISE = 0.058
RADIAL_SPOKES = 24
CONCENTRIC_WEAVERS = 29
PAPER_SIZE = 0.34


def collection(name):
    result = bpy.data.collections.get(name)
    if result is None:
        result = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(result)
    return result


def move_to_collection(obj, target):
    if target not in obj.users_collection:
        target.objects.link(obj)
    for current in list(obj.users_collection):
        if current != target:
            current.objects.unlink(obj)


def reset_asset_scene():
    current = Path(bpy.data.filepath).resolve() if bpy.data.filepath else None
    if current == CANONICAL_BLEND.resolve():
        raise RuntimeError("Refusing to replace the canonical Guadalajara scene with an asset file")
    if current is not None and current != BLEND_PATH.resolve():
        raise RuntimeError(f"Open an empty scene or the canasto asset scene, not: {current}")
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for child in list(bpy.context.scene.collection.children):
        bpy.context.scene.collection.children.unlink(child)
    for item in list(bpy.data.collections):
        bpy.data.collections.remove(item)
    for item in list(bpy.data.materials):
        bpy.data.materials.remove(item)


def material(name, color, roughness=0.5, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color, 1.0)
    mat.roughness = roughness
    mat.metallic = metallic
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    return mat


def create_materials():
    return {
        "fiber_light": material("MAT_Canasto_Fiber_Light", (0.38, 0.20, 0.065), 0.50),
        "fiber_mid": material("MAT_Canasto_Fiber_Mid", (0.24, 0.10, 0.025), 0.54),
        "fiber_dark": material("MAT_Canasto_Fiber_Dark", (0.09, 0.03, 0.006), 0.58),
        "paper": material("MAT_Canasto_Food_Paper", (0.86, 0.80, 0.66), 0.82),
    }


def profile_height(radius):
    normalized = max(0.0, min(1.0, radius / WEAVE_OUTER_RADIUS))
    return WEAVE_BASE_HEIGHT + WEAVE_WALL_RISE * normalized ** 1.85


def annotate(obj, role, status="Approximate user dimensions; visual-reference detail"):
    obj["generated_by"] = SCRIPT_ID
    obj["asset_id"] = ROOT_NAME
    obj["asset_role"] = role
    obj["source_reference"] = SOURCE_REFERENCE
    obj["dimensions_status"] = status
    return obj


def create_root(target):
    root = bpy.data.objects.new(ROOT_NAME, None)
    target.objects.link(root)
    root.empty_display_type = "CIRCLE"
    root.empty_display_size = OUTER_DIAMETER * 0.55
    root["asset_id"] = ROOT_NAME
    root["source_reference"] = SOURCE_REFERENCE
    root["outer_diameter_m"] = OUTER_DIAMETER
    root["total_height_m"] = TOTAL_HEIGHT
    root["dimensions_status"] = "Approximate dimensions reported by user"
    root["interior_profile_status"] = "Provisional visual match; bottom diameter unmeasured"
    root["food_contact_note"] = "Food sits on the removable paper liner, not on the basket"
    return root


def parent(obj, root):
    obj.parent = root
    obj.matrix_parent_inverse = root.matrix_world.inverted()


def create_radial_splints(target, root, mats):
    vertices = []
    faces = []
    segments = 24
    inner_radius = 0.006
    outer_radius = WEAVE_OUTER_RADIUS
    width = 0.010

    for spoke in range(RADIAL_SPOKES):
        angle = 2.0 * math.pi * spoke / RADIAL_SPOKES
        tangent = Vector((-math.sin(angle), math.cos(angle), 0.0))
        base = len(vertices)
        for index in range(segments + 1):
            t = index / segments
            radius = inner_radius + (outer_radius - inner_radius) * t
            center = Vector((
                radius * math.cos(angle),
                radius * math.sin(angle),
                profile_height(radius) - 0.0010,
            ))
            half_width = width * (0.68 + 0.32 * t) * 0.5
            vertices.extend((center - tangent * half_width, center + tangent * half_width))
        for index in range(segments):
            a = base + index * 2
            faces.append((a, a + 2, a + 3, a + 1))

    mesh = bpy.data.meshes.new("CANASTO_RADIAL_SPLINTS_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("CANASTO_RADIAL_SPLINTS", mesh)
    target.objects.link(obj)
    obj.data.materials.append(mats["fiber_light"])
    solidify = obj.modifiers.new("FIBER_THICKNESS", "SOLIDIFY")
    solidify.thickness = 0.0014
    solidify.offset = 0.0
    bevel = obj.modifiers.new("FIBER_EDGE_SOFTNESS", "BEVEL")
    bevel.width = 0.00045
    bevel.segments = 2
    annotate(obj, "radial structural splints")
    parent(obj, root)
    return obj


def curve_to_mesh(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target="MESH")
    return bpy.context.object


def create_concentric_weave(target, root, mats):
    curve = bpy.data.curves.new("CANASTO_CONCENTRIC_WEAVE_CURVE", type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 1
    curve.bevel_depth = 0.00145
    curve.bevel_resolution = 2
    curve.resolution_u = 2
    points_per_ring = 144
    minimum_radius = 0.027

    for ring in range(CONCENTRIC_WEAVERS):
        t = ring / (CONCENTRIC_WEAVERS - 1)
        radius = minimum_radius + (WEAVE_OUTER_RADIUS - minimum_radius) * t
        spline = curve.splines.new("POLY")
        spline.points.add(points_per_ring - 1)
        phase = math.pi if ring % 2 else 0.0
        for index, point in enumerate(spline.points):
            angle = 2.0 * math.pi * index / points_per_ring
            over_under = 0.00115 * math.sin(RADIAL_SPOKES * angle + phase)
            small_irregularity = 0.00055 * math.sin(5.0 * angle + ring * 0.73)
            local_radius = radius + small_irregularity
            point.co = (
                local_radius * math.cos(angle),
                local_radius * math.sin(angle),
                profile_height(radius) + 0.0012 + over_under,
                1.0,
            )
        spline.use_cyclic_u = True

    obj = bpy.data.objects.new("CANASTO_CONCENTRIC_WEAVE", curve)
    target.objects.link(obj)
    obj.data.materials.append(mats["fiber_mid"])
    obj = curve_to_mesh(obj)
    annotate(obj, "concentric woven cane")
    parent(obj, root)
    return obj


def create_center_binding(target, root, mats):
    curve = bpy.data.curves.new("CANASTO_CENTER_BINDING_CURVE", type="CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = 0.0019
    curve.bevel_resolution = 2
    spline = curve.splines.new("POLY")
    count = 96
    spline.points.add(count - 1)
    radius = 0.022
    for index, point in enumerate(spline.points):
        angle = 2.0 * math.pi * index / count
        point.co = (radius * math.cos(angle), radius * math.sin(angle), 0.0092, 1.0)
    spline.use_cyclic_u = True
    obj = bpy.data.objects.new("CANASTO_CENTER_BINDING", curve)
    target.objects.link(obj)
    obj.data.materials.append(mats["fiber_dark"])
    obj = curve_to_mesh(obj)
    annotate(obj, "center binding")
    parent(obj, root)
    return obj


def create_braided_rim(target, root, mats):
    objects = []
    points_per_strand = 256
    braid_lobes = 18
    palette = (mats["fiber_light"], mats["fiber_mid"], mats["fiber_dark"])

    for strand_index in range(3):
        curve = bpy.data.curves.new(f"CANASTO_RIM_STRAND_{strand_index + 1:02d}_CURVE", type="CURVE")
        curve.dimensions = "3D"
        curve.bevel_depth = RIM_STRAND_RADIUS
        curve.bevel_resolution = 3
        spline = curve.splines.new("POLY")
        spline.points.add(points_per_strand - 1)
        phase = strand_index * 2.0 * math.pi / 3.0
        for index, point in enumerate(spline.points):
            angle = 2.0 * math.pi * index / points_per_strand
            braid_angle = braid_lobes * angle + phase
            radius = RIM_CENTER_RADIUS + 0.0016 * math.cos(braid_angle)
            z = RIM_CENTER_HEIGHT + 0.0026 * math.sin(braid_angle)
            point.co = (radius * math.cos(angle), radius * math.sin(angle), z, 1.0)
        spline.use_cyclic_u = True
        obj = bpy.data.objects.new(f"CANASTO_RIM_STRAND_{strand_index + 1:02d}", curve)
        target.objects.link(obj)
        obj.data.materials.append(palette[strand_index])
        obj = curve_to_mesh(obj)
        annotate(obj, "thick braided rim")
        parent(obj, root)
        objects.append(obj)

    # A hidden structural binding below the braid closes the wall-to-rim seam.
    curve = bpy.data.curves.new("CANASTO_RIM_BINDING_CURVE", type="CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = 0.0028
    curve.bevel_resolution = 2
    spline = curve.splines.new("POLY")
    spline.points.add(191)
    for index, point in enumerate(spline.points):
        angle = 2.0 * math.pi * index / 192
        point.co = (0.212 * math.cos(angle), 0.212 * math.sin(angle), 0.067, 1.0)
    spline.use_cyclic_u = True
    binding = bpy.data.objects.new("CANASTO_RIM_BINDING", curve)
    target.objects.link(binding)
    binding.data.materials.append(mats["fiber_dark"])
    binding = curve_to_mesh(binding)
    annotate(binding, "rim structural binding")
    parent(binding, root)
    objects.append(binding)
    return objects


def create_paper_liner(target, root, mats):
    resolution = 24
    half = PAPER_SIZE * 0.5
    vertices = []
    faces = []
    for row in range(resolution + 1):
        v = -half + PAPER_SIZE * row / resolution
        for column in range(resolution + 1):
            u = -half + PAPER_SIZE * column / resolution
            original_radius = math.hypot(u, v)
            if original_radius > 0.190:
                compressed_radius = 0.190 + 0.020 * (1.0 - math.exp(-(original_radius - 0.190) / 0.028))
                factor = compressed_radius / original_radius
                x = u * factor
                y = v * factor
                fold = (original_radius - 0.190) * 0.65
            else:
                x, y, fold = u, v, 0.0
            radius = math.hypot(x, y)
            crinkle = 0.0018 * math.sin(31.0 * u + 7.0 * v) * math.sin(23.0 * v - 3.0 * u)
            z = profile_height(min(radius, WEAVE_OUTER_RADIUS)) + 0.0055 + fold + crinkle
            vertices.append((x, y, z))
    stride = resolution + 1
    for row in range(resolution):
        for column in range(resolution):
            a = row * stride + column
            faces.append((a, a + 1, a + stride + 1, a + stride))

    mesh = bpy.data.meshes.new("CANASTO_PAPER_LINER_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("CANASTO_PAPER_LINER", mesh)
    target.objects.link(obj)
    obj.data.materials.append(mats["paper"])
    subdivision = obj.modifiers.new("PAPER_SOFT_FOLDS", "SUBSURF")
    subdivision.subdivision_type = "CATMULL_CLARK"
    subdivision.levels = 1
    subdivision.render_levels = 1
    solidify = obj.modifiers.new("PAPER_THICKNESS", "SOLIDIFY")
    solidify.thickness = 0.00045
    solidify.offset = 0.0
    bevel = obj.modifiers.new("PAPER_EDGE_SOFTNESS", "BEVEL")
    bevel.width = 0.00035
    bevel.segments = 2
    annotate(obj, "removable food paper liner", "Proportional fit to approximate basket envelope")
    obj["optional_accessory"] = True
    obj["food_contact_surface"] = True
    obj["basket_food_contact"] = False
    parent(obj, root)
    return obj


def apply_modifiers(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    for modifier in list(obj.modifiers):
        bpy.ops.object.modifier_apply(modifier=modifier.name)


def asset_bounds(objects):
    points = [obj.matrix_world @ Vector(corner) for obj in objects if obj.type == "MESH" for corner in obj.bound_box]
    minimum = Vector(tuple(min(point[index] for point in points) for index in range(3)))
    maximum = Vector(tuple(max(point[index] for point in points) for index in range(3)))
    return minimum, maximum


def build_asset():
    reset_asset_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    target = collection(ASSET_COLLECTION)
    root = create_root(target)
    mats = create_materials()
    basket_objects = [
        create_radial_splints(target, root, mats),
        create_concentric_weave(target, root, mats),
        create_center_binding(target, root, mats),
        *create_braided_rim(target, root, mats),
    ]
    liner = create_paper_liner(target, root, mats)
    for obj in basket_objects + [liner]:
        apply_modifiers(obj)
    target["asset_id"] = ROOT_NAME
    target["source_reference"] = SOURCE_REFERENCE
    target["outer_diameter_m"] = OUTER_DIAMETER
    target["total_height_m"] = TOTAL_HEIGHT
    target["dimensions_status"] = "Approximate dimensions reported by user"
    if hasattr(target, "asset_mark"):
        target.asset_mark()
    return root, basket_objects, liner


def save_blend():
    BLEND_PATH.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))


def export_usd():
    target = bpy.data.collections[ASSET_COLLECTION]
    objects = [obj for obj in target.all_objects if obj.type in {"MESH", "EMPTY"}]
    USD_PATH.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.hide_set(False)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = bpy.data.objects[ROOT_NAME]
    bpy.ops.wm.usd_export(
        filepath=str(USD_PATH),
        selected_objects_only=True,
        export_animation=False,
        export_materials=True,
        generate_preview_surface=True,
        export_textures_mode="NEW",
        overwrite_textures=True,
        relative_paths=True,
        meters_per_unit=1.0,
        convert_scene_units="METERS",
        export_cameras=False,
        export_lights=False,
        convert_world_material=False,
        root_prim_path="/Canasto",
        export_custom_properties=True,
    )
    stage = Usd.Stage.Open(str(USD_PATH))
    root = stage.GetPrimAtPath("/Canasto")
    if not root:
        raise RuntimeError("Exported stage is missing /Canasto")
    stage.SetDefaultPrim(root)
    Usd.ModelAPI(root).SetKind(Kind.Tokens.component)
    Usd.ModelAPI(root).SetAssetName("Canasto")
    Usd.ModelAPI(root).SetAssetIdentifier(Sdf.AssetPath(USD_PATH.name))
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    root.SetCustomDataByKey("sourceBlend", str(BLEND_PATH.relative_to(ROOT)))
    root.SetCustomDataByKey("sourceReference", SOURCE_REFERENCE)
    root.SetCustomDataByKey("outerDiameterMeters", OUTER_DIAMETER)
    root.SetCustomDataByKey("totalHeightMeters", TOTAL_HEIGHT)
    root.SetCustomDataByKey("dimensionsStatus", "Approximate dimensions reported by user")
    root.SetCustomDataByKey("interiorProfileStatus", "Provisional visual match; bottom diameter unmeasured")
    stage.GetRootLayer().Save()


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def render_preview(output_path, liner, show_liner):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    liner.hide_render = not show_liner

    review = collection("REVIEW_CANASTO")
    bpy.ops.mesh.primitive_plane_add(size=1.8, location=(0.0, 0.0, -0.003))
    ground = bpy.context.object
    ground.name = "REVIEW_CANASTO_GROUND"
    move_to_collection(ground, review)
    ground.data.materials.append(material("MAT_Review_Canasto_Ground", (0.075, 0.065, 0.050), 0.72))

    camera_data = bpy.data.cameras.new("CAM_CanastoPreview_DATA")
    camera = bpy.data.objects.new("CAM_CanastoPreview", camera_data)
    review.objects.link(camera)
    camera.location = (0.48, -0.54, 0.35)
    camera_data.lens = 58.0
    look_at(camera, (0.0, 0.0, 0.045))
    scene.camera = camera

    for name, location, energy, size in (
        ("LIGHT_Canasto_Key", (0.35, -0.30, 0.70), 20.0, 0.65),
        ("LIGHT_Canasto_Fill", (-0.42, -0.05, 0.42), 9.0, 0.55),
        ("LIGHT_Canasto_Rim", (0.12, 0.48, 0.58), 13.0, 0.48),
    ):
        data = bpy.data.lights.new(f"{name}_DATA", type="AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        light = bpy.data.objects.new(name, data)
        review.objects.link(light)
        light.location = location
        look_at(light, (0.0, 0.0, 0.04))

    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.025, 0.022, 0.018, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.03

    scene.render.engine = "BLENDER_EEVEE"
    scene.view_settings.exposure = -0.7
    scene.render.resolution_x = 900
    scene.render.resolution_y = 760
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(output_path)
    scene.render.film_transparent = False
    bpy.ops.render.render(write_still=True)

    for obj in list(review.objects):
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if isinstance(data, bpy.types.Camera):
            bpy.data.cameras.remove(data)
        elif isinstance(data, bpy.types.Light):
            bpy.data.lights.remove(data)
    bpy.data.collections.remove(review)
    liner.hide_render = False


def validate_asset(basket_objects):
    minimum, maximum = asset_bounds(basket_objects)
    dimensions = maximum - minimum
    if abs(dimensions.x - OUTER_DIAMETER) > 0.004 or abs(dimensions.y - OUTER_DIAMETER) > 0.004:
        raise RuntimeError(f"Basket diameter outside tolerance: {dimensions}")
    if abs(dimensions.z - TOTAL_HEIGHT) > 0.006:
        raise RuntimeError(f"Basket height outside tolerance: {dimensions}")

    stage = Usd.Stage.Open(str(USD_PATH), load=Usd.Stage.LoadAll)
    if stage is None:
        raise RuntimeError(f"Cannot open {USD_PATH}")
    if stage.GetDefaultPrim().GetPath() != Sdf.Path("/Canasto"):
        raise RuntimeError("Canasto USD defaultPrim must be /Canasto")
    if Usd.ModelAPI(stage.GetDefaultPrim()).GetKind() != Kind.Tokens.component:
        raise RuntimeError("Canasto USD must declare kind=component")
    if UsdGeom.GetStageMetersPerUnit(stage) != 1.0:
        raise RuntimeError("Canasto USD must use meters")
    if UsdGeom.GetStageUpAxis(stage) != UsdGeom.Tokens.z:
        raise RuntimeError("Canasto USD must be Z-up")
    _layers, _assets, unresolved = UsdUtils.ComputeAllDependencies(str(USD_PATH))
    if unresolved:
        raise RuntimeError(f"Unresolved USD dependencies: {unresolved}")
    return dimensions, sum(1 for _ in stage.Traverse())


def main():
    root, basket_objects, liner = build_asset()
    save_blend()
    export_usd()
    dimensions, prim_count = validate_asset(basket_objects)
    render_preview(PREVIEW_BASKET, liner, False)
    render_preview(PREVIEW_LINER, liner, True)
    # Review objects are local-only and removed; save the clean reusable asset.
    save_blend()
    print("CANASTO_BLEND", BLEND_PATH)
    print("CANASTO_USD", USD_PATH)
    print("CANASTO_ROOT", root.name)
    print("CANASTO_DIMENSIONS", tuple(round(value, 4) for value in dimensions))
    print("CANASTO_USD_PRIMS", prim_count)
    print("CANASTO_PREVIEW", PREVIEW_BASKET)
    print("CANASTO_LINER_PREVIEW", PREVIEW_LINER)


if __name__ == "__main__":
    main()
