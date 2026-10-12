"""Build a reusable comedor table with two integrated bench seats.

The proportions are visual estimates from IMG_5989.heic and remain provisional
until field dimensions are supplied. The generated Blender collection is marked
as an asset, and the matching OpenUSD file is published as a component in meters
with Z-up orientation.
"""

from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Vector
from pxr import Kind, Sdf, Usd, UsdGeom


ROOT = Path(__file__).resolve().parents[1]
BLEND_PATH = ROOT / "blend" / "assets" / "furniture" / "comedor_bench_table.blend"
USD_PATH = ROOT / "usd" / "assets" / "furniture" / "comedor_bench_table" / "comedor_bench_table.usdc"
PREVIEW_PATH = ROOT / "outputs" / "previews" / "comedor_bench_table_asset.png"

ASSET_COLLECTION = "ASSET_COMEDOR_BENCH_TABLE"
REVIEW_COLLECTION = "REVIEW_COMEDOR_BENCH_TABLE"

# Provisional visual estimates in meters. Adjust these constants when measured.
TABLE_LENGTH = 1.40
TABLE_WIDTH = 0.76
TABLE_HEIGHT = 0.75
TABLE_TOP_THICKNESS = 0.055
SEAT_LENGTH = 1.55
SEAT_WIDTH = 0.32
SEAT_HEIGHT = 0.45
SEAT_THICKNESS = 0.045
SEAT_CENTER_Y = 0.64
BACK_CENTER_Y = 0.84
BACK_SLAT_LENGTH = 1.48
BACK_SLAT_HEIGHT = 0.115
BACK_SLAT_THICKNESS = 0.035
BACK_SLAT_Z = (0.61, 0.76, 0.91)
TUBE_RADIUS = 0.020


def collection(name: str):
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


def material(name, color, metallic=0.0, roughness=0.4):
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    result.diffuse_color = (*color, 1.0)
    result.metallic = metallic
    result.roughness = roughness
    shader = result.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = roughness
    return result


def activate(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def beveled_box(name, dimensions, location, mat, bevel=0.012):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    activate(obj)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0.0:
        modifier = obj.modifiers.new("EDGE_RADIUS", "BEVEL")
        modifier.width = bevel
        modifier.segments = 3
        modifier.limit_method = "ANGLE"
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    obj.data.materials.append(mat)
    move_to_collection(obj, collection(ASSET_COLLECTION))
    return obj


def cylinder_between(name, start, end, radius, mat, vertices=20):
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
    obj.data.materials.append(mat)
    move_to_collection(obj, collection(ASSET_COLLECTION))
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def tube_assembly(name, points, radius, mat):
    parts = []
    for index, (start, end) in enumerate(zip(points, points[1:]), start=1):
        parts.append(cylinder_between(f"{name}_SEG_{index:02d}", start, end, radius, mat))
    for index, point in enumerate(points[1:-1], start=1):
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=20,
            ring_count=10,
            radius=radius,
            location=point,
        )
        joint = bpy.context.object
        joint.name = f"{name}_BEND_{index:02d}"
        joint.data.materials.append(mat)
        move_to_collection(joint, collection(ASSET_COLLECTION))
        parts.append(joint)
    bpy.ops.object.select_all(action="DESELECT")
    for part in parts:
        part.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    result = bpy.context.object
    result.name = name
    return result


def create_asset_geometry():
    metal = material("MAT_Stainless_Satin", (0.42, 0.46, 0.48), metallic=0.92, roughness=0.26)
    wood = material("MAT_Wood_Warm_Medium", (0.33, 0.13, 0.055), metallic=0.0, roughness=0.38)
    terrazzo = material("MAT_Tabletop_Light_Terrazzo", (0.70, 0.61, 0.46), metallic=0.0, roughness=0.42)
    dark_metal = material("MAT_Backrest_Bracket_Dark", (0.035, 0.03, 0.027), metallic=0.65, roughness=0.30)

    objects = []
    objects.append(beveled_box(
        "TABLE_TOP",
        (TABLE_LENGTH, TABLE_WIDTH, TABLE_TOP_THICKNESS),
        (0.0, 0.0, TABLE_HEIGHT - TABLE_TOP_THICKNESS * 0.5),
        terrazzo,
        bevel=0.025,
    ))

    for side_name, sign in (("LEFT", -1.0), ("RIGHT", 1.0)):
        objects.append(beveled_box(
            f"BENCH_SEAT_{side_name}",
            (SEAT_LENGTH, SEAT_WIDTH, SEAT_THICKNESS),
            (0.0, sign * SEAT_CENTER_Y, SEAT_HEIGHT - SEAT_THICKNESS * 0.5),
            wood,
            bevel=0.014,
        ))
        for slat_index, z in enumerate(BACK_SLAT_Z, start=1):
            objects.append(beveled_box(
                f"BACKREST_{side_name}_SLAT_{slat_index:02d}",
                (BACK_SLAT_LENGTH, BACK_SLAT_THICKNESS, BACK_SLAT_HEIGHT),
                (0.0, sign * BACK_CENTER_Y, z),
                wood,
                bevel=0.010,
            ))

        # Rear posts lean slightly away from the table, matching the reference.
        for end_name, x in (("A", -0.68), ("B", 0.68)):
            objects.append(tube_assembly(
                f"FRAME_BACK_{side_name}_{end_name}",
                [
                    (x, sign * 0.77, 0.40),
                    (x, sign * 0.80, 0.52),
                    (x, sign * 0.87, 1.00),
                ],
                TUBE_RADIUS,
                metal,
            ))
            objects.append(beveled_box(
                f"BACKREST_{side_name}_BRACKET_{end_name}",
                (0.038, 0.018, 0.43),
                (x, sign * 0.845, 0.76),
                dark_metal,
                bevel=0.004,
            ))
            for bolt_index, z in enumerate(BACK_SLAT_Z, start=1):
                objects.append(cylinder_between(
                    f"BACKREST_{side_name}_{end_name}_BOLT_{bolt_index:02d}",
                    (x, sign * 0.82, z),
                    (x, sign * 0.87, z),
                    0.010,
                    metal,
                    vertices=16,
                ))

        inner_y = sign * (SEAT_CENTER_Y - SEAT_WIDTH * 0.40)
        outer_y = sign * (SEAT_CENTER_Y + SEAT_WIDTH * 0.40)
        for rail_name, y in (("INNER", inner_y), ("OUTER", outer_y)):
            objects.append(cylinder_between(
                f"FRAME_SEAT_{side_name}_{rail_name}",
                (-0.69, y, SEAT_HEIGHT - SEAT_THICKNESS - 0.012),
                (0.69, y, SEAT_HEIGHT - SEAT_THICKNESS - 0.012),
                TUBE_RADIUS,
                metal,
            ))
        for end_name, x in (("A", -0.62), ("B", 0.62)):
            objects.append(tube_assembly(
                f"FRAME_BENCH_LEG_{side_name}_{end_name}",
                [
                    (x, outer_y, 0.035),
                    (x, outer_y, SEAT_HEIGHT - 0.065),
                    (x, inner_y, SEAT_HEIGHT - 0.065),
                    (x, inner_y, 0.10),
                ],
                TUBE_RADIUS,
                metal,
            ))

    # Two transverse lower rails and table supports make the unit one structure.
    for end_name, x in (("A", -0.54), ("B", 0.54)):
        objects.append(cylinder_between(
            f"FRAME_LOWER_CROSS_{end_name}",
            (x, -0.76, 0.075),
            (x, 0.76, 0.075),
            TUBE_RADIUS,
            metal,
        ))
        for side_name, sign in (("LEFT", -1.0), ("RIGHT", 1.0)):
            objects.append(cylinder_between(
                f"FRAME_TABLE_LEG_{end_name}_{side_name}",
                (x, sign * 0.28, 0.075),
                (x, sign * 0.28, TABLE_HEIGHT - TABLE_TOP_THICKNESS - 0.008),
                TUBE_RADIUS,
                metal,
            ))
    for side_name, sign in (("LEFT", -1.0), ("RIGHT", 1.0)):
        objects.append(cylinder_between(
            f"FRAME_TABLE_TOP_RAIL_{side_name}",
            (-0.62, sign * 0.28, TABLE_HEIGHT - TABLE_TOP_THICKNESS - 0.008),
            (0.62, sign * 0.28, TABLE_HEIGHT - TABLE_TOP_THICKNESS - 0.008),
            TUBE_RADIUS,
            metal,
        ))

    for obj in objects:
        obj["asset_id"] = "COMEDOR_BENCH_TABLE"
        obj["dimensions_status"] = "Provisional visual estimate from IMG_5989.heic"
        obj["source_reference"] = "IMG_5989.heic"
    return objects


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def create_preview_scene():
    review = collection(REVIEW_COLLECTION)
    ground_mat = material("MAT_Review_Ground", (0.16, 0.16, 0.16), metallic=0.0, roughness=0.70)
    ground = beveled_box("REVIEW_GROUND", (4.0, 4.0, 0.025), (0.0, 0.0, -0.025), ground_mat, bevel=0.0)
    move_to_collection(ground, review)
    ground["not_for_export"] = True

    camera_data = bpy.data.cameras.new("CAM_AssetPreview_DATA")
    camera = bpy.data.objects.new("CAM_AssetPreview", camera_data)
    review.objects.link(camera)
    camera.location = (2.65, -3.10, 2.05)
    camera_data.lens = 52.0
    look_at(camera, (0.0, 0.0, 0.50))
    bpy.context.scene.camera = camera

    for name, location, energy, size in (
        ("LIGHT_Asset_Key", (2.4, -2.4, 4.0), 850.0, 3.0),
        ("LIGHT_Asset_Fill", (-2.0, 1.3, 2.8), 500.0, 2.5),
    ):
        data = bpy.data.lights.new(f"{name}_DATA", type="AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        light = bpy.data.objects.new(name, data)
        review.objects.link(light)
        light.location = location
        look_at(light, (0.0, 0.0, 0.45))

    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.045, 0.045, 0.045, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 960
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(PREVIEW_PATH)
    scene.render.film_transparent = False


def publish_usd(asset_objects):
    USD_PATH.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in asset_objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = asset_objects[0]
    bpy.ops.wm.usd_export(
        filepath=str(USD_PATH),
        selected_objects_only=True,
        export_animation=False,
        export_materials=True,
        generate_preview_surface=True,
        export_textures_mode="KEEP",
        relative_paths=True,
        meters_per_unit=1.0,
        convert_scene_units="METERS",
        export_cameras=False,
        export_lights=False,
        convert_world_material=False,
        root_prim_path="/ComedorBenchTable",
        export_custom_properties=True,
        triangulate_meshes=True,
        quad_method="BEAUTY",
        ngon_method="BEAUTY",
    )

    stage = Usd.Stage.Open(str(USD_PATH))
    root = stage.GetPrimAtPath("/ComedorBenchTable")
    if not root:
        raise RuntimeError("USD export is missing /ComedorBenchTable")
    stage.SetDefaultPrim(root)
    Usd.ModelAPI(root).SetKind(Kind.Tokens.component)
    Usd.ModelAPI(root).SetAssetName("ComedorBenchTable")
    Usd.ModelAPI(root).SetAssetIdentifier(Sdf.AssetPath(USD_PATH.name))
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    root.SetCustomDataByKey("dimensionsStatus", "Provisional visual estimate")
    root.SetCustomDataByKey("sourceReference", "IMG_5989.heic")
    root.SetCustomDataByKey("tableHeightM", TABLE_HEIGHT)
    root.SetCustomDataByKey("seatHeightM", SEAT_HEIGHT)
    stage.GetRootLayer().Save()


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    asset_collection = collection(ASSET_COLLECTION)
    asset_collection["asset_id"] = "COMEDOR_BENCH_TABLE"
    asset_collection["dimensions_status"] = "Provisional visual estimate from IMG_5989.heic"
    if hasattr(asset_collection, "asset_mark"):
        asset_collection.asset_mark()
        if asset_collection.asset_data:
            asset_collection.asset_data.description = (
                "Integrated comedor table with two bench seats and slatted backrests"
            )

    asset_objects = create_asset_geometry()
    create_preview_scene()

    BLEND_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    publish_usd(asset_objects)
    bpy.ops.render.render(write_still=True)

    print("ASSET_BLEND", BLEND_PATH)
    print("ASSET_USD", USD_PATH)
    print("ASSET_PREVIEW", PREVIEW_PATH)
    print("ASSET_OBJECT_COUNT", len(asset_objects))


if __name__ == "__main__":
    main()
