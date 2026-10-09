"""Budgeted subprocess execution including load; no retries or overwritten runs."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from .budget import Budget


def _stop_tree(child):
    if child.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=15)
    else:
        os.killpg(child.pid, signal.SIGTERM)
    try:
        child.wait(timeout=3)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            os.killpg(child.pid, signal.SIGKILL)
        else:
            child.kill()
        child.wait(timeout=3)


def supervise(command, output, budget_path, stage, seconds):
    if not isinstance(command, list) or not command or any(not isinstance(s, str) for s in command):
        raise ValueError("Command must be an argv list, not shell text")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    with Budget(budget_path) as budget:
        run_id = budget.reserve(stage, seconds)
        receipt = dict(run_id=run_id, stage=stage, reserved_seconds=seconds, command=command,
                       status="reserved", error=None, exit_code=None)
        (output / "reservation.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        started = time.perf_counter()
        child = None
        try:
            with (output / "stdout.log").open("xb") as stdout, (output / "stderr.log").open("xb") as stderr:
                child = subprocess.Popen(command, stdout=stdout, stderr=stderr, shell=False,
                    env=dict(os.environ, PYTHONIOENCODING="utf-8"),
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), start_new_session=os.name != "nt")
                try:
                    receipt["exit_code"] = child.wait(timeout=max(.001, seconds - (time.perf_counter() - started)))
                    receipt["status"] = "completed" if receipt["exit_code"] == 0 else "failed"
                except subprocess.TimeoutExpired:
                    receipt["status"] = "timeout"
        except KeyboardInterrupt:
            receipt["status"] = "interrupted"
        except Exception as exc:
            receipt.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        finally:
            try:
                if child is not None:
                    _stop_tree(child)
                    receipt["exit_code"] = child.returncode
            finally:
                receipt["elapsed_seconds"] = time.perf_counter() - started
                # If killing failed, conservatively retain the reservation.
                if child is None or child.poll() is not None:
                    budget.finish(run_id, receipt["elapsed_seconds"], receipt["status"])
                else:
                    receipt["error"] = "Worker still alive; full reservation retained"
                with (output / "receipt.json").open("x", encoding="utf-8") as stream:
                    json.dump(receipt, stream, indent=2)
        return receipt
