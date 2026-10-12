"""Refine SHOWCASE_D01_TRAY_01 into a stamped aluminum food pan.

The user-authored object transform and local bounding box are preserved. Only
the mesh, tray-specific material, and non-destructive edge bevel are replaced.
"""

from math import cos, pi, sin
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
BLEND_PATH = ROOT / "blend" / "guadalajara_base.blend"
OBJECT_NAME = "SHOWCASE_D01_TRAY_01"
MATERIAL_NAME = "MAT_Aluminum_Tray_Realistic"
BEVEL_NAME = "TRAY_ROLLED_EDGE_BEVEL"
AUTHORED_DIMENSIONS = Vector((0.60, 0.45, 0.05))


def rounded_rectangle(cx, cy, half_x, half_y, radius, z, segments=7):
    points = []
    corners = (
        (cx + half_x - radius, cy + half_y - radius, 0.0),
        (cx - half_x + radius, cy + half_y - radius, pi / 2.0),
        (cx - half_x + radius, cy - half_y + radius, pi),
        (cx + half_x - radius, cy - half_y + radius, 3.0 * pi / 2.0),
    )
    for corner_x, corner_y, start_angle in corners:
        for index in range(segments + 1):
            angle = start_angle + index * (pi / 2.0) / segments
            points.append((corner_x + radius * cos(angle), corner_y + radius * sin(angle), z))
    return points


def connect_rings(faces, first_start, second_start, count, reverse=False):
    for index in range(count):
        next_index = (index + 1) % count
        if reverse:
            faces.append((first_start + index, second_start + index, second_start + next_index, first_start + next_index))
        else:
            faces.append((first_start + index, first_start + next_index, second_start + next_index, second_start + index))


def aluminum_material():
    material = bpy.data.materials.get(MATERIAL_NAME) or bpy.data.materials.new(MATERIAL_NAME)
    material.use_nodes = True
    node = material.node_tree.nodes.get("Principled BSDF")
    node.inputs["Base Color"].default_value = (0.52, 0.55, 0.58, 1.0)
    node.inputs["Metallic"].default_value = 1.0
    node.inputs["Roughness"].default_value = 0.22
    if "Anisotropic IOR Level" in node.inputs:
        node.inputs["Anisotropic IOR Level"].default_value = 0.28
    elif "Anisotropic" in node.inputs:
        node.inputs["Anisotropic"].default_value = 0.28
    return material


def main():
    obj = bpy.data.objects.get(OBJECT_NAME)
    if obj is None or obj.type != "MESH":
        raise RuntimeError(f"Missing mesh object: {OBJECT_NAME}")

    original_location = obj.location.copy()
    original_rotation = obj.rotation_euler.copy()
    original_scale = obj.scale.copy()
    corners = [Vector(corner) for corner in obj.bound_box]
    minimum = Vector((min(point.x for point in corners), min(point.y for point in corners), min(point.z for point in corners)))
    maximum = Vector((max(point.x for point in corners), max(point.y for point in corners), max(point.z for point in corners)))
    center = (minimum + maximum) / 2.0
    size = maximum - minimum

    # Four corresponding rounded rings form a thin, closed stamped-metal shell:
    # outer lip, inner lip, inner floor edge, and underside floor edge.
    outer_half_x = size.x / 2.0
    outer_half_y = size.y / 2.0
    rim_width = min(size.x, size.y) * 0.045
    wall_inset = min(size.x, size.y) * 0.14
    shell_thickness = min(size.z * 0.16, 0.008)
    outer_radius = min(size.x, size.y) * 0.075
    inner_radius = max(outer_radius - rim_width * 0.45, rim_width)
    floor_radius = min(size.x, size.y) * 0.085

    z_top = maximum.z
    z_inner_rim = maximum.z - shell_thickness * 0.55
    z_inner_floor = minimum.z + shell_thickness
    z_outer_floor = minimum.z

    rings = (
        rounded_rectangle(center.x, center.y, outer_half_x, outer_half_y, outer_radius, z_top),
        rounded_rectangle(center.x, center.y, outer_half_x - rim_width, outer_half_y - rim_width, inner_radius, z_inner_rim),
        rounded_rectangle(center.x, center.y, outer_half_x - wall_inset, outer_half_y - wall_inset, floor_radius, z_inner_floor),
        rounded_rectangle(center.x, center.y, outer_half_x - wall_inset + shell_thickness, outer_half_y - wall_inset + shell_thickness, floor_radius, z_outer_floor),
    )
    ring_count = len(rings[0])
    vertices = [point for ring in rings for point in ring]
    faces = []
    outer_lip, inner_lip, inner_floor, outer_floor = (index * ring_count for index in range(4))

    connect_rings(faces, outer_lip, inner_lip, ring_count)
    connect_rings(faces, inner_lip, inner_floor, ring_count)
    connect_rings(faces, outer_floor, outer_lip, ring_count, reverse=True)
    faces.append(tuple(inner_floor + index for index in range(ring_count)))
    faces.append(tuple(outer_floor + index for index in reversed(range(ring_count))))

    mesh = bpy.data.meshes.new(f"{OBJECT_NAME}_STAMPED_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.update(calc_edges=True)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    obj.data = mesh

    obj.data.materials.clear()
    obj.data.materials.append(aluminum_material())
    old_bevel = obj.modifiers.get(BEVEL_NAME)
    if old_bevel:
        obj.modifiers.remove(old_bevel)
    bevel = obj.modifiers.new(BEVEL_NAME, "BEVEL")
    bevel.width = min(size.x, size.y) * 0.006
    bevel.segments = 3
    bevel.limit_method = "ANGLE"
    bevel.angle_limit = 0.35
    bpy.context.view_layer.update()

    # The bevel can expand the evaluated bounds slightly. Compensate on the
    # mesh (not the object transform) until the authored exterior dimensions
    # are restored to sub-millimeter tolerance.
    for _ in range(5):
        current_dimensions = obj.dimensions.copy()
        factors = Vector(tuple(
            AUTHORED_DIMENSIONS[index] / current_dimensions[index]
            for index in range(3)
        ))
        if max(abs(current_dimensions[index] - AUTHORED_DIMENSIONS[index]) for index in range(3)) < 1e-6:
            break
        for vertex in mesh.vertices:
            offset = vertex.co - center
            vertex.co = center + Vector((offset.x * factors.x, offset.y * factors.y, offset.z * factors.z))
        mesh.update()
        bpy.context.view_layer.update()

    # Explicitly restore the authored transform after the data replacement.
    obj.location = original_location
    obj.rotation_euler = original_rotation
    obj.scale = original_scale
    obj["phase"] = "Phase 1"
    obj["fixture_detail"] = "Stamped aluminum food pan"
    obj["reference_url"] = "https://www.rewonline.com/images/p/bro/bro-22164.lg.jpg"
    obj["geometry_status"] = "Detailed from visual reference; exterior dimensions and inclination preserved"

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.shade_smooth_by_angle()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))

    print("TRAY_OBJECT", obj.name)
    print("TRAY_DIMENSIONS_M", tuple(round(value, 6) for value in obj.dimensions))
    print("TRAY_ROTATION_DEG_Y", round(obj.rotation_euler.y * 180.0 / pi, 6))
    print("TRAY_MESH_COUNTS", len(mesh.vertices), len(mesh.polygons))


if __name__ == "__main__":
    main()
