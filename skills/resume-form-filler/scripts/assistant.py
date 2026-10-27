"""First-run import, environment diagnostics, and existing form workflow."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from context import ROOT, STATE, PROFILE, SKILL, init_state
from ingest import import_resume, review_profile

def doctor(browser=False):
    chrome = next((str(p) for p in (
        Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
        Path('/Applications/Chromium.app/Contents/MacOS/Chromium'),
        Path(os.environ.get('PROGRAMFILES', '')) / 'Google/Chrome/Application/chrome.exe',
        Path(os.environ.get('LOCALAPPDATA', '')) / 'Google/Chrome/Application/chrome.exe') if p.is_file()), None)
    chrome = chrome or shutil.which('google-chrome') or shutil.which('chromium') or shutil.which('chromium-browser')
    result = {'state': 'environment_ready', 'python': sys.version.split()[0], 'project': str(ROOT),
              'data_dir': str(STATE), 'chrome': chrome,
              'dependencies': {p: importlib.metadata.version(p) for p in ('browser-harness', 'pypdf', 'python-docx', 'pylatexenc')},
              'legacy_doc_converter': shutil.which('textutil') or shutil.which('libreoffice') or shutil.which('soffice'),
              'browser_connection': 'not_checked',
              'notes': ['Dependencies are project-local. Browser login/debugging permission is local to this computer.']}
    if not chrome:
        result['notes'].append('Chrome not discovered. Install Chrome manually or use an explicit remote CDP endpoint; no system browser is installed.')
    if browser:
        # Explicit opt-in only; unlike ordinary doctor this may contact Chrome.
        proc = subprocess.run([sys.executable, str(SKILL / 'scripts/harness.py'), 'doctor', '--json'], capture_output=True, text=True, timeout=90)
        result['browser_connection'] = 'ready' if proc.returncode == 0 else 'blocked'
        result['browser_diagnostics'] = proc.stdout[-6000:]
        if proc.returncode:
            result['state'] = 'browser_blocked'
    return result

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    workflows = {'start', 'apply', 'verify', 'checkpoint', 'ui', 'update', 'refresh-sources'}
    if argv and argv[0] in workflows:
        from workflow import main as run_workflow
        return run_workflow(argv)
    parser = argparse.ArgumentParser(description='Persistent local resume assistant. Form commands: start, apply, verify, checkpoint, ui, update, refresh-sources.')
    sub = parser.add_subparsers(dest='command')
    q = sub.add_parser('init', help='Import PDF, LaTeX or Word into a reviewable draft')
    q.add_argument('--resume', required=True)
    q = sub.add_parser('review-profile', help='Persist a source-checked structured draft')
    q.add_argument('--draft', required=True)
    q.add_argument('--source', required=True, help='Actual basis of source review; do not invent user confirmation')
    q.add_argument('--reviewed', action='store_true', required=True)
    q.add_argument('--replace-reviewed', action='store_true')
    q = sub.add_parser('doctor', help='Check local dependencies; does not contact Chrome by default')
    q.add_argument('--browser', action='store_true')
    sub.add_parser('status')
    args = parser.parse_args(argv)
    init_state()
    if args.command == 'init':
        result = import_resume(args.resume)
        result['environment'] = doctor()
    elif args.command == 'review-profile':
        result = review_profile(args.draft, args.source, args.replace_reviewed)
    elif args.command == 'doctor':
        result = doctor(args.browser)
    elif PROFILE.exists():
        from workflow import current_profile
        data = current_profile()
        result = {'state': 'ready', 'profile': str(PROFILE), 'pending': list(data.get('pending_confirmations', {}))}
    else:
        result = {'state': 'resume_required', 'next': 'Run init --resume /path/to/resume.pdf (also .tex, .docx or .doc); then have the calling AI assistant review the draft.'}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result['state'] == 'browser_blocked':
        return 1
    return 0

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'state': 'blocked', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
