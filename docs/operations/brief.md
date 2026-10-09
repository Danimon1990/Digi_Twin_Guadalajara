# Operations foundation

The implementation authority and detailed acceptance criteria are recorded in
`GUADALAJARA_CODEX_OPERATIONS_PROMPT.md`. This brief keeps the project rules
discoverable without duplicating that prompt.

## Current sequence

1. Typed domain records, event contract, SQLite schema, and transactional recorder.
2. A deterministic, resource-based dispatch/service simulation.
3. Reports and read-only replay from persisted data.
4. Local observation import/service and a reconnecting live reader.
5. Non-destructive USD bindings and an optional viewer adapter.

Only dispatch/service is in the first simulator. Full production, inventory,
computer vision, pedestrian routing, real payments, public networking, and
hardware control are deferred.

## Evidence and safety

- Every run and event distinguishes synthetic, observed, reported, or inferred evidence.
- Synthetic fixtures are not restaurant observations.
- Unknown prices, masses, durations, distances, and staffing remain null or explicit assumptions.
- Core domain/storage/report code must not require Blender, USD, Isaac Sim, or a GPU.
- The canonical architecture and source evidence are read-only to operations code.
