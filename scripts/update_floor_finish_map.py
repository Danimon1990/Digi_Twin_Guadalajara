"""Apply the confirmed general and rear-service floor finish map."""

from pathlib import Path
import math

import bpy


ROOT = Path(__file__).resolve().parents[1]
BLEND_PATH = ROOT / "blend" / "guadalajara_base.blend"
TEXTURE_DIR = ROOT / "textures" / "generated"

GENERAL_MATERIAL = "MAT_Floor_Comedor_HeavyDutyAggregateTile"
GENERAL_UV = "UV_FLOOR_COMEDOR_TILE"
GENERAL_TILE_SIZE_M = 0.30
DESPACHO_MATERIAL = "MAT_Floor_Despacho_WineTile"
WINE_MATERIAL = "MAT_Floor_CleaningStorage_WineTile"
WINE_UV = "UV_FLOOR_WINE_TILE"
WINE_TILE_SIZE_M = 0.25
WINE_JOINT_WIDTH_M = 0.003

GENERAL_FLOORS = (
    "FLOOR_PROPERTY_COMMON",
)
DESPACHO_THICK_JOINT_FLOORS = (
    "FLOOR_DESPACHO_LOWER",
    "FLOOR_CLIENT_ARRIVAL_LOWER",
    "STEP_DESPACHO_CUBE002",
)
WINE_GUIDES = (
    "FLOOR_NEVERAS",
    "FLOOR_CUARTO_DE_OLLAS",
    "FLOOR_ALMACEN",
    "FLOOR_BASURAS",
)
LOWER_FLOOR_CUTTERS = (
    "CUTTER_FLOOR_DESPACHO_LOWER",
    "CUTTER_FLOOR_CLIENT_ARRIVAL_LOWER",
)


def hash_value(x, y, seed):
    value = math.sin(x * 12.9898 + y * 78.233 + seed * 41.17) * 43758.5453
    return value - math.floor(value)


def wine_color(x, y, width, height):
    joint_pixels = max(2, round(width * WINE_JOINT_WIDTH_M / WINE_TILE_SIZE_M))
    edge = min(x, width - 1 - x, y, height - 1 - y)
    if edge < joint_pixels:
        value = 0.32 + 0.025 * edge / max(joint_pixels - 1, 1)
        return (value, value * 0.98, value * 0.94, 1.0)
    variation = 0.018 * (hash_value(x // 12, y // 12, 3) - 0.5)
    edge_soft = min(1.0, (edge - joint_pixels) / 14.0)
    return (
        0.19 + variation + 0.020 * edge_soft,
        0.014 + variation * 0.16,
        0.022 + variation * 0.12,
        1.0,
    )


def wine_height(x, y, width, height):
    joint_pixels = max(2, round(width * WINE_JOINT_WIDTH_M / WINE_TILE_SIZE_M))
    edge = min(x, width - 1 - x, y, height - 1 - y)
    value = max(0.0, min(1.0, (edge - joint_pixels + 2) / 5.0))
    return (value, value, value, 1.0)


def save_generated_image(path, width, height, pixel_function, non_color=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        image = bpy.data.images.new(path.stem, width=width, height=height, alpha=True)
        pixels = [0.0] * (width * height * 4)
        for y in range(height):
            for x in range(width):
                index = (y * width + x) * 4
                pixels[index:index + 4] = pixel_function(x, y, width, height)
        image.pixels.foreach_set(pixels)
        image.filepath_raw = str(path)
        image.file_format = "PNG"
        image.save()
        bpy.data.images.remove(image)
    image = bpy.data.images.load(str(path), check_existing=True)
    if non_color:
        image.colorspace_settings.name = "Non-Color"
    return image


def build_wine_material():
    color_image = save_generated_image(
        TEXTURE_DIR / "cleaning_storage_wine_tile_color.png", 512, 512, wine_color
    )
    height_image = save_generated_image(
        TEXTURE_DIR / "cleaning_storage_wine_tile_height.png", 512, 512, wine_height, non_color=True
    )
    material = bpy.data.materials.get(WINE_MATERIAL) or bpy.data.materials.new(WINE_MATERIAL)
    material.use_nodes = True
    material.diffuse_color = (0.19, 0.014, 0.022, 1.0)
    material.roughness = 0.40

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (620, 0)
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.location = (350, 0)
    shader.inputs["Roughness"].default_value = 0.40
    shader.inputs["Metallic"].default_value = 0.0
    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = WINE_UV
    uv.location = (-620, 0)
    color = nodes.new("ShaderNodeTexImage")
    color.image = color_image
    color.extension = "REPEAT"
    color.location = (-380, 90)
    height = nodes.new("ShaderNodeTexImage")
    height.image = height_image
    height.extension = "REPEAT"
    height.location = (-380, -190)
    bump = nodes.new("ShaderNodeBump")
    bump.location = (90, -180)
    bump.inputs["Strength"].default_value = 0.16
    bump.inputs["Distance"].default_value = 0.002
    links.new(uv.outputs["UV"], color.inputs["Vector"])
    links.new(uv.outputs["UV"], height.inputs["Vector"])
    links.new(color.outputs["Color"], shader.inputs["Base Color"])
    links.new(height.outputs["Color"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])

    material["finish"] = "Dark wine-red service tile with thin cement-gray joints"
    material["tile_width_m"] = WINE_TILE_SIZE_M
    material["tile_height_m"] = WINE_TILE_SIZE_M
    material["joint_width_m"] = WINE_JOINT_WIDTH_M
    material["dimensions_status"] = "25 cm tile confirmed previously; 3 mm joint is provisional from 'very thin' description"
    return material


def assign_single_material(obj, material):
    obj.data.materials.clear()
    obj.data.materials.append(material)
    for polygon in obj.data.polygons:
        polygon.material_index = 0


def ensure_world_floor_uv(obj, uv_name, tile_size):
    uv_layer = obj.data.uv_layers.get(uv_name) or obj.data.uv_layers.new(name=uv_name)
    for polygon in obj.data.polygons:
        for loop_index in polygon.loop_indices:
            vertex = obj.data.vertices[obj.data.loops[loop_index].vertex_index]
            world = obj.matrix_world @ vertex.co
            uv_layer.data[loop_index].uv = (world.x / tile_size, world.y / tile_size)


def ensure_wine_uv(obj):
    ensure_world_floor_uv(obj, WINE_UV, WINE_TILE_SIZE_M)


def rename_cuarto_de_ollas():
    guide = bpy.data.objects.get("FLOOR_CUARTO_DE_OLLAS") or bpy.data.objects.get("FLOOR_AREA_UNNAMED_01")
    if guide is None:
        raise RuntimeError("Missing FLOOR_AREA_UNNAMED_01 / FLOOR_CUARTO_DE_OLLAS")
    guide.name = "FLOOR_CUARTO_DE_OLLAS"
    guide.data.name = "FLOOR_CUARTO_DE_OLLAS_GUIDE_MESH"
    guide["zone_name"] = "Cuarto de Ollas"

    label = bpy.data.objects.get("LABEL_CUARTO_DE_OLLAS") or bpy.data.objects.get("LABEL_AREA_UNNAMED_01")
    if label is not None:
        label.name = "LABEL_CUARTO_DE_OLLAS"
        label.data.name = "LABEL_CUARTO_DE_OLLAS_TEXT"
        label.data.body = "Cuarto de Ollas"
    return guide


def finish_from_guide(guide, material):
    object_name = f"FLOOR_FINISH_{guide.name.removeprefix('FLOOR_')}_WINE"
    world_polygons = []
    for polygon in guide.data.polygons:
        if polygon.normal.z <= 0.7:
            continue
        world_polygons.append([
            guide.matrix_world @ guide.data.vertices[index].co
            for index in polygon.vertices
        ])
    if not world_polygons:
        raise RuntimeError(f"No upward floor polygon in {guide.name}")

    vertices = []
    faces = []
    for polygon in world_polygons:
        start = len(vertices)
        vertices.extend((point.x, point.y, 0.003) for point in polygon)
        faces.append(tuple(range(start, start + len(polygon))))

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        mesh = bpy.data.meshes.new(f"{object_name}_MESH")
        obj = bpy.data.objects.new(object_name, mesh)
        collection = bpy.data.collections.get("Floors")
        if collection is None:
            raise RuntimeError("Missing Floors collection")
        collection.objects.link(obj)
    else:
        mesh = obj.data
        mesh.clear_geometry()
    mesh.from_pydata(vertices, [], faces)
    mesh.update(calc_edges=True)
    assign_single_material(obj, material)
    ensure_wine_uv(obj)
    obj["floor_role"] = f"Wine tile finish for {guide.get('zone_name', guide.name)}"
    obj["finish_plane_offset_m"] = 0.003
    return obj


def main():
    general = bpy.data.materials.get(GENERAL_MATERIAL)
    if general is None:
        raise RuntimeError(f"Missing general floor material: {GENERAL_MATERIAL}")
    despacho = bpy.data.materials.get(DESPACHO_MATERIAL)
    if despacho is None:
        raise RuntimeError(f"Missing despacho floor material: {DESPACHO_MATERIAL}")
    wine = build_wine_material()
    rename_cuarto_de_ollas()

    for name in GENERAL_FLOORS:
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != "MESH":
            raise RuntimeError(f"Missing general physical floor: {name}")
        assign_single_material(obj, general)
        ensure_world_floor_uv(obj, GENERAL_UV, GENERAL_TILE_SIZE_M)

    for name in DESPACHO_THICK_JOINT_FLOORS:
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != "MESH":
            raise RuntimeError(f"Missing despacho physical floor: {name}")
        assign_single_material(obj, despacho)

    finishes = []
    for name in WINE_GUIDES:
        guide = bpy.data.objects.get(name)
        if guide is None or guide.type != "MESH":
            raise RuntimeError(f"Missing service-zone guide: {name}")
        guide["floor_finish"] = WINE_MATERIAL
        finishes.append(finish_from_guide(guide, wine).name)

    guide_collection = bpy.data.collections.get("Zone_Guides_NotForExport")
    if guide_collection is not None:
        guide_collection.hide_render = True
        guide_collection.hide_viewport = True

    # Keep the editable Boolean operands, but do not let their solid viewport
    # display cover the lowered finish surfaces revealed by the cutouts.
    for name in LOWER_FLOOR_CUTTERS:
        cutter = bpy.data.objects.get(name)
        if cutter is None:
            raise RuntimeError(f"Missing lower-floor cutter: {name}")
        cutter.display_type = "WIRE"
        cutter.hide_render = True
        cutter.hide_set(True)
        cutter["purpose"] = "Hidden editable Boolean cutter for lowered floor opening"

    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    print("GENERAL_FLOOR_MATERIAL", general.name)
    print("DESPACHO_THICK_JOINT_MATERIAL", despacho.name)
    print("WINE_FLOOR_MATERIAL", wine.name)
    print("WINE_FINISH_OBJECTS", finishes)
    print("RENAMED_ZONE", "FLOOR_CUARTO_DE_OLLAS")


if __name__ == "__main__":
    main()
