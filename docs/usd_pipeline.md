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
│   └── Exterior/PeatonWalks
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

No roof or physics schemas are exported in the current exploration milestone.

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
5. Exports cameras and lights into optional review layers.
6. Builds ingredient references from `config/usd/ingredients.json`.
7. Reopens and validates the composed stage, units, axis, hierarchy, and
   material targets.

Wall meshes are triangulated only in the generated USD. This preserves editable
Boolean cutters in Blender while preventing OpenUSD viewers from filling the
inner loops of door, rectangular-window, and extractor openings. The exporter
also adds two neutral review-only fill lights to `layers/review/lights.usda`;
they remain separate from physical architecture and are not a lighting design.

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
