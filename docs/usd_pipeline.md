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
├── Lighting/Interior               54 linear emitters with visible tubular fixtures
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
these fixtures remain independently mutable and use provisional placement and power.
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

## Roof curve thickness and room fixtures

The earlier roof-finish export wrote 20 beveled Blender curves as 40 USD
BasisCurves (duplicate paths), with widths of 2 metres. Blender bevel radii were
0.022–0.028 m for the patio structure and 0.025 m for flashing; the USD width
lost that bevel profile. The exporter now temporarily creates evaluated mesh
copies, exports each once, and restores the editable curves. World-space mesh
bounds have been checked against Blender to within 0.1 mm.

`build_interior_lighting.py` creates visible 50 mm diameter tubular diffusers
and narrow downward rectangular emitters. Fixtures are up to 1.2 m long, arranged
on room-guide grids of at most 3 m spacing. Both dining polygons, both kitchen
zones, bathrooms, storage and covered patio positions are included. Tube ends
and centres are checked against the evaluated ceiling; uncovered patio grid
positions are skipped. There are currently 54 fixtures across 12 named zones.
Colour and power are presentation settings, not a calibrated illuminance design.

To rebuild only these leaves while retaining local Isaac Sim root-layer edits:

```bash
blender --background blend/guadalajara_base.blend --python scripts/build_interior_lighting.py
blender --background blend/guadalajara_base.blend --python scripts/export_layered_usd.py -- --roof-lighting-only
```

The targeted export updates roof finishes, interior lighting and any new shared
materials. The full export still regenerates the composition root. Save any
Isaac Sim session edits before reloading updated layers. Package validation may
require Omniverse asset resolution when local edits reference online MDL materials.

### USD sunlight and brightness

`build_stage_daylight.py` adds a separate `Lighting/Daylight` layer with a
warm distant Sun (intensity 2500, angle 1 degree) and a cool SkyFill dome
(intensity 250). Interior rectangular emitters receive an absolute +4-stop
USD exposure boost (16 times exported power) for the darker stage viewport.
The full exporter and targeted refresh both reapply these settings. To tune
brightness, edit the values in this script and rerun with a Python runtime
that provides `pxr`. This preserves existing root-layer camera and material
edits. Viewport exposure and renderer settings still affect perceived brightness;
these USD presentation adjustments do not change Blender's render lighting.

The saved perspective and scene cameras used f/5 and a 0.02-second exposure;
the scene camera explicitly disabled auto exposure. The daylight builder now
sets `exposure = 4` on `/OmniverseKit_Persp` and `/Guadalajara/Camera`, with
manual exposure enabled, to compensate for the dark interior view. Camera
compensation is separate from light exposure. This is a provisional adjustment;
a running Isaac Sim session may retain stronger session-layer camera settings.
The active viewport must be checked after reload before judging the result.

Perspective navigation now uses auto exposure instead of the fixed +4 camera
compensation above. The named scene camera keeps its manual setting. Perspective
histogram clamping is disabled so dark interior pixels participate in metering.
For an already-open viewport, run `scripts/enable_perspective_visibility.py` in
Isaac Sim's Script Editor. It discovers the actual active viewport camera and
sets its session-layer exposure controls, without moving the camera, saving
unrelated edits, or assuming that the camera is `/OmniverseKit_Persp`.
This runtime helper is syntax/composition tested but requires visual validation
inside the user's running Isaac Sim instance.

## Dining-room point instances

`scripts/build_dining_instances.py` places the reusable table with two integrated
benches as two USD PointInstancers under
`/Guadalajara/Areas/Comedores/Stations/Furniture/DiningSets`:
`MainDining` and `RaisedDining`, each with nine sets in three aligned rows.
The current trial scales the footprint to 1.25 × 1.511 m while retaining the
original table and seat heights. The standalone source asset is unchanged.
Their prototype references `assets/furniture/comedor_bench_table/comedor_bench_table.usdc`.
The dedicated `layers/areas/dining_instances.usda` layer is composed by the comedor
manifest; the full exporter regenerates it after building the stage.

Placement uses the main floor edge for alignment, checks each full asset footprint
against the room polygon with at least 0.30 m boundary clearance, and grounds the
asset's lowest point on the appropriate floor surface (0.002 m and 0.08 m).
Row gaps are approximately 0.78 m in the main room and only 0.275 m in the raised
room; column gaps are approximately 1.39 m. The raised-room row gaps are too tight
to count as walking aisles. This is the requested three-row visual trial, not a
final circulation layout. `TARGET_SHORT_SIDE`, `ROW_COUNT`, and `COLUMNS` in the
generator control the trial; row centres are fitted to the actual floor polygons.
The arrangement is provisional, not a surveyed seating or accessibility plan. World-space checks found no intersections with
exported wall triangles or neighbouring sets. No pre-existing furniture was removed.

Regenerate with a Python environment providing `pxr`:

```bash
python scripts/build_dining_instances.py
```

### Additional cone-marked dining spaces

`build_cone_dining.py` adds one table/bench point instance at each saved top-level
`/Guadalajara/Cone*` marker. The current three markers create three extra sets,
using the main dining instances' reduced footprint and orientation. Floor-mesh
intersections determine grounding rather than the marker's elevated Z position.
`layers/areas/cone_dining.usda` contains the instances and reversible visibility
overrides hiding the markers; the source markers and their transforms are retained.
The comedor manifest composes this layer, and full exports preserve its inclusion.
To relocate these extra sets, reveal/move the marker cones, save, and rerun the
builder with a Python environment providing `pxr`. This does not regenerate the
18 existing room instances. Current placements pass wall intersection checks.

### Cube-marked dining areas

The later cube-area layout supersedes two of the original single-cone placements.
`config/usd/dining_areas.json` records the horizontal centre-plane footprints of
`/Guadalajara/Cube` and `/Guadalajara/Cube_01`, including the second marker's
rotation. Both cubes have been removed from the composed stage as requested;
their original USD specs are retained in `config/usd/dining_area_markers.usda`.

Run `scripts/build_marked_dining.py` with a `pxr` Python runtime to rebuild
`layers/areas/marked_dining.usda`. It tries aligned grids in two orientations,
using at least 0.60 m between sets and 0.15 m inside the marked boundary, then
rejects positions without level floor support or with wall, column or stair
intersections. These are provisional layout assumptions. The resulting layouts
have two sets in SmallDining and six in PatioDining. This is a practical grid
layout, not a proof of maximum capacity or a surveyed circulation design.

`build_cone_dining.py` now excludes markers inside those recorded areas to avoid
duplicate tables. Only the Cone_02 placement remains, giving 27 total sets:
18 in the original dining rooms, eight in the marked areas, and one standalone.
All cone markers remain hidden. The full exporter retains the generated marked
area layer; the footprint configuration survives removal of the cube markers.

## Back door on WALL_002

`build_back_door.py` fits a closed door, frame, threshold, three hinges, and
handles on both sides into the pre-existing `OPENING_DOOR_WALL_002_01` opening.
The USD assembly is `/Guadalajara/Architecture/Walls/WALL_002/BackDoor`, in
`layers/architecture/back_door.usda`. The wall mesh, opening, and existing wall
materials remain unchanged. Door/frame use the existing white paint; hardware
uses the existing stainless material. Opening bounds were derived from the
exported jamb/header vertices (approximately 1.0 × 2.04 m in world space).
`HingedLeaf` has a rotateZ operation for posing; no articulation/physics is added.
The full exporter regenerates this layer. Dimensions remain provisional.
