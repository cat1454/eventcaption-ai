"""Install built wheel into an isolated environment and exercise outside the source tree."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import venv

root = Path(__file__).resolve().parents[1]
wheel = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else next((root / 'dist').glob('*.whl'))
if not wheel.is_file():
    raise SystemExit(f'Wheel does not exist: {wheel}')
with tempfile.TemporaryDirectory() as directory:
    scratch = Path(directory)
    venv.EnvBuilder(with_pip=True).create(scratch / 'env')
    python = scratch / 'env' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    def run(*args):
        subprocess.run([str(python), *args], cwd=scratch, check=True)
    run('-m', 'pip', 'install', str(wheel))
    run('-c', 'from eventcaption_ai.contract import SCHEMA; assert SCHEMA["$id"] == "urn:causalstream:event-caption:1"')
    run('-c', 'from eventcaption_ai.contract import SCHEMA as old; from eventcaption_ai.core.contract import SCHEMA as new; assert old is new')
    run('-m', 'eventcaption_ai', '--help')
    run('-m', 'eventcaption_ai.inference', '--help')
    run('-m', 'eventcaption_ai.training', '--help')
    run('-m', 'eventcaption_ai.drive_inventory', '--help')
    run('-m', 'eventcaption_ai.execution.inference', '--help')
    run('-m', 'eventcaption_ai.learning.training', '--help')
    run('-m', 'eventcaption_ai.integrations.drive_inventory', '--help')
    run('-m', 'eventcaption_ai', 'demo', '--output', 'demo')
    run('-m', 'eventcaption_ai', 'replay', 'demo/records.jsonl')
