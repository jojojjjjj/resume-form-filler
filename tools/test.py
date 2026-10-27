#!/usr/bin/env python3
"""Run tests with this project's dependency runtime; --browser opts into an isolated local browser fixture."""
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/resume-form-filler/scripts'))
from runtime import ensure_runtime

if __name__ == '__main__':
    python, _, env = ensure_runtime()
    status = subprocess.call([str(python), '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'), '-p', 'test_*.py', '-v'], cwd=ROOT, env=env)
    if status == 0 and '--browser' in sys.argv:
        status = subprocess.call([str(python), str(ROOT / 'tests/browser_fixture.py')], cwd=ROOT, env=env)
    raise SystemExit(status)
