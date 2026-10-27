#!/usr/bin/env python3
"""Validate the explicit public file set before packaging or publication."""
import ast
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def public_files():
    paths = (ROOT / 'PUBLIC_FILES.txt').read_text(encoding='utf-8').splitlines()
    if len(paths) != len(set(paths)):
        raise ValueError('Duplicate public manifest entry')
    for name in paths:
        path = ROOT / name
        if Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink() or not path.is_file():
            raise ValueError('Invalid public file: ' + name)
        if any(part in {'.resume-form-filler', 'memory', '.runtime', '.bootstrap', '__pycache__', '.git'} for part in path.relative_to(ROOT).parts):
            raise ValueError('Private/runtime file in public manifest: ' + name)
    return paths

def check():
    paths = public_files()
    for name in paths:
        text = (ROOT / name).read_text(encoding='utf-8')
        if name.endswith('.py'):
            ast.parse(text, filename=name)
        forbidden = [r'gh[pousr]_[A-Za-z0-9]{20,}', r'(?<!\d)\d{17}[\dXx](?!\d)',
                     '/' + r'Users/[^\s/]+/', '/' + r'Volumes/[^\s/]+/']
        if any(re.search(pattern, text) for pattern in forbidden):
            raise ValueError('Potential private path/secret in public file: ' + name)
        if name.endswith('.md'):
            for link in re.findall(r'\]\(([^)]+)\)', text):
                if '://' in link or link.startswith('#'):
                    continue
                target = link.split('#')[0]
                if target and not (ROOT / name).parent.joinpath(target).exists():
                    raise ValueError('Broken documentation link in ' + name + ': ' + target)
    skill = (ROOT / 'skills/resume-form-filler/SKILL.md').read_text(encoding='utf-8')
    if not skill.startswith('---\nname: resume-form-filler\ndescription:'):
        raise ValueError('Invalid skill frontmatter')
    if (ROOT / '.git').exists():
        result = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, check=True, capture_output=True)
        tracked = set(result.stdout.decode().split('\0')) - {''}
        if tracked != set(paths):
            raise ValueError('Tracked files differ from public allowlist: ' + repr(sorted(tracked ^ set(paths))))
    return {'state': 'passed', 'public_files': len(paths)}

if __name__ == '__main__':
    import json
    print(json.dumps(check(), indent=2))
