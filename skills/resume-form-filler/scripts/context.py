"""Installation-independent project paths. Personal state never lives in the skill."""
import os
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
def project_root():
    if os.environ.get('RF_PROJECT_ROOT'):
        return Path(os.environ['RF_PROJECT_ROOT']).expanduser().resolve()
    if SKILL.parent.name == 'skills' and SKILL.parent.parent.name == '.agents':
        return SKILL.parent.parent.parent
    return SKILL.parents[1]  # repository/skills/resume-form-filler

ROOT = project_root()
STATE = ROOT / '.resume-form-filler'
PROFILE = STATE / 'profile.md'
SITES = STATE / 'sites'
RUNS = STATE / 'runs'

def private_dir(path):
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass  # Some external filesystems do not implement Unix permissions.
    return path

def init_state():
    private_dir(STATE)
    (STATE / '.gitignore').write_text('*\n!.gitignore\n', encoding='utf-8')
    for name in ('imports', 'sites', 'runs', 'helpers', 'runtime', 'cache'):
        private_dir(STATE / name)
    return STATE
