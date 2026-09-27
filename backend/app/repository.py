"""SQLite boundary; originals immutable, updates guarded by version and owner."""

import hashlib
import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class Conflict(ValueError):
    pass


class Repository:
    def __init__(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "opsflow.sqlite3"
        self.lock = threading.RLock()
        with self.connection() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, owner TEXT, fingerprint TEXT, created REAL, body TEXT, raw BLOB);
            CREATE INDEX IF NOT EXISTS jobs_owner ON jobs(owner,created);
            CREATE INDEX IF NOT EXISTS jobs_fingerprint ON jobs(owner,fingerprint);
            CREATE TABLE IF NOT EXISTS datasets(id TEXT PRIMARY KEY, owner TEXT, created REAL, version INTEGER, original TEXT, body TEXT);
            CREATE INDEX IF NOT EXISTS datasets_owner ON datasets(owner,created);
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, dataset_id TEXT, version INTEGER, body TEXT);
            CREATE INDEX IF NOT EXISTS audit_dataset ON audit(dataset_id,version);
            CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, dataset_id TEXT, body TEXT);
            CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, body TEXT);
            CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, email TEXT UNIQUE COLLATE NOCASE, name TEXT, password_hash TEXT, salt TEXT, created REAL);
            CREATE INDEX IF NOT EXISTS users_email ON users(email);
            CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id TEXT, created REAL);
            CREATE INDEX IF NOT EXISTS sessions_token ON sessions(token);
            """)
            # Retention for demo/guest sessions. Registered user datasets are preserved.
            cutoff = time.time() - 86400
            db.execute(
                "DELETE FROM audit WHERE dataset_id IN (SELECT id FROM datasets WHERE owner NOT LIKE 'user_%' AND created < ?)",
                (cutoff,),
            )
            db.execute(
                "DELETE FROM messages WHERE dataset_id IN (SELECT id FROM datasets WHERE owner NOT LIKE 'user_%' AND created < ?)",
                (cutoff,),
            )
            db.execute("DELETE FROM datasets WHERE owner NOT LIKE 'user_%' AND created < ?", (cutoff,))
            db.execute("DELETE FROM jobs WHERE owner NOT LIKE 'user_%' AND created < ?", (cutoff,))
            db.execute("DELETE FROM cache")
            for row in db.execute("SELECT id,body FROM jobs").fetchall():
                job = json.loads(row["body"])
                if job["status"] in ("queued", "processing", "awaiting_selection"):
                    job.update(
                        status="failed",
                        error="Processing was interrupted by a server restart. Upload the file again; original bytes were preserved.",
                    )
                    db.execute("UPDATE jobs SET body=? WHERE id=?", (json.dumps(job), row["id"]))

    @contextmanager
    def connection(self):
        with self.lock:
            db = sqlite3.connect(self.path, timeout=10)
            db.row_factory = sqlite3.Row
            try:
                with db:
                    yield db
            finally:
                db.close()

    def create_job(self, job, raw):
        with self.connection() as db:
            db.execute(
                "INSERT INTO jobs VALUES(?,?,?,?,?,?)",
                (job["id"], job["owner"], job["fingerprint"], job["created"], json.dumps(job), raw),
            )

    def update_job(self, job):
        with self.connection() as db:
            db.execute("UPDATE jobs SET body=? WHERE id=?", (json.dumps(job), job["id"]))

    def get_job(self, jid, owner):
        with self.connection() as db:
            row = db.execute(
                "SELECT body FROM jobs WHERE id=? AND owner=?", (jid, owner)
            ).fetchone()
            return json.loads(row["body"]) if row else None

    def raw(self, jid, owner):
        with self.connection() as db:
            row = db.execute("SELECT raw FROM jobs WHERE id=? AND owner=?", (jid, owner)).fetchone()
            return row["raw"] if row else None

    def jobs(self, owner):
        with self.connection() as db:
            return [
                json.loads(r["body"])
                for r in db.execute(
                    "SELECT body FROM jobs WHERE owner=? ORDER BY created DESC LIMIT 50", (owner,)
                )
            ]

    def cached_job(self, owner, fingerprint):
        with self.connection() as db:
            rows = db.execute(
                "SELECT body FROM jobs WHERE owner=? AND fingerprint=? ORDER BY created DESC",
                (owner, fingerprint),
            ).fetchall()
            for row in rows:
                job = json.loads(row["body"])
                if job["status"] != "failed":
                    return job

    def create_dataset(self, dataset):
        with self.connection() as db:
            db.execute(
                "INSERT INTO datasets VALUES(?,?,?,?,?,?)",
                (
                    dataset["id"],
                    dataset["owner"],
                    dataset["created"],
                    0,
                    json.dumps(dataset["data"]),
                    json.dumps(dataset),
                ),
            )

    def dataset(self, did, owner):
        with self.connection() as db:
            row = db.execute(
                "SELECT body FROM datasets WHERE id=? AND owner=?", (did, owner)
            ).fetchone()
            return json.loads(row["body"]) if row else None

    def original_rows(self, did, owner):
        with self.connection() as db:
            row = db.execute(
                "SELECT original FROM datasets WHERE id=? AND owner=?", (did, owner)
            ).fetchone()
            return json.loads(row["original"]) if row else None

    def save_version(self, dataset, expected, audit):
        with self.connection() as db:
            changed = db.execute(
                "UPDATE datasets SET version=?,body=? WHERE id=? AND owner=? AND version=?",
                (
                    dataset["version"],
                    json.dumps(dataset),
                    dataset["id"],
                    dataset["owner"],
                    expected,
                ),
            )
            if changed.rowcount != 1:
                raise Conflict(
                    "This dataset changed after your preview. Refresh and review the latest version."
                )
            for entry in audit:
                entry.update(
                    dataset_id=dataset["id"],
                    run_id=dataset["job_id"],
                    timestamp=time.time(),
                    version=dataset["version"],
                )
                db.execute(
                    "INSERT INTO audit(dataset_id,version,body) VALUES(?,?,?)",
                    (dataset["id"], dataset["version"], json.dumps(entry)),
                )

    def audit(self, did):
        with self.connection() as db:
            return [
                json.loads(r["body"])
                for r in db.execute("SELECT body FROM audit WHERE dataset_id=? ORDER BY id", (did,))
            ]

    def messages(self, did, entry=None):
        with self.connection() as db:
            if entry:
                db.execute(
                    "INSERT INTO messages(dataset_id,body) VALUES(?,?)", (did, json.dumps(entry))
                )
            return [
                json.loads(r["body"])
                for r in db.execute(
                    "SELECT body FROM messages WHERE dataset_id=? ORDER BY id DESC LIMIT 50", (did,)
                )
            ][::-1]

    def clear_messages(self, did: str):
        with self.connection() as db:
            db.execute("DELETE FROM messages WHERE dataset_id=?", (did,))

    def clear_owner_messages(self, owner: str):
        u1 = owner if owner.startswith("user_") else f"user_{owner}"
        u2 = owner[5:] if owner.startswith("user_") else owner
        with self.connection() as db:
            db.execute(
                "DELETE FROM messages WHERE dataset_id IN (SELECT id FROM datasets WHERE owner=? OR owner=?)",
                (u1, u2),
            )

    def cache(self, key, value=None):
        with self.connection() as db:
            if value is not None:
                db.execute("INSERT OR REPLACE INTO cache VALUES(?,?)", (key, json.dumps(value)))
            row = db.execute("SELECT body FROM cache WHERE key=?", (key,)).fetchone()
            return json.loads(row["body"]) if row else None

    def storage_bytes(self):
        with self.connection() as db:
            return db.execute("SELECT COALESCE(SUM(length(raw)),0) FROM jobs").fetchone()[0]

    def create_user(self, email: str, name: str, password: str) -> dict:
        email = email.strip().lower()
        salt = uuid.uuid4().hex
        pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
        uid = uuid.uuid4().hex
        now = time.time()
        with self.connection() as db:
            try:
                db.execute(
                    "INSERT INTO users(id, email, name, password_hash, salt, created) VALUES(?,?,?,?,?,?)",
                    (uid, email, name.strip() or email.split("@")[0], pwd_hash, salt, now),
                )
            except sqlite3.IntegrityError:
                raise Conflict("An account with this email already exists.")
            return {"id": uid, "email": email, "name": name.strip() or email.split("@")[0], "created": now}

    def authenticate_user(self, email: str, password: str) -> dict | None:
        email = email.strip().lower()
        with self.connection() as db:
            row = db.execute("SELECT id, email, name, password_hash, salt, created FROM users WHERE email=?", (email,)).fetchone()
            if not row:
                return None
            pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), row["salt"].encode("utf-8"), 100_000).hex()
            if pwd_hash != row["password_hash"]:
                return None
            return {"id": row["id"], "email": row["email"], "name": row["name"], "created": row["created"]}

    def create_session(self, user_id: str) -> str:
        token = "usr_" + uuid.uuid4().hex + uuid.uuid4().hex
        now = time.time()
        with self.connection() as db:
            db.execute("INSERT INTO sessions(token, user_id, created) VALUES(?,?,?)", (token, user_id, now))
            return token

    def get_user_by_session(self, token: str) -> dict | None:
        if not token:
            return None
        with self.connection() as db:
            row = db.execute(
                "SELECT u.id, u.email, u.name, u.created FROM users u JOIN sessions s ON u.id = s.user_id WHERE s.token=?",
                (token,),
            ).fetchone()
            return dict(row) if row else None

    def delete_session(self, token: str):
        with self.connection() as db:
            db.execute("DELETE FROM sessions WHERE token=?", (token,))

    def clear_owner_workspace(self, owner: str):
        with self.connection() as db:
            db.execute(
                "DELETE FROM audit WHERE dataset_id IN (SELECT id FROM datasets WHERE owner=?)",
                (owner,),
            )
            db.execute(
                "DELETE FROM messages WHERE dataset_id IN (SELECT id FROM datasets WHERE owner=?)",
                (owner,),
            )
            db.execute("DELETE FROM datasets WHERE owner=?", (owner,))
            db.execute("DELETE FROM jobs WHERE owner=?", (owner,))

