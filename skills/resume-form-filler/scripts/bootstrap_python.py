"""Download a Python runtime inside this project when the host Python is old."""
import hashlib
import io
import os
from pathlib import Path
import platform
import subprocess
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile

UV_VERSION = '0.12.23'
DIGESTS = {
    'aarch64-apple-darwin': '50487ae565ccd96e499056b4674d438f4c53170202617b4c759defe0c6a1b544',
    'x86_64-apple-darwin': '960da44cb4b73685206ddd250b19e0a117fa41095710c1038f081f5cb613efb4',
    'aarch64-unknown-linux-gnu': '6524bd338177ed50d035d39354e12545e993bbeba2ecbddf0480c5b3a81d313f',
    'x86_64-unknown-linux-gnu': '9167d72b3319674b6303c4cbe071854bba13ebdf3d76b1a7cbdc175471fb66d6',
    'aarch64-pc-windows-msvc': '13294e232ececbe709c06b74e6ced06f2a225ea5591476685362f22be56a50d5',
    'x86_64-pc-windows-msvc': '75d05de6762778c31ee183398de7dd15093fad0ed90b1f236d8205ea5ec00c90',
}

def project_python(root):
    machine = platform.machine().lower()
    arch = {'arm64': 'aarch64', 'aarch64': 'aarch64', 'amd64': 'x86_64', 'x86_64': 'x86_64'}.get(machine)
    target_os = {'Darwin': 'apple-darwin', 'Linux': 'unknown-linux-gnu', 'Windows': 'pc-windows-msvc'}.get(platform.system())
    target = '%s-%s' % (arch, target_os)
    if target not in DIGESTS:
        raise RuntimeError('Automatic Python setup is unavailable for this platform; provide Python 3.12+.')
    home = root / '.bootstrap' / target
    home.mkdir(parents=True, exist_ok=True)
    executable = 'uv.exe' if os.name == 'nt' else 'uv'
    uv = home / executable
    if not uv.exists():
        extension = '.zip' if os.name == 'nt' else '.tar.gz'
        url = 'https://github.com/astral-sh/uv/releases/download/%s/uv-%s%s' % (UV_VERSION, target, extension)
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != DIGESTS[target]:
            raise RuntimeError('uv archive checksum mismatch')
        if os.name == 'nt':
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                member = next(n for n in archive.namelist() if Path(n).name == executable)
                contents = archive.read(member)
        else:
            with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
                member = next(m for m in archive.getmembers() if Path(m.name).name == executable and m.isfile())
                contents = archive.extractfile(member).read()
        uv.write_bytes(contents)
        uv.chmod(0o755)
    env = os.environ.copy()
    env.update({
        'UV_PYTHON_INSTALL_DIR': str(home / 'python'),
        'UV_PYTHON_BIN_DIR': str(home / 'bin'),
        'UV_CACHE_DIR': str(root / '.cache' / 'uv'),
        'UV_TOOL_DIR': str(home / 'tools'),
        'UV_NO_MODIFY_PATH': '1',
    })
    # exFAT cannot create Python's internal symlinks. Extract temporarily on the
    # OS filesystem, then copy real files into the project and remove staging.
    existing = subprocess.run([str(uv), '--no-config', 'python', 'find', '3.12', '--managed-python'], env=env, capture_output=True, text=True)
    if existing.returncode != 0:
        with tempfile.TemporaryDirectory(prefix='rff-python-') as stage:
            staged_env = dict(env, UV_PYTHON_INSTALL_DIR=stage)
            subprocess.run([str(uv), '--no-config', 'python', 'install', '3.12', '--no-bin', '--no-registry'], env=staged_env, check=True)
            for installation in Path(stage).glob('cpython-*'):
                shutil.copytree(installation, home / 'python' / installation.name, symlinks=False, dirs_exist_ok=True)
    result = subprocess.run([str(uv), '--no-config', 'python', 'find', '3.12', '--managed-python'], env=env, check=True, capture_output=True, text=True)
    return result.stdout.strip()

if __name__ == '__main__':
    print(project_python(Path(__file__).resolve().parent))
