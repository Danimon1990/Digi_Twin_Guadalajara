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
  abandonment, two servers, one cashier, shared food access, cutting, finishing,
  basket splitting, conditional packaging, handover, configurable payment/server
  release relationships, cashier assistance, deterministic seeds, and cutoffs.
- Runnable `python -m operations demo` command and synthetic scenario fixture.
- Observation preparation slice: registered camera/manual sources, explicit
  cross-source alignments, coverage gaps, multi-clip event evidence, and an
  idempotent JSONL importer with line-level errors.
- Spanish field protocol, camera registry template, importable test example,
  and presentation outline for the initial 3D-to-operations narrative.
- Read-only, dependency-free 2D HTML playback generated from a saved simulation
  run, using a clearly non-measured schematic based on the 2026-10-09 flow sketch.

## Tested

- See `tests/operations/`; exact execution results belong in the session handoff.

## Next

- Capture and register the first authorized service session without personal data.
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
