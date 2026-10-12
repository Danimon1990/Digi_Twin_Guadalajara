"""Create and assign the provisional wine-red tile finish for Despacho."""

from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
BLEND_PATH = ROOT / "blend" / "guadalajara_base.blend"
MATERIAL_NAME = "MAT_Floor_Despacho_WineTile"
COORDINATE_OBJECT_NAME = "TEXCOORD_FLOOR_TILE_WORLD"
HELPER_COLLECTION_NAME = "Construction_Helpers"
TARGET_OBJECTS = ("FLOOR_DESPACHO_LOWER", "STEP_DESPACHO_CUBE002")
ZONE_GUIDE_NAME = "FLOOR_DESPACHO"


def helper_collection():
    collection = bpy.data.collections.get(HELPER_COLLECTION_NAME)
    if collection is None:
        collection = bpy.data.collections.new(HELPER_COLLECTION_NAME)
        bpy.context.scene.collection.children.link(collection)
    return collection


def coordinate_object(collection):
    obj = bpy.data.objects.get(COORDINATE_OBJECT_NAME)
    if obj is None:
        obj = bpy.data.objects.new(COORDINATE_OBJECT_NAME, None)
        collection.objects.link(obj)
    elif collection not in obj.users_collection:
        collection.objects.link(obj)
    for current in list(obj.users_collection):
        if current != collection:
            current.objects.unlink(obj)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 0.20
    obj.location = (0.0, 0.0, 0.0)
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj.scale = (1.0, 1.0, 1.0)
    obj.hide_render = True
    obj.hide_set(True)
    obj["purpose"] = "World-space coordinates for consistent floor tile scale"
    return obj


def build_material(texture_coordinates):
    material = bpy.data.materials.get(MATERIAL_NAME)
    if material is None:
        material = bpy.data.materials.new(MATERIAL_NAME)
    material.use_nodes = True
    material.diffuse_color = (0.20, 0.018, 0.025, 1.0)
    material.roughness = 0.42

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.name = "OUTPUT"
    output.location = (650, 20)

    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.name = "WINE_TILE_SHADER"
    shader.location = (380, 20)
    shader.inputs["Metallic"].default_value = 0.0
    shader.inputs["IOR"].default_value = 1.46

    coordinates = nodes.new("ShaderNodeTexCoord")
    coordinates.name = "WORLD_COORDINATES"
    coordinates.location = (-850, 50)
    coordinates.object = texture_coordinates

    mapping = nodes.new("ShaderNodeMapping")
    mapping.name = "CONFIRMED_TILE_SIZE_25_CM"
    mapping.location = (-650, 50)
    mapping.inputs["Scale"].default_value = (4.0, 4.0, 4.0)

    brick = nodes.new("ShaderNodeTexBrick")
    brick.name = "WINE_TILES_CEMENT_JOINTS"
    brick.location = (-395, 50)
    brick.offset = 0.0
    brick.offset_frequency = 1
    brick.squash = 1.0
    brick.squash_frequency = 1
    brick.inputs["Color1"].default_value = (0.245, 0.012, 0.020, 1.0)
    brick.inputs["Color2"].default_value = (0.135, 0.006, 0.012, 1.0)
    brick.inputs["Mortar"].default_value = (0.29, 0.30, 0.29, 1.0)
    brick.inputs["Scale"].default_value = 1.0
    brick.inputs["Mortar Size"].default_value = 0.055
    brick.inputs["Mortar Smooth"].default_value = 0.010
    brick.inputs["Bias"].default_value = -0.15
    brick.inputs["Brick Width"].default_value = 1.0
    brick.inputs["Row Height"].default_value = 1.0

    roughness = nodes.new("ShaderNodeMapRange")
    roughness.name = "TILE_GROUT_ROUGHNESS"
    roughness.location = (85, -95)
    roughness.inputs["From Min"].default_value = 0.0
    roughness.inputs["From Max"].default_value = 1.0
    roughness.inputs["To Min"].default_value = 0.72
    roughness.inputs["To Max"].default_value = 0.36
    roughness.clamp = True

    bump = nodes.new("ShaderNodeBump")
    bump.name = "RECESSED_CEMENT_JOINTS"
    bump.location = (100, -245)
    bump.invert = False
    bump.inputs["Strength"].default_value = 0.30
    bump.inputs["Distance"].default_value = 0.008

    links.new(coordinates.outputs["Object"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], brick.inputs["Vector"])
    links.new(brick.outputs["Color"], shader.inputs["Base Color"])
    links.new(brick.outputs["Fac"], roughness.inputs["Value"])
    links.new(roughness.outputs["Result"], shader.inputs["Roughness"])
    links.new(brick.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])

    material["finish"] = "Dark wine-red ceramic floor tiles in a thick cement-gray grout matrix"
    material["tile_nominal_width_m"] = 0.25
    material["tile_nominal_height_m"] = 0.25
    material["joint_nominal_width_m"] = 0.0165
    material["dimensions_status"] = "Tile size confirmed by user; joint width remains provisional"
    return material


def assign_single_material(obj, material):
    obj.data.materials.clear()
    obj.data.materials.append(material)
    obj["finish_status"] = "Visual material description supplied by user; dimensions remain provisional"


def main():
    targets = []
    for name in TARGET_OBJECTS:
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != "MESH":
            raise RuntimeError(f"Missing mesh object: {name}")
        targets.append(obj)

    texture_coordinates = coordinate_object(helper_collection())
    material = build_material(texture_coordinates)
    for obj in targets:
        assign_single_material(obj, material)

    # This review-only plane sits above the lowered physical floor and would
    # otherwise obscure its material in the viewport.
    zone_guide = bpy.data.objects.get(ZONE_GUIDE_NAME)
    if zone_guide is not None:
        zone_guide.hide_set(True)
        zone_guide.hide_render = True

    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))

    print("DESPACHO_FLOOR_MATERIAL", material.name)
    print("ASSIGNED_OBJECTS", [obj.name for obj in targets])
    print("CONFIRMED_TILE_SIZE_M", (0.25, 0.25))
    print("PROVISIONAL_JOINT_WIDTH_M", 0.0165)


if __name__ == "__main__":
    main()
