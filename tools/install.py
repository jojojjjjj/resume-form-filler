#!/usr/bin/env python3
"""Install the self-contained skill in a project; never touch global configuration."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import tempfile

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / 'skills/resume-form-filler'
SHIM = '''#!/usr/bin/env python3
"""resume-form-filler managed project entrypoint."""
from pathlib import Path
import runpy
import sys
scripts = Path(__file__).resolve().parents[1] / '.agents/skills/resume-form-filler/scripts'
sys.path.insert(0, str(scripts))
runpy.run_path(str(scripts / 'run.py'), run_name='__main__')
'''

def install(project, replace=False):
    project = Path(project).expanduser().resolve()
    target = project / '.agents/skills/resume-form-filler'
    if SOURCE == target or SOURCE in target.parents or target in SOURCE.parents:
        raise ValueError('Source and destination must not contain one another')
    shim = project / 'tools/resume-fill.py'
    if shim.exists() and 'resume-form-filler managed project entrypoint' not in shim.read_text(encoding='utf-8'):
        raise ValueError('Existing tools/resume-fill.py is unmanaged; preserve it and call the installed skill scripts/run.py directly or choose another project')
    if target.exists() and not replace:
        raise ValueError('Skill already exists; --replace backs it up before upgrading')
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    with tempfile.TemporaryDirectory(prefix='rff-install-') as tmp:
        staged = Path(tmp) / 'skill'
        shutil.copytree(SOURCE, staged, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '._*'))
        if target.exists():
            backup = project / '.resume-form-filler' / 'skill-backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(target, backup, symlinks=False)
            shutil.rmtree(target)
        shutil.copytree(staged, target)
    shim.parent.mkdir(parents=True, exist_ok=True)
    shim.write_text(SHIM, encoding='utf-8')
    state = project / '.resume-form-filler'
    state.mkdir(exist_ok=True)
    (state / '.gitignore').write_text('*\n!.gitignore\n', encoding='utf-8')
    ignore = project / '.gitignore'
    old = ignore.read_text(encoding='utf-8') if ignore.exists() else ''
    if '/.resume-form-filler/' not in old.splitlines():
        ignore.write_text(old + ('\n' if old and not old.endswith('\n') else '') + '/.resume-form-filler/\n', encoding='utf-8')
    return {'skill': str(target), 'entrypoint': str(shim), 'backup': str(backup) if backup else None}

if __name__ == '__main__':
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--replace', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(install(args.project, args.replace), ensure_ascii=False, indent=2))
    except Exception as exc:
        parser.exit(1, str(exc) + '\n')
