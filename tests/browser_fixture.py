"""Opt-in end-to-end test using a fresh headless Chrome, never a user profile."""
import contextlib
import functools
import http.server
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'skills/resume-form-filler/scripts'))
import ingest
import workflow as w

FIXTURE = '''<!doctype html><meta charset="utf-8"><title>Synthetic resume fixture</title>
<label for="name">Name</label><input id="name" required>
<label for="desc">Description</label><textarea id="desc"></textarea>
<label for="date">Date</label><input id="date">
<label for="degree">Degree</label><select id="degree"><option></option><option>Example degree</option></select>
<label for="ac">School</label><input id="ac" oninput="document.querySelector('#menu').hidden=false">
<span id="selected"></span><div id="menu" hidden><div role="option" onclick="document.querySelector('#selected').innerText=this.innerText;this.parentElement.hidden=true">Example University</div></div>
<label for="passport">Passport</label><input id="passport" aria-label="Passport" value="SYNTHETIC-PASSPORT">
<button id="save" onclick="localStorage.setItem('savedName',document.querySelector('#name').value);document.querySelector('#message').textContent='Saved successfully'">Save</button>
<div id="message" role="alert"></div>
<script>document.querySelector('#name').value=localStorage.getItem('savedName')||'';</script>
'''

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

def main():
    chrome = next((p for p in ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', shutil.which('google-chrome'), shutil.which('chromium')) if p and Path(p).is_file()), None)
    if not chrome:
        raise RuntimeError('Isolated browser fixture requires a local Chrome executable')
    passed = []
    with tempfile.TemporaryDirectory(prefix='rff-browser-test-') as tmp:
        root = Path(tmp).resolve()
        (root/'index.html').write_text(FIXTURE)
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(root)))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        url = 'http://127.0.0.1:%d/index.html' % server.server_port
        chrome_profile = root/'chrome'
        browser = subprocess.Popen([chrome, '--headless=new', '--no-first-run', '--no-default-browser-check', '--disable-gpu', '--remote-debugging-port=0', '--user-data-dir='+str(chrome_profile), url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        args = None
        try:
            port_file = chrome_profile/'DevToolsActivePort'
            deadline = time.monotonic()+20
            while not port_file.exists() and time.monotonic()<deadline:
                if browser.poll() is not None: raise RuntimeError('Isolated Chrome exited')
                time.sleep(.1)
            port = port_file.read_text().splitlines()[0]
            args = SimpleNamespace(cdp_url='http://127.0.0.1:'+port, cdp_ws=None, url=url, target_id=None)
            # All facts and snapshots are synthetic and scoped to this temp directory.
            w.PROFILE = root/'profile.md'; w.RUNS = root/'runs'; w.SITES = root/'sites'
            w.RUNS.mkdir(); w.SITES.mkdir()
            source = root/'resume.tex'; source.write_text('Alex Example, Example University, Example degree')
            facts = {'basic': {'name':'Alex Example'}, 'education': [{'school':'Example University','degree':'Example degree'}],
                     'work': [], 'projects': [], 'skills': [], 'languages': [], 'publications': [], 'awards': [],
                     'example': {'description':'Synthetic description with 25% improvement', 'date':'2025-01'}}
            ingest.write_profile(w.PROFILE, {'schema_version':1,'status':'ready','facts':facts,
                                           'sources':[{'path':str(source),'sha256':ingest.digest(source)}],
                                           'pending_confirmations':{},'workflow_preferences':{}})
            output = io.StringIO()
            with contextlib.redirect_stdout(output): w.start(args)
            paths = json.loads(output.getvalue()); run = Path(paths['session'])
            session = json.loads((run/'session.json').read_text())
            self_url = json.loads((run/'snapshot.json').read_text())['url']
            assert self_url == url
            assert 'SYNTHETIC-PASSPORT' not in (run/'snapshot.json').read_text()
            passed.append('sensitive field values redacted from full snapshot')
            passed.append('exact target tab in isolated browser')
            plan = json.loads((run/'plan.json').read_text())
            def row(key, selector, label, kind, value_from, **extra):
                return dict(key=key,selector=selector,label=label,kind=kind,value_from=value_from,expected='',**extra)
            plan.update(fields=[row('name','#name','Name','text','profile:basic.name'),
                                row('desc','#desc','Description','text','profile:example.description'),
                                row('date','#date','Date','date','profile:example.date'),
                                row('degree','#degree','Degree','select','profile:education.0.degree'),
                                row('school','#ac','School','autocomplete','profile:education.0.school',option_selector='#menu [role=option]',selected_selector='#selected')],
                        pending=[],reviewed_full_form=True)
            w.save_json(run/'plan.json',plan)
            task = SimpleNamespace(**vars(args),session=str(run),plan=str(run/'plan.json'))
            with contextlib.redirect_stdout(io.StringIO()):
                w.execute(task); w.execute(task,True)
            verified = json.loads((run/'verify.json').read_text())
            assert verified['state']=='draft_verified' and all(r['ok'] for r in verified['fields'])
            passed.append('text textarea date native select autocomplete and actual readback')
            with contextlib.redirect_stdout(io.StringIO()): w.execute(task)
            assert all(r['action']=='already_equal' for r in json.loads((run/'apply.json').read_text())['fields'])
            passed.append('idempotent repeat')
            w.harness(w.bound_code(session)+"js(\"document.querySelector('#name').value='User edit'\")\nprint(json.dumps(True))",args)
            try:
                with contextlib.redirect_stdout(io.StringIO()): w.execute(task)
            except RuntimeError:
                pass
            else:
                raise AssertionError('Nonempty conflict was not blocked')
            passed.append('nonempty user edit protected')
            w.harness(w.bound_code(session)+"js(\"document.querySelector('#name').value='Alex Example'\")\nprint(json.dumps(True))",args)
            cp = SimpleNamespace(**vars(task),module='Synthetic module',save_selector='#save',success_text='Saved successfully',success_url_fragment='',local_only=False)
            with contextlib.redirect_stdout(io.StringIO()): w.checkpoint(cp)
            record = json.loads(next((run/'checkpoints').glob('*.json')).read_text())
            assert record['state']=='saved' and record['persistence_verified'] is False
            passed.append('save action evidence recorded without claiming persistence')
            w.harness(w.bound_code(session)+"js('location.reload()')\nwait(.5)\nprint(json.dumps(True))",args)
            value = w.harness(w.bound_code(session)+"print(json.dumps(js(\"document.querySelector('#name').value\")))",args)
            assert value=='Alex Example'
            passed.append('synthetic fixture value survives reload')
        finally:
            if args:
                # Stop only the daemon for the explicit test endpoint; not user daemons/tabs.
                env = os.environ.copy()
                env.update(BU_NAME=w.DAEMON+'-'+w.interface_id(args), BU_CDP_URL=args.cdp_url)
                subprocess.run([sys.executable,str(w.SKILL/'scripts/harness.py'),'--reload'],env=env,capture_output=True,timeout=30,check=True)
            browser.terminate()
            try: browser.wait(timeout=10)
            except subprocess.TimeoutExpired: browser.kill(); browser.wait(timeout=10)
            server.shutdown(); server.server_close()
    print(json.dumps({'passed':passed,'count':len(passed),'scope':'temporary localhost form and fresh headless Chrome profile only'},indent=2))

if __name__ == '__main__':
    main()
