#!/usr/bin/env python3
"""Bootstrap dependencies locally, then run the persistent resume assistant."""
from pathlib import Path
import subprocess
import sys
from runtime import ensure_runtime

def main():
    python, _, env = ensure_runtime()
    return subprocess.call([str(python), str(Path(__file__).with_name('assistant.py')), *sys.argv[1:]], env=env)

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('Environment setup failed: ' + str(exc), file=sys.stderr)
        raise SystemExit(1)
