"""Export and validate the Guadalajara architectural base as USD."""

from pathlib import Path

import bpy


def find_project_root():
    """Locate the project from the saved Blender file.

    The expected layout places the source file in ``blend/``. A Blender file
    saved directly at the project root is also supported.
    """
    if not bpy.data.filepath:
        raise RuntimeError("Save the Blender file before exporting USD")

    scene_directory = Path(bpy.data.filepath).resolve().parent
    if scene_directory.name == "blend":
        return scene_directory.parent
    return scene_directory


ROOT = find_project_root()
ASSET = ROOT / "usd" / "assets" / "guadalajara_architecture.usdc"
BASE = ROOT / "usd" / "guadalajara_base.usda"


def main():
    collections = []
    for name in ("Walls", "Floors", "Columns", "Stairs", "Fixtures_Despacho"):
        collection = bpy.data.collections.get(name)
        if collection is None:
            raise RuntimeError(f"Missing required collection: {name}")
        collections.append(collection)

    export_objects = [
        obj for collection in collections for obj in collection.objects if obj.type == "MESH"
    ]
    # Hidden selected objects are omitted from ``bpy.context.selected_objects``
    # but can still leak into a selected-only USD export. Clear every object
    # datablock before selecting the explicit export collections.
    for obj in bpy.data.objects:
        obj.select_set(False)
    for obj in export_objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = export_objects[0]

    ASSET.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.usd_export(
        filepath=str(ASSET),
        selected_objects_only=True,
        export_animation=False,
        export_materials=True,
        generate_preview_surface=True,
        relative_paths=True,
        meters_per_unit=1.0,
        convert_scene_units="METERS",
        export_cameras=False,
        export_lights=False,
        root_prim_path="/Guadalajara/Architecture/Level_00",
    )

    from pxr import Usd, UsdGeom

    asset_stage = Usd.Stage.Open(str(ASSET))
    asset_root = asset_stage.GetPrimAtPath("/Guadalajara")
    if not asset_root:
        raise RuntimeError("Exported USD is missing /Guadalajara")
    asset_stage.SetDefaultPrim(asset_root)
    UsdGeom.SetStageMetersPerUnit(asset_stage, 1.0)
    UsdGeom.SetStageUpAxis(asset_stage, UsdGeom.Tokens.z)
    asset_stage.GetRootLayer().Save()

    base_stage = Usd.Stage.CreateNew(str(BASE))
    root = UsdGeom.Xform.Define(base_stage, "/Guadalajara").GetPrim()
    base_stage.SetDefaultPrim(root)
    UsdGeom.SetStageMetersPerUnit(base_stage, 1.0)
    UsdGeom.SetStageUpAxis(base_stage, UsdGeom.Tokens.z)
    root.GetReferences().AddReference("assets/guadalajara_architecture.usdc")
    root.SetCustomDataByKey(
        "deliverableStatus",
        "Phase 1 architectural base; confirmed stair, door, and wall dimensions, ceilings, and upper floor pending",
    )
    base_stage.GetRootLayer().Save()

    check = Usd.Stage.Open(str(BASE))
    if not check:
        raise RuntimeError("Could not reopen composed USD stage")
    print("USD_DEFAULT_PRIM", check.GetDefaultPrim().GetPath())
    print("USD_METERS_PER_UNIT", UsdGeom.GetStageMetersPerUnit(check))
    print("USD_UP_AXIS", UsdGeom.GetStageUpAxis(check))
    print("USD_PRIM_COUNT", sum(1 for _ in check.Traverse()))


if __name__ == "__main__":
    main()
