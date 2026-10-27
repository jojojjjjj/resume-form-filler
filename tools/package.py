#!/usr/bin/env python3
"""Create an allowlisted source release archive and SHA256SUMS."""
import hashlib
from pathlib import Path
import zipfile
from check import ROOT, check, public_files

if __name__ == '__main__':
    check()
    folder = ROOT / 'dist'; folder.mkdir(exist_ok=True)
    archive = folder / 'resume-form-filler-v1.0.0.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as handle:
        for name in public_files():
            handle.write(ROOT / name, 'resume-form-filler/' + name)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (folder / 'SHA256SUMS').write_text(digest + '  ' + archive.name + '\n', encoding='utf-8')
    print(archive)
