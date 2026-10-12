"""Create reusable worktable metals and assign them to both table groups."""

from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
BLEND_PATH = ROOT / "blend" / "guadalajara_base.blend"

SURFACE_MATERIAL = "MAT_Metal_Worktable_SatinAluminum"
FRAME_MATERIAL = "MAT_Metal_Worktable_DarkSteel"
TABLE_COLLECTIONS = ("Mesas_trabajo 1", "Mesas_trabajo 1.001")


def input_if_present(shader, names, value):
    for name in names:
        socket = shader.inputs.get(name)
        if socket is not None:
            socket.default_value = value
            return


def metal_material(name, base_color, roughness, anisotropy, description):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = (*base_color, 1.0)
    material.metallic = 1.0
    material.roughness = roughness

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.name = "OUTPUT"
    output.location = (320, 0)

    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.name = "METAL_SHADER"
    shader.location = (20, 0)
    shader.inputs["Base Color"].default_value = (*base_color, 1.0)
    shader.inputs["Metallic"].default_value = 1.0
    shader.inputs["Roughness"].default_value = roughness
    input_if_present(shader, ("Anisotropic IOR Level", "Anisotropic"), anisotropy)

    links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    material["finish"] = description
    material["reuse_scope"] = "Reusable on other food-service furniture and fixtures"
    material["usd_compatibility"] = "Principled metallic/roughness values export as UsdPreviewSurface"
    return material


def assign_material(obj, material, role):
    obj.data.materials.clear()
    obj.data.materials.append(material)
    obj["fixture_role"] = role
    obj["material_assignment"] = material.name


def main():
    surface = metal_material(
        SURFACE_MATERIAL,
        base_color=(0.56, 0.61, 0.65),
        roughness=0.39,
        anisotropy=0.32,
        description="Satin aluminum-tone food-service work surface; subdued reflections",
    )
    frame = metal_material(
        FRAME_MATERIAL,
        base_color=(0.16, 0.18, 0.20),
        roughness=0.31,
        anisotropy=0.12,
        description="Dark structural steel table frame and legs",
    )

    assigned_surfaces = []
    assigned_frames = []
    for collection_name in TABLE_COLLECTIONS:
        collection = bpy.data.collections.get(collection_name)
        if collection is None:
            raise RuntimeError(f"Missing table collection: {collection_name}")
        for obj in collection.objects:
            if obj.type != "MESH":
                continue
            if obj.name.startswith("Cylinder"):
                assign_material(obj, frame, "worktable_leg")
                assigned_frames.append(obj.name)
            elif obj.name.startswith("Cube"):
                assign_material(obj, surface, "worktable_surface_or_shelf")
                assigned_surfaces.append(obj.name)

    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    print("WORKTABLE_SURFACE_MATERIAL", surface.name)
    print("WORKTABLE_FRAME_MATERIAL", frame.name)
    print("WORKTABLE_SURFACES", assigned_surfaces)
    print("WORKTABLE_FRAME_PARTS", assigned_frames)


if __name__ == "__main__":
    main()
