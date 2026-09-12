"""Small durable workspace with atomic SQLite state changes."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3


def now():
    return datetime.now(timezone.utc).isoformat()


def valid_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{32}", value):
        raise KeyError("Invalid identifier")
    return value


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        for folder in ("uploads", "results", "exports", "templates"):
            (self.root / folder).mkdir(exist_ok=True)
        self.database = self.root / "state.sqlite"
        with self.connection() as con:
            con.execute("PRAGMA journal_mode=WAL")
            for table in ("uploads", "jobs", "results"):
                con.execute(f"CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")

    @contextmanager
    def connection(self):
        con = sqlite3.connect(self.database, timeout=30)
        try:
            yield con
            con.commit()
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()

    def put(self, table, item):
        assert table in {"uploads", "jobs", "results"}
        valid_id(item["id"])
        with self.connection() as con:
            con.execute(f"INSERT OR REPLACE INTO {table} (id,payload) VALUES (?,?)",
                        (item["id"], json.dumps(item, ensure_ascii=False, allow_nan=False)))
        return item

    def get(self, table, item_id):
        assert table in {"uploads", "jobs", "results"}
        valid_id(item_id)
        with self.connection() as con:
            row = con.execute(f"SELECT payload FROM {table} WHERE id=?", (item_id,)).fetchone()
        if row is None:
            raise KeyError("Unknown identifier")
        return json.loads(row[0])

    def all(self, table):
        assert table in {"uploads", "jobs", "results"}
        with self.connection() as con:
            rows = con.execute(f"SELECT payload FROM {table} ORDER BY rowid DESC").fetchall()
        return [json.loads(row[0]) for row in rows]

    def patch_job(self, job_id, **changes):
        valid_id(job_id)
        with self.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT payload FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError("Unknown job")
            job = json.loads(row[0])
            if job["status"] == "cancelled" and changes.get("status") != "cancelled":
                return job
            job.update(changes)
            job["updated_at"] = now()
            con.execute("UPDATE jobs SET payload=? WHERE id=?",
                        (json.dumps(job, ensure_ascii=False, allow_nan=False), job_id))
        return job

    def upload_path(self, upload):
        return self.root / "uploads" / (valid_id(upload["id"]) + upload["suffix"])

    def result_path(self, result_id):
        return self.root / "results" / (valid_id(result_id) + ".json")


class WorkspaceLock:
    """Prevent two local services from scheduling against the same workspace."""
    def __init__(self, root):
        self.path = Path(root) / ".service.lock"
        self.stream = None

    def acquire(self):
        self.stream = self.path.open("a+b")
        self.stream.seek(0)
        if not self.stream.read(1):
            self.stream.write(b"0")
            self.stream.flush()
        self.stream.seek(0)
        try:
            import os
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, IOError) as exc:
            self.stream.close()
            self.stream = None
            raise RuntimeError("This workspace is already open in another Hyper-Brain service.") from exc

    def release(self):
        if self.stream is not None:
            self.stream.close()
            self.stream = None
