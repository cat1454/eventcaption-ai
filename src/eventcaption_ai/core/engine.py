"""Reference causal orchestration; policies receive only a snapshot and bounded memory."""
from copy import deepcopy
import json


class Engine:
    def __init__(self, ledger, policy, max_events=16, max_bytes=16384, use_memory=True):
        if type(max_events) is not int or max_events < 1 or type(max_bytes) is not int or max_bytes < 1:
            raise ValueError("Invalid memory limits")
        self.ledger, self.policy = ledger, policy
        self.max_events, self.max_bytes, self.use_memory = max_events, max_bytes, use_memory
        self._memory = []
        self.last_cutoff = ledger.last_cutoff()
        cursor = 0
        while rows := ledger.read_after(cursor):
            for record in rows:
                self._remember(record)
            cursor = rows[-1]["sequence_no"]

    def _remember(self, record):
        self._memory = [r for r in self._memory if r["event_id"] != record["event_id"]]
        if record["operation"] != "withdraw":
            self._memory.append(deepcopy(record))
        while self._memory and (len(self._memory) > self.max_events or len(json.dumps(self._memory, ensure_ascii=False).encode("utf-8")) > self.max_bytes):
            self._memory.pop(0)

    def memory(self):
        return deepcopy(self._memory)

    def step(self, snapshot, emitted_ms, provenance=None):
        if snapshot.cutoff_ms < self.last_cutoff or any(r["evidence_cutoff_ms"] > snapshot.cutoff_ms for r in self._memory):
            raise ValueError("Cannot replay an earlier prefix into a later state")
        # Active state remains necessary even in the no-history ablation, to target revisions.
        active = [{k: r[k] for k in ("event_id", "record_id", "version", "text", "start_ms", "end_ms", "event_status")} for r in self._memory]
        memory = self.memory() if self.use_memory else []
        historical = {}
        for record in memory:
            for ref, timestamp in record["evidence_timestamps"].items():
                if ref in historical and historical[ref] != timestamp:
                    raise ValueError("Conflicting memory evidence")
                historical[ref] = timestamp
        evidence = dict(historical)
        for ref, timestamp in snapshot.evidence().items():
            if ref in evidence and evidence[ref] != timestamp:
                raise ValueError("Conflicting snapshot evidence")
            evidence[ref] = timestamp
        context = dict(cutoff_ms=snapshot.cutoff_ms, frames=snapshot.frames,
                       evidence=evidence, memory=memory, active_events=active)
        decision = self.policy(deepcopy(context))
        emitted = emitted_ms() if callable(emitted_ms) else emitted_ms
        record = self.ledger.submit(decision, snapshot, emitted, provenance or {}, historical)
        self.last_cutoff = snapshot.cutoff_ms
        if record:
            self._remember(record)
        return record
