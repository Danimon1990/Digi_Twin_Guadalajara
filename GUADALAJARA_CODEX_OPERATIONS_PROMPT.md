# Guadalajara — Implement the operations foundation in the existing project

You are my Python, discrete-event simulation, and OpenUSD engineering collaborator.

Work inside this existing repository. The architectural Blender/USD model is nearly complete. Do not rebuild the restaurant. This task authorizes the next milestone: an operational data model, persistent event recording, and a small working dispatch simulator, followed by local observation ingestion and a non-destructive scene adapter.

Implement working code and tests, not only another plan or collection of empty classes. Build the milestones below sequentially, validating each before expanding. Preserve my existing work.

## 1. Inspect the repository before editing

Read the applicable AGENTS.md files, README, environment/dependency files, relevant source code, and existing project documentation. Inspect Git status where available; preserve all unrelated and uncommitted changes.

Look for these previously prepared files, but do not assume they exist locally:

- GUADALAJARA_OPERATIONS_DATA_MODEL_V1.md
- event_recorder_demo.py
- test_event_recorder.py
- GUADALAJARA_CODEX_MASTER_PROMPT.md
- GUADALAJARA_OPERATIONS_V1.zip or its extracted directory

Read and reuse compatible work. The earlier recorder example, if present, is a storage demonstration with explicitly supplied events, not a complete simulator. Run its existing tests before refactoring; do not claim they pass without execution. If those files are absent, proceed from this brief and report their absence.

An earlier project brief may restrict work to architectural Phase 1. This current request authorizes the operations milestone. Update the project-specific milestone description while retaining its measurement, preservation, and safety rules. Do not change global agent configuration or unrelated instructions. Keep AGENTS.md concise and link to the full brief rather than copying this entire document into it.

Discover the actual Python environment and optional Blender/USD/Isaac tools. Follow repository packaging conventions. Do not upgrade Isaac Sim, modify system Python, or install large GPU dependencies. Use an isolated project environment for permitted dependencies and respect approval requirements.

Do not overwrite .blend files, original USD assets, reference photographs, existing observations, or databases. Back up any existing database before an explicit migration. Create new output paths for demonstrations.

Start with a brief inventory, a proposed implementation sequence, and genuine blockers. Then continue implementing safe, authorized work without waiting for approval of every ordinary file creation.

## 2. Business goal and scope

The client is Restaurante Guadalajara in Fontibón, Bogotá. I coordinate remotely from Los Angeles.

The restaurant sells fritanga/picadas assembled from portions of different products. Morcilla/rellena is the signature product. Other examples include longaniza, papa criolla, plantain, arepas, chicharrón, and meats. Two preset offers exist: Picada Insaciable and Picada Doña Chela. Use verified local catalog information; do not invent their recipes, exact prices, or portion weights.

The building grew from a former house. An internal production kitchen replenishes a compact front dispatch area through shared circulation. We want to investigate service times, access to shared products, finishing work, queues, payment, and eventually spatial alternatives.

The existing shared architecture must support different operating configurations: Wednesday cleaning, Thursday production, Friday/Saturday service, Sunday peak, and holiday service. Implement dispatch/service first. Do not attempt the complete weekly production operation now.

### Reported dispatch behavior

A server usually takes the next customer and handles the order from selection through finishing. After gathering products, she may cut them, add salt/ají, divide them among baskets, separate products, and package takeaway orders. The owner estimates finishing can take a couple of minutes; this is not a measured universal duration.

The restaurant reports keeping chicharrón separate from steamy meats to preserve texture. Represent this as a configurable business packaging rule, not a thermal simulation or safety certification.

Cashiers also provide bags/napkins, assist customers, resolve problems, and verify payment. Other roles include frying/heating, soup service, replenishment, and general assistance. Approximately 8–9 people were reported in the compact area, but exact staffing and assignments remain unverified.

Payment timing, handover timing, and when a server becomes free must be independently configurable until validated. Do not automatically hold the server through the customer's payment or dining time.

### Questions the system should support

How long do visitors wait? Who abandons before ordering? Which activities consume order time? How much is travel versus resource waiting versus handling? How do quantities and packaging affect time? Which resources are occupied? How do walk-in/online channels and dine-in/takeaway/delivery differ?

All results must distinguish measured observations from reported estimates and synthetic simulation assumptions. Do not claim a simulation has discovered Guadalajara's actual bottleneck or proven financial savings.

## 3. Architecture and responsibilities

Use these separate responsibilities:

- Python classes/dataclasses: entities, relationships, rules, and state transitions.
- JSON: versioned scenario configuration and interchange, not the main transaction history.
- SQLite: durable events, entity relationships, and queryable operational projections.
- SimPy: the first discrete-event engine, unless the repository already contains a suitable tested alternative; explain any substitution.
- OpenUSD: shared spatial representation and entity bindings, not an event database.
- Isaac Sim: optional visualization/replay through an adapter, not a prerequisite for the core.

The domain, storage, simulation, and analytics code must import and run without omni, isaacsim, pxr, Blender, or a GPU.

Use one straightforward application/service, not microservices, Kafka, distributed event sourcing, or a custom full Isaac distribution. Prefer composition over deep inheritance. Products are instances of Product, not one subclass per food. Roles are assignments, not subclasses of a person.

Use one EventRecorder write path:

    simulator or observation input
        -> validation / application service
        -> EventRecorder
        -> committed SQLite transaction
        -> projections, reports, live readers, scene adapter

Simulation commands request actions; accepted events describe what happened. Observed events report the real world and must not be resimulated to fit our assumptions. Flag observed capacity conflicts for review rather than changing observations to fit a hypothetical capacity.

## 4. Data model

Implement the records needed for the MVP with explicit types and validation. Separate static/versioned catalog data from run-specific instances and state. Use stable business IDs; a USD prim path is a binding, not the identity itself.

### Runs and provenance

Run: run_id, kind (simulated or observed), scenario_id, status, schema/model/layout versions, effective configuration snapshot, seed when simulated, source dataset/reference, parent_run_id when appropriate, is_test, creation time, and analysis cutoff/stop metadata.

Every new simulation gets a new run_id. Preserve the effective configuration so later JSON edits do not change the interpretation of an old run.

Replay is a read-only mode over an existing run, not a new observed session and not a source of duplicate events.

Use evidence labels such as synthetic, observed, reported, and inferred. Preserve source references and missing-data indicators.

### Products, offers, and orders

Product: product_id, name, category, sale_unit, default_price_cop if known, optional portion mass with provenance, and handling/packaging tags.

MenuOffer / OfferComponent: a versioned preset offer and its physical ingredients/choices. Preserve the commercial offer separately from its preparation components.

Order: order_id, run_id, optional visit_id, channel, fulfillment_mode, primary_server_id, and separate preparation/payment/fulfillment states.

Keep these milestones distinct: created, service_started, items_selected, ready, handed_over, payment_confirmed, closed, and server_released where applicable. Missing milestones stay null.

channel: walk_in, online, phone.
fulfillment_mode: dine_in, takeaway, delivery.

Do not make online synonymous with delivery.

OrderLine: line_id, order_id, product_id OR offer_id, quantity, unit, unit_price_cop snapshot, discount_cop, and selected options.

FulfillmentComponent: component_id, line_id, product_id, required quantity/unit; selected quantities derived from effective events. One component may require multiple picks; multiple portions may also be served in a single pick.

Do not double-count preset revenue by charging its physical components again. Do not alter historical order prices when the catalog changes.

Use integer COP amounts, explicit quantity units, seconds, and meters. Unknown is null, not zero. Do not infer grams per portion or reconstruct unreadable prices.

### People, roles, and customer queues

Worker: worker_id, eligible_roles, optional operational display code.
Shift: shift_id, worker_id, planned/observed start/end and breaks, scoped to a run.
RoleAssignment: worker_id, role, optional station_id, and effective interval.

Roles: ORDER_SERVER, CASHIER, FRY_OPERATOR, SOUP_SERVER, RUNNER, SUPPORT.

One worker remains one capacity-limited person across roles. Do not reserve the same person twice through separate role pools. Record the role on each activity as it occurred. Assignments express eligibility; actual tasks establish workload.

CustomerVisit: visit_id, run_id, optional party_size and queue_participants, arrival/departure, outcome. A visit can produce zero, one, or multiple orders. A group of six may have one person queuing and one order.

Queue / QueueVisit: queue identity/type, visit or order reference, entered time, service start, departure, outcome. Distinguish ordering, pickup, and cashier queues from employees waiting for shared resources.

A visitor abandoning before ordering must be measurable without an order_id. Do not require personal names, faces, phone numbers, or identification documents.

### Work, resources, containers, and payment

Station: station_id, zone_id, location/binding, and configuration-specific access points.
Resource: resource_id, station_id, type, capacity, availability. Model worker availability separately from tray access, utensils, cutting positions, packing positions, and cashier resources.

A single tray does not prove effective capacity one. Capacity one is permitted in synthetic fixtures, clearly labeled as an assumption.

ActivityInstance: activity_id, type, related order/component/worker/role, request/start/end, state, quantity/unit, and reason where needed.
ResourceAllocation: resource, activity, acquired/released times, and reserved units.

Keep resource occupancy separate from the total activity interval. Release tray access when it is actually released, not automatically after every downstream motion ends.

Container / ContainerContent: baskets, boxes, bags, parent-container relationships, contents, and packaging state. Prevent contents being double-counted in both a basket and its parent bag.

Payment / PaymentAllocation: payment_id, cashier/register, integer amount, method, status, confirmation time, and allocations to orders. Implement the initial one-order payment path, while retaining a clean allocation relationship for future splits. Do not process real payments or store credentials.

Orders served, prepared order value, confirmed receipts, and worker utilization are derived results, not permanent counters on Worker. Keep primary-server attribution and assisting contributions separate.

Defer full recipe/batch inventory, table occupancy, computer vision, and automated hardware control. List the extension points without creating an empty class for every future feature.

## 5. Event contract and persistence

Define a validated DomainEvent envelope containing:

    event_id
    schema_version
    run_id
    activity
    lifecycle
    activity_id, when applicable
    sim_time_s, simulation only
    occurred_at_utc, observation when known
    recorded_at_utc, assigned by recorder
    source_id
    source_event_id
    evidence
    source_ref and source_offset_s, where applicable
    objects: typed IDs with relationship qualifiers
    payload: activity-specific validated data

Lifecycle values may include request, start, complete, cancel, and instant. Implement only supported transitions and document them. Correlate every multi-stage activity using its own activity_id, including repeated picks of the same product.

Use events plus event_objects so a single event can relate to worker, order, product, station, and container without duplicated history rows. Validate object references through a suitable registry or equivalent typed repositories.

Store run metadata and needed entity/projection tables alongside the log. Inspect existing schema before migration. Enable referential-integrity checks. Add indexes for run/time, activity, object lookup, and source-event deduplication. Provide an explicit schema version and non-destructive migration path.

A recorder transaction must atomically save the event, links, and any eagerly maintained projection updates. Notify subscribers only after commit. A failed subscriber must not make a persisted event appear unwritten; readers must be able to catch up from durable history.

Use one controlled writer per database for this MVP, with safe connection/thread ownership. Do not let HTTP handlers share a SQLite connection unsafely. A headless demo writer and the ingestion service must not independently own the same database at once: enforce exclusive writer ownership or route writes through the service. Persist continuously, not only on Stop. Use a monotonically increasing recording cursor for polling; event time alone cannot safely identify newly received late events.

Identical retries with the same source identity must be idempotent. Reusing an identity with different content must raise a clear conflict. Recorder-generated fields such as recorded_at must not turn a legitimate retry into a conflict.

Reject malformed IDs, non-finite times, invalid units, negative quantities, and invalid payloads with useful errors. Preserve partial observations; never fabricate missing starts/ends. Handle out-of-order arrival while a session remains open, and reconstruct projections using source-time semantics with explicit tie handling.

No silent history edits/deletions. Include a correction-reference design. If correction application is deferred, disable editing rather than pretending the history is correctable already, and list this limitation.

Seal sessions explicitly. Identical retries can be acknowledged without change after sealing; new historical input needs a documented amendment/reopening path, not silent insertion. A database failure must be visible and must not silently discard events.

## 6. Time and stopping rules

In simulation, use one authoritative logical clock. Rendering, report refreshes, real-time pacing, and replay speed must not determine service durations.

In observations, preserve occurrence time separately from receipt time. Store timezone-aware UTC and display America/Bogota when needed. For video without a known wall-clock anchor, retain source ID plus video offset rather than assigning a false time. Do not subtract offsets belonging to unrelated videos without an alignment.

Do not use observation ingestion to generate the missing events that a simulator would expect. Mark uncertainty and coverage.

Stop/interrupt must flush committed work and report the analysis cutoff. Open activities, customers still waiting, and unfinished shifts stay visibly incomplete/censored. Do not invent complete or shift_end events.

A replay never writes operational events. Pausing a live viewer must not pause observation capture. Resetting a simulation creates a new run rather than clearing an existing one.

## 7. Implement an actual dispatch simulator

Begin with a small SYNTHETIC_TEST scenario: two order servers, one cashier, a few products, one shared morcilla-access resource, cutting/packing resources, customer arrivals, and both dine-in and takeaway orders.

Generate events from actual scheduled processes and resource acquisition/release, not from a prerecorded list of desired output timestamps.

Implement this configurable workflow:

    arrival -> ordering queue -> server assignment -> order taking
    -> product picks -> cutting -> seasoning -> basket splitting
    -> required packaging -> ready/handover

Payment/verification and server release have explicit configurable relationships to this workflow. Pick one documented synthetic baseline; do not present it as confirmed restaurant practice. Add at least one cashier-assistance task that occupies the same cashier without increasing sales.

For each selection, distinguish product request, travel to station, request for access, waiting for access, handling, depositing, and completion as far as the modeled data permit. Waiting for access must not include unrelated prior work. Track known resource-allocation intervals independently.

Support quantities and configurable duration models. Start with fixed durations for deterministic tests and a seeded bounded distribution for illustrative scenarios. Keep setup time distinct from per-portion effort where configured. Use documented assumptions, not fitted claims without measurements.

Model finishing work separately from food selection. Packaging depends on fulfillment mode, components, and containers. Include a fixture demonstrating the reported chicharrón separation rule.

Do not model full frying/production yet. Support the role vocabulary and explicit resource unavailability/interruption reasons; declare whether product supply is assumed unlimited in the demo. Do not invent inventory analytics without stock events.

Travel may initially be a configured duration. Distance remains unknown unless a supported route distance exists. Do not infer walking through walls from straight-line positions. Abstract resource queues are not a validated pedestrian-congestion model.

Avoid worker/resource deadlocks. Document resource acquisition/release rules and test that incompatible tasks cannot overlap on one worker. Optional passive equipment phases must not reserve the operator unnecessarily.

Use deterministic seeds and a stored arrival/order workload. Re-running identical inputs should reproduce logical outputs, excluding run IDs and recording timestamps. Keep demand randomness separate from optional presentation behavior.

## 8. Reports, replay, and process mining

Produce reports from saved data, not solely from live mutable objects. Reopening the database in a new process must be sufficient to reconstruct results.

Report by run and explicit analysis window:

- Visits/persons/orders separately; unknown group sizes remain unknown.
- Queue waiting, abandonment, number still waiting, maximum queue, and time-weighted mean queue length.
- Selection, finishing, packaging, ready/handover, and payment milestones by order.
- Product frequency by distinct order, portions, number of picks, and handling/waiting by quantity.
- Worker/role active time, travel, blocking, assistance, and availability, with declared non-overlapping or explicitly overlapping accounting rules.
- Resource occupancy and utilization using occupied capacity over available capacity, not naive summed task durations.
- Primary-server prepared order value versus confirmed payment receipts; never sum every helper's attributed order value as total sales.

Include sample counts, missing values, assumptions, incomplete cases, mean, and P50/P90 where computable. State the quantile convention. Do not silently treat incomplete durations as completed samples, or sum concurrent tasks as sequential elapsed time.

Export per-run summary JSON, readable Markdown, and CSV tables. Include an order-centric process-mining export with:

    case:concept:name = run_id + order_id
    concept:name
    time:timestamp
    lifecycle:transition
    org:resource
    activity_id
    source/evidence

Preserve starts and ends. Provide a visit-centric view for pre-order queue/abandonment. Do not invent order IDs for replenishment or assistance tasks that serve no specific order.

For simulated timestamps, document an explicitly synthetic epoch plus logical seconds. For unanchored observations, preserve relative timing in a separate export rather than pretending dates are known.

Keep event-object relationships for future object-centric mining; do not claim OCEL compliance without a tested exporter. PM4Py should remain optional; CSV export must work without it.

Implement a read-only replay with adjustable pacing and a recording-cursor live reader. The same saved run must produce identical business metrics regardless of playback speed.

## 9. Local observation ingestion and live updates

After the headless simulator and storage/report tests work, implement a minimal local input path through the same validation/recorder service.

Required: a manual JSONL observation import with line-level errors and stable retry identities, and a small local HTTP API or equivalent existing service for registering a run/entities, submitting events, reading events after a cursor, and reading current metrics.

Reuse the existing web stack if suitable; otherwise a small optional FastAPI service is acceptable. Keep it optional to the headless engine and use one service/writer process initially.

Bind to localhost by default. Keep ingestion protected with an environment-provided development token; no hardcoded secrets. Do not expose the service publicly, configure tunnels, deploy remotely, or connect real payment systems. Document that remote Bogotá-to-Los-Angeles use requires a separate authenticated transport/deployment decision.

Provide a tiny console live monitor or simple read-only page showing run kind, last committed event, queues, resource state, and completed/paid counts. Prefer the console monitor over building a large frontend.

Use a clearly labeled test producer to demonstrate updates. Never describe generated sample observations as actual restaurant data. Observation-schema test fixtures must carry synthetic evidence and is_test=true, preferably in a separate test database; exclude them from real-observation reports by default. Pausing/disconnecting the monitor must not lose input; demonstrate catch-up after reconnecting by cursor.

Do not share the SQLite file through a remote synchronized/network folder. The service owns the database; clients send validated messages.

## 10. Non-destructive OpenUSD / Isaac adapter

Define and test a small viewer-facing interface for snapshots/events and entity bindings. The core must not import graphics libraries.

Create a binding file containing entity_type, entity_id, layout_version, and actual usd_prim_path when verified. Discover paths from the existing stage; leave unresolved bindings null and report them rather than inventing paths.

If pxr is available, validate bindings, stage units/up-axis, and referenced prims. Use a separate session/overlay layer for runtime appearance, labels, status, and optional simple proxies. Keep original architecture, white walls, maroon floor materials, and operating-state layers intact.

Implement a minimal standalone viewer/replay entry point only when the installed Isaac environment permits testing. Verify available APIs locally; do not assume an Isaac version from old notes. Apply stage changes on the appropriate application/update thread, not directly from arbitrary HTTP callbacks.

Start by reflecting station occupancy, worker state, and queue counts. Do not make attractive pedestrian animation a prerequisite. Do not derive business time from interpolation, render FPS, or viewer sleep calls.

When the graphics runtime is absent, provide the tested headless snapshot/binding adapter and a documented optional viewer entry point, explicitly labeled untested where applicable. This must not block or break the working operations deliverables.

## 11. Implementation milestones and interfaces

Adapt names to the existing repository rather than creating a competing project. Suggested responsibilities:

    operations/domain/
    operations/engine/
    operations/storage/
    operations/capture/
    operations/analytics/
    operations/adapters/
    operations/cli.py
    config/operations/
    tests/operations/
    docs/operations/
    data/operations/
    reports/operations/<run_id>/

Milestone A: inspect/preserve; domain records; recorder; schema; validation and storage tests.
Milestone B: working resource-based dispatch simulation; finishing, packaging, payment, role constraints, and deterministic tests.
Milestone C: persisted-data reports, process-mining exports, and read-only replay.
Milestone D: manual/local event input, minimal local service, and live monitor with reconnect.
Milestone E: bindings and optional USD/Isaac integration without changing architecture.

Proceed in this order. Keep a short progress file with implemented, tested, blocked, and deferred items so another session can resume precisely. Do not stop after producing documentation when executable work is possible. Do not label deferred features as implemented.

Provide a real CLI, using the repository's conventions. Suggested commands are:

    python -m operations demo --scenario <file> --db <path> --seed 42
    python -m operations report --db <path> --run-id <id> --out <directory>
    python -m operations replay --db <path> --run-id <id> --speed 10
    python -m operations import-observations --input <jsonl> --db <path>
    python -m operations serve --db <path> --host 127.0.0.1
    python -m operations monitor --run-id <id> <documented connection options>
    python -m operations validate-bindings --bindings <file> --stage <usd>

These are requested interfaces, not commands that already exist. Adjust names if necessary and provide the exact tested equivalents. Never display success for an unsupported optional command.

## 12. Acceptance tests and handoff

Add automated tests covering:

1. Capacity-one resource allocation does not overlap in simulation.
2. Two requests at t=0 and t=3 with service durations 10 and 12 seconds yield starts at 0 and 10, completion at 10 and 22, and waits 0 and 7. Produce these through the engine, not hardcoded history.
3. One worker cannot perform two attention-requiring tasks through different roles simultaneously.
4. Quantity handling, finishing, packaging, payment, and server release have distinct supported milestones.
5. A visitor can abandon without an order; party sizes do not inflate order counts.
6. A combo expands into components without double-counting revenue; container nesting does not duplicate food quantities.
7. Cashier assistance consumes capacity but adds no payment amount.
8. Identical retries do not duplicate history/projections; conflicting reuse is rejected, including retries after session sealing.
9. Events survive database close/reopen; a failed write leaves no partially linked event/projection.
10. Unknown/missing times remain missing, invalid/non-finite input fails clearly, and observation/source clocks remain distinct.
11. Stop reports incomplete tasks/shifts rather than fabricating completion.
12. Replay/live viewing does not append operational events or alter sales.
13. Seeded logical results and reports are independent of playback/render pacing.
14. Metrics remain scoped to their run; observed and synthetic data never merge accidentally.
15. Out-of-order input is handled according to the documented policy and a reconnecting reader catches newly recorded late events.
16. Local input authorization and malformed-event rejection work; the demo does not require an external service.
17. The core and reports work without USD/Isaac, unresolved bindings are reported, and original scene assets remain unchanged.

Use isolated temporary databases for tests. Do not run tests against real observation data. Run pre-existing relevant tests as well as new ones. If any test cannot run, say exactly why; do not fabricate test output.

Deliver actual code, configuration examples, schema/migrations, tests, a synthetic demonstration run, saved reports, and a concise README explaining who writes each event, where the database lives, how to replay it, and how to replace assumptions with observations.

End with exact created/modified paths, commands executed and outcomes, database/run/report locations, remaining assumptions, and tested versus untested graphics integration. Include a short prioritized list of measurement questions in Spanish for the family.

Do not commit/push, upload restaurant data, expose a public endpoint, execute payments, or control equipment unless I separately authorize it.

The immediate definition of success is:

A customer joins a queue; a server prepares a multi-product order while competing for a shared station; cutting and packaging happen; payment is tracked separately; every relevant event is stored; after closing the program I can reopen the data, inspect waiting/work times, and replay the same history without duplicating it. A local test producer can add observations through the same recorder, and the system is ready to connect to the existing USD scene.
