PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('simulated', 'observed')),
    scenario_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'sealed', 'interrupted')),
    schema_version TEXT NOT NULL,
    model_version TEXT NOT NULL,
    layout_version TEXT NOT NULL,
    effective_config_json TEXT NOT NULL,
    seed INTEGER,
    source_ref TEXT,
    parent_run_id TEXT REFERENCES runs(run_id),
    is_test INTEGER NOT NULL CHECK (is_test IN (0, 1)),
    created_at_utc TEXT NOT NULL,
    analysis_cutoff_s REAL,
    stopped_at_utc TEXT,
    stop_reason TEXT
);

CREATE TABLE IF NOT EXISTS entity_registry (
    run_scope TEXT NOT NULL,
    object_type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    PRIMARY KEY (run_scope, object_type, object_id)
);

CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    sale_unit TEXT NOT NULL,
    default_price_cop INTEGER,
    portion_mass_g REAL,
    portion_mass_evidence TEXT,
    tags_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS menu_offers (
    offer_id TEXT NOT NULL,
    version TEXT NOT NULL,
    name TEXT NOT NULL,
    price_cop INTEGER,
    PRIMARY KEY (offer_id, version)
);

CREATE TABLE IF NOT EXISTS offer_components (
    offer_id TEXT NOT NULL,
    offer_version TEXT NOT NULL,
    product_id TEXT NOT NULL REFERENCES products(product_id),
    quantity REAL NOT NULL CHECK (quantity > 0),
    unit TEXT NOT NULL,
    choice_group TEXT,
    PRIMARY KEY (offer_id, offer_version, product_id, unit, choice_group),
    FOREIGN KEY (offer_id, offer_version) REFERENCES menu_offers(offer_id, version)
);

CREATE TABLE IF NOT EXISTS workers (
    worker_id TEXT PRIMARY KEY,
    eligible_roles_json TEXT NOT NULL,
    display_code TEXT
);

CREATE TABLE IF NOT EXISTS stations (
    station_id TEXT PRIMARY KEY,
    zone_id TEXT NOT NULL,
    layout_version TEXT NOT NULL,
    usd_prim_path TEXT,
    access_points_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resources (
    resource_id TEXT PRIMARY KEY,
    station_id TEXT REFERENCES stations(station_id),
    resource_type TEXT NOT NULL,
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    available INTEGER NOT NULL CHECK (available IN (0, 1)),
    evidence TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shifts (
    shift_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    worker_id TEXT NOT NULL REFERENCES workers(worker_id),
    planned_start_s REAL,
    planned_end_s REAL,
    observed_start_utc TEXT,
    observed_end_utc TEXT,
    breaks_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS role_assignments (
    assignment_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    worker_id TEXT NOT NULL REFERENCES workers(worker_id),
    role TEXT NOT NULL,
    station_id TEXT REFERENCES stations(station_id),
    start_s REAL,
    end_s REAL
);

CREATE TABLE IF NOT EXISTS visits (
    visit_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    party_size INTEGER,
    queue_participants INTEGER,
    arrival_s REAL,
    departure_s REAL,
    outcome TEXT
);

CREATE TABLE IF NOT EXISTS queues (
    queue_id TEXT PRIMARY KEY,
    queue_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    visit_id TEXT REFERENCES visits(visit_id),
    channel TEXT NOT NULL,
    fulfillment_mode TEXT NOT NULL,
    primary_server_id TEXT REFERENCES workers(worker_id),
    preparation_state TEXT NOT NULL,
    payment_state TEXT NOT NULL,
    fulfillment_state TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS queue_visits (
    queue_visit_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    queue_id TEXT NOT NULL REFERENCES queues(queue_id),
    visit_id TEXT REFERENCES visits(visit_id),
    order_id TEXT REFERENCES orders(order_id),
    entered_s REAL,
    service_start_s REAL,
    departure_s REAL,
    outcome TEXT,
    CHECK (visit_id IS NOT NULL OR order_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS order_lines (
    line_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    product_id TEXT REFERENCES products(product_id),
    offer_id TEXT,
    offer_version TEXT,
    quantity REAL NOT NULL CHECK (quantity > 0),
    unit TEXT NOT NULL,
    unit_price_cop INTEGER,
    discount_cop INTEGER NOT NULL DEFAULT 0,
    selected_options_json TEXT NOT NULL,
    CHECK ((product_id IS NULL) <> (offer_id IS NULL)),
    CHECK ((offer_id IS NULL) = (offer_version IS NULL)),
    FOREIGN KEY (offer_id, offer_version) REFERENCES menu_offers(offer_id, version)
);

CREATE TABLE IF NOT EXISTS fulfillment_components (
    component_id TEXT PRIMARY KEY,
    line_id TEXT NOT NULL REFERENCES order_lines(line_id),
    product_id TEXT NOT NULL REFERENCES products(product_id),
    required_quantity REAL NOT NULL CHECK (required_quantity > 0),
    unit TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activities (
    activity_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    activity_type TEXT NOT NULL,
    current_state TEXT NOT NULL,
    request_time TEXT,
    start_time TEXT,
    end_time TEXT,
    last_event_cursor INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS resource_allocations (
    allocation_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    resource_id TEXT NOT NULL REFERENCES resources(resource_id),
    activity_id TEXT NOT NULL REFERENCES activities(activity_id),
    units INTEGER NOT NULL CHECK (units > 0),
    acquired_s REAL,
    released_s REAL
);

CREATE TABLE IF NOT EXISTS containers (
    container_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    container_type TEXT NOT NULL,
    parent_container_id TEXT REFERENCES containers(container_id),
    packaging_state TEXT NOT NULL,
    CHECK (parent_container_id IS NULL OR parent_container_id <> container_id)
);

CREATE TABLE IF NOT EXISTS container_contents (
    content_id TEXT PRIMARY KEY,
    container_id TEXT NOT NULL REFERENCES containers(container_id),
    component_id TEXT NOT NULL REFERENCES fulfillment_components(component_id),
    quantity REAL NOT NULL CHECK (quantity > 0),
    unit TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS trg_container_content_quantity_insert
BEFORE INSERT ON container_contents
BEGIN
    SELECT CASE WHEN NEW.unit <> (SELECT unit FROM fulfillment_components WHERE component_id=NEW.component_id)
      THEN RAISE(ABORT, 'container content unit differs from component unit') END;
    SELECT CASE WHEN NEW.quantity + COALESCE((
        SELECT SUM(quantity) FROM container_contents WHERE component_id=NEW.component_id
      ), 0) > (SELECT required_quantity FROM fulfillment_components WHERE component_id=NEW.component_id)
      THEN RAISE(ABORT, 'container content exceeds component quantity') END;
    SELECT CASE WHEN EXISTS (
      WITH RECURSIVE ancestors(container_id) AS (
        SELECT parent_container_id FROM containers WHERE container_id=NEW.container_id
        UNION ALL
        SELECT c.parent_container_id FROM containers c JOIN ancestors a ON c.container_id=a.container_id
        WHERE c.parent_container_id IS NOT NULL
      )
      SELECT 1 FROM container_contents cc JOIN ancestors a ON cc.container_id=a.container_id
      WHERE cc.component_id=NEW.component_id
    ) THEN RAISE(ABORT, 'component already recorded in ancestor container') END;
    SELECT CASE WHEN EXISTS (
      WITH RECURSIVE descendants(container_id) AS (
        SELECT container_id FROM containers WHERE parent_container_id=NEW.container_id
        UNION ALL
        SELECT c.container_id FROM containers c JOIN descendants d ON c.parent_container_id=d.container_id
      )
      SELECT 1 FROM container_contents cc JOIN descendants d ON cc.container_id=d.container_id
      WHERE cc.component_id=NEW.component_id
    ) THEN RAISE(ABORT, 'component already recorded in descendant container') END;
END;

CREATE TABLE IF NOT EXISTS payments (
    payment_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    cashier_id TEXT REFERENCES workers(worker_id),
    register_resource_id TEXT REFERENCES resources(resource_id),
    amount_cop INTEGER NOT NULL CHECK (amount_cop >= 0),
    method TEXT NOT NULL,
    status TEXT NOT NULL,
    confirmed_s REAL
);

CREATE TABLE IF NOT EXISTS payment_allocations (
    allocation_id TEXT PRIMARY KEY,
    payment_id TEXT NOT NULL REFERENCES payments(payment_id),
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    amount_cop INTEGER NOT NULL CHECK (amount_cop >= 0)
);

CREATE TRIGGER IF NOT EXISTS trg_payment_allocation_amount_insert
BEFORE INSERT ON payment_allocations
BEGIN
    SELECT CASE WHEN (SELECT run_id FROM payments WHERE payment_id=NEW.payment_id)
      <> (SELECT run_id FROM orders WHERE order_id=NEW.order_id)
      THEN RAISE(ABORT, 'payment and order belong to different runs') END;
    SELECT CASE WHEN NEW.amount_cop + COALESCE((
        SELECT SUM(amount_cop) FROM payment_allocations WHERE payment_id=NEW.payment_id
      ), 0) > (SELECT amount_cop FROM payments WHERE payment_id=NEW.payment_id)
      THEN RAISE(ABORT, 'payment allocations exceed payment amount') END;
END;

CREATE TABLE IF NOT EXISTS events (
    recording_cursor INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    content_hash TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    activity TEXT NOT NULL,
    lifecycle TEXT NOT NULL,
    activity_id TEXT,
    sim_time_s REAL,
    occurred_at_utc TEXT,
    recorded_at_utc TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_event_id TEXT NOT NULL,
    evidence TEXT NOT NULL,
    source_ref TEXT,
    source_offset_s REAL,
    correction_of_event_id TEXT REFERENCES events(event_id),
    payload_json TEXT NOT NULL,
    UNIQUE (run_id, source_id, source_event_id)
);

CREATE TABLE IF NOT EXISTS event_objects (
    recording_cursor INTEGER NOT NULL REFERENCES events(recording_cursor) ON DELETE RESTRICT,
    object_type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    qualifier TEXT NOT NULL,
    PRIMARY KEY (recording_cursor, object_type, object_id, qualifier)
);

CREATE INDEX IF NOT EXISTS idx_events_run_cursor ON events(run_id, recording_cursor);
CREATE INDEX IF NOT EXISTS idx_events_run_sim_time ON events(run_id, sim_time_s, recording_cursor);
CREATE INDEX IF NOT EXISTS idx_events_run_occurred ON events(run_id, occurred_at_utc, source_offset_s, recording_cursor);
CREATE INDEX IF NOT EXISTS idx_events_activity ON events(run_id, activity_id, recording_cursor);
CREATE INDEX IF NOT EXISTS idx_event_objects_lookup ON event_objects(object_type, object_id, recording_cursor);
CREATE INDEX IF NOT EXISTS idx_events_source ON events(run_id, source_id, source_event_id);
