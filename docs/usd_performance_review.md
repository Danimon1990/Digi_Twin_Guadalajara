# USD rendering performance review

Snapshot: 2026-11-02. This reviews the accepted scene version without changing its
appearance. The inventory is a static USD inspection, not an FPS or GPU-memory
benchmark. The active Isaac Sim viewport and hardware were not accessible.

## What the scene actually contains

The `usd/` directory is 19,463,981 bytes (18.56 MiB), including reusable assets
that may not all be loaded. The composed stage uses 31 file-backed layers, 915
mesh prims, 74 material prims, and eight cameras. Cameras do not imply eight
simultaneous renders: extra active viewports/render products would need checking
in the running app.

There are 173,926 triangles counting each composed point-instancer prototype
once. Expanding the 27 table instances gives an approximate 392,078 triangles.
These counts include hidden geometry and omit analytic primitives and runtime
tessellation; they are not GPU memory figures. The screenshot's **Process Memory**
reading refers to application process memory, not a measurement of scene VRAM.
Compressed file size also does not predict memory used by RTX acceleration
structures, render targets, material compilation, caches, or the application.

The 27 tables are already represented by five PointInstancers, each referencing
the same component asset. There are no native scene-graph instance roots and no
payloads. Sublayers organize the scene well, but all are eagerly composed.
Point instancing reduces duplicated data; it does not remove the cost of shading
and tracing visible copies.

Ten local PNGs range from 256×256 to 2048×2048. Local texture resolution is not an
obvious first optimization target. This excludes remote MDL textures and runtime
texture expansion. The layer count itself is also not evidence of a bottleneck.

## Best candidates, in order of investigation

1. **Measure the actual renderer first.** The saved render product requests
   `RealTimePathTracing`, NVIDIA's RTX Real-Time 2.0 mode, and DLSS Performance.
   It is already a real-time renderer; simply suggesting “switch to real-time”
   would miss this. Check active render mode, Ray Reconstruction, resolution,
   many-light sampling, GPU memory and frame time on the same camera. Several
   saved denoiser fields are disabled, but some belong to other renderer paths;
   their presence does not establish that they slow the active renderer.
   `maxVolumeBounces = 15` is not a priority finding without participating volumes.

2. **Simplify the repeated bench/table asset.** Each component has 9,916 triangles.
   Its 27 copies account for 267,732 triangles, about 68% of the expanded estimate.
   Smooth tube bends and beveled parts are good candidates for a lower-detail
   review variant. A target of 3,000–5,000 triangles per set would remove roughly
   133,000–187,000 expanded triangles if appearance remains acceptable. Those are
   geometry reductions, not predicted FPS gains. Keep the current asset for
   close-up renders. A shared prototype or consolidating room instancers could
   reduce composed prim overhead, but RTX may already deduplicate repeated data;
   measure before restructuring the existing editable room groups.

3. **Replace over-detailed perforations on the potato-drain filter.**
   `EQUIP_POTATO_DRAIN_01_FILTER_PLATE/Cube_170` has 41,652 triangles—the largest
   individual mesh and about 24% of the unexpanded mesh triangle inventory.
   Use a low-detail plate with a normal/roughness pattern for distant views,
   retaining actual holes for close-ups. Avoid assuming alpha cutouts are free:
   they can increase ray/shading work. A simpler opaque plate is the cleanest
   first A/B comparison.

4. **A/B test glass and reflective materials.** Showcase glass is bound to 12
   meshes, plus one second-floor glass mesh. Compare the Despacho camera with a
   temporary simplified-glass override, then restore the original. If it changes
   GPU frame time substantially, tune transmission/reflection settings or retain
   a cheaper review material. The screenshot alone cannot prove glass is the
   bottleneck.

5. **Measure lighting rather than blindly deleting fixtures.** The stage has 54
   rectangular room lights, one disk review light, one sun, and one sky dome.
   Fifty-seven lights is not inherently excessive for RTX's many-light sampler.
   Preserve the improved visibility. Compare selected lighting zones or fewer
   larger emitters in a temporary review layer, and verify brightness and shadow
   quality. Merely increasing light intensity does not multiply triangle counts
   or directly establish a performance regression.

6. **Deduplicate small repeated equipment meshes.** Exact local geometry hashes
   identify repeated tray meshes and table parts. Hash matches are only candidates:
   material bindings, normals, UVs and overrides must also be compatible. Merge
   static pieces by material only where it preserves selection and editing needs.
   Never merge the whole building simply to reduce the prim count.

7. **Use payloads or unloadable zones only when load time/memory warrants it.**
   Convert expensive kitchen/detail collections to payloads or a review variant.
   Hiding the roof improves the view but does not unload its composed USD data.
   For this small on-disk package, payload conversion is secondary to GPU profiling
   and the two identified geometry targets.

## Portability and material cleanup

The package checker reaches dependency validation, then fails in standalone USD
on three online MDL references (carpet, car paint, leather). These can require
Omniverse's resolver/network and can affect cold material load/compilation, but
are not proof of steady-state rendering slowdown. The old red leather material
has no effective geometry bindings in this snapshot and can be removed in a
cleanup pass. The gray material and carpet still have users; preserve those
appearances when localizing or simplifying them.

## Suggested benchmark

Use the saved Despacho, Comedor, Patio and Perspective views at the same viewport
resolution. After a warm-up, record median FPS/frame time and GPU memory over a
fixed stationary interval plus the same navigation path. Capture cold-load time
separately. Change one factor at a time: stock Real-Time 2.0 settings, simplified
glass, lighting zones, low-detail table, low-detail drain plate. Restore the
accepted baseline between runs. Keep an optimized review profile only if the
measured gain and visual comparison justify it. No speedup is claimed yet.

## Reproduce and checks

```bash
/home/daniel/scene-venv/bin/python scripts/audit_usd_performance.py --output /tmp/usd-performance.json
/home/daniel/scene-venv/bin/python -m unittest discover -s tests/scene_controls -v
.venv/bin/python -m unittest discover -s tests/operations
```

The machine-readable snapshot is `docs/usd_performance_inventory.json`.
All five scene-control tests and all 50 operations tests pass. The complete USD portability checker remains
blocked by the online MDL resolution described above. Live extension UI and GPU
performance have not been verified in Isaac Sim.

References:
- [NVIDIA RTX Real-Time 2.0: many-light sampling, caching and bounce costs](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/rtx-renderer_rt.html)
- [NVIDIA RTX common settings: geometry deduplication and streaming](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/rtx-renderer_common.html)
- [NVIDIA merge-static-meshes trade-offs](https://docs.omniverse.nvidia.com/extensions/latest/_downloads/08c629e35213d0a1eca5e8ccd2a14281/Merge_Static_Meshes.pdf)

## Authoring structure to improve separately

The accepted root USD now contains Isaac-authored cameras, the support extension,
material/UV overrides, and viewport settings that are not all present in Blender.
A full Blender export recreates that root and can discard these edits. Preserve
this committed USD as the current scene; use targeted refresh commands when needed.
A future pipeline improvement should put user edits in a stronger authored layer
above the generated assembly and move session-specific render settings into a
review profile. That protects edits and makes performance comparisons repeatable;
it is primarily a workflow safeguard, not an FPS optimization.
