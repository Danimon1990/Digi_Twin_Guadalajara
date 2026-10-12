"""Create and assign the comedor heavy-duty aggregate tile finish."""

from pathlib import Path
import math

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
BLEND_PATH = ROOT / "blend" / "guadalajara_base.blend"
TEXTURE_DIR = ROOT / "textures" / "generated"

MATERIAL_NAME = "MAT_Floor_Comedor_HeavyDutyAggregateTile"
UV_NAME = "UV_FLOOR_COMEDOR_TILE"
GUIDE_NAME = "FLOOR_COMEDORES"
MAIN_FINISH_NAME = "FLOOR_COMEDOR_MAIN_FINISH"
RAISED_FLOOR_NAME = "FLOOR_COMEDOR_RAISED"
STEP_NAME = "STEP_COMEDOR_CUBE005"
FLOORS_COLLECTION = "Floors"

# Scale is provisional until a field measurement is available.
TILE_SIZE_M = 0.30


def hash_value(x, y, seed):
    value = math.sin(x * 12.9898 + y * 78.233 + seed * 37.719) * 43758.5453
    return value - math.floor(value)


def aggregate_color(x, y, width, height):
    joint = 5
    edge = min(x, width - 1 - x, y, height - 1 - y)
    if edge < joint:
        shade = 0.31 + 0.035 * edge / max(joint - 1, 1)
        return (shade, shade * 0.96, shade * 0.88, 1.0)

    # A warm cement body with dense, irregular heavy-duty aggregate flecks.
    base_noise = hash_value(x // 3, y // 3, 2)
    base = 0.34 + 0.055 * base_noise
    color = [base * 1.04, base * 0.91, base * 0.70]

    # Stable cellular flecks at multiple sizes. The palette follows the photo:
    # cream/white, ochre yellow, burnt orange, and dark brown.
    palettes = (
        (0.78, 0.73, 0.60),
        (0.88, 0.82, 0.62),
        (0.73, 0.49, 0.16),
        (0.58, 0.22, 0.075),
        (0.24, 0.13, 0.075),
    )
    for scale, threshold, seed in ((9, 0.77, 5), (5, 0.84, 11), (3, 0.90, 19)):
        cell_x = x // scale
        cell_y = y // scale
        chance = hash_value(cell_x, cell_y, seed)
        if chance > threshold:
            center_x = (cell_x + hash_value(cell_x, cell_y, seed + 1)) * scale
            center_y = (cell_y + hash_value(cell_x, cell_y, seed + 2)) * scale
            radius = scale * (0.28 + 0.38 * hash_value(cell_x, cell_y, seed + 3))
            if (x - center_x) ** 2 + (y - center_y) ** 2 <= radius ** 2:
                palette_index = int(hash_value(cell_x, cell_y, seed + 4) * len(palettes)) % len(palettes)
                color = list(palettes[palette_index])
    return (*color, 1.0)


def aggregate_height(x, y, width, height):
    joint = 5
    edge = min(x, width - 1 - x, y, height - 1 - y)
    if edge < joint:
        value = 0.18
    else:
        value = 0.56 + 0.10 * hash_value(x // 4, y // 4, 29)
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


def build_material():
    color_image = save_generated_image(
        TEXTURE_DIR / "comedor_heavy_duty_tile_color.png",
        512,
        512,
        aggregate_color,
    )
    height_image = save_generated_image(
        TEXTURE_DIR / "comedor_heavy_duty_tile_height.png",
        512,
        512,
        aggregate_height,
        non_color=True,
    )

    material = bpy.data.materials.get(MATERIAL_NAME) or bpy.data.materials.new(MATERIAL_NAME)
    material.use_nodes = True
    material.diffuse_color = (0.46, 0.34, 0.20, 1.0)
    material.roughness = 0.54

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (620, 0)
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.location = (350, 0)
    shader.inputs["Roughness"].default_value = 0.54
    shader.inputs["Metallic"].default_value = 0.0

    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = UV_NAME
    uv.location = (-620, 0)
    color = nodes.new("ShaderNodeTexImage")
    color.image = color_image
    color.extension = "REPEAT"
    color.interpolation = "Linear"
    color.location = (-380, 90)
    height = nodes.new("ShaderNodeTexImage")
    height.image = height_image
    height.extension = "REPEAT"
    height.interpolation = "Linear"
    height.location = (-380, -190)
    bump = nodes.new("ShaderNodeBump")
    bump.location = (90, -180)
    bump.inputs["Strength"].default_value = 0.22
    bump.inputs["Distance"].default_value = 0.003

    links.new(uv.outputs["UV"], color.inputs["Vector"])
    links.new(uv.outputs["UV"], height.inputs["Vector"])
    links.new(color.outputs["Color"], shader.inputs["Base Color"])
    links.new(height.outputs["Color"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])

    material["finish"] = "Heavy-duty warm aggregate tile with brown, orange, cream, white, and yellow flecks"
    material["reference_image"] = "IMG_0497.PNG"
    material["tile_nominal_size_m"] = TILE_SIZE_M
    material["dimensions_status"] = "Pattern scale is provisional; verify tile and grout dimensions in field"
    return material


def ensure_uv(obj):
    uv_layer = obj.data.uv_layers.get(UV_NAME) or obj.data.uv_layers.new(name=UV_NAME)
    for polygon in obj.data.polygons:
        for loop_index in polygon.loop_indices:
            vertex_index = obj.data.loops[loop_index].vertex_index
            world = obj.matrix_world @ obj.data.vertices[vertex_index].co
            uv_layer.data[loop_index].uv = (world.x / TILE_SIZE_M, world.y / TILE_SIZE_M)


def ensure_material_slot(obj, material):
    for index, slot in enumerate(obj.material_slots):
        if slot.material == material:
            return index
    obj.data.materials.append(material)
    return len(obj.material_slots) - 1


def assign_top_faces(obj, material):
    material_index = ensure_material_slot(obj, material)
    normal_matrix = obj.matrix_world.to_3x3().inverted().transposed()
    assigned = 0
    for polygon in obj.data.polygons:
        world_normal = (normal_matrix @ polygon.normal).normalized()
        if world_normal.z > 0.7:
            polygon.material_index = material_index
            assigned += 1
    ensure_uv(obj)
    obj["finish_assignment"] = "Comedor aggregate tile on upward-facing polygons"
    return assigned


def build_main_level_finish(material):
    guide = bpy.data.objects.get(GUIDE_NAME)
    if guide is None or guide.type != "MESH":
        raise RuntimeError(f"Missing comedor guide: {GUIDE_NAME}")
    top_polygons = [polygon for polygon in guide.data.polygons if polygon.normal.z > 0.7]
    if len(top_polygons) < 2:
        raise RuntimeError("Expected two comedor guide regions")
    main_polygon = max(top_polygons, key=lambda polygon: (guide.matrix_world @ polygon.center).y)
    world_vertices = [guide.matrix_world @ guide.data.vertices[index].co for index in main_polygon.vertices]
    vertices = [(point.x, point.y, 0.002) for point in world_vertices]

    obj = bpy.data.objects.get(MAIN_FINISH_NAME)
    if obj is None:
        mesh = bpy.data.meshes.new(f"{MAIN_FINISH_NAME}_MESH")
        obj = bpy.data.objects.new(MAIN_FINISH_NAME, mesh)
        collection = bpy.data.collections.get(FLOORS_COLLECTION)
        if collection is None:
            raise RuntimeError(f"Missing collection: {FLOORS_COLLECTION}")
        collection.objects.link(obj)
    else:
        mesh = obj.data
        mesh.clear_geometry()
    mesh.from_pydata(vertices, [], [tuple(range(len(vertices)))])
    mesh.update(calc_edges=True)
    obj.data.materials.clear()
    obj.data.materials.append(material)
    ensure_uv(obj)
    obj["phase"] = "Phase 1"
    obj["floor_role"] = "Main-level comedor finish surface"
    obj["thickness_status"] = "Finish plane only; physical slab remains FLOOR_PROPERTY_COMMON"
    return obj


def main():
    material = build_material()
    raised = bpy.data.objects.get(RAISED_FLOOR_NAME)
    step = bpy.data.objects.get(STEP_NAME)
    if raised is None or raised.type != "MESH":
        raise RuntimeError(f"Missing mesh: {RAISED_FLOOR_NAME}")
    if step is None or step.type != "MESH":
        raise RuntimeError(f"Missing mesh: {STEP_NAME}")

    raised_faces = assign_top_faces(raised, material)
    step_faces = assign_top_faces(step, material)
    main_finish = build_main_level_finish(material)

    guide = bpy.data.objects.get(GUIDE_NAME)
    guide.hide_set(True)
    guide.hide_render = True

    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    print("COMEDOR_FLOOR_MATERIAL", material.name)
    print("COMEDOR_MAIN_FINISH", main_finish.name)
    print("RAISED_TOP_FACES", raised_faces)
    print("STEP_TOP_FACES", step_faces)
    print("PROVISIONAL_TILE_SIZE_M", TILE_SIZE_M)


if __name__ == "__main__":
    main()
