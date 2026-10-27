"""Project-local dependency bootstrap, shared by resume and browser entrypoints."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import venv
from context import STATE, init_state

REQUIREMENTS = Path(__file__).with_name('requirements.txt')

def ensure_runtime():
    init_state()
    if sys.version_info < (3, 12):
        candidate = shutil.which('python3.12')
        if not candidate:
            from bootstrap_python import project_python
            candidate = project_python(STATE)
        command = [candidate, str(Path(sys.argv[0]).resolve()), *sys.argv[1:]]
        raise SystemExit(subprocess.call(command))
    identity = '|'.join((platform.node(), platform.system(), platform.machine(), str(sys.version_info[:2]), str(Path(sys.base_prefix).resolve())))
    key = hashlib.sha256(identity.encode()).hexdigest()[:12]
    host = STATE / 'runtime' / key
    python = host / 'venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    marker = host / 'installed.json'
    fingerprint = hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()
    env = os.environ.copy()
    env['PIP_CACHE_DIR'] = str(STATE / 'cache' / 'pip')
    env['PYTHONPYCACHEPREFIX'] = str(host / 'pycache')
    env['PYTHONNOUSERSITE'] = '1'
    env.pop('PYTHONPATH', None)
    ready = False
    if python.is_file() and marker.is_file():
        try:
            ready = json.loads(marker.read_text())['requirements_sha256'] == fingerprint
        except (ValueError, KeyError):
            pass
    if not python.is_file():
        print('Creating project-local Python environment...', file=sys.stderr)
        venv.EnvBuilder(with_pip=True, symlinks=False).create(host / 'venv')
    if ready:
        check = subprocess.run([str(python), '-c', 'import browser_harness, pypdf, docx, pylatexenc'], env=env, capture_output=True)
        ready = check.returncode == 0
    if not ready:
        print('Installing resume parser and Browser Harness dependencies in this project...', file=sys.stderr)
        subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(REQUIREMENTS)], env=env, check=True, stdout=sys.stderr)
        subprocess.run([str(python), '-c', 'import browser_harness, pypdf, docx, pylatexenc'], env=env, check=True)
        marker.write_text(json.dumps({'requirements_sha256': fingerprint, 'identity': identity}) + '\n')
    return python, host, env
