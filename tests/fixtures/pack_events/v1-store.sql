BEGIN TRANSACTION;
CREATE TABLE workflow_actions (
    action_id TEXT PRIMARY KEY CHECK (length(action_id) = 36),
    record_id TEXT NOT NULL CHECK (record_id <> ''),
    -- A caller-minted idempotency key for the action's intent, unique per record (not
    -- globally) so the same key on two records is two independent actions. Modeled on the
    -- outbound outbox's dedupe_key but scoped to the owning record.
    dedupe_key TEXT NOT NULL CHECK (dedupe_key <> ''),
    kind TEXT NOT NULL CHECK (kind <> ''),
    request TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'settled', 'failed')),
    result TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (record_id, dedupe_key),
    CHECK (
        (status = 'pending' AND result IS NULL)
        OR (status = 'settled' AND result IS NOT NULL)
        OR (status = 'failed')
    )
);
INSERT INTO "workflow_actions" VALUES('e3ad9625-ebd5-452e-a9d7-88a9cd053f83','3eea48d3-1667-4766-a4d1-9b1364838cb0','legacy-action','notify.local','{"body":"Synthetic existing row","title":"Legacy proof"}','pending',NULL,NULL,'2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00');
CREATE TABLE workflow_events (
    event_id TEXT PRIMARY KEY CHECK (length(event_id) = 36),
    record_id TEXT NOT NULL CHECK (record_id <> ''),
    sequence_no INTEGER NOT NULL CHECK (sequence_no >= 0),
    previous_stage TEXT CHECK (previous_stage IS NULL OR previous_stage <> ''),
    next_stage TEXT NOT NULL CHECK (next_stage <> ''),
    state_version INTEGER NOT NULL CHECK (state_version >= 1),
    operation_name TEXT NOT NULL CHECK (operation_name <> ''),
    operation_key TEXT CHECK (operation_key IS NULL OR operation_key <> ''),
    request_fingerprint TEXT CHECK (
        request_fingerprint IS NULL OR length(request_fingerprint) = 64
    ),
    effects TEXT CHECK (effects IS NULL OR effects <> ''),
    created_at TEXT NOT NULL,
    UNIQUE (record_id, sequence_no),
    UNIQUE (record_id, state_version),
    CHECK (
        (previous_stage IS NULL AND sequence_no = 0 AND state_version = 1
            AND operation_name = 'create' AND operation_key IS NULL AND effects IS NULL)
        OR (previous_stage IS NOT NULL AND sequence_no >= 1
            AND state_version = sequence_no + 1 AND effects IS NOT NULL)
    )
);
INSERT INTO "workflow_events" VALUES('29a5497d-c232-430e-b62b-ac85ebc15924','3eea48d3-1667-4766-a4d1-9b1364838cb0',0,NULL,'ready',1,'create',NULL,NULL,NULL,'2026-01-01T00:00:00+00:00');
INSERT INTO "workflow_events" VALUES('8da2a859-40d0-4ee6-9304-b673d99beac1','3eea48d3-1667-4766-a4d1-9b1364838cb0',1,'ready','reviewing',2,'review','legacy-op','a8198524f58e72b56283ab71ebddada22840f108b46ef7165bb3fca9919c5558','[{"kind":"record.transition","to_stage":"reviewing"}]','2026-01-01T00:00:00+00:00');
CREATE TABLE workflow_operations (
    record_id TEXT NOT NULL CHECK (record_id <> ''),
    operation_key TEXT NOT NULL CHECK (operation_key <> ''),
    operation_name TEXT NOT NULL CHECK (operation_name <> ''),
    request_fingerprint TEXT NOT NULL CHECK (length(request_fingerprint) = 64),
    -- NULL event_id records a no-match: the decision was made under this key but no
    -- definition applied, so no event exists. Reserving the key keeps a retry idempotent
    -- across later stage changes instead of re-applying.
    event_id TEXT CHECK (event_id IS NULL OR length(event_id) = 36),
    created_at TEXT NOT NULL,
    PRIMARY KEY (record_id, operation_key)
);
INSERT INTO "workflow_operations" VALUES('3eea48d3-1667-4766-a4d1-9b1364838cb0','legacy-op','review','a8198524f58e72b56283ab71ebddada22840f108b46ef7165bb3fca9919c5558','8da2a859-40d0-4ee6-9304-b673d99beac1','2026-01-01T00:00:00+00:00');
CREATE TABLE workflow_overlays (
    record_id TEXT NOT NULL CHECK (record_id <> ''),
    key TEXT NOT NULL CHECK (key <> ''),
    value_json TEXT NOT NULL,
    state_version INTEGER NOT NULL CHECK (state_version >= 1),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (record_id, key)
);
CREATE TABLE workflow_records (
    record_id TEXT PRIMARY KEY CHECK (length(record_id) = 36),
    workflow TEXT NOT NULL CHECK (workflow <> ''),
    pack_id TEXT CHECK (pack_id IS NULL OR pack_id <> ''),
    pack_version INTEGER CHECK (pack_version IS NULL OR pack_version >= 1),
    stage TEXT NOT NULL CHECK (stage <> ''),
    state_version INTEGER NOT NULL CHECK (state_version >= 1),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    -- A pack-bound record carries both its pack identity and version, or neither (a
    -- bare-workflow record); a version without an identity is meaningless.
    CHECK ((pack_id IS NULL) = (pack_version IS NULL))
);
INSERT INTO "workflow_records" VALUES('3eea48d3-1667-4766-a4d1-9b1364838cb0','legacy-proof',NULL,NULL,'reviewing',2,'2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00');
CREATE INDEX idx_workflow_events_record
    ON workflow_events(record_id, sequence_no);
CREATE INDEX idx_workflow_actions_record
    ON workflow_actions(record_id, created_at);
CREATE TRIGGER workflow_events_no_update
BEFORE UPDATE ON workflow_events
BEGIN
    SELECT RAISE(ABORT, 'workflow_events are immutable');
END;
CREATE TRIGGER workflow_events_no_delete
BEFORE DELETE ON workflow_events
BEGIN
    SELECT RAISE(ABORT, 'workflow_events are immutable');
END;
COMMIT;
