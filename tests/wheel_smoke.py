"""Install built wheel into an isolated environment and exercise outside the source tree."""
from pathlib import Path
import os
import subprocess
import tempfile
import venv

root = Path(__file__).resolve().parents[1]
wheel = next((root / 'dist').glob('*.whl'))
with tempfile.TemporaryDirectory() as directory:
    scratch = Path(directory)
    venv.EnvBuilder(with_pip=True).create(scratch / 'env')
    python = scratch / 'env' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    def run(*args):
        subprocess.run([str(python), *args], cwd=scratch, check=True)
    run('-m', 'pip', 'install', str(wheel))
    run('-c', 'from eventcaption_ai.contract import SCHEMA; assert SCHEMA["$id"] == "urn:causalstream:event-caption:1"')
    run('-m', 'eventcaption_ai', '--help')
    run('-m', 'eventcaption_ai.inference', '--help')
    run('-m', 'eventcaption_ai', 'demo', '--output', 'demo')
    run('-m', 'eventcaption_ai', 'replay', 'demo/records.jsonl')
