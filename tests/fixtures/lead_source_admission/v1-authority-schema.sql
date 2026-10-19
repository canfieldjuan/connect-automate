-- Frozen authority schema from a0b64e164732957d00e0db3c1ae51dd75d351b89.
CREATE TABLE deployment (singleton INTEGER PRIMARY KEY CHECK(singleton=1), host_id TEXT NOT NULL, organization_id TEXT NOT NULL) STRICT;
CREATE TABLE authority_history (generation INTEGER PRIMARY KEY CHECK(generation BETWEEN 1 AND 2147483647), snapshot TEXT NOT NULL, sha256 TEXT NOT NULL) STRICT;
CREATE TRIGGER deployment_no_update BEFORE UPDATE ON deployment BEGIN SELECT RAISE(ABORT, 'immutable'); END;
CREATE TRIGGER deployment_no_delete BEFORE DELETE ON deployment BEGIN SELECT RAISE(ABORT, 'immutable'); END;
CREATE TRIGGER history_no_update BEFORE UPDATE ON authority_history BEGIN SELECT RAISE(ABORT, 'immutable'); END;
CREATE TRIGGER history_no_delete BEFORE DELETE ON authority_history BEGIN SELECT RAISE(ABORT, 'immutable'); END;
PRAGMA user_version=1;
