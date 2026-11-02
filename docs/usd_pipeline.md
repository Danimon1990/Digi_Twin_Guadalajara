# OpenUSD pipeline

`blend/guadalajara_base.blend` remains the editable source of truth. The USD
files are generated deliverables and should be rebuilt rather than manually
patched when Blender geometry changes.

## Composition

Open `usd/guadalajara_base.usda`. It composes the following layers into the
shared `/Guadalajara` namespace:

```text
/Guadalajara                         kind=assembly
├── Architecture                    kind=group
│   ├── Floors
│   ├── Walls
│   ├── Columns
│   ├── Stairs
│   ├── Roof / Roof_Finishes / SecondFloor
│   └── Exterior
│       ├── PeatonWalks
│       └── SecondFloorFacade
├── Areas                           kind=group
│   ├── Despacho                    kind=assembly
│   │   └── Stations
│   │       ├── ServiceCounter
│   │       ├── PrepTables
│   │       └── Equipment
│   ├── Cocina                      kind=assembly
│   │   └── Stations/Equipment
│   └── Comedores                   kind=assembly
│       └── Stations/Furniture
├── Lighting/Interior               13 review area lights below ceilings
├── Materials
├── Assets/Ingredients
└── Review
    ├── Cameras
    └── Lights
```

Readable `.usda` files are composition manifests. Compact `.usdc` files are
generated geometry leaves. Sublayers are used because each file contributes a
separate responsibility to the same site namespace and can be muted for review.
References are reserved for reusable components such as ingredients and
equipment. Payloads are deferred until asset volume makes selective loading
valuable.

Roof and second-floor geometry and finishes are exported from the existing
`Roof` and `Roof_Finishes` Blender collections. Dimensions remain provisional.
No physics schemas are exported.

## Export from Blender

Run from the repository root:

```bash
/Applications/Blender.app/Contents/MacOS/Blender \
  --background blend/guadalajara_base.blend \
  --python scripts/export_layered_usd.py
```

The legacy command using `scripts/export_base.py` remains supported and calls
the same layered exporter.

The exporter:

1. Publishes architectural collections as leaf geometry layers.
2. Routes despacho, cocina, and comedor objects by collection and zone guides.
3. Centralizes material definitions under `/Guadalajara/Materials`.
4. Copies referenced textures to `usd/textures/`.
5. Exports interior lighting to `layers/lighting/interior.usda` and other
   cameras/lights to optional review layers.
6. Builds ingredient references from `config/usd/ingredients.json`.
7. Reopens and validates the composed stage, units, axis, hierarchy, and
   material targets.

Wall meshes are triangulated only in the generated USD. This preserves editable
Boolean cutters in Blender while preventing OpenUSD viewers from filling the
inner loops of door, rectangular-window, and extractor openings. The exporter
exports the `Lighting_Interior_Review` Blender collection to its own layer;
these lights remain separate from physical architecture and are not a lighting design.
The previous USD-only fills above the roof have been removed.

## Adding ingredient assets

Model each ingredient as an independent Blender asset instead of merging its
mesh into `guadalajara_base.blend`. Publish it as a USD component with:

- one root prim;
- `defaultPrim` set to that root;
- `kind = "component"`;
- meters and Z-up metadata;
- geometry and materials contained below the component root.

Store published files below `usd/assets/ingredients/<asset-name>/`. Add each
placement to `config/usd/ingredients.json`:

```bash
blender --background blend/assets/ingredients/arepa.blend \
  --python scripts/export_ingredient_asset.py -- \
  --collection INGREDIENT_AREPA \
  --name Arepa \
  --output usd/assets/ingredients/arepa/arepa.usdc
```

```json
{
  "id": "AREPA_TRAY_01",
  "asset": "usd/assets/ingredients/arepa/arepa.usdc",
  "area": "Despacho",
  "station": "ServiceCounter",
  "transform": {
    "translate": [0.0, 0.0, 0.0],
    "rotate_xyz_degrees": [0.0, 0.0, 0.0],
    "scale": [1.0, 1.0, 1.0]
  }
}
```

Re-exporting creates a reference at
`/Guadalajara/Areas/Despacho/Stations/ServiceCounter/Ingredients/AREPA_TRAY_01`.
The same component may be placed multiple times without duplicating geometry.

Use a payload instead of a reference only when the ingredient library becomes
large enough that clients need selective loading.

## Furniture assets

Reusable furniture is authored in a separate Blender file and published as an
OpenUSD component before it is instanced into an area. The first comedor unit is
generated with:

```bash
blender --background --python scripts/build_comedor_bench_table_asset.py
```

This creates:

- `blend/assets/furniture/comedor_bench_table.blend` for editable Blender work;
- `usd/assets/furniture/comedor_bench_table/comedor_bench_table.usdc` as the
  portable component;
- `outputs/previews/comedor_bench_table_asset.png` as a local-only review render.

Its current dimensions are explicitly provisional visual estimates from
`IMG_5989.heic`; update the constants at the top of the generator after field
measurements are available.

## Serving assets

Reusable serving equipment is also authored outside the building scene. Build
the woven canasto with:

```bash
blender --background --python scripts/build_canasto_asset.py
```

This creates:

- `blend/assets/serving/canasto.blend` as the editable Blender component;
- `usd/assets/serving/canasto/canasto.usdc` as a portable OpenUSD component;
- local-only previews with and without the removable paper liner.

The reported envelope is approximately 0.45 m in diameter and 0.08 m high. The
interior curve remains provisional because the flat-bottom diameter has not
been measured. `CANASTO_PAPER_LINER` is a separate object so a simulation or
render can hide, replace, or deform it without changing the basket structure.

## Linux and Isaac Sim handoff

Keep the complete `usd/` directory together after cloning the repository. Open
`usd/guadalajara_base.usda` in Isaac Sim; its sublayers and textures are
repository-relative. The comedor table is a standalone component at
`usd/assets/furniture/comedor_bench_table/comedor_bench_table.usdc` and may be
referenced multiple times without duplicating its source geometry.
The canasto component is similarly reusable at
`usd/assets/serving/canasto/canasto.usdc`.

Run the portable package check with an environment that provides `pxr`, such as
Isaac Sim's bundled Python:

```bash
./python.sh scripts/validate_usd_package.py
```

The source photographs, `Medidas/`, automatic Blender backups, and local preview
renders are intentionally excluded from the shared repository. They are not
required to open the USD stage.


## Interior lighting and current layer controls

Run `scripts/build_interior_lighting.py` in Blender to recreate/update the 13
managed area lights. It uses existing zone polygons and evaluated roof/floor
surfaces to place downward-facing broad lights below ceilings. Powers, color,
and placement are provisional presentation choices, not measured fixtures or
an electrical design. The script updates stable light names and does not alter
building meshes. Save the canonical blend, then run `scripts/export_base.py`.
The main entry point is unchanged.

Mute these layers independently in a USD viewer:

| Layer | Responsibility |
| --- | --- |
| `layers/architecture.usda` | Shell, roofs, upper-floor geometry |
| `layers/exterior.usda` | Exterior walks and second-floor façade |
| `layers/areas/cocina.usda` | Indoor kitchen equipment |
| `layers/areas/despacho.usda` | Dispatch stations and equipment |
| `layers/lighting/interior.usda` | Interior review lighting |
| `layers/materials.usda` | Shared material definitions |
| `layers/review/cameras.usda` | Presentation cameras |
| `layers/review/lights.usda` | Exterior review key light |

The kitchen layer isolates equipment; its enclosing shell is still owned by
architecture. Muting it does not remove kitchen walls or ceiling. The exterior
layer isolates site walks/façade, not all external-facing building surfaces.
Existing prim paths remain stable for operational bindings.

## Practical OpenUSD / Isaac Sim efficiency rules

Implemented: binary geometry leaves (`.usdc`), readable composition manifests,
repository-relative dependencies, meters/Z-up/defaultPrim, shared materials,
and separately mutable area/lighting layers. The validator checks dependency
resolution, material targets, layer muting, lighting separation, and reusable
component metadata. The second-floor collection and façade are explicitly
routed so moving objects out of Roof_Finishes does not silently drop them.

Next steps, only when profiling shows a need:

1. Reference repeated tables, trays and baskets from reusable components. Mark
   placements instanceable only when their descendants can stay identical;
   unique edits require an override outside the instance or de-instancing.
2. Put large, independently loaded areas behind payloads. Sublayers organize
   authoring but do not provide on-demand geometry loading. The present package
   is small enough that adding payload complexity is not yet justified.
3. Keep operational animation and future collision/physics opinions in separate
   layers. Do not bake replay frames or duplicate the building per simulation.
4. Use simple proxy geometry and reduced detail for distant/repeated objects;
   keep detailed render geometry separate. Avoid merging independently moving
   equipment merely to reduce prim count.
5. Keep shared opaque materials where possible, reuse textures, and avoid
   unnecessary transparency. Keep only required lights active for interactive
   viewing; these 13 lights are a starting point, not an FPS guarantee. Reduce
   shadowed light count and rendering quality after measuring on the target GPU.
6. Benchmark stage opening time, peak memory and viewport FPS in the target
   Isaac Sim version before/after optimization. Blender rendering and USD
   structural checks do not verify RTX appearance or Isaac Sim performance.

Official references used (the requested OpenUSD/Isaac Sim skills were not
installed in this environment):

- https://openusd.org/release/glossary.html (references, payloads, model hierarchy)
- https://docs-prod.omniverse.nvidia.com/usd/latest/learn-openusd/independent/asset-structure-principles.html
- https://docs.isaacsim.omniverse.nvidia.com/6.1.0/reference_material/sim_performance_optimization_handbook.html

Verified with Blender 5.1.2 on 2026-11-02: roof-on before/after Cycles review
renders, canonical stage export, and portable package validator. Isaac Sim was
not run here; RTX appearance/performance remain to be checked there.

## Gray cement-sheet roof appearance

`scripts/build_roof_cement_material.py` creates `MAT_Roof_Teja_Gris_Cemento`
for the five existing opaque roof-sheet meshes. It uses existing UVs with
matte gray color and normal textures in `usd/textures/roof_teja_gris_*.png`.
Wave spacing and weathering are illustrative; this is an appearance study of
the Proteja corrugated reinforced-cement reference, not measured sheet geometry.
No mesh vertices, topology, UVs, transforms, or displacement are changed.
The translucent roof and structural pieces retain their existing materials.
Regenerate the stage after saving Blender; texture images already inside the
USD package are reused without copying them onto themselves.
