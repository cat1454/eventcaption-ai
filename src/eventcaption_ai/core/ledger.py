"""Durable decision log and append-only captions; separate from online-update/1."""
from copy import deepcopy
import json
import sqlite3
import threading
import uuid

from ..core.contract import CONTENT, finite, validate_decision, validate_evidence, validate_record, validate_transition


class Ledger:
    def __init__(self, path, session_id):
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("Nonempty session ID required")
        self.session_id = session_id
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS metadata(session TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS records(seq INTEGER PRIMARY KEY, record_id TEXT UNIQUE NOT NULL,
              event_id TEXT NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL, UNIQUE(event_id,version));
            CREATE TABLE IF NOT EXISTS decisions(seq INTEGER PRIMARY KEY, cutoff REAL NOT NULL,
              emitted REAL NOT NULL, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS evidence(ref TEXT PRIMARY KEY, timestamp REAL NOT NULL);
            CREATE TRIGGER IF NOT EXISTS immutable_records_update BEFORE UPDATE ON records
              BEGIN SELECT RAISE(ABORT, 'append-only'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_records_delete BEFORE DELETE ON records
              BEGIN SELECT RAISE(ABORT, 'append-only'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_decisions_update BEFORE UPDATE ON decisions
              BEGIN SELECT RAISE(ABORT, 'append-only'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_decisions_delete BEFORE DELETE ON decisions
              BEGIN SELECT RAISE(ABORT, 'append-only'); END;
        """)
        try:
            with self.db:
                self.db.execute("BEGIN IMMEDIATE")
                row = self.db.execute("SELECT session FROM metadata").fetchone()
                if row and row[0] != session_id:
                    raise ValueError("Ledger belongs to another session")
                if not row:
                    self.db.execute("INSERT INTO metadata VALUES (?)", (session_id,))
        except BaseException:
            self.db.close()
            raise

    def submit(self, decision, snapshot, emitted_ms, provenance, memory_evidence=None):
        evidence = dict(memory_evidence or {})
        for ref, timestamp in snapshot.evidence().items():
            if ref in evidence and evidence[ref] != timestamp:
                raise ValueError("Conflicting evidence timestamp")
            evidence[ref] = timestamp
        validate_evidence(evidence, snapshot.cutoff_ms)
        validate_decision(decision, snapshot.cutoff_ms, evidence)
        finite(emitted_ms, "emission clock")
        if not isinstance(provenance, dict):
            raise ValueError("Provenance must be an object")
        with self.lock, self.db:
            self.db.execute("BEGIN IMMEDIATE")
            last = self.db.execute("SELECT seq,cutoff,emitted FROM decisions ORDER BY seq DESC LIMIT 1").fetchone()
            if last and (snapshot.cutoff_ms < last[1] or emitted_ms < last[2]):
                raise ValueError("Source/emission clock moved backwards")
            for ref, timestamp in evidence.items():
                registered = self.db.execute("SELECT timestamp FROM evidence WHERE ref=?", (ref,)).fetchone()
                if registered and registered[0] != timestamp:
                    raise ValueError("Evidence identity changed timestamp")
                self.db.execute("INSERT OR IGNORE INTO evidence VALUES(?,?)", (ref, timestamp))
            record = None
            if decision["action"] != "WAIT":
                old = None
                if decision["previous_record_id"] is not None:
                    row = self.db.execute("SELECT body FROM records WHERE record_id=?", (decision["previous_record_id"],)).fetchone()
                    if row is None:
                        raise ValueError("Unknown previous record")
                    target = json.loads(row[0])
                    old = json.loads(self.db.execute("SELECT body FROM records WHERE event_id=? ORDER BY version DESC LIMIT 1", (target["event_id"],)).fetchone()[0])
                seq = self.db.execute("SELECT COALESCE(MAX(seq),0)+1 FROM records").fetchone()[0]
                record = {k: deepcopy(decision[k]) for k in CONTENT}
                record.update(schema_version="event-caption/1", session_id=self.session_id,
                              sequence_no=seq, record_id=str(uuid.uuid4()),
                              event_id=old["event_id"] if old else str(uuid.uuid4()),
                              version=old["version"] + 1 if old else 1,
                              previous_record_id=decision["previous_record_id"],
                              operation={"EMIT": "create", "REVISE": "revise", "WITHDRAW": "withdraw"}[decision["action"]],
                              evidence_cutoff_ms=snapshot.cutoff_ms,
                              evidence_timestamps={r: evidence[r] for r in decision["evidence_refs"]},
                              emitted_elapsed_ms=emitted_ms, provenance=deepcopy(provenance))
                validate_record(record)
                validate_transition(old, record)
                body = json.dumps(record, ensure_ascii=False, allow_nan=False)
                self.db.execute("INSERT INTO records VALUES(?,?,?,?,?)", (seq, record["record_id"], record["event_id"], record["version"], body))
            trace = dict(decision=decision, evidence_cutoff_ms=snapshot.cutoff_ms, emitted_elapsed_ms=emitted_ms,
                         record_id=record["record_id"] if record else None, provenance=provenance)
            self.db.execute("INSERT INTO decisions VALUES(?,?,?,?)", (last[0] + 1 if last else 1, snapshot.cutoff_ms, emitted_ms, json.dumps(trace, ensure_ascii=False, allow_nan=False)))
        return deepcopy(record)

    def read_after(self, cursor=0, limit=100):
        if type(cursor) is not int or cursor < 0 or type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("Invalid cursor/limit")
        with self.lock:
            return [json.loads(r[0]) for r in self.db.execute("SELECT body FROM records WHERE seq>? ORDER BY seq LIMIT ?", (cursor, limit))]

    def decisions(self):
        with self.lock:
            return [json.loads(r[0]) for r in self.db.execute("SELECT body FROM decisions ORDER BY seq")]

    def last_cutoff(self):
        with self.lock:
            row = self.db.execute("SELECT cutoff FROM decisions ORDER BY seq DESC LIMIT 1").fetchone()
            return row[0] if row else -1

    def export(self, path):
        with open(path, "x", encoding="utf-8") as stream:
            cursor = 0
            while rows := self.read_after(cursor):
                for record in rows:
                    stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
                cursor = rows[-1]["sequence_no"]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.db.close()


class Consumer:
    """Strict reference consumer; duplicate replay must be byte-equivalent JSON data."""
    def __init__(self):
        self.cursor = 0
        self.session_id = None
        self.events = {}
        self.history = {}
        self.last_emitted = self.last_cutoff = -1
        self.evidence = {}

    def apply(self, record):
        validate_record(record)
        if self.session_id is not None and self.session_id != record["session_id"]:
            raise ValueError("Mixed sessions")
        seq = record["sequence_no"]
        if seq <= self.cursor:
            if self.history.get(seq) != record:
                raise ValueError("Conflicting replay")
            return False
        if seq != self.cursor + 1:
            raise ValueError("Missing records; replay from cursor")
        if record["emitted_elapsed_ms"] < self.last_emitted or record["evidence_cutoff_ms"] < self.last_cutoff:
            raise ValueError("Clock moved backwards")
        if any(r["record_id"] == record["record_id"] for r in self.history.values()):
            raise ValueError("Duplicate record ID")
        if any(ref in self.evidence and self.evidence[ref] != timestamp for ref, timestamp in record["evidence_timestamps"].items()):
            raise ValueError("Evidence identity changed timestamp")
        validate_transition(self.events.get(record["event_id"]), record)
        self.events[record["event_id"]] = deepcopy(record)
        self.history[seq] = deepcopy(record)
        self.cursor, self.session_id = seq, record["session_id"]
        self.last_emitted, self.last_cutoff = record["emitted_elapsed_ms"], record["evidence_cutoff_ms"]
        self.evidence.update(record["evidence_timestamps"])
        return True

    def current(self, event_id):
        return deepcopy(self.events[event_id])
