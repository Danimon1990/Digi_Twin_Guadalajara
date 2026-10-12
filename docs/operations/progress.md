# Operations progress

## Implemented

- Milestone authorization and scope documentation.
- Standard-library typed records for runs, catalog, people, queues, orders,
  fulfillment components, resources, activities, containers, and payments.
- Validated event envelope with simulation/observation clock separation.
- SQLite schema v2, typed setup repository, identity registry, transactional
  recorder, idempotency conflicts, sealing, source-time activity projections,
  cursor reads, post-commit subscribers, and integrity checks.
- Milestone B synthetic dispatch engine using SimPy 4.1.2, with customer
  abandonment, configurable serving staff, dedicated cashier/soup/fryer roles,
  shared food access, cutting, finishing,
  basket splitting, conditional packaging, handover, configurable payment/server
  release relationships, cashier assistance, deterministic seeds, and cutoffs.
- Runnable `python -m operations demo` command and synthetic scenario fixture.
- Observation preparation slice: registered camera/manual sources, explicit
  cross-source alignments, coverage gaps, multi-clip event evidence, and an
  idempotent JSONL importer with line-level errors.
- Spanish field protocol, camera registry template, importable test example,
  and presentation outline for the initial 3D-to-operations narrative.
- Read-only, dependency-free 2D HTML playback generated from a saved simulation
  run. Its current layout consumes a reproducible meter-scale geometry snapshot
  extracted from the canonical Blender scene, validates worker access points,
  separates worker footprints, follows a route graph, and reports modeled
  distance per worker.
- Client journey distinguishes payment from handoff: takeaway departs after
  receipt, while dine-in uses the back-door handoff by `Mesas_trabajo 1.004`
  before continuing toward the comedor.
- Canonical versioned menu-price catalog with explicit commercial portions,
  confirmation status and provenance. Incorrect provisional prices were removed;
  simulations derive line/payment amounts only from confirmed catalog entries.

## Tested

- See `tests/operations/`; exact execution results belong in the session handoff.

## Next

- Capture and register the first authorized service session without personal data.
- Confirm the exact Blender object(s) or endpoints for the fryer station; the
  current upper cooking-line group remains explicitly unclassified.
- Replace synthetic worker envelope and route nodes with agreed values, then add
  shift length and demand profiles for daily walking-distance estimates.
- Milestone C: persisted-data reports, process-mining exports, and read-only replay.
- Then complete Milestone D with the protected localhost service and reconnecting
  live monitor; the manual importer was advanced early to support field capture.

## Deferred

- Reports/replay, observation HTTP service/monitor, and USD/Isaac bindings.
- Applying corrections; history editing is disabled.
- Full production/inventory, pedestrian routing, computer vision, real payment,
  remote networking, and hardware control.

## Environment

Python 3.14.2 is present. SimPy 4.1.2 is installed in the project-local `.venv`.
Pytest, Pydantic, FastAPI, and pxr are not installed; the suite uses `unittest`.
