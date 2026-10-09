"""Publish one Blender collection as a reusable OpenUSD ingredient component.

Example:
    blender --background blend/assets/ingredients/arepa.blend \
      --python scripts/export_ingredient_asset.py -- \
      --collection INGREDIENT_AREPA --name Arepa \
      --output usd/assets/ingredients/arepa/arepa.usdc
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy
from pxr import Kind, Sdf, Usd, UsdGeom


def arguments():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", required=True, help="Blender collection containing one ingredient asset")
    parser.add_argument("--name", required=True, help="Stable ASCII USD root prim name")
    parser.add_argument("--output", required=True, help="Destination .usd, .usda, or .usdc file")
    return parser.parse_args(argv)


def main():
    args = arguments()
    collection = bpy.data.collections.get(args.collection)
    if collection is None:
        raise RuntimeError(f"Missing Blender collection: {args.collection}")
    objects = [obj for obj in collection.all_objects if obj.type in {"MESH", "EMPTY"}]
    if not objects:
        raise RuntimeError(f"Collection has no exportable objects: {args.collection}")

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    for obj in bpy.data.objects:
        obj.select_set(False)
    hidden = {obj.name: obj.hide_get() for obj in objects}
    try:
        for obj in objects:
            obj.hide_set(False)
            obj.select_set(True)
        bpy.context.view_layer.objects.active = objects[0]
        bpy.ops.wm.usd_export(
            filepath=str(output),
            selected_objects_only=True,
            export_animation=False,
            export_materials=True,
            generate_preview_surface=True,
            export_textures_mode="NEW",
            overwrite_textures=True,
            relative_paths=True,
            meters_per_unit=1.0,
            convert_scene_units="METERS",
            export_cameras=False,
            export_lights=False,
            convert_world_material=False,
            root_prim_path=f"/{args.name}",
            export_custom_properties=True,
        )
    finally:
        for name, was_hidden in hidden.items():
            obj = bpy.data.objects.get(name)
            if obj is not None:
                obj.hide_set(was_hidden)

    stage = Usd.Stage.Open(str(output))
    root = stage.GetPrimAtPath(f"/{args.name}")
    if not root:
        raise RuntimeError(f"Exported stage is missing /{args.name}")
    stage.SetDefaultPrim(root)
    Usd.ModelAPI(root).SetKind(Kind.Tokens.component)
    Usd.ModelAPI(root).SetAssetName(args.name)
    Usd.ModelAPI(root).SetAssetIdentifier(Sdf.AssetPath(output.name))
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    root.SetCustomDataByKey("sourceBlend", bpy.data.filepath or "unsaved")
    root.SetCustomDataByKey("sourceCollection", args.collection)
    stage.GetRootLayer().Save()

    check = Usd.Stage.Open(str(output))
    print("INGREDIENT_USD", output)
    print("DEFAULT_PRIM", check.GetDefaultPrim().GetPath())
    print("KIND", Usd.ModelAPI(check.GetDefaultPrim()).GetKind())
    print("OBJECT_COUNT", len(objects))


if __name__ == "__main__":
    main()
