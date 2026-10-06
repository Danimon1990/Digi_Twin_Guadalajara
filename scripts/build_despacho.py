"""Build the provisional Phase 1 despacho display fixtures in Blender.

Run with Blender, not the system Python::

    Blender --background blend/guadalajara_base.blend --python scripts/build_despacho.py

The model is intentionally limited to the static counter-top display geometry
visible in the supplied photograph. Room dimensions and the meaning/endpoints
of the reported 1.2 m dimension remain unresolved in the measurement register.
"""

from math import atan2, hypot
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


ROOT = Path(__file__).resolve().parents[1]
BLEND_PATH = ROOT / "blend" / "guadalajara_base.blend"

COLLECTION_NAME = "Fixtures_Despacho"
SOURCE_IMAGE = "117316404_2634697473458632_5819890937000716496_n.jpg"

# Existing provisional counter segment used only as the placement reference.
COUNTER_NAME = "Cube.006"
SMALL_COUNTER_NAME = "Cube.046"

# Provisional dimensions derived from the existing counter and the image.
# They are not survey measurements.
MODULE_WIDTH = 1.20
MODULE_GAP = 0.04
SMALL_MODULE_WIDTH = 0.66
CASE_DEPTH = 0.56
COUNTER_TOP_Z = 0.80
DIAGONAL_LOW_Z = 1.05
DIAGONAL_HIGH_Z = 1.52


def material(name, base_color, metallic=0.0, roughness=0.45, alpha=1.0, transmission=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    node = mat.node_tree.nodes.get("Principled BSDF")
    if node:
        node.inputs["Base Color"].default_value = base_color
        node.inputs["Metallic"].default_value = metallic
        node.inputs["Roughness"].default_value = roughness
        if "Alpha" in node.inputs:
            node.inputs["Alpha"].default_value = alpha
        if "Transmission Weight" in node.inputs:
            node.inputs["Transmission Weight"].default_value = transmission
    mat.diffuse_color = (*base_color[:3], alpha)
    if alpha < 1.0:
        mat.surface_render_method = "DITHERED"
        mat.use_transparency_overlap = False
    return mat


MAT_GLASS = material(
    "MAT_Glass_Showcase",
    (0.70, 0.95, 1.00, 1.0),
    roughness=0.08,
    alpha=0.26,
    transmission=0.85,
)
MAT_METAL = material(
    "MAT_Metal_Showcase",
    (0.16, 0.18, 0.20, 1.0),
    metallic=0.85,
    roughness=0.24,
)
MAT_ALUMINUM = material(
    "MAT_Aluminum_Tray",
    (0.62, 0.65, 0.68, 1.0),
    metallic=0.72,
    roughness=0.28,
)


def ensure_collection():
    old = bpy.data.collections.get(COLLECTION_NAME)
    if old:
        for obj in list(old.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for parent in bpy.data.collections:
            if old.name in parent.children:
                parent.children.unlink(old)
        if old.name in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.unlink(old)
        bpy.data.collections.remove(old)

    collection = bpy.data.collections.new(COLLECTION_NAME)
    architecture = bpy.data.collections.get("Architecture")
    if architecture:
        architecture.children.link(collection)
    else:
        bpy.context.scene.collection.children.link(collection)
    return collection


def cube_mesh(name, center, dimensions, transform, mat, collection, role, module_index):
    hx, hy, hz = (value / 2.0 for value in dimensions)
    local_vertices = [
        (-hx, -hy, -hz), (-hx, -hy, hz), (-hx, hy, -hz), (-hx, hy, hz),
        (hx, -hy, -hz), (hx, -hy, hz), (hx, hy, -hz), (hx, hy, hz),
    ]
    faces = [
        (0, 4, 6, 2), (1, 3, 7, 5), (0, 1, 5, 4),
        (2, 6, 7, 3), (0, 2, 3, 1), (4, 5, 7, 6),
    ]
    local_matrix = Matrix.Translation(Vector(center))
    vertices = [transform @ local_matrix @ Vector((*vertex, 1.0)) for vertex in local_vertices]
    mesh = bpy.data.meshes.new(f"{name}_MESH")
    mesh.from_pydata([vertex.xyz for vertex in vertices], [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.data.materials.append(mat)
    obj["evidence_status"] = "Provisional"
    obj["source_image"] = SOURCE_IMAGE
    obj["showcase_role"] = role
    obj["module_index"] = module_index
    obj["phase"] = "Phase 1"
    return obj


def rotated_box(name, center, dimensions, angle_x, base_transform, *args):
    transform = (
        base_transform
        @ Matrix.Translation(Vector(center))
        @ Matrix.Rotation(angle_x, 4, "X")
    )
    return cube_mesh(name, (0.0, 0.0, 0.0), dimensions, transform, *args)


def add_module(module_index, x_center, base_transform, collection, module_width=MODULE_WIDTH, tray_count=3):
    prefix = f"SHOWCASE_D{module_index:02d}"
    glass_thickness = 0.012
    metal_size = 0.025

    # Customer-side short vertical glass.
    front_y = CASE_DEPTH / 2.0
    vertical_mid_z = (COUNTER_TOP_Z + DIAGONAL_LOW_Z) / 2.0
    cube_mesh(
        f"{prefix}_GLASS_FRONT",
        (x_center, front_y, vertical_mid_z),
        (module_width, glass_thickness, DIAGONAL_LOW_Z - COUNTER_TOP_Z),
        base_transform,
        MAT_GLASS,
        collection,
        "front_vertical_glass",
        module_index,
    )

    # Large diagonal viewing pane rising toward the worker side.
    back_y = -CASE_DEPTH / 2.0
    delta_y = back_y - front_y
    delta_z = DIAGONAL_HIGH_Z - DIAGONAL_LOW_Z
    diagonal_length = hypot(delta_y, delta_z)
    diagonal_angle = atan2(-delta_y, delta_z)
    rotated_box(
        f"{prefix}_GLASS_DIAGONAL",
        (x_center, (front_y + back_y) / 2.0, (DIAGONAL_LOW_Z + DIAGONAL_HIGH_Z) / 2.0),
        (module_width, glass_thickness, diagonal_length),
        diagonal_angle,
        base_transform,
        MAT_GLASS,
        collection,
        "diagonal_viewing_glass",
        module_index,
    )

    # Small horizontal glass cap and smaller internal shelf.
    cube_mesh(
        f"{prefix}_GLASS_TOP",
        (x_center, back_y + 0.11, DIAGONAL_HIGH_Z),
        (module_width, 0.22, glass_thickness),
        base_transform,
        MAT_GLASS,
        collection,
        "top_horizontal_glass",
        module_index,
    )
    cube_mesh(
        f"{prefix}_GLASS_SHELF",
        (x_center, 0.01, 1.17),
        (module_width - 0.12, 0.32, glass_thickness),
        base_transform,
        MAT_GLASS,
        collection,
        "secondary_display_shelf",
        module_index,
    )

    # Metal support rails at both ends of each identical module.
    for side_index, side_x in enumerate((x_center - module_width / 2.0, x_center + module_width / 2.0), 1):
        cube_mesh(
            f"{prefix}_FRAME_FRONT_{side_index:02d}",
            (side_x, front_y, vertical_mid_z),
            (metal_size, metal_size, DIAGONAL_LOW_Z - COUNTER_TOP_Z),
            base_transform,
            MAT_METAL,
            collection,
            "front_support",
            module_index,
        )
        rotated_box(
            f"{prefix}_FRAME_DIAGONAL_{side_index:02d}",
            (side_x, (front_y + back_y) / 2.0, (DIAGONAL_LOW_Z + DIAGONAL_HIGH_Z) / 2.0),
            (metal_size, metal_size, diagonal_length),
            diagonal_angle,
            base_transform,
            MAT_METAL,
            collection,
            "diagonal_support",
            module_index,
        )
        cube_mesh(
            f"{prefix}_FRAME_BACK_{side_index:02d}",
            (side_x, back_y, (COUNTER_TOP_Z + DIAGONAL_HIGH_Z) / 2.0),
            (metal_size, metal_size, DIAGONAL_HIGH_Z - COUNTER_TOP_Z),
            base_transform,
            MAT_METAL,
            collection,
            "back_support",
            module_index,
        )

    cube_mesh(
        f"{prefix}_FRAME_TOP",
        (x_center, back_y, DIAGONAL_HIGH_Z),
        (module_width, metal_size, metal_size),
        base_transform,
        MAT_METAL,
        collection,
        "top_crossbar",
        module_index,
    )

    # Optional shallow aluminum tray placeholders; food is not modeled.
    if tray_count == 0:
        return
    tray_gap = 0.025
    tray_width = (module_width - (tray_count + 1) * tray_gap) / tray_count
    start_x = x_center - module_width / 2.0 + tray_gap + tray_width / 2.0
    for tray_index in range(tray_count):
        tray_x = start_x + tray_index * (tray_width + tray_gap)
        tray = cube_mesh(
            f"{prefix}_TRAY_{tray_index + 1:02d}",
            (tray_x, 0.00, COUNTER_TOP_Z + 0.025),
            (tray_width, CASE_DEPTH - 0.10, 0.05),
            base_transform,
            MAT_ALUMINUM,
            collection,
            "aluminum_tray_placeholder",
            module_index,
        )
        tray["contents"] = "Not modeled in Phase 1"


def main():
    counter = bpy.data.objects.get(COUNTER_NAME)
    if counter is None:
        raise RuntimeError(f"Missing provisional placement reference: {COUNTER_NAME}")
    small_counter = bpy.data.objects.get(SMALL_COUNTER_NAME)
    if small_counter is None:
        raise RuntimeError(f"Missing provisional placement reference: {SMALL_COUNTER_NAME}")

    collection = ensure_collection()
    counter_angle = counter.rotation_euler.z
    base_transform = Matrix.Translation(counter.location) @ Matrix.Rotation(counter_angle, 4, "Z")

    total_width = 2 * MODULE_WIDTH + MODULE_GAP
    add_module(1, -total_width / 2.0 + MODULE_WIDTH / 2.0, base_transform, collection)
    add_module(2, total_width / 2.0 - MODULE_WIDTH / 2.0, base_transform, collection)

    small_counter_transform = (
        Matrix.Translation(small_counter.location)
        @ Matrix.Rotation(small_counter.rotation_euler.z, 4, "Z")
    )
    add_module(
        3,
        0.0,
        small_counter_transform,
        collection,
        module_width=SMALL_MODULE_WIDTH,
        tray_count=0,
    )

    for obj in collection.objects:
        obj["placement_reference"] = SMALL_COUNTER_NAME if obj.get("module_index") == 3 else COUNTER_NAME

    collection["evidence_status"] = "Provisional"
    collection["source_image"] = SOURCE_IMAGE
    collection["placement_references"] = f"{COUNTER_NAME}; {SMALL_COUNTER_NAME}"
    collection["notes"] = (
        "Two identical 1.20 m-wide placeholder modules fitted to the existing 2.50 m counter. "
        "The 1.20 m module width is a reversible working interpretation, not a confirmed endpoint measurement. "
        "One 0.66 m-wide glass module is fitted to Cube.046; its tray count remains unresolved."
    )

    bpy.context.scene["despacho_fixture_status"] = "Provisional; exact room and showcase endpoints pending"
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))

    trays = [obj for obj in collection.objects if obj.get("showcase_role") == "aluminum_tray_placeholder"]
    print("DESPACHO_FIXTURE_OBJECTS", len(collection.objects))
    print("DESPACHO_TRAY_COUNT", len(trays))
    print("DESPACHO_MODULE_WIDTH_M", MODULE_WIDTH)
    print("DESPACHO_SMALL_MODULE_WIDTH_M", SMALL_MODULE_WIDTH)
    print("DESPACHO_PLACEMENT_REFERENCES", COUNTER_NAME, SMALL_COUNTER_NAME)


if __name__ == "__main__":
    main()
