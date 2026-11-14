-- Disposable OFFLINE_CONFORMANCE database only. Bootstrap runs as fixture admin.
CREATE SCHEMA licensing_register AUTHORIZATION register_owner;
REVOKE ALL ON SCHEMA licensing_register FROM PUBLIC;
SET ROLE register_owner;
SET search_path = licensing_register, pg_catalog;
CREATE DOMAIN uid AS uuid CHECK (substring(VALUE::text,15,1) = '4'
  AND substring(VALUE::text,20,1) IN ('8','9','a','b'));
CREATE DOMAIN digest AS text CHECK (VALUE ~ '^[0-9a-f]{64}$');
CREATE TYPE proof_kind AS ENUM ('GRANT','ENROLLMENT','ISSUANCE','ASSOCIATION','CONSUMPTION');
CREATE TYPE command_kind AS ENUM ('grant','enroll','issuance','associate','consume',
  'withdraw_grant','withdraw_enrollment','withdraw_association');
CREATE TYPE record_state AS ENUM ('CURRENT','WITHDRAWN');
CREATE TABLE control (
  singleton boolean PRIMARY KEY CHECK(singleton), epoch uid NOT NULL,
  locked boolean NOT NULL DEFAULT false, sequence bigint NOT NULL CHECK(sequence>=0),
  tail digest NOT NULL);
CREATE TABLE actors (
  login name PRIMARY KEY, actor uid NOT NULL UNIQUE, organization uid NOT NULL,
  lane text NOT NULL CHECK(lane IN ('LICENSING','ENROLLMENT')), active boolean NOT NULL);
CREATE TABLE proofs (
  id uid PRIMARY KEY, kind proof_kind NOT NULL, organization uid NOT NULL,
  record_id uid NOT NULL, document jsonb NOT NULL, signature bytea NOT NULL,
  UNIQUE(id,organization));
CREATE TABLE grants (
  id uid PRIMARY KEY, organization uid NOT NULL, revision bigint NOT NULL CHECK(revision>0),
  state record_state NOT NULL, proof uid NOT NULL,
  UNIQUE(id,organization), FOREIGN KEY(proof,organization) REFERENCES proofs(id,organization));
CREATE TABLE enrollments (
  id uid PRIMARY KEY, organization uid NOT NULL, revision bigint NOT NULL CHECK(revision>0),
  state record_state NOT NULL, proof uid NOT NULL, expires timestamptz NOT NULL,
  source_expires timestamptz, UNIQUE(id,organization),
  FOREIGN KEY(proof,organization) REFERENCES proofs(id,organization));
CREATE TABLE issuances (
  id uid PRIMARY KEY, organization uid NOT NULL, grant_id uid NOT NULL, proof uid NOT NULL,
  UNIQUE(id,organization), FOREIGN KEY(grant_id,organization) REFERENCES grants(id,organization),
  FOREIGN KEY(proof,organization) REFERENCES proofs(id,organization));
CREATE TABLE associations (
  id uid PRIMARY KEY, organization uid NOT NULL, entitlement uid NOT NULL UNIQUE,
  grant_id uid NOT NULL, enrollment uid NOT NULL, enrollment_revision bigint NOT NULL,
  grant_revision bigint NOT NULL, revision bigint NOT NULL CHECK(revision>0),
  state record_state NOT NULL, proof uid NOT NULL, UNIQUE(id,organization,entitlement),
  FOREIGN KEY(entitlement,organization) REFERENCES issuances(id,organization),
  FOREIGN KEY(grant_id,organization) REFERENCES grants(id,organization),
  FOREIGN KEY(enrollment,organization) REFERENCES enrollments(id,organization),
  FOREIGN KEY(proof,organization) REFERENCES proofs(id,organization));
CREATE TABLE consumptions (
  id uid PRIMARY KEY, organization uid NOT NULL, entitlement uid NOT NULL,
  claim uid NOT NULL UNIQUE, consumed_operation uid NOT NULL UNIQUE,
  proof uid NOT NULL, FOREIGN KEY(id,organization,entitlement)
    REFERENCES associations(id,organization,entitlement),
  FOREIGN KEY(proof,organization) REFERENCES proofs(id,organization));
CREATE TABLE journal (
  sequence bigint PRIMARY KEY CHECK(sequence>0), operation uid NOT NULL UNIQUE,
  request jsonb NOT NULL, result jsonb NOT NULL, snapshot jsonb NOT NULL,
  previous digest NOT NULL, hash digest NOT NULL);

CREATE FUNCTION hash(v jsonb) RETURNS digest LANGUAGE sql IMMUTABLE
SET search_path = pg_catalog, licensing_register
AS $$ SELECT encode(sha256(convert_to(v::text,'UTF8')),'hex')::licensing_register.digest $$;

-- Full projection snapshots are deliberately small-fixture evidence, not a production index.
CREATE FUNCTION snapshot() RETURNS jsonb LANGUAGE sql STABLE
SET search_path = pg_catalog, licensing_register
AS $$ SELECT jsonb_build_object(
 'grants', (SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY id),'[]') FROM licensing_register.grants t),
 'enrollments', (SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY id),'[]') FROM licensing_register.enrollments t),
 'issuances', (SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY id),'[]') FROM licensing_register.issuances t),
 'associations', (SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY id),'[]') FROM licensing_register.associations t),
 'consumptions', (SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY id),'[]') FROM licensing_register.consumptions t),
 'proofs', (SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY id),'[]') FROM licensing_register.proofs t
   WHERE id IN (SELECT proof FROM licensing_register.grants UNION SELECT proof FROM licensing_register.enrollments
    UNION SELECT proof FROM licensing_register.issuances UNION SELECT proof FROM licensing_register.associations
    UNION SELECT proof FROM licensing_register.consumptions))) $$;

CREATE FUNCTION assert_history() RETURNS void LANGUAGE plpgsql
SET search_path = pg_catalog, licensing_register AS $$
DECLARE c licensing_register.control; e licensing_register.journal; n bigint:=0;
 h text:=repeat('0',64); last_snapshot jsonb;
BEGIN
 SELECT * INTO STRICT c FROM licensing_register.control WHERE singleton;
 FOR e IN SELECT * FROM licensing_register.journal ORDER BY sequence LOOP
   n:=n+1;
   IF e.sequence<>n OR e.previous<>h OR e.hash<>licensing_register.hash(
       jsonb_build_array(e.sequence,e.operation,e.request,e.result,e.snapshot,e.previous)) THEN
     RAISE EXCEPTION 'HISTORY_CORRUPT';
   END IF;
   h:=e.hash; last_snapshot:=e.snapshot;
 END LOOP;
 IF c.sequence<>n OR c.tail<>h THEN RAISE EXCEPTION 'HISTORY_CORRUPT'; END IF;
 IF n>0 AND last_snapshot<>licensing_register.snapshot() THEN
   RAISE EXCEPTION 'HISTORY_CORRUPT';
 END IF;
 IF n=0 AND licensing_register.snapshot() <> jsonb_build_object('grants','[]'::jsonb,
   'enrollments','[]'::jsonb,'issuances','[]'::jsonb,'associations','[]'::jsonb,
   'consumptions','[]'::jsonb,'proofs','[]'::jsonb) THEN
   RAISE EXCEPTION 'HISTORY_CORRUPT';
 END IF;
END $$;

CREATE FUNCTION apply(cmd command_kind, op uid, requested_epoch uid, rid uid,
 proof_id uid DEFAULT NULL, expected bigint DEFAULT NULL) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, licensing_register AS $$
DECLARE c licensing_register.control; a licensing_register.actors; p licensing_register.proofs;
 g licensing_register.grants; en licensing_register.enrollments; ass licensing_register.associations;
 old licensing_register.journal; req jsonb; res jsonb; snap jsonb; hashed licensing_register.digest;
 target_kind licensing_register.proof_kind; new_revision bigint; current_time_value timestamptz;
BEGIN
 IF cmd IS NULL OR op IS NULL OR requested_epoch IS NULL OR rid IS NULL THEN
   RAISE EXCEPTION 'INPUT_INVALID';
 END IF;
 SELECT * INTO c FROM licensing_register.control WHERE singleton FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'HISTORY_CORRUPT'; END IF;
 IF c.locked OR c.epoch<>requested_epoch THEN RAISE EXCEPTION 'REGISTER_LOCKED'; END IF;
 SELECT * INTO a FROM licensing_register.actors WHERE login=session_user AND active;
 IF NOT FOUND THEN RAISE EXCEPTION 'UNAUTHORIZED'; END IF;
 IF (cmd IN ('enroll','withdraw_enrollment')) <> (a.lane='ENROLLMENT') THEN
   RAISE EXCEPTION 'UNAUTHORIZED';
 END IF;
 PERFORM licensing_register.assert_history();
 IF cmd::text LIKE 'withdraw_%' THEN
   IF proof_id IS NOT NULL OR expected IS NULL OR expected<=0 THEN
     RAISE EXCEPTION 'INPUT_INVALID'; END IF;
 ELSE
   IF proof_id IS NULL OR expected IS NOT NULL THEN RAISE EXCEPTION 'INPUT_INVALID'; END IF;
 END IF;
 req:=jsonb_build_array(cmd,op,requested_epoch,rid,proof_id,expected,a.actor,a.organization);
 SELECT * INTO old FROM licensing_register.journal WHERE operation=op;
 IF FOUND THEN
   IF old.request<>req THEN RAISE EXCEPTION 'BINDING_CONFLICT'; END IF;
   RETURN old.result || jsonb_build_object('result_kind','REPLAY');
 END IF;
 IF cmd::text NOT LIKE 'withdraw_%' THEN
   target_kind:=CASE cmd WHEN 'grant' THEN 'GRANT' WHEN 'enroll' THEN 'ENROLLMENT'
     WHEN 'issuance' THEN 'ISSUANCE' WHEN 'associate' THEN 'ASSOCIATION'
     ELSE 'CONSUMPTION' END;
   SELECT * INTO p FROM licensing_register.proofs WHERE id=proof_id;
   IF NOT FOUND THEN RAISE EXCEPTION 'SOURCE_UNAVAILABLE'; END IF;
   IF p.kind<>target_kind OR p.organization<>a.organization OR p.record_id<>rid THEN
     RAISE EXCEPTION 'BINDING_CONFLICT'; END IF;
 END IF;
 new_revision:=1;
 CASE cmd
 WHEN 'grant' THEN
   INSERT INTO licensing_register.grants VALUES(rid,a.organization,1,'CURRENT',p.id);
 WHEN 'enroll' THEN
   current_time_value:=clock_timestamp();
   IF (p.document->>'authority_expires_at')::timestamptz<=current_time_value OR
      (p.document->>'required_source_expires_at')::timestamptz<=current_time_value THEN
     RAISE EXCEPTION 'AUTHORITY_NOT_CURRENT'; END IF;
   INSERT INTO licensing_register.enrollments VALUES(rid,a.organization,1,'CURRENT',p.id,
     (p.document->>'authority_expires_at')::timestamptz,
     (p.document->>'required_source_expires_at')::timestamptz);
 WHEN 'issuance' THEN
   INSERT INTO licensing_register.issuances VALUES(rid,a.organization,
      (p.document->>'grant_id')::uuid,p.id);
 WHEN 'associate' THEN
   SELECT * INTO g FROM licensing_register.grants
      WHERE id=(p.document->>'grant_id')::uuid AND organization=a.organization FOR UPDATE;
   IF NOT FOUND THEN RAISE EXCEPTION 'BINDING_CONFLICT'; END IF;
   SELECT * INTO en FROM licensing_register.enrollments
      WHERE id=(p.document->>'enrollment_id')::uuid AND organization=a.organization FOR UPDATE;
   IF NOT FOUND THEN RAISE EXCEPTION 'BINDING_CONFLICT'; END IF;
   IF NOT EXISTS(SELECT FROM licensing_register.issuances WHERE id=(p.document->>'entitlement_id')::uuid
        AND organization=a.organization AND grant_id=g.id) THEN
      RAISE EXCEPTION 'BINDING_CONFLICT'; END IF;
   current_time_value:=clock_timestamp();
   IF g.state<>'CURRENT' OR en.state<>'CURRENT' OR en.expires<=current_time_value OR
        en.source_expires<=current_time_value THEN RAISE EXCEPTION 'AUTHORITY_NOT_CURRENT'; END IF;
   INSERT INTO licensing_register.associations VALUES(rid,a.organization,
      (p.document->>'entitlement_id')::uuid,g.id,en.id,en.revision,g.revision,1,'CURRENT',p.id);
 WHEN 'consume' THEN
   SELECT * INTO ass FROM licensing_register.associations WHERE id=rid AND organization=a.organization;
   IF NOT FOUND THEN RAISE EXCEPTION 'BINDING_CONFLICT'; END IF;
   IF (p.document->'binding'->>'entitlement_id')::uuid<>ass.entitlement THEN
      RAISE EXCEPTION 'BINDING_CONFLICT'; END IF;
   INSERT INTO licensing_register.consumptions VALUES(rid,a.organization,ass.entitlement,
      (p.document->'binding'->>'claim_id')::uuid,
      (p.document->'binding'->>'operation_id')::uuid,p.id);
 WHEN 'withdraw_grant' THEN
   UPDATE licensing_register.grants SET state='WITHDRAWN',revision=revision+1
     WHERE id=rid AND organization=a.organization AND revision=expected RETURNING revision INTO new_revision;
   IF NOT FOUND THEN RAISE EXCEPTION 'REVISION_CONFLICT'; END IF;
 WHEN 'withdraw_enrollment' THEN
   UPDATE licensing_register.enrollments SET state='WITHDRAWN',revision=revision+1
     WHERE id=rid AND organization=a.organization AND revision=expected RETURNING revision INTO new_revision;
   IF NOT FOUND THEN RAISE EXCEPTION 'REVISION_CONFLICT'; END IF;
 WHEN 'withdraw_association' THEN
   UPDATE licensing_register.associations SET state='WITHDRAWN',revision=revision+1
     WHERE id=rid AND organization=a.organization AND revision=expected RETURNING revision INTO new_revision;
   IF NOT FOUND THEN RAISE EXCEPTION 'REVISION_CONFLICT'; END IF;
 END CASE;
 res:=jsonb_build_object('version','offline-register/1','evidence_class','OFFLINE_CONFORMANCE',
   'qualification_pass',false,'result_kind','RECORDED','operation_id',op,'record_id',rid,
   'revision',new_revision,'sequence',c.sequence+1);
 snap:=licensing_register.snapshot();
 hashed:=licensing_register.hash(jsonb_build_array(c.sequence+1,op,req,res,snap,c.tail));
 INSERT INTO licensing_register.journal VALUES(c.sequence+1,op,req,res,snap,c.tail,hashed);
 UPDATE licensing_register.control SET sequence=c.sequence+1,tail=hashed WHERE singleton;
 RETURN res;
EXCEPTION WHEN unique_violation OR foreign_key_violation THEN RAISE EXCEPTION 'BINDING_CONFLICT';
 WHEN undefined_table OR undefined_column OR no_data_found THEN RAISE EXCEPTION 'HISTORY_CORRUPT';
END $$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA licensing_register FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA licensing_register FROM PUBLIC;
GRANT USAGE ON SCHEMA licensing_register TO register_licensing,register_enrollment;
GRANT EXECUTE ON FUNCTION apply(command_kind,uid,uid,uid,uid,bigint)
  TO register_licensing,register_enrollment;
RESET ROLE;
