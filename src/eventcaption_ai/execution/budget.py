"""Persistent reservations: unclosed/crashed runs retain their full reservation."""
import sqlite3
import uuid

from ..core.contract import finite

LIMITS = {"feasibility": 4 * 3600, "A": 10 * 3600, "B": 10 * 3600,
          "ablation": 8 * 3600, "final": 4 * 3600, "reserve": 4 * 3600}


class Budget:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, stage TEXT NOT NULL, reserved REAL NOT NULL, actual REAL, status TEXT NOT NULL)")

    def used(self, stage):
        return self.db.execute("SELECT COALESCE(SUM(COALESCE(actual,reserved)),0) FROM runs WHERE stage=?", (stage,)).fetchone()[0]

    def reserve(self, stage, seconds):
        finite(seconds, "seconds")
        if stage not in LIMITS or not 0 < seconds <= 4 * 3600:
            raise ValueError("Unknown stage or run exceeds 4-hour cap")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            total = self.db.execute("SELECT COALESCE(SUM(COALESCE(actual,reserved)),0) FROM runs").fetchone()[0]
            if self.used(stage) + seconds > LIMITS[stage] or total + seconds > 40 * 3600:
                raise ValueError("Study/stage budget exhausted")
            run_id = str(uuid.uuid4())
            self.db.execute("INSERT INTO runs VALUES(?,?,?,NULL,'reserved')", (run_id, stage, seconds))
        return run_id

    def finish(self, run_id, actual_seconds, status):
        finite(actual_seconds, "actual_seconds")
        if status not in ("completed", "failed", "interrupted", "timeout"):
            raise ValueError("Invalid terminal status")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None or row[0] != "reserved":
                raise ValueError("Unknown or already closed run")
            # Record actual overrun honestly, blocking later reservations if exhausted.
            self.db.execute("UPDATE runs SET actual=?,status=? WHERE id=?", (actual_seconds, status, run_id))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.db.close()
