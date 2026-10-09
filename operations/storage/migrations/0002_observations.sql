CREATE TABLE observation_sources (
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('camera_video','manual','other')),
    file_name TEXT,
    sha256 TEXT,
    viewpoint TEXT,
    visible_zones_json TEXT NOT NULL,
    timezone TEXT,
    wall_clock_start_utc TEXT,
    duration_s REAL CHECK (duration_s IS NULL OR duration_s >= 0),
    notes TEXT,
    PRIMARY KEY (run_id, source_id)
);

CREATE TABLE source_alignments (
    run_id TEXT NOT NULL,
    alignment_id TEXT NOT NULL,
    source_a_id TEXT NOT NULL,
    source_b_id TEXT NOT NULL,
    offset_b_minus_a_s REAL NOT NULL,
    method TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    notes TEXT,
    PRIMARY KEY (run_id, alignment_id),
    FOREIGN KEY (run_id, source_a_id) REFERENCES observation_sources(run_id, source_id),
    FOREIGN KEY (run_id, source_b_id) REFERENCES observation_sources(run_id, source_id)
);

CREATE TABLE observation_coverage (
    run_id TEXT NOT NULL,
    coverage_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    start_offset_s REAL NOT NULL CHECK (start_offset_s >= 0),
    end_offset_s REAL NOT NULL CHECK (end_offset_s >= start_offset_s),
    state TEXT NOT NULL CHECK (state IN ('visible','partial','occluded','missing')),
    zones_json TEXT NOT NULL,
    notes TEXT,
    PRIMARY KEY (run_id, coverage_id),
    FOREIGN KEY (run_id, source_id) REFERENCES observation_sources(run_id, source_id)
);

CREATE TABLE event_evidence (
    recording_cursor INTEGER NOT NULL REFERENCES events(recording_cursor) ON DELETE RESTRICT,
    evidence_index INTEGER NOT NULL CHECK (evidence_index >= 0),
    run_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    clip_start_offset_s REAL,
    clip_end_offset_s REAL,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    observation_kind TEXT NOT NULL CHECK (observation_kind IN ('direct','inferred')),
    notes TEXT,
    PRIMARY KEY (recording_cursor, evidence_index),
    FOREIGN KEY (run_id, source_id) REFERENCES observation_sources(run_id, source_id),
    CHECK (clip_start_offset_s IS NULL OR clip_start_offset_s >= 0),
    CHECK (clip_end_offset_s IS NULL OR clip_end_offset_s >= clip_start_offset_s)
);

CREATE INDEX idx_observation_sources_run ON observation_sources(run_id, source_id);
CREATE INDEX idx_event_evidence_source ON event_evidence(run_id, source_id, clip_start_offset_s);
CREATE INDEX idx_observation_coverage_source ON observation_coverage(run_id, source_id, start_offset_s);
