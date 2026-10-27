#!/usr/bin/env python3
"""Run the official Browser Harness with state scoped to this project."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from context import ROOT
from runtime import ensure_runtime

def main():
    python, host, env = ensure_runtime()
    key = hashlib.sha256(str(ROOT).encode()).hexdigest()[:12]
    # macOS limits the whole Unix socket path to 104 bytes; its per-user
    # tempfile directory plus a daemon name can already exceed that limit.
    ipc_root = Path('/tmp') if os.name != 'nt' else Path(tempfile.gettempdir())
    env.update({
        'BH_HOME': str(host / 'browser-state'),
        'BH_RUNTIME_DIR': str(ipc_root / ('rff-' + key)),
        'BH_RUNTIME_DIR_SHARED': '1', 'BH_TMP_DIR_SHARED': '1',
        'BH_TMP_DIR': str(host / 'tmp'),
        'BH_AGENT_WORKSPACE': str(host / 'agent-workspace'),
        'BH_RECORD': '0', 'BH_TAB_MARKER': '0', 'BH_TELEMETRY': '0',
    })
    args = sys.argv[1:]
    if args[:1] == ['--mcp']:
        command = [str(python), '-c', 'from browser_harness.mcp_cli import main; main()', *args[1:]]
    else:
        command = [str(python), '-m', 'browser_harness.run', *args]
    return subprocess.call(command, env=env)

if __name__ == '__main__':
    raise SystemExit(main())
