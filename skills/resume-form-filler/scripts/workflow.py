#!/usr/bin/env python3
"""Project resume workflow; browser operations delegated exclusively to Harness."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit

from context import ROOT, SKILL, STATE, PROFILE, SITES, RUNS, init_state
from ingest import validate_profile
OPS = SKILL/'scripts/browser_ops.py'
DAEMON = 'resume-form-filler-' + hashlib.sha256(str(ROOT).encode()).hexdigest()[:10]
KINDS = {'text', 'date', 'select', 'custom', 'autocomplete', 'checkbox', 'radio'}

def load_md(path):
    raw = Path(path).read_text(encoding='utf-8')
    blocks = re.findall(r'^```json\s*\n(.*?)\n```', raw, re.S|re.M)
    if len(blocks) != 1:
        raise ValueError('Expected exactly one JSON data block in ' + str(path))
    return json.loads(blocks[0])

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def current_profile():
    if not PROFILE.exists():
        raise ValueError('PROFILE_REQUIRED: run init --resume FILE; review the extracted draft first')
    data = load_md(PROFILE)
    if data.get('status') != 'ready':
        raise ValueError('PROFILE_REVIEW_REQUIRED')
    validate_profile(data)
    for source in data['sources']:
        path = ROOT/source['path']
        if not path.is_file() or digest(path) != source['sha256']:
            raise ValueError('CV_SOURCE_CHANGED: reconcile profile.md with ' + source['path'])
    return data

def fact_at(data, key, allow_none=False):
    value = data
    for part in key.split('.'):
        value = value[int(part)] if isinstance(value, list) else value[part]
    if (value is None and not allow_none) or isinstance(value, (dict, list)):
        raise ValueError('Fact must be a confirmed scalar: ' + key)
    return value

def resolve(source, profile, site):
    prefix, key = source.split(':', 1)
    if prefix == 'profile':
        if key in profile.get('pending_confirmations', {}):
            raise ValueError('Pending fact is not confirmed: ' + key)
        value = fact_at(profile['facts'], key)
    elif prefix == 'site':
        if key not in site.get('overrides', {}):
            raise ValueError('Unconfirmed site choice: ' + key)
        value = site['overrides'][key]
    else:
        raise ValueError('Only profile: and site: sources are permitted')
    authorized_identity = prefix == 'profile' and key == 'basic.id_card' and profile.get('workflow_preferences', {}).get('identity_storage_and_fill_authorized') is True
    if authorized_identity and not re.fullmatch(r'\d{17}[\dXx]',str(value)):
        raise ValueError('Confirmed identity must have 18 characters')
    if not authorized_identity and (re.search(r'cardnum|idcard|identity|身份证|password|secret|token|otp', key, re.I) or re.search(r'\b\d{17}[\dXx]\b', str(value))):
        raise ValueError('Sensitive fact cannot be stored or filled by this workflow')
    return value

def interface_id(args):
    endpoint=getattr(args,'cdp_ws',None) or getattr(args,'cdp_url',None) or os.environ.get('BU_CDP_WS') or os.environ.get('BU_CDP_URL')
    return hashlib.sha256(endpoint.encode()).hexdigest()[:10] if endpoint else 'local'


def harness(code, args):
    env = os.environ.copy()
    env['BU_NAME'] = DAEMON+('' if interface_id(args)=='local' else '-'+interface_id(args))
    if getattr(args, 'cdp_url', None): env['BU_CDP_URL'] = args.cdp_url
    if getattr(args, 'cdp_ws', None): env['BU_CDP_WS'] = args.cdp_ws
    # Close only the explicit operation session, never a page/tab. Helpers stay
    # bound for the whole script; no implicit daemon target switching.
    code = "try:\n"+''.join('    '+line+'\n' for line in code.splitlines())+"finally:\n    if '_rf_session' in globals():\n        _rf_cdp_root('Target.detachFromTarget',sessionId=_rf_session)\n"
    process = subprocess.run([sys.executable, str(SKILL/'scripts/harness.py')], input=code, text=True, cwd=ROOT, env=env, capture_output=True, timeout=180)
    if process.returncode:
        # No raw stdout: a malformed snapshot might contain sensitive fields.
        raise RuntimeError('Browser Harness failed; run doctor and inspect the control error. ' + process.stderr[-2000:])
    try:
        return json.loads(process.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError('Browser Harness did not return a structured result; do not treat as success')

def bound_code(session):
    return "exec(open(%r,encoding='utf-8').read())\nrf_bind(%r,%r)\n" % (str(OPS),session['target_id'],session['url'])


def save_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def start(args):
    parsed = urlsplit(args.url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Supply the full http(s) resume editor URL, without credentials')
    if any(re.search(r'token|secret|password|authorization', item.split('=')[0], re.I) for item in parsed.query.split('&')):
        raise ValueError('Do not persist authentication tokens in a resume URL')
    profile = current_profile()
    tabs = harness('import json\nprint(json.dumps(list_tabs(),ensure_ascii=False))', args)
    matches = [t for t in tabs if t['url'] == args.url and (not args.target_id or t['targetId'] == args.target_id)]
    if len(matches) != 1:
        raise ValueError('TARGET_MATCH_COUNT=%d; open exact URL or specify --target-id' % len(matches))
    site_path = SITES/((parsed.hostname or '')+'.md')
    site = load_md(site_path) if site_path.exists() else {'host': parsed.hostname, 'overrides': {}, 'pending': [], 'state': 'new'}
    if site['host'] != parsed.hostname: raise ValueError('Site memory host mismatch')
    session = {'interface_id': interface_id(args), 'url': args.url, 'target_id': matches[0]['targetId'], 'profile_sha256': digest(PROFILE), 'site_sha256': digest(site_path) if site_path.exists() else None, 'site_path': str(site_path.relative_to(ROOT)) if site_path.exists() else None}
    snapshot = harness(bound_code(session)+"print(json.dumps(rf_snapshot(),ensure_ascii=False))", args)
    run = RUNS/ (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+parsed.hostname)
    run.mkdir(parents=True)
    save_json(run/'session.json', session)
    save_json(run/'snapshot.json', snapshot)
    save_json(run/'plan.json', {**session, 'fields': [], 'pending': ['Build mapping from snapshot and confirmed facts'], 'reviewed_full_form': False})
    print(json.dumps({'session': str(run), 'snapshot': str(run/'snapshot.json'), 'plan': str(run/'plan.json'), 'target_id': session['target_id'], 'site_memory': session['site_path'], 'daemon_name': DAEMON+('' if interface_id(args)=='local' else '-'+interface_id(args)), 'state': 'snapshot_ready'}, ensure_ascii=False, indent=2))

def prepare(args):
    run = Path(args.session).resolve()
    session = json.loads((run/'session.json').read_text())
    plan = json.loads(Path(args.plan).read_text())
    profile = current_profile()
    if interface_id(args)!=session.get('interface_id','local'): raise ValueError('INTERFACE_CHANGED: pass the same interface or start again')
    for key in ('url', 'target_id', 'profile_sha256', 'site_sha256'):
        if plan.get(key) != session.get(key): raise ValueError('PLAN_BINDING_MISMATCH: '+key)
    if digest(PROFILE) != session['profile_sha256']: raise ValueError('PROFILE_CHANGED: start again')
    site_path = ROOT/session['site_path'] if session['site_path'] else None
    if site_path and digest(site_path) != session['site_sha256']: raise ValueError('SITE_MEMORY_CHANGED: start again')
    site = load_md(site_path) if site_path else {'overrides': {}}
    rows, seen = [], set()
    if not plan['fields']: raise ValueError('EMPTY_PLAN: map fields before apply/verify')
    for row in plan['fields']:
        for key in ('key', 'selector', 'label', 'expected', 'kind', 'value_from'):
            if key not in row: raise ValueError('Missing plan field: '+key)
        if row['selector'] in seen: raise ValueError('DUPLICATE_SELECTOR')
        seen.add(row['selector'])
        if row['kind'] not in KINDS: raise ValueError('Unsupported kind; uploads and submit are separate authorized actions')
        if row.get('overwrite_confirmed') and not row.get('confirmation_source'): raise ValueError('Overwrite requires a human confirmation source')
        if row['kind'] in ('custom', 'autocomplete') and (not row.get('option_selector') or not row.get('selected_selector')): raise ValueError('Custom controls need option and selected selectors')
        if row['kind']=='autocomplete' and row['selected_selector']==row['selector'] and not row.get('selection_evidence'):
            raise ValueError('Input-only autocomplete requires independent selection evidence')
        if row.get('selection_evidence'):
            evidence=row['selection_evidence']
            if not evidence.get('selector') or not evidence.get('value_from'): raise ValueError('Incomplete selection evidence')
            row={**row,'selection_evidence':{**evidence,'resolved':str(resolve(evidence['value_from'],profile,site))}}
        value = resolve(row['value_from'], profile, site)
        transform = row.get('transform')
        if transform == 'domestic_phone': value = str(value).replace('+86', '').replace(' ', '')
        elif transform == 'boolean_yes_no': value = {'是': True, '否': False}[value]
        elif transform in ('month_start', 'month_end'):
            import calendar
            year, month = map(int, str(value).split('-'))
            value = '%04d-%02d-%02d' % (year, month, 1 if transform == 'month_start' else calendar.monthrange(year, month)[1])
        elif transform is not None: raise ValueError('Unsupported transform')
        if row['kind'] not in ('checkbox', 'radio'): value = str(value)
        rows.append({**row, 'resolved': value, 'sensitive_authorized': row['value_from']=='profile:basic.id_card' and profile.get('workflow_preferences',{}).get('identity_storage_and_fill_authorized') is True})
    return run, session, plan, rows

def execute(args, verify=False):
    run, session, plan, rows = prepare(args)
    code = bound_code(session)+"rows = json.loads(%r)\n" % json.dumps(rows, ensure_ascii=False)
    if verify:
        code += "results=[]\nfor r in rows:\n    try:\n        actual=rf_read(r)\n        results.append({'key':r['key'],'ok':actual==r['resolved'],'actual':actual})\n    except Exception as exc:\n        results.append({'key':r['key'],'ok':False,'error':str(exc)})\nprint(json.dumps({'fields':results,'snapshot':rf_snapshot()},ensure_ascii=False))"
    else:
        code += "states=[rf_preflight(r,r['resolved']) for r in rows]\nresults=[]\nerror=None\nfor r,state in zip(rows,states):\n    try:\n        if page_info()['url'] != %r: raise RuntimeError('TARGET_URL_CHANGED')\n        if state=='fill': rf_write(r,r['resolved'])\n        results.append({'key':r['key'],'ok':True,'action':state,'actual':rf_read(r)})\n    except Exception as exc:\n        error=str(exc)\n        results.append({'key':r['key'],'ok':False})\n        break\nprint(json.dumps({'fields':results,'error':error,'snapshot':rf_snapshot()},ensure_ascii=False))" % session['url']
    result = harness(code, args)
    result['pending'] = plan.get('pending', [])
    result['reviewed_full_form'] = bool(plan.get('reviewed_full_form'))
    def missing(f):
        if not f.get('required') or f.get('disabled'): return False
        if f['type']=='file': return not f.get('uploaded_files') and not f.get('value')
        if f['type']=='radio': return not f.get('group_has_checked')
        if f['type']=='checkbox': return not f.get('value')
        return (f['value'] in ('', None, '请选择', '请输入') and not f.get('selected_text')) or (f.get('sensitive') and not f.get('sensitive_has_value'))
    result['required_unresolved'] = [{'selector': f['selector'], 'label': f['label'], 'manual': bool(f.get('sensitive'))} for f in result['snapshot']['fields'] if missing(f)]
    result['page_errors'] = result['snapshot']['errors']
    result['state'] = 'blocked' if result.get('error') else 'draft_verified' if verify and all(r['ok'] for r in result['fields']) and not result['pending'] and result['reviewed_full_form'] and not result['required_unresolved'] and not result['page_errors'] else ('draft_with_pending' if verify else 'filled_fields')
    identity = current_profile()['facts']['basic'].get('id_card')
    def redact(value):
        if isinstance(value,str): return value.replace(identity,'<redacted>') if identity else value
        if isinstance(value,list): return [redact(v) for v in value]
        if isinstance(value,dict): return {k:redact(v) for k,v in value.items()}
        return value
    result = redact(result)
    save_json(run/('verify.json' if verify else 'apply.json'), result)
    save_json(run/'snapshot.json', result.pop('snapshot'))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get('error') or any(not r['ok'] for r in result['fields']):
        raise RuntimeError('Verification failed; inspect saved result and refresh mapping')

def ui_task(args):
    run=Path(args.session).resolve()
    session=json.loads((run/'session.json').read_text())
    current_profile()
    if interface_id(args)!=session.get('interface_id','local'): raise ValueError('INTERFACE_CHANGED: start again')
    if digest(PROFILE)!=session['profile_sha256']: raise ValueError('PROFILE_CHANGED: start again')
    script=Path(args.script).resolve()
    allowed=[SKILL/'scripts',STATE/'helpers']
    if script.suffix!='.py' or not any(folder.resolve() in script.parents for folder in allowed): raise ValueError('Task script must be a project workflow Python helper')
    code=bound_code(session)+"exec(open(%r,encoding='utf-8').read())\nprint(json.dumps(rf_snapshot(),ensure_ascii=False))" % str(script)
    snapshot=harness(code,args)
    save_json(run/'snapshot.json',snapshot)
    print(json.dumps({'state':'ui_task_complete','url':snapshot['url'],'snapshot':str(run/'snapshot.json')},ensure_ascii=False,indent=2))


def checkpoint(args):
    run, session, plan, rows = prepare(args)
    site_path = ROOT/session['site_path'] if session.get('site_path') else None
    site = load_md(site_path) if site_path else {}
    completion = site.get('confirmed_mappings', {}).get('completion', {})
    code = bound_code(session)+"rows=json.loads(%r)\n" % json.dumps(rows,ensure_ascii=False)
    code += "if not all(rf_read(r)==r['resolved'] for r in rows): raise RuntimeError('MODULE_NOT_VERIFIED')\n"
    if args.local_only:
        code += "print(json.dumps({'state':'local_checkpoint','snapshot':rf_snapshot()},ensure_ascii=False))"
    else:
        # Module saving is the skill's documented default, separate from applications.
        code += "save_selector=%r\nsuccess_text=%r\nsuccess_url_fragment=%r\n" % (args.save_selector,args.success_text,args.success_url_fragment)
        code += "mapped_button_text=%r\nmapped_data_test=%r\nmapped_route=%r\n" % (completion.get('button_text'),completion.get('data_test'),completion.get('route'))
        code += """meta=rf_inspect(save_selector)
if meta['tag']!='button' and meta['type'] not in ('button','submit'): raise RuntimeError('NOT_A_SAVE_CONTROL')
button_text=re.sub(r'\\s+','',js('(s=>document.querySelector(s).innerText.trim())('+json.dumps(save_selector)+')'))
data_test=js('(s=>document.querySelector(s).getAttribute("data-test")||"")('+json.dumps(save_selector)+')')
pathname=js('location.pathname')
mapped_match=bool(mapped_button_text and mapped_data_test and mapped_route and button_text==re.sub(r'\\s+','',mapped_button_text) and data_test==mapped_data_test and pathname==mapped_route)
if '保存' not in button_text and 'save' not in button_text.lower() and not mapped_match: raise RuntimeError('NOT_A_SAVE_CONTROL')
if re.search(r'投递|申请职位|提交申请|apply|submit application',button_text,re.I): raise RuntimeError('APPLICATION_NOT_AUTHORIZED')
if meta['disabled']: raise RuntimeError('SAVE_DISABLED')
if success_url_fragment and re.search(r'apply|apply-confirm|申请|投递',success_url_fragment,re.I): raise RuntimeError('APPLICATION_ROUTE_NOT_AUTHORIZED')
initial_url=js('location.href')
if mapped_match and re.search(r'apply|apply-confirm|申请|投递',pathname,re.I): raise RuntimeError('APPLICATION_ROUTE_NOT_AUTHORIZED')
if success_url_fragment and success_url_fragment in initial_url: raise RuntimeError('STALE_SUCCESS_ROUTE')
if success_text and success_text in js('document.body.innerText'): raise RuntimeError('STALE_SUCCESS_MARKER')
js('(s=>{const e=document.querySelector(s);if(!e.getClientRects().length)throw Error(\"SAVE_NOT_VISIBLE\");e.click()})('+json.dumps(save_selector)+')')
saved=False
evidence=None
for _ in range(60):
    wait(.25)
    body_text=js('document.body.innerText')
    if success_text and success_text in body_text:
        saved=True
        evidence=success_text
        break
    if mapped_match:
        notices=js('''(()=>{const v=e=>!!e.getClientRects().length&&getComputedStyle(e).visibility!=="hidden"&&getComputedStyle(e).display!=="none";return Array.from(document.querySelectorAll('[role="alert"],[role="status"],[class*="toast"],[class*="message"],[class*="notification"]')).filter(v).map(e=>e.innerText.trim()).filter(Boolean)})()''')
        positive=[t for t in notices if re.search(r'保存成功|创建成功|创建简历成功|更新成功|更新简历成功|简历已保存|简历保存完成|保存完成',t) and not re.search(r'失败|错误|异常|投递|申请|岗位|职位',t)]
        if positive:
            saved=True
            evidence=positive[0]
            break
    current_url=js('location.href')
    if success_url_fragment and success_url_fragment in current_url and current_url!=initial_url:
        saved=True
        evidence='页面跳转至 '+current_url
        break
print(json.dumps({'state':'saved' if saved else 'save_unconfirmed','evidence':evidence,'snapshot':rf_snapshot()},ensure_ascii=False))
"""
    result=harness(code,args)
    result.update(module=args.module,pending=plan.get('pending',[]),persistence_verified=False)
    folder=run/'checkpoints';folder.mkdir(exist_ok=True)
    name=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+re.sub(r'[^\w-]','_',args.module)
    save_json(folder/(name+'.json'),result)
    md='# 模块保存记录\n\n模块：%s\n\n网页状态：%s\n\n保存证据：%s\n\n' % (args.module,result['state'],result.get('evidence') or '尚未确认网页保存；JSON 是本地恢复记录')
    md+='\n'.join('- %s：%s' % (r['key'],json.dumps('<redacted>' if r.get('sensitive_authorized') else r['resolved'],ensure_ascii=False)) for r in rows)+'\n'
    (folder/(name+'.md')).write_text(md,encoding='utf-8')
    print(json.dumps({'module':args.module,'state':result['state'],'evidence':result.get('evidence'),'checkpoint':str(folder/(name+'.md')),'page_errors':result['snapshot']['errors']},ensure_ascii=False,indent=2))
    if not args.local_only and result['state']!='saved': raise RuntimeError('SAVE_NOT_CONFIRMED: inspect required errors; local checkpoint retained')

def refresh_sources(args):
    # Do not refresh hashes without re-parsing and reconciling the new resume.
    from ingest import import_resume
    print(json.dumps(import_resume(args.cv_source), ensure_ascii=False, indent=2))


def update(args):
    current_profile()
    data = load_md(PROFILE)
    # Existing schema keys only: adding complex records is an explicit MD edit.
    old = fact_at(data['facts'], args.key, allow_none=True)
    authorized_identity=args.key=='basic.id_card' and data.get('workflow_preferences',{}).get('identity_storage_and_fill_authorized') is True
    if not authorized_identity and re.search(r'cardnum|idcard|identity|passport|ssn|身份证|password|secret|token|otp',args.key,re.I): raise ValueError('Sensitive key rejected')
    value = json.loads(args.value) if args.value_json else args.value
    if isinstance(value, (dict, list)) or value is None: raise ValueError('Use MD editing for complex/unknown fields')
    if authorized_identity and not re.fullmatch(r'\d{17}[\dXx]',str(value)): raise ValueError('Identity must have 18 characters')
    if not authorized_identity and re.search(r'\b\d{17}[\dXx]\b', str(value)): raise ValueError('Sensitive value rejected')
    parent = data['facts']
    parts = args.key.split('.')
    for part in parts[:-1]: parent = parent[int(part)] if isinstance(parent, list) else parent[part]
    parent[int(parts[-1]) if isinstance(parent, list) else parts[-1]] = value
    data.get('pending_confirmations',{}).pop(args.key,None)
    data['updated_at']=datetime.now(timezone.utc).date().isoformat()
    raw = PROFILE.read_text(encoding='utf-8')
    raw = re.sub(r'^```json\s*\n.*?\n```', lambda _: '```json\n'+json.dumps(data, ensure_ascii=False, indent=2)+'\n```', raw, count=1, flags=re.S|re.M)
    raw += '\n- %s：更新 `%s`；来源：%s。\n' % (datetime.now(timezone.utc).date(), args.key, args.source.replace('\n', ' '))
    PROFILE.write_text(raw, encoding='utf-8')
    print(json.dumps({'updated': args.key, 'profile_sha256': digest(PROFILE)}, ensure_ascii=False))

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('start'); p.add_argument('--url', required=True); p.add_argument('--target-id')
    q = sub.add_parser('ui'); q.add_argument('--session', required=True); q.add_argument('--script', required=True)
    for name in ('apply', 'verify', 'checkpoint'):
        q = sub.add_parser(name); q.add_argument('--session', required=True); q.add_argument('--plan', required=True)
    sub.choices['checkpoint'].add_argument('--module', required=True)
    sub.choices['checkpoint'].add_argument('--save-selector')
    sub.choices['checkpoint'].add_argument('--success-text', default='保存成功')
    sub.choices['checkpoint'].add_argument('--success-url-fragment', default='')
    sub.choices['checkpoint'].add_argument('--local-only', action='store_true')
    for q in (p, sub.choices['apply'], sub.choices['verify'], sub.choices['checkpoint'], sub.choices['ui']):
        group = q.add_mutually_exclusive_group(); group.add_argument('--cdp-url'); group.add_argument('--cdp-ws')
    q = sub.add_parser('refresh-sources'); q.add_argument('--cv-source', required=True); q.add_argument('--source', required=True)
    q = sub.add_parser('update'); q.add_argument('--key', required=True); q.add_argument('--value', required=True); q.add_argument('--value-json', action='store_true'); q.add_argument('--source', required=True)
    args = parser.parse_args(argv)
    init_state()
    try:
        if args.command == 'start': start(args)
        elif args.command == 'update': update(args)
        elif args.command == 'refresh-sources': refresh_sources(args)
        elif args.command == 'ui': ui_task(args)
        elif args.command == 'checkpoint':
            if not args.local_only and not args.save_selector: raise ValueError('checkpoint needs observed --save-selector or --local-only')
            checkpoint(args)
        else: execute(args, args.command == 'verify')
    except Exception as error:
        identity = None
        try: identity = load_md(PROFILE).get('facts',{}).get('basic',{}).get('id_card')
        except Exception: pass
        message = str(error).replace(str(identity), '<redacted>') if identity else str(error)
        print(json.dumps({'state': 'blocked', 'error': message}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)

if __name__ == '__main__': main()
