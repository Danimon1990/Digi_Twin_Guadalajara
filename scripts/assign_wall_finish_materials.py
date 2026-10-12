"""Assign spatial wall finishes and USD-friendly per-face material slots.

The script preserves object transforms and existing modifiers.  It subdivides
only walls adjacent to the Despacho or Comedores guide polygons, then assigns
materials by polygon.  The comedor brick-tile wainscot terminates at 1.00 m.
"""

from math import sin
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
BLEND_PATH = ROOT / "blend" / "guadalajara_base.blend"
TEXTURE_DIR = ROOT / "textures" / "generated"

BASE_PAINT_NAME = "MAT_Wall_Paint_White"
WHITE_TILE_NAME = "MAT_Wall_WhiteTile"
COMEDOR_PAINT_NAME = "MAT_Wall_Comedor_WarmPaint"
COMEDOR_BRICK_NAME = "MAT_Wall_Comedor_BrickTile"

WHITE_TILE_UV = "UV_WALL_WHITE_TILE"
BRICK_TILE_UV = "UV_WALL_BRICK_TILE"
WAINSCOT_HEIGHT_M = 1.0


def save_generated_image(path, width, height, pixel_function, non_color=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        image = bpy.data.images.new(path.stem, width=width, height=height, alpha=True)
        pixels = [0.0] * (width * height * 4)
        for y in range(height):
            for x in range(width):
                color = pixel_function(x, y, width, height)
                index = (y * width + x) * 4
                pixels[index:index + 4] = color
        image.pixels.foreach_set(pixels)
        image.filepath_raw = str(path)
        image.file_format = "PNG"
        image.save()
        bpy.data.images.remove(image)
    image = bpy.data.images.load(str(path), check_existing=True)
    if non_color:
        image.colorspace_settings.name = "Non-Color"
    return image


def white_tile_color(x, y, width, height):
    joint = 7
    edge = min(x, width - 1 - x, y, height - 1 - y)
    if edge < joint:
        shade = 0.35 + 0.025 * (edge / max(joint - 1, 1))
        return (shade, shade, shade * 0.98, 1.0)
    soft_edge = min(1.0, (edge - joint) / 16.0)
    value = 0.82 + 0.10 * soft_edge
    return (value, value * 1.005, value * 0.99, 1.0)


def white_tile_height(x, y, width, height):
    joint = 7
    edge = min(x, width - 1 - x, y, height - 1 - y)
    value = max(0.0, min(1.0, (edge - joint + 2) / 5.0))
    return (value, value, value, 1.0)


def brick_cell(x, y, width, height):
    brick_width = width // 4
    brick_height = height // 8
    row = y // brick_height
    shifted_x = (x + (brick_width // 2 if row % 2 else 0)) % width
    column = shifted_x // brick_width
    local_x = shifted_x % brick_width
    local_y = y % brick_height
    return row, column, local_x, local_y, brick_width, brick_height


def comedor_brick_color(x, y, width, height):
    row, column, local_x, local_y, brick_width, brick_height = brick_cell(x, y, width, height)
    joint = 6
    if local_x < joint or local_y < joint:
        return (0.39, 0.36, 0.31, 1.0)
    variation = 0.035 * sin((row * 11 + column * 17) * 1.73)
    edge = min(local_x - joint, brick_width - local_x, local_y - joint, brick_height - local_y)
    soft = min(1.0, max(0.0, edge / 9.0))
    return (
        0.28 + variation + 0.035 * soft,
        0.075 + variation * 0.35 + 0.018 * soft,
        0.028 + variation * 0.18,
        1.0,
    )


def comedor_brick_height(x, y, width, height):
    _, _, local_x, local_y, brick_width, brick_height = brick_cell(x, y, width, height)
    joint = 6
    edge = min(local_x, brick_width - 1 - local_x, local_y, brick_height - 1 - local_y)
    value = max(0.0, min(1.0, (edge - joint + 2) / 5.0))
    return (value, value, value, 1.0)


def principled_material(name, color, roughness):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = (*color, 1.0)
    material.roughness = roughness
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (300, 0)
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.location = (20, 0)
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = 0.0
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    return material


def textured_material(name, color_image, height_image, uv_name, roughness, bump_distance):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (620, 0)
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.location = (340, 0)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = 0.0

    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = uv_name
    uv.location = (-620, 0)

    color = nodes.new("ShaderNodeTexImage")
    color.image = color_image
    color.interpolation = "Linear"
    color.extension = "REPEAT"
    color.location = (-380, 80)

    height = nodes.new("ShaderNodeTexImage")
    height.image = height_image
    height.interpolation = "Linear"
    height.extension = "REPEAT"
    height.location = (-380, -190)

    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.28
    bump.inputs["Distance"].default_value = bump_distance
    bump.location = (80, -170)

    links.new(uv.outputs["UV"], color.inputs["Vector"])
    links.new(uv.outputs["UV"], height.inputs["Vector"])
    links.new(color.outputs["Color"], shader.inputs["Base Color"])
    links.new(height.outputs["Color"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    return material


def build_materials():
    white_color = save_generated_image(
        TEXTURE_DIR / "white_wall_tile_color.png", 256, 256, white_tile_color
    )
    white_height = save_generated_image(
        TEXTURE_DIR / "white_wall_tile_height.png", 256, 256, white_tile_height, non_color=True
    )
    brick_color = save_generated_image(
        TEXTURE_DIR / "comedor_brick_tile_color.png", 512, 512, comedor_brick_color
    )
    brick_height = save_generated_image(
        TEXTURE_DIR / "comedor_brick_tile_height.png", 512, 512, comedor_brick_height, non_color=True
    )

    base = principled_material(BASE_PAINT_NAME, (0.76, 0.76, 0.72), 0.58)
    warm = principled_material(COMEDOR_PAINT_NAME, (0.56, 0.34, 0.115), 0.62)
    white_tile = textured_material(WHITE_TILE_NAME, white_color, white_height, WHITE_TILE_UV, 0.24, 0.004)
    brick = textured_material(COMEDOR_BRICK_NAME, brick_color, brick_height, BRICK_TILE_UV, 0.48, 0.006)

    base["finish"] = "Neutral white painted wall; default non-tiled finish"
    white_tile["finish"] = "Glossy white ceramic wall tile with vertical and horizontal grout"
    white_tile["tile_width_m"] = 0.20
    white_tile["tile_height_m"] = 0.10
    white_tile["dimensions_status"] = "Provisional visual assumption; verify tile and joint dimensions"
    warm["finish"] = "Warm yellow-orange comedor wall paint"
    warm["color_status"] = "Estimated from IMG_0497.PNG; verify with color sample"
    brick["finish"] = "Decorative reddish-brown brick-design wall tile"
    brick["nominal_brick_width_m"] = 0.15
    brick["nominal_brick_height_m"] = 0.06
    brick["dimensions_status"] = "Pattern scale estimated from IMG_0497.PNG; wainscot height confirmed at 1.00 m"
    return base, white_tile, warm, brick


def guide_regions(object_name):
    obj = bpy.data.objects.get(object_name)
    if obj is None or obj.type != "MESH":
        raise RuntimeError(f"Missing guide mesh: {object_name}")
    regions = []
    for polygon in obj.data.polygons:
        if polygon.normal.z < 0.5:
            continue
        regions.append([
            (obj.matrix_world @ obj.data.vertices[index].co).xy.copy()
            for index in polygon.vertices
        ])
    if not regions:
        raise RuntimeError(f"Guide has no upward polygons: {object_name}")
    return regions


def point_in_polygon(point, polygon):
    inside = False
    x, y = point
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        if ((y1 > y) != (y2 > y)):
            crossing = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing:
                inside = not inside
        previous = current
    return inside


def inside_regions(point, regions):
    return any(point_in_polygon(point, polygon) for polygon in regions)


def region_bounds(regions):
    points = [point for polygon in regions for point in polygon]
    return (
        min(point.x for point in points), max(point.x for point in points),
        min(point.y for point in points), max(point.y for point in points),
    )


def wall_intersects_bounds(obj, bounds, margin=0.25):
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    minimum_x = min(point.x for point in corners)
    maximum_x = max(point.x for point in corners)
    minimum_y = min(point.y for point in corners)
    maximum_y = max(point.y for point in corners)
    return not (
        maximum_x < bounds[0] - margin or minimum_x > bounds[1] + margin
        or maximum_y < bounds[2] - margin or minimum_y > bounds[3] + margin
    )


def bisect_for_regions(obj, regions):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    inverse = obj.matrix_world.inverted()
    normal_matrix = obj.matrix_world.to_3x3().transposed()

    # Confirmed 1.00 m decorative wainscot boundary.
    point_local = inverse @ Vector((0.0, 0.0, WAINSCOT_HEIGHT_M))
    normal_local = (normal_matrix @ Vector((0.0, 0.0, 1.0))).normalized()
    bmesh.ops.bisect_plane(
        bm,
        geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
        plane_co=point_local,
        plane_no=normal_local,
        clear_inner=False,
        clear_outer=False,
    )

    # Vertical planes through every room-guide edge isolate only those pieces
    # actually adjacent to the room, including partial spans of long walls.
    for polygon in regions:
        for index, start in enumerate(polygon):
            end = polygon[(index + 1) % len(polygon)]
            edge = end - start
            if edge.length < 1e-8:
                continue
            world_point = Vector((start.x, start.y, 0.0))
            world_normal = Vector((edge.y, -edge.x, 0.0)).normalized()
            local_point = inverse @ world_point
            local_normal = (normal_matrix @ world_normal).normalized()
            bmesh.ops.bisect_plane(
                bm,
                geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
                plane_co=local_point,
                plane_no=local_normal,
                clear_inner=False,
                clear_outer=False,
            )

    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update(calc_edges=True)


def ensure_wall_uvs(obj):
    for name, width, height in (
        (WHITE_TILE_UV, 0.20, 0.10),
        (BRICK_TILE_UV, 0.60, 0.48),
    ):
        uv_layer = obj.data.uv_layers.get(name) or obj.data.uv_layers.new(name=name)
        normal_matrix = obj.matrix_world.to_3x3().inverted().transposed()
        for polygon in obj.data.polygons:
            normal = (normal_matrix @ polygon.normal).normalized()
            if abs(normal.z) < 0.65:
                tangent = Vector((-normal.y, normal.x, 0.0)).normalized()
                for loop_index in polygon.loop_indices:
                    vertex = obj.data.vertices[obj.data.loops[loop_index].vertex_index]
                    world = obj.matrix_world @ vertex.co
                    uv_layer.data[loop_index].uv = (world.dot(tangent) / width, world.z / height)
            else:
                for loop_index in polygon.loop_indices:
                    vertex = obj.data.vertices[obj.data.loops[loop_index].vertex_index]
                    world = obj.matrix_world @ vertex.co
                    uv_layer.data[loop_index].uv = (world.x / width, world.y / height)


def assign_wall_faces(obj, materials, despacho_regions, comedor_regions):
    base, white_tile, warm, brick = materials
    obj.data.materials.clear()
    for material in materials:
        obj.data.materials.append(material)

    normal_matrix = obj.matrix_world.to_3x3().inverted().transposed()
    counts = {material.name: 0 for material in materials}
    for polygon in obj.data.polygons:
        polygon.material_index = 0
        normal = (normal_matrix @ polygon.normal).normalized()
        if abs(normal.z) >= 0.65:
            counts[base.name] += 1
            continue
        center = obj.matrix_world @ polygon.center
        sample = center + normal * 0.12
        if inside_regions(sample.xy, comedor_regions):
            polygon.material_index = 3 if center.z <= WAINSCOT_HEIGHT_M + 0.002 else 2
        elif inside_regions(sample.xy, despacho_regions):
            polygon.material_index = 1
        counts[materials[polygon.material_index].name] += 1
    return counts


def main():
    materials = build_materials()
    despacho_regions = guide_regions("FLOOR_DESPACHO")
    comedor_regions = guide_regions("FLOOR_COMEDORES")
    all_regions = despacho_regions + comedor_regions
    bounds = region_bounds(all_regions)

    totals = {material.name: 0 for material in materials}
    affected = []
    for obj in sorted(bpy.data.objects, key=lambda item: item.name):
        if obj.type != "MESH" or not obj.name.startswith("WALL_"):
            continue
        if wall_intersects_bounds(obj, bounds) and obj.get("wall_finish_topology_version") != 1:
            bisect_for_regions(obj, all_regions)
            obj["wall_finish_topology_version"] = 1
        ensure_wall_uvs(obj)
        counts = assign_wall_faces(obj, materials, despacho_regions, comedor_regions)
        if counts[WHITE_TILE_NAME] or counts[COMEDOR_PAINT_NAME] or counts[COMEDOR_BRICK_NAME]:
            affected.append((obj.name, counts))
        for name, count in counts.items():
            totals[name] += count

    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    print("WALL_FINISH_AFFECTED", affected)
    print("WALL_FINISH_TOTAL_POLYGONS", totals)
    print("COMEDOR_WAINSCOT_HEIGHT_M", WAINSCOT_HEIGHT_M)


if __name__ == "__main__":
    main()
