"""Validate the portable Guadalajara USD package and reusable table asset.

Run with Blender's bundled Python or Isaac Sim's bundled Python so ``pxr`` is
available. The script performs no writes.
"""

from pathlib import Path

from pxr import Kind, Sdf, Usd, UsdGeom, UsdUtils


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_STAGE = ROOT / "usd" / "guadalajara_base.usda"
TABLE_COMPONENT = (
    ROOT
    / "usd"
    / "assets"
    / "furniture"
    / "comedor_bench_table"
    / "comedor_bench_table.usdc"
)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def validate_dependencies(asset_path: Path):
    layers, assets, unresolved = UsdUtils.ComputeAllDependencies(str(asset_path))
    require(not unresolved, f"Unresolved dependencies for {asset_path}: {unresolved}")
    missing_assets = [path for path in assets if not Path(path).exists()]
    require(not missing_assets, f"Missing dependencies for {asset_path}: {missing_assets}")
    return layers, assets


def main():
    stage = Usd.Stage.Open(str(CANONICAL_STAGE), load=Usd.Stage.LoadAll)
    require(stage is not None, f"Cannot open {CANONICAL_STAGE}")
    require(
        stage.GetDefaultPrim().GetPath() == Sdf.Path("/Guadalajara"),
        "Canonical stage defaultPrim must be /Guadalajara",
    )
    require(UsdGeom.GetStageMetersPerUnit(stage) == 1.0, "Canonical stage must use meters")
    require(UsdGeom.GetStageUpAxis(stage) == UsdGeom.Tokens.z, "Canonical stage must be Z-up")
    require(
        stage.GetPrimAtPath(
            "/Guadalajara/Areas/Despacho/Stations/ServiceCounter/DOMICILIOS_STATION_01"
        ),
        "Domicilios station is missing from the composed stage",
    )
    require(
        stage.GetPrimAtPath(
            "/Guadalajara/Areas/Despacho/Stations/Equipment/SOUP_STATION_01"
        ),
        "Soup station is missing from the composed stage",
    )
    require(
        stage.GetPrimAtPath(
            "/Guadalajara/Areas/Despacho/Stations/Equipment/CASH_INTERIOR_STATION_01"
        ),
        "Interior cash station is missing from the composed stage",
    )

    session_layer = stage.GetSessionLayer()
    missing_layers = []
    external_layers = []
    unexpected_anonymous = []
    for layer in stage.GetUsedLayers():
        if layer == session_layer:
            continue
        if layer.anonymous:
            unexpected_anonymous.append(layer.identifier)
            continue
        path = Path(layer.realPath or layer.identifier).resolve()
        if not path.exists():
            missing_layers.append(str(path))
            continue
        try:
            path.relative_to(ROOT.resolve())
        except ValueError:
            external_layers.append(str(path))
    require(not unexpected_anonymous, f"Unexpected anonymous layers: {unexpected_anonymous}")
    require(not missing_layers, f"Missing composed layers: {missing_layers}")
    require(not external_layers, f"Composed layers outside repository: {external_layers}")
    canonical_layers, canonical_assets = validate_dependencies(CANONICAL_STAGE)

    table = Usd.Stage.Open(str(TABLE_COMPONENT), load=Usd.Stage.LoadAll)
    require(table is not None, f"Cannot open {TABLE_COMPONENT}")
    table_root = table.GetDefaultPrim()
    require(
        table_root and table_root.GetPath() == Sdf.Path("/ComedorBenchTable"),
        "Table component defaultPrim must be /ComedorBenchTable",
    )
    require(
        Usd.ModelAPI(table_root).GetKind() == Kind.Tokens.component,
        "Table component must declare kind=component",
    )
    require(UsdGeom.GetStageMetersPerUnit(table) == 1.0, "Table component must use meters")
    require(UsdGeom.GetStageUpAxis(table) == UsdGeom.Tokens.z, "Table component must be Z-up")
    validate_dependencies(TABLE_COMPONENT)

    print("USD_PACKAGE_OK", True)
    print("CANONICAL_PRIMS", sum(1 for _ in stage.Traverse()))
    print("CANONICAL_DEPENDENCY_LAYERS", len(canonical_layers))
    print("CANONICAL_DEPENDENCY_ASSETS", len(canonical_assets))
    print("TABLE_DEFAULT_PRIM", table_root.GetPath())
    print("TABLE_KIND", Usd.ModelAPI(table_root).GetKind())
    print("TABLE_PRIMS", sum(1 for _ in table.Traverse()))
    print("TABLE_METERS_PER_UNIT", UsdGeom.GetStageMetersPerUnit(table))
    print("TABLE_UP_AXIS", UsdGeom.GetStageUpAxis(table))


if __name__ == "__main__":
    main()
