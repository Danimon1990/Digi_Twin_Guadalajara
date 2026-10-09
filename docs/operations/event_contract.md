# Event contract and persistence policy

Schema version `ops_event_v1` uses an immutable `DomainEvent` envelope. Simulation
events use logical seconds only. Observations use a timezone-aware UTC occurrence
time or a source-local offset; the recorder never invents a wall clock for video.
`recorded_at_utc` and the monotonic `recording_cursor` are assigned by storage.

Supported correlated activity sequences are request/start/complete,
request/start/cancel, request/cancel, start/complete, and partial observed
start, complete, or cancel records. `instant` events are not correlated. An
activity always has its own `activity_id`, including repeated product picks.

Events arriving out of receipt order are retained. Activity projections are
rebuilt from source time, with recording cursor as the deterministic tie-breaker.
Wall-clock timestamps and video offsets from different sources are not asserted
to be mutually aligned; cross-source analysis must supply an explicit alignment.

The source tuple `(run_id, source_id, source_event_id)` is the retry identity.
Identical content returns the existing cursor. Different content raises an
idempotency conflict. Recorder timestamps and caller-generated `event_id` values
are excluded from that comparison.

Sealing records the cutoff and rejects new history. Identical retries are still
acknowledged. Corrections are represented by `correction_of_event_id`, but no
correction application/editing behavior exists in Milestone A. Amendments must
use a new run linked by `parent_run_id`; history is never silently edited.

Catalog, worker, station, queue, and resource identities are shared across runs;
an identical definition is reusable and a conflicting definition is rejected.
Visit, order, line, and component instance IDs are namespaced by `run_id`, so
repeating the same stored workload in one database creates separate history.

SQLite is initialized non-destructively at schema version 2 with foreign keys
enabled. Version 2 adds observation sources, cross-camera alignments, coverage,
and per-event evidence clips. A version 1 database is backed up before automatic
migration. A database containing operations tables without migration metadata,
or a newer schema version, is rejected instead of guessed or overwritten. Event,
event-object links, evidence links, and the activity projection commit in one transaction.
Subscribers run only after commit and may catch up by cursor after failure or
disconnect. A process-held OS file lock gives each database one active
`EventRecorder`; a second history writer is rejected. Entity setup through the
typed repository is an offline setup step and must finish before the recorder
service takes ownership.

Observation metadata is immutable by stable identity: identical source,
alignment, coverage, and event records can be retried, while conflicting reuse
is rejected. A single event may cite clips from several registered camera
sources. Coverage explicitly records visible, partial, occluded, or missing
intervals. A JSONL import continues after line-level errors but does not seal a
run unless every non-empty line succeeds.
