"""Add the dispatch extractor opening and the first reusable wall finish.

The wall opening remains editable: the user-authored cylinder is retained as a
hidden Boolean cutter.  The existing shared white-wall material is upgraded to
a procedural, meter-scaled ceramic tile finish.
"""

from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
BLEND_PATH = ROOT / "blend" / "guadalajara_base.blend"

CUTTER_SOURCE_NAME = "Cylinder.022"
CUTTER_NAME = "CUTTER_WALL_015_EXTRACTOR_OPENING"
WALL_NAME = "WALL_015"
BOOLEAN_NAME = "OPENING_EXTRACTOR_CIRCULAR"
HELPER_COLLECTION_NAME = "Construction_Helpers"
MATERIAL_NAME = "MAT_Wall_White"
COORDINATE_OBJECT_NAME = "TEXCOORD_WALL_TILE_WORLD"


def ensure_helper_collection():
    collection = bpy.data.collections.get(HELPER_COLLECTION_NAME)
    if collection is None:
        collection = bpy.data.collections.new(HELPER_COLLECTION_NAME)
        bpy.context.scene.collection.children.link(collection)
    return collection


def move_to_collection(obj, collection):
    if collection not in obj.users_collection:
        collection.objects.link(obj)
    for current in list(obj.users_collection):
        if current != collection:
            current.objects.unlink(obj)


def ensure_world_coordinate_object(collection):
    coordinate_object = bpy.data.objects.get(COORDINATE_OBJECT_NAME)
    if coordinate_object is None:
        coordinate_object = bpy.data.objects.new(COORDINATE_OBJECT_NAME, None)
        collection.objects.link(coordinate_object)
    else:
        move_to_collection(coordinate_object, collection)
    coordinate_object.empty_display_type = "PLAIN_AXES"
    coordinate_object.empty_display_size = 0.20
    coordinate_object.location = (0.0, 0.0, 0.0)
    coordinate_object.rotation_euler = (0.0, 0.0, 0.0)
    coordinate_object.scale = (1.0, 1.0, 1.0)
    coordinate_object.hide_render = True
    coordinate_object.hide_set(True)
    coordinate_object["purpose"] = "World-space coordinates for consistent 0.20 m x 0.10 m wall tiles"
    return coordinate_object


def build_white_tile_material(coordinate_object):
    material = bpy.data.materials.get(MATERIAL_NAME)
    if material is None:
        material = bpy.data.materials.new(MATERIAL_NAME)
    material.use_nodes = True
    material.diffuse_color = (0.92, 0.92, 0.90, 1.0)
    material.roughness = 0.24

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.name = "OUTPUT"
    output.location = (620, 0)

    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.name = "CERAMIC_SHADER"
    shader.location = (340, 0)
    shader.inputs["Metallic"].default_value = 0.0
    shader.inputs["Roughness"].default_value = 0.22
    shader.inputs["IOR"].default_value = 1.46

    coordinates = nodes.new("ShaderNodeTexCoord")
    coordinates.name = "WORLD_COORDINATES"
    coordinates.location = (-820, 40)
    coordinates.object = coordinate_object

    mapping = nodes.new("ShaderNodeMapping")
    mapping.name = "TILE_SIZE_20X10_CM"
    mapping.location = (-610, 40)
    # With the Brick node dimensions below, scale 5 yields tiles measuring
    # approximately 0.20 m wide and 0.10 m high in world space.
    mapping.inputs["Scale"].default_value = (5.0, 5.0, 5.0)

    brick = nodes.new("ShaderNodeTexBrick")
    brick.name = "WHITE_TILE_AND_GROUT"
    brick.location = (-340, 40)
    brick.offset = 0.0
    brick.offset_frequency = 1
    brick.squash = 1.0
    brick.squash_frequency = 1
    brick.inputs["Color1"].default_value = (0.96, 0.97, 0.95, 1.0)
    brick.inputs["Color2"].default_value = (0.90, 0.92, 0.90, 1.0)
    brick.inputs["Mortar"].default_value = (0.34, 0.36, 0.35, 1.0)
    brick.inputs["Scale"].default_value = 1.0
    brick.inputs["Mortar Size"].default_value = 0.025
    brick.inputs["Mortar Smooth"].default_value = 0.012
    brick.inputs["Bias"].default_value = 0.0
    brick.inputs["Brick Width"].default_value = 1.0
    brick.inputs["Row Height"].default_value = 0.5

    bump = nodes.new("ShaderNodeBump")
    bump.name = "RECESSED_GROUT"
    bump.location = (90, -145)
    bump.invert = True
    bump.inputs["Strength"].default_value = 0.20
    bump.inputs["Distance"].default_value = 0.006

    links.new(coordinates.outputs["Object"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], brick.inputs["Vector"])
    links.new(brick.outputs["Color"], shader.inputs["Base Color"])
    links.new(brick.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])

    material["finish"] = "Glossy white kitchen-grade ceramic wall tile"
    material["tile_nominal_width_m"] = 0.20
    material["tile_nominal_height_m"] = 0.10
    material["dimensions_status"] = "Visual assumption; verify tile size in field"
    return material


def main():
    wall = bpy.data.objects.get(WALL_NAME)
    cutter = bpy.data.objects.get(CUTTER_NAME) or bpy.data.objects.get(CUTTER_SOURCE_NAME)
    if wall is None or wall.type != "MESH":
        raise RuntimeError(f"Missing mesh wall: {WALL_NAME}")
    if cutter is None or cutter.type != "MESH":
        raise RuntimeError(f"Missing mesh cutter: {CUTTER_SOURCE_NAME}")

    helper_collection = ensure_helper_collection()
    cutter.name = CUTTER_NAME
    move_to_collection(cutter, helper_collection)
    cutter.display_type = "WIRE"
    cutter.hide_render = True
    cutter.hide_set(True)
    cutter["original_object_name"] = CUTTER_SOURCE_NAME
    cutter["purpose"] = "Editable Boolean cutter for circular extractor opening"
    cutter["dimension_status"] = "User-authored placement and diameter; not independently measured"

    boolean = wall.modifiers.get(BOOLEAN_NAME)
    if boolean is None:
        boolean = wall.modifiers.new(BOOLEAN_NAME, "BOOLEAN")
    boolean.operation = "DIFFERENCE"
    boolean.solver = "EXACT"
    boolean.object = cutter
    wall["extractor_opening_status"] = "User-authored circular opening; editable Boolean"
    wall["extractor_cutter"] = CUTTER_NAME

    coordinate_object = ensure_world_coordinate_object(helper_collection)
    material = build_white_tile_material(coordinate_object)

    tiled_objects = []
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        if any(slot.material == material for slot in obj.material_slots):
            tiled_objects.append(obj.name)

    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))

    print("EXTRACTOR_WALL", wall.name)
    print("EXTRACTOR_CUTTER", cutter.name)
    print("EXTRACTOR_DIAMETER_M", round(max(cutter.dimensions), 4))
    print("WALL_TILE_MATERIAL", material.name)
    print("WALL_TILE_OBJECT_COUNT", len(tiled_objects))


if __name__ == "__main__":
    main()
