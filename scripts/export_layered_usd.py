"""Export the Guadalajara scene as a layered, regenerable OpenUSD assembly.

Blender remains the source of truth. Generated USD geometry layers are not
intended for hand editing; readable USDA manifests provide the composition and
station hierarchy. Shared materials are centralized and texture paths are
rewritten to ``usd/textures``.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

import bpy
from mathutils import Vector
from pxr import Kind, Sdf, Usd, UsdGeom, UsdShade


ROOT = Path(__file__).resolve().parents[1]
USD_ROOT = ROOT / "usd"
LAYERS = USD_ROOT / "layers"
ARCH_LEAVES = LAYERS / "architecture"
AREA_MANIFESTS = LAYERS / "areas"
STATION_LEAVES = AREA_MANIFESTS / "stations"
REVIEW_LAYERS = LAYERS / "review"
ASSET_LAYERS = LAYERS / "assets"
USD_TEXTURES = USD_ROOT / "textures"
SOURCE_TEXTURES = ROOT / "textures" / "generated"
INGREDIENT_MANIFEST = ROOT / "config" / "usd" / "ingredients.json"

ROOT_STAGE = USD_ROOT / "guadalajara_base.usda"
MATERIAL_LAYER = LAYERS / "materials.usda"
ARCH_MANIFEST = LAYERS / "architecture.usda"
DESPACHO_MANIFEST = AREA_MANIFESTS / "despacho.usda"
COCINA_MANIFEST = AREA_MANIFESTS / "cocina.usda"
COMEDORES_MANIFEST = AREA_MANIFESTS / "comedores.usda"
CAMERA_LAYER = REVIEW_LAYERS / "cameras.usda"
LIGHT_LAYER = REVIEW_LAYERS / "lights.usda"
INGREDIENT_LAYER = ASSET_LAYERS / "ingredients.usda"

EXPORTABLE_TYPES = {"MESH", "EMPTY"}
AREA_GUIDES = {
    "Despacho": "FLOOR_DESPACHO",
    "Cocina": "FLOOR_COCINA",
    "Comedores": "FLOOR_COMEDORES",
}


def ensure_directories():
    for path in (ARCH_LEAVES, AREA_MANIFESTS, STATION_LEAVES, REVIEW_LAYERS, ASSET_LAYERS, USD_TEXTURES):
        path.mkdir(parents=True, exist_ok=True)


def define_xform(stage, path, kind=None):
    prim = UsdGeom.Xform.Define(stage, path).GetPrim()
    if kind:
        Usd.ModelAPI(prim).SetKind(kind)
    return prim


def configure_stage(stage):
    root = define_xform(stage, "/Guadalajara", Kind.Tokens.assembly)
    stage.SetDefaultPrim(root)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    return root


def collection_objects(name):
    collection = bpy.data.collections.get(name)
    if collection is None:
        raise RuntimeError(f"Missing required Blender collection: {name}")
    return [obj for obj in collection.all_objects if obj.type in EXPORTABLE_TYPES]


def guide_regions(name):
    guide = bpy.data.objects.get(name)
    if guide is None or guide.type != "MESH":
        raise RuntimeError(f"Missing area guide: {name}")
    regions = []
    for polygon in guide.data.polygons:
        if polygon.normal.z <= 0.5:
            continue
        regions.append([
            (guide.matrix_world @ guide.data.vertices[index].co).xy.copy()
            for index in polygon.vertices
        ])
    return regions


def point_in_polygon(point, polygon):
    inside = False
    x, y = point
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            crossing = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing:
                inside = not inside
        previous = current
    return inside


def object_center_xy(obj):
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return (sum(point.x for point in corners) / len(corners), sum(point.y for point in corners) / len(corners))


def existing_objects_in_area(area_name):
    regions = guide_regions(AREA_GUIDES[area_name])
    collection = bpy.data.collections.get("Existing_Unclassified")
    if collection is None:
        return []
    result = []
    for obj in collection.all_objects:
        if obj.type != "MESH" or obj.dimensions.z <= 0.01:
            continue
        center = object_center_xy(obj)
        if any(point_in_polygon(center, polygon) for polygon in regions):
            result.append(obj)
    return result


def unique_objects(objects):
    result = []
    seen = set()
    for obj in objects:
        if obj.name in seen:
            continue
        seen.add(obj.name)
        result.append(obj)
    return result


def select_for_export(objects):
    for obj in bpy.data.objects:
        obj.select_set(False)
    states = {}
    for obj in objects:
        states[obj.name] = obj.hide_get()
        obj.hide_set(False)
        obj.select_set(True)
    if objects:
        bpy.context.view_layer.objects.active = objects[0]
    return states


def restore_visibility(states):
    for name, hidden in states.items():
        obj = bpy.data.objects.get(name)
        if obj is not None:
            obj.hide_set(hidden)


def replace_prefix(path, source_prefix, destination_prefix):
    text = str(path)
    source = str(source_prefix)
    if text == source or text.startswith(source + "/"):
        return Sdf.Path(str(destination_prefix) + text[len(source):])
    return path


def resolve_texture_source(asset_path, source_usd):
    name = Path(asset_path).name
    generated = SOURCE_TEXTURES / name
    if generated.exists():
        return generated
    candidate = (source_usd.parent / asset_path).resolve()
    if candidate.exists():
        return candidate
    return None


def rewrite_material_network(materials_stage, destination_path, source_path, source_usd):
    destination = materials_stage.GetPrimAtPath(destination_path)
    for prim in Usd.PrimRange(destination):
        for attribute in prim.GetAttributes():
            connections = attribute.GetConnections()
            if connections:
                attribute.SetConnections([
                    replace_prefix(path, source_path, destination_path)
                    for path in connections
                ])
            value = attribute.Get()
            if isinstance(value, Sdf.AssetPath) and value.path:
                source = resolve_texture_source(value.path, source_usd)
                if source is not None:
                    destination_texture = USD_TEXTURES / source.name
                    shutil.copy2(source, destination_texture)
                    attribute.Set(Sdf.AssetPath(f"../textures/{source.name}"))
        for relationship in prim.GetRelationships():
            targets = relationship.GetTargets()
            if targets:
                relationship.SetTargets([
                    replace_prefix(path, source_path, destination_path)
                    for path in targets
                ])


def centralize_materials(stage, usd_path, materials_stage):
    material_prims = [prim for prim in stage.Traverse() if prim.IsA(UsdShade.Material)]
    mappings = {}
    material_parents = set()
    for material_prim in material_prims:
        source_path = material_prim.GetPath()
        destination_path = Sdf.Path(f"/Guadalajara/Materials/{material_prim.GetName()}")
        mappings[source_path] = destination_path
        material_parents.add(source_path.GetParentPath())
        if not materials_stage.GetPrimAtPath(destination_path):
            Sdf.CopySpec(
                stage.GetRootLayer(),
                source_path,
                materials_stage.GetRootLayer(),
                destination_path,
            )
            rewrite_material_network(materials_stage, destination_path, source_path, usd_path)

    for prim in list(stage.Traverse()):
        for relationship in prim.GetRelationships():
            if not relationship.GetName().startswith("material:binding"):
                continue
            targets = relationship.GetTargets()
            rewritten = []
            for target in targets:
                replacement = mappings.get(target)
                if replacement is None:
                    replacement = Sdf.Path(f"/Guadalajara/Materials/{target.name}")
                rewritten.append(replacement)
            if rewritten:
                relationship.SetTargets(rewritten)

    for parent in sorted(material_parents, key=lambda path: len(str(path)), reverse=True):
        stage.RemovePrim(parent)


def tag_export_hierarchy(stage, leaf_root, leaf_kind=Kind.Tokens.group):
    configure_stage(stage)
    parts = [part for part in leaf_root.split("/") if part]
    current = ""
    for index, part in enumerate(parts):
        current += f"/{part}"
        prim = stage.GetPrimAtPath(current)
        if not prim:
            prim = define_xform(stage, current)
        if current == "/Guadalajara":
            Usd.ModelAPI(prim).SetKind(Kind.Tokens.assembly)
        elif index == len(parts) - 1:
            Usd.ModelAPI(prim).SetKind(leaf_kind)
        elif part in {"Areas", "Stations", "Architecture", "Review", "Assets"}:
            Usd.ModelAPI(prim).SetKind(Kind.Tokens.group)
        elif index == 2 and parts[1] == "Areas":
            Usd.ModelAPI(prim).SetKind(Kind.Tokens.assembly)
        else:
            Usd.ModelAPI(prim).SetKind(Kind.Tokens.group)

    root_path = Sdf.Path(leaf_root)
    for child in stage.GetPrimAtPath(root_path).GetChildren():
        if child.GetTypeName() == "Xform":
            Usd.ModelAPI(child).SetKind(Kind.Tokens.component)


def export_leaf(filepath, objects, root_path, materials_stage, *, cameras=False, lights=False):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    objects = unique_objects(objects)
    if not objects:
        stage = Usd.Stage.CreateNew(str(filepath))
        configure_stage(stage)
        define_xform(stage, root_path, Kind.Tokens.group)
        stage.GetRootLayer().Save()
        return 0

    states = select_for_export(objects)
    try:
        bpy.ops.wm.usd_export(
            filepath=str(filepath),
            selected_objects_only=True,
            export_animation=False,
            export_materials=not (cameras or lights),
            generate_preview_surface=True,
            export_textures_mode="KEEP",
            relative_paths=True,
            meters_per_unit=1.0,
            convert_scene_units="METERS",
            export_cameras=cameras,
            export_lights=lights,
            export_meshes=not (cameras or lights),
            convert_world_material=False,
            root_prim_path=root_path,
            export_custom_properties=True,
        )
    finally:
        restore_visibility(states)

    stage = Usd.Stage.Open(str(filepath))
    if stage is None:
        raise RuntimeError(f"Could not reopen USD leaf: {filepath}")
    tag_export_hierarchy(stage, root_path)
    if not (cameras or lights):
        centralize_materials(stage, filepath, materials_stage)
    stage.GetRootLayer().customLayerData = {
        "generatedBy": "scripts/export_layered_usd.py",
        "sourceBlend": "blend/guadalajara_base.blend",
        "leafRoot": root_path,
    }
    stage.GetRootLayer().Save()
    return len(objects)


def create_manifest(path, sublayers, hierarchy, role):
    stage = Usd.Stage.CreateNew(str(path))
    configure_stage(stage)
    for prim_path, kind in hierarchy:
        define_xform(stage, prim_path, kind)
    stage.GetRootLayer().subLayerPaths = list(sublayers)
    stage.GetRootLayer().customLayerData = {
        "generatedBy": "scripts/export_layered_usd.py",
        "layerRole": role,
        "sourceBlend": "blend/guadalajara_base.blend",
    }
    stage.GetRootLayer().Save()


def initialize_material_stage():
    stage = Usd.Stage.CreateNew(str(MATERIAL_LAYER))
    configure_stage(stage)
    UsdGeom.Scope.Define(stage, "/Guadalajara/Materials")
    stage.GetRootLayer().customLayerData = {
        "generatedBy": "scripts/export_layered_usd.py",
        "layerRole": "shared material library",
    }
    return stage


def build_ingredient_layer():
    stage = Usd.Stage.CreateNew(str(INGREDIENT_LAYER))
    configure_stage(stage)
    define_xform(stage, "/Guadalajara/Assets", Kind.Tokens.group)
    define_xform(stage, "/Guadalajara/Assets/Ingredients", Kind.Tokens.group)

    if INGREDIENT_MANIFEST.exists():
        data = json.loads(INGREDIENT_MANIFEST.read_text(encoding="utf-8"))
    else:
        data = {"schema_version": 1, "placements": []}

    for placement in data.get("placements", []):
        identifier = placement["id"]
        area = placement["area"]
        station = placement["station"]
        asset_file = (ROOT / placement["asset"]).resolve()
        prim_path = f"/Guadalajara/Areas/{area}/Stations/{station}/Ingredients/{identifier}"
        parent_path = str(Sdf.Path(prim_path).GetParentPath())
        define_xform(stage, parent_path, Kind.Tokens.group)
        prim = define_xform(stage, prim_path, Kind.Tokens.component)
        relative_asset = os.path.relpath(asset_file, INGREDIENT_LAYER.parent)
        prim.GetReferences().AddReference(relative_asset)
        transform = placement.get("transform", {})
        xform = UsdGeom.Xformable(prim)
        if "translate" in transform:
            xform.AddTranslateOp().Set(tuple(transform["translate"]))
        if "rotate_xyz_degrees" in transform:
            xform.AddRotateXYZOp().Set(tuple(transform["rotate_xyz_degrees"]))
        if "scale" in transform:
            xform.AddScaleOp().Set(tuple(transform["scale"]))

    stage.GetRootLayer().customLayerData = {
        "generatedBy": "scripts/export_layered_usd.py",
        "layerRole": "ingredient reference placements",
        "manifest": "config/usd/ingredients.json",
    }
    stage.GetRootLayer().Save()


def build_root_stage():
    stage = Usd.Stage.CreateNew(str(ROOT_STAGE))
    root = configure_stage(stage)
    define_xform(stage, "/Guadalajara/Architecture", Kind.Tokens.group)
    define_xform(stage, "/Guadalajara/Areas", Kind.Tokens.group)
    UsdGeom.Scope.Define(stage, "/Guadalajara/Materials")
    define_xform(stage, "/Guadalajara/Assets", Kind.Tokens.group)
    define_xform(stage, "/Guadalajara/Review", Kind.Tokens.group)
    stage.GetRootLayer().subLayerPaths = [
        "layers/review/lights.usda",
        "layers/review/cameras.usda",
        "layers/assets/ingredients.usda",
        "layers/areas/comedores.usda",
        "layers/areas/cocina.usda",
        "layers/areas/despacho.usda",
        "layers/architecture.usda",
        "layers/materials.usda",
    ]
    root.SetCustomDataByKey("deliverableStatus", "Exploration stage; no roof and no physics")
    root.SetCustomDataByKey("authoringSource", "blend/guadalajara_base.blend")
    root.SetCustomDataByKey("pipeline", "Regenerate with scripts/export_layered_usd.py")
    stage.GetRootLayer().customLayerData = {
        "generatedBy": "scripts/export_layered_usd.py",
        "layerRole": "composition root",
    }
    stage.GetRootLayer().Save()


def validate_stage(counts):
    stage = Usd.Stage.Open(str(ROOT_STAGE))
    if stage is None:
        raise RuntimeError("Could not reopen composed root stage")
    if stage.GetDefaultPrim().GetPath() != Sdf.Path("/Guadalajara"):
        raise RuntimeError("Root defaultPrim is not /Guadalajara")
    if UsdGeom.GetStageMetersPerUnit(stage) != 1.0:
        raise RuntimeError("Root stage is not authored in meters")
    if UsdGeom.GetStageUpAxis(stage) != UsdGeom.Tokens.z:
        raise RuntimeError("Root stage is not Z-up")
    required = (
        "/Guadalajara/Architecture/Floors",
        "/Guadalajara/Architecture/Walls",
        "/Guadalajara/Areas/Despacho/Stations",
        "/Guadalajara/Areas/Cocina/Stations",
        "/Guadalajara/Areas/Comedores/Stations",
        "/Guadalajara/Materials",
        "/Guadalajara/Review/Cameras",
        "/Guadalajara/Review/Lights",
    )
    missing = [path for path in required if not stage.GetPrimAtPath(path)]
    if missing:
        raise RuntimeError(f"Composed stage is missing required prims: {missing}")
    if any("roof" in str(prim.GetPath()).lower() for prim in stage.Traverse()):
        raise RuntimeError("Roof content was exported despite the current scope")

    invalid_bindings = []
    for prim in stage.Traverse():
        for relationship in prim.GetRelationships():
            if not relationship.GetName().startswith("material:binding"):
                continue
            for target in relationship.GetTargets():
                if not stage.GetPrimAtPath(target):
                    invalid_bindings.append((str(prim.GetPath()), str(target)))
    if invalid_bindings:
        raise RuntimeError(f"Invalid material bindings: {invalid_bindings[:10]}")

    print("USD_ROOT", ROOT_STAGE)
    print("USD_DEFAULT_PRIM", stage.GetDefaultPrim().GetPath())
    print("USD_METERS_PER_UNIT", UsdGeom.GetStageMetersPerUnit(stage))
    print("USD_UP_AXIS", UsdGeom.GetStageUpAxis(stage))
    print("USD_PRIM_COUNT", sum(1 for _ in stage.Traverse()))
    print("USD_EXPORT_COUNTS", counts)


def main():
    if not bpy.data.filepath:
        raise RuntimeError("Save the Blender scene before exporting")
    ensure_directories()
    materials_stage = initialize_material_stage()

    counts = {}
    architecture_exports = (
        ("floors", "Floors"),
        ("walls", "Walls"),
        ("columns", "Columns"),
        ("stairs", "Stairs"),
    )
    for leaf_name, collection_name in architecture_exports:
        path = ARCH_LEAVES / f"{leaf_name}.usdc"
        root_path = f"/Guadalajara/Architecture/{leaf_name.title()}"
        counts[f"architecture_{leaf_name}"] = export_leaf(
            path, collection_objects(collection_name), root_path, materials_stage
        )

    despacho_service = collection_objects("Fixtures_Despacho")
    despacho_tables = collection_objects("Mesas_trabajo")
    despacho_equipment = existing_objects_in_area("Despacho")
    cocina_equipment = existing_objects_in_area("Cocina")
    comedores_furniture = existing_objects_in_area("Comedores")

    station_exports = (
        ("despacho_service_counter", despacho_service, "/Guadalajara/Areas/Despacho/Stations/ServiceCounter"),
        ("despacho_prep_tables", despacho_tables, "/Guadalajara/Areas/Despacho/Stations/PrepTables"),
        ("despacho_equipment", despacho_equipment, "/Guadalajara/Areas/Despacho/Stations/Equipment"),
        ("cocina_equipment", cocina_equipment, "/Guadalajara/Areas/Cocina/Stations/Equipment"),
        ("comedores_furniture", comedores_furniture, "/Guadalajara/Areas/Comedores/Stations/Furniture"),
    )
    for leaf_name, objects, root_path in station_exports:
        counts[leaf_name] = export_leaf(
            STATION_LEAVES / f"{leaf_name}.usdc", objects, root_path, materials_stage
        )

    counts["review_cameras"] = export_leaf(
        CAMERA_LAYER,
        [obj for obj in bpy.data.objects if obj.type == "CAMERA"],
        "/Guadalajara/Review/Cameras",
        materials_stage,
        cameras=True,
    )
    counts["review_lights"] = export_leaf(
        LIGHT_LAYER,
        [obj for obj in bpy.data.objects if obj.type == "LIGHT"],
        "/Guadalajara/Review/Lights",
        materials_stage,
        lights=True,
    )
    materials_stage.GetRootLayer().Save()

    create_manifest(
        ARCH_MANIFEST,
        [
            "architecture/floors.usdc",
            "architecture/walls.usdc",
            "architecture/columns.usdc",
            "architecture/stairs.usdc",
        ],
        [("/Guadalajara/Architecture", Kind.Tokens.group)],
        "architectural shell manifest",
    )
    create_manifest(
        DESPACHO_MANIFEST,
        [
            "stations/despacho_service_counter.usdc",
            "stations/despacho_prep_tables.usdc",
            "stations/despacho_equipment.usdc",
        ],
        [
            ("/Guadalajara/Areas", Kind.Tokens.group),
            ("/Guadalajara/Areas/Despacho", Kind.Tokens.assembly),
            ("/Guadalajara/Areas/Despacho/Stations", Kind.Tokens.group),
            ("/Guadalajara/Areas/Despacho/Stations/ServiceCounter", Kind.Tokens.group),
            ("/Guadalajara/Areas/Despacho/Stations/PrepTables", Kind.Tokens.group),
            ("/Guadalajara/Areas/Despacho/Stations/Equipment", Kind.Tokens.group),
        ],
        "despacho area manifest",
    )
    create_manifest(
        COCINA_MANIFEST,
        ["stations/cocina_equipment.usdc"],
        [
            ("/Guadalajara/Areas", Kind.Tokens.group),
            ("/Guadalajara/Areas/Cocina", Kind.Tokens.assembly),
            ("/Guadalajara/Areas/Cocina/Stations", Kind.Tokens.group),
            ("/Guadalajara/Areas/Cocina/Stations/Equipment", Kind.Tokens.group),
        ],
        "other kitchen area manifest",
    )
    create_manifest(
        COMEDORES_MANIFEST,
        ["stations/comedores_furniture.usdc"],
        [
            ("/Guadalajara/Areas", Kind.Tokens.group),
            ("/Guadalajara/Areas/Comedores", Kind.Tokens.assembly),
            ("/Guadalajara/Areas/Comedores/Stations", Kind.Tokens.group),
            ("/Guadalajara/Areas/Comedores/Stations/Furniture", Kind.Tokens.group),
        ],
        "comedores area manifest",
    )
    build_ingredient_layer()
    build_root_stage()
    validate_stage(counts)


if __name__ == "__main__":
    main()
