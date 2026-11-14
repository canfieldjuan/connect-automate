"""Own a fresh socket-only PostgreSQL fixture; never accept an external DSN.

Bootstrap/admin and ephemeral proof signing are deliberately separate from Client.
Nothing here is packaged in the installed product or authenticates real people.
"""

import hashlib
import os
import secrets
import subprocess
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import psycopg
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from psycopg import sql
from psycopg.types.json import Jsonb

from qualification.licensing_register.protocol import EVIDENCE, Command
from qualification.owner_authority.protocol import canonical

SQL = Path(__file__).with_name("core.sql")
CONTRACT = "0981a88f3d8eb2d081ed2b2c2cb8d50157c819ce"


def postgres_bin():
    """Fixed installed version for this lane; env path must be an absolute directory."""
    configured = os.environ.get("REGISTER_PG_BIN")
    path = Path(configured) if configured else Path("/usr/lib/postgresql/16/bin")
    if not path.is_absolute() or not all((path / n).is_file() for n in
                                         ("postgres", "initdb", "pg_ctl")):
        raise RuntimeError("PostgreSQL 16 binaries required; set REGISTER_PG_BIN")
    return path


class Client:
    """Scoped database login; no admin connection, signer or table access."""

    def __init__(self, connection_args, epoch):
        self._args, self.epoch = dict(connection_args), epoch

    def connect(self):
        return psycopg.connect(**self._args)

    def apply(self, value):
        command = Command.validate_python(value)
        with self.connect() as db:
            return execute(db, command)


def execute(db, command):
    """Transaction commits at the caller's connection boundary, never before it."""
    command = Command.validate_python(command)
    return db.execute("SELECT licensing_register.apply(%s,%s,%s,%s,%s,%s)", (
        command.command, command.operation_id, command.epoch, command.record_id,
        command.proof_id, command.expected_revision,
    )).fetchone()[0]


class Cluster:
    def __init__(self, root):
        self.root = Path(root).absolute()
        self.bin = postgres_bin()
        self.secret = secrets.token_urlsafe(32)
        self.passwords = {n: secrets.token_urlsafe(32) for n in
                          ("actor_licensing", "actor_enrollment", "actor_other")}
        self.started = False

    def __enter__(self):
        # Exclusive creation: never reuse a database path, socket or existing server.
        self.root.mkdir(mode=0o700)
        self.socket = self.root / "socket"
        self.socket.mkdir(mode=0o700)
        password = self.root / "bootstrap-password"
        password.touch(mode=0o600)
        password.write_text(self.secret)
        self.log = self.root / "postgres.log"
        self.log.touch(mode=0o600)
        subprocess.run([str(self.bin / "initdb"), "-D", str(self.root / "data"),
                        "-U", "fixture_admin", "--auth-local=scram-sha-256",
                        "--auth-host=reject", "--pwfile", str(password), "--no-locale",
                        "--encoding=UTF8"], check=True, capture_output=True, text=True)
        with (self.root / "data" / "postgresql.conf").open("a") as f:
            f.write("\nlisten_addresses = ''\nunix_socket_permissions = 0700\n")
        subprocess.run([str(self.bin / "pg_ctl"), "-D", str(self.root / "data"),
                        "-l", str(self.log), "-o", f"-k {self.socket}", "-w", "start"],
                       check=True, capture_output=True, text=True)
        self.started = True
        try:
            with self.admin("postgres", autocommit=True) as db:
                for role in ("register_owner", "register_licensing", "register_enrollment"):
                    db.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
                for role, pw in self.passwords.items():
                    db.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                        sql.Identifier(role), sql.Literal(pw)))
                db.execute("GRANT register_licensing TO actor_licensing,actor_other")
                db.execute("GRANT register_enrollment TO actor_enrollment")
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *args):
        if self.started:
            subprocess.run([str(self.bin / "pg_ctl"), "-D", str(self.root / "data"),
                            "-m", "fast", "-w", "stop"], check=True, capture_output=True)
            self.started = False
        # No database drop or directory deletion; caller owns disposable fixture retention.

    def args(self, database, user="fixture_admin"):
        return dict(host=str(self.socket), dbname=database, user=user,
                    password=self.secret if user == "fixture_admin" else self.passwords[user],
                    connect_timeout=5)

    def admin(self, database, **kwargs):
        return psycopg.connect(**self.args(database), **kwargs)

    def create(self, organization, other_organization):
        name = "fixture_" + uuid4().hex
        with self.admin("postgres", autocommit=True) as db:
            db.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        return Register(self, name, organization, other_organization)


class Register:
    """Privileged synthetic test controller, never the application client."""

    def __init__(self, cluster, name, organization, other_organization):
        self.cluster, self.name = cluster, name
        self.epoch = str(uuid4())
        self._signer = Ed25519PrivateKey.generate()
        self._public = self._signer.public_key()
        with self.admin() as db:
            db.execute(SQL.read_text())
            db.execute("INSERT INTO licensing_register.control VALUES(true,%s,false,0,%s)",
                       (self.epoch, "0" * 64))
            for login, org, lane in (("actor_licensing", organization, "LICENSING"),
                                    ("actor_enrollment", organization, "ENROLLMENT"),
                                    ("actor_other", other_organization, "LICENSING")):
                db.execute("INSERT INTO licensing_register.actors VALUES(%s,%s,%s,%s,true)",
                           (login, str(uuid4()), org, lane))

    def admin(self):
        return self.cluster.admin(self.name)

    def client(self, role="licensing"):
        return Client(self.cluster.args(self.name, "actor_" + role), self.epoch)

    def sign(self, document):
        value = EVIDENCE.validate_python(document).model_dump(mode="json")
        return value, self._signer.sign(b"offline-register-proof/1\0" + canonical(value))

    def import_proof(self, document, signature):
        value = EVIDENCE.validate_python(document).model_dump(mode="json")
        self._public.verify(signature, b"offline-register-proof/1\0" + canonical(value))
        with self.admin() as db:
            db.execute("INSERT INTO licensing_register.proofs VALUES(%s,%s,%s,%s,%s,%s)",
                       (value["proof_id"], value["kind"], value["organization_id"],
                        value["record_id"], Jsonb(value), signature))
        return value["proof_id"]

    def proof(self, document):
        return self.import_proof(*self.sign(document))

    def snapshot(self):
        with self.admin() as db:
            value = db.execute("SELECT licensing_register.snapshot()").fetchone()[0]
            history = db.execute("SELECT coalesce(jsonb_agg(to_jsonb(j) ORDER BY sequence),'[]') "
                                 "FROM licensing_register.journal j").fetchone()[0]
            control = db.execute("SELECT coalesce(jsonb_agg(to_jsonb(c)),'[]') "
                                 "FROM licensing_register.control c").fetchone()[0]
            return hashlib.sha256(canonical([value, history, control])).hexdigest()

    def lock_restored(self):
        # Simulates the externally imposed restore interlock. There is no unlock API.
        with self.admin() as db:
            db.execute("UPDATE licensing_register.control SET locked=true,epoch=%s",
                       (str(uuid4()),))


@contextmanager
def temporary_cluster(parent):
    """Fresh path on a short private socket parent, no ambient PG connection variables."""
    # Socket path has a platform size bound; keep nested pytest directory names out.
    root = Path(parent) / ("reg_" + secrets.token_hex(6))
    with Cluster(root) as cluster:
        yield cluster
