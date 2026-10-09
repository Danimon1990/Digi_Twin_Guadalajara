# Guadalajara USD package

Open `guadalajara_base.usda` as the canonical entry stage.

- `layers/materials.usda` contains shared materials.
- `layers/architecture.usda` composes floor, wall, column, and stair leaves.
- `layers/areas/` contains Despacho, Cocina, and Comedores manifests.
- `layers/areas/stations/` contains station-level geometry leaves.
- `layers/review/` contains optional cameras and lights.
- `layers/assets/ingredients.usda` contains reference-based ingredient placements.
- `textures/` contains portable textures referenced by the material library.

`assets/guadalajara_architecture.usdc` and `assets/textures/` are retained as
legacy monolithic-export artifacts for compatibility. They are not composed by
the canonical entry stage and can be removed in a later cleanup after downstream
consumers confirm migration.

Regenerate the package from Blender with:

```bash
blender --background blend/guadalajara_base.blend --python scripts/export_layered_usd.py
```

See `docs/usd_pipeline.md` for hierarchy and ingredient publishing rules.
