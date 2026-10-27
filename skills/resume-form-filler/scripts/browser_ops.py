"""Executed inside Browser Harness: UI reads/writes only, no site backend APIs."""
import json
import re

# A dedicated Harness daemon keeps its own blank control tab. Actual resume
# operations bind an explicit CDP session without enabling Runtime events.
def rf_bind(target_id, url):
    import browser_harness.helpers as harness_helpers
    global cdp, current_tab, _rf_session, _rf_cdp_root
    if '_rf_session' in globals(): raise RuntimeError('SESSION_ALREADY_BOUND: do not rebind inside a task')
    _rf_cdp_root = cdp
    _rf_session = _rf_cdp_root('Target.attachToTarget', targetId=target_id, flatten=True)['sessionId']
    def pinned_cdp(method, session_id=None, **params):
        return _rf_cdp_root(method, session_id=session_id or _rf_session, **params)
    def pinned_current():
        info = _rf_cdp_root('Target.getTargetInfo', targetId=target_id)['targetInfo']
        return {'targetId':target_id, 'target_id':target_id, 'url':info['url'], 'title':info.get('title','')}
    cdp = pinned_cdp
    current_tab = pinned_current
    harness_helpers.cdp = pinned_cdp
    harness_helpers.current_tab = pinned_current
    cdp('Runtime.disable')
    if page_info()['url'] != url:
        raise RuntimeError('TARGET_URL_CHANGED')

SENSITIVE = re.compile(r'password|cardnum|idcard|identity|passport|ssn|身份证|证件号|护照|验证码|\botp\b|token|secret', re.I)

SNAPSHOT_JS = r'''(()=>{
 const visible=e=>!!e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden'&&getComputedStyle(e).display!=='none';
 const unique=s=>document.querySelectorAll(s).length===1;
 const selector=e=>{
  if(e.id&&unique('#'+CSS.escape(e.id)))return '#'+CSS.escape(e.id);
  if(e.name){const s=e.tagName.toLowerCase()+'[name='+JSON.stringify(e.name)+']';if(unique(s))return s;}
  let id=e.getAttribute('data-resume-fill-id');
  if(!id){id='rff-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);e.setAttribute('data-resume-fill-id',id);}
  const s='[data-resume-fill-id='+JSON.stringify(id)+']';if(!unique(s))throw Error('Duplicate local anchor');return s;
 };
 const fields=Array.from(document.querySelectorAll('input,textarea,select,[role=combobox],.brick-select-selection')).map(e=>{
  const field=e.closest('.brick-field')||e.closest('[class*=field-]')||e.parentElement;
  const label=(Array.from(e.labels||[]).map(x=>x.innerText).join(' ')||e.getAttribute('aria-label')||field?.querySelector('label,.brick-field-label,[class*=label]')?.innerText||'').trim();
  const context=(field?.innerText||'').trim().slice(0,350);
  const sensitive=/password|cardnum|idcard|identity|passport|ssn|身份证|证件号|护照|验证码|otp|token|secret/i.test([e.name,e.type,label].join(' '));
  const value=e.type==='checkbox'||e.type==='radio'?e.checked:e.tagName==='SELECT'?e.selectedOptions[0]?.textContent?.trim():('value' in e?e.value:e.innerText.trim());
  const uploaded_files=e.type==='file'?(field?.innerText||'').split('\n').map(x=>x.trim()).filter(x=>/^[^\/\n]+\.(pdf|png|jpg|jpeg|docx?)$/i.test(x)):[];
  const group_has_checked=e.type==='radio'?!!field?.querySelector('input[type=radio]:checked'):null;
  return {selector:selector(e),tag:e.tagName.toLowerCase(),type:e.type||e.getAttribute('role')||'custom',name:e.name||'',label,context,sensitive_has_value:sensitive?!!value:null,uploaded_files,group_has_checked,selected_text:(e.closest('.ant-select')?.querySelector('.ant-select-selection-item')?.innerText||'').trim(),placeholder:e.placeholder||'',value:sensitive?'<redacted>':value,sensitive,visible:visible(e),disabled:!!e.disabled,readonly:!!e.readOnly,required:!!e.required||e.getAttribute('aria-required')==='true'||!!field?.querySelector('[class*=required]'),maxLength:e.maxLength>0?e.maxLength:null,options:e.tagName==='SELECT'?Array.from(e.options).map(o=>o.textContent.trim()):[],accept:e.accept||''};
 });
 const secrets=Array.from(document.querySelectorAll('input')).filter(e=>/password|cardnum|idcard|identity|passport|ssn|身份证|证件号|护照|验证码|otp|token|secret/i.test(e.name+' '+e.type+' '+(e.getAttribute('aria-label')||'')+' '+Array.from(e.labels||[]).map(x=>x.innerText).join(' '))).map(e=>e.value).filter(Boolean);
 let text=document.body.innerText;for(const s of secrets)text=text.split(s).join('<redacted>');text=text.replace(/\b\d{17}[\dXx]\b/g,'<redacted>');
 return {url:location.href,title:document.title,headings:Array.from(document.querySelectorAll('h1,h2,h3,h4')).map(e=>e.innerText),fields,text,errors:Array.from(document.querySelectorAll('[role=alert],.brick-field-feedback,[class*=error]')).filter(visible).map(e=>e.innerText).filter(Boolean),buttons:Array.from(document.querySelectorAll('button,[role=button]')).filter(visible).map(e=>({selector:selector(e),text:e.innerText.trim()}))};
})()'''

def rf_snapshot():
    data = js(SNAPSHOT_JS)
    # Redact AX names using current sensitive input values; never print raw AX.
    sensitive_values = js("Array.from(document.querySelectorAll('input')).filter(e=>/password|cardnum|idcard|identity|passport|ssn|身份证|证件号|护照|验证码|otp|token|secret/i.test(e.name+' '+e.type+' '+(e.getAttribute('aria-label')||'')+' '+Array.from(e.labels||[]).map(x=>x.innerText).join(' '))).map(e=>e.value).filter(Boolean)")
    def redact(text):
        for value in sensitive_values:
            text = text.replace(value, '<redacted>')
        return re.sub(r'(?<!\d)\d{17}[\dXx](?!\d)', '<redacted>', text)
    data['ax'] = [{'role': n.get('role', {}).get('value'), 'name': redact(n.get('name', {}).get('value', ''))} for n in cdp('Accessibility.getFullAXTree')['nodes'] if not n.get('ignored') and n.get('name', {}).get('value') and n.get('role', {}).get('value') not in ('InlineTextBox', 'image')]
    def redact_tree(value):
        if isinstance(value, str): return redact(value)
        if isinstance(value, list): return [redact_tree(item) for item in value]
        if isinstance(value, dict): return {key:redact_tree(item) for key,item in value.items()}
        return value
    data=redact_tree(data)
    return data

def rf_inspect(selector):
    return js("""(s=>{const es=document.querySelectorAll(s);if(es.length!==1)throw Error('selector matches '+es.length);const e=es[0];const f=e.closest('.brick-field')||e.closest('[class*=field-]')||e.parentElement;return {tag:e.tagName.toLowerCase(),type:e.type||e.getAttribute('role')||'custom',label:(Array.from(e.labels||[]).map(x=>x.innerText).join(' ')||e.getAttribute('aria-label')||f?.querySelector('label,.brick-field-label,[class*=label]')?.innerText||'').trim(),name:e.name||'',readonly:!!e.readOnly,disabled:!!e.disabled,maxLength:e.maxLength>0?e.maxLength:null,value:e.type==='checkbox'||e.type==='radio'?e.checked:e.tagName==='SELECT'?e.selectedOptions[0]?.textContent?.trim():('value' in e?e.value:e.innerText.trim())}})(""" + json.dumps(selector) + ')')

def rf_click(selector):
    # Enforce unique match before querying the node.
    rf_inspect(selector)
    doc = cdp('DOM.getDocument')['root']['nodeId']
    node = cdp('DOM.querySelector', nodeId=doc, selector=selector)['nodeId']
    cdp('DOM.scrollIntoViewIfNeeded', nodeId=node)
    wait(0.2)
    box = cdp('DOM.getBoxModel', nodeId=node)['model']['content']
    click_at_xy(sum(box[0::2])/4, sum(box[1::2])/4)

def rf_read(row):
    try:
        evidence=row.get('selection_evidence')
        if evidence and rf_inspect(evidence['selector'])['value']!=evidence['resolved']:
            raise RuntimeError('selection evidence mismatch')
        return rf_inspect(row.get('selected_selector', row['selector']))['value']
    except Exception:
        raise RuntimeError('CONTROL_UNAVAILABLE: '+row['key']) from None

def rf_type(selector, value):
    fill_input(selector, str(value))
    if rf_inspect(selector)['value'] != str(value):
        # One event-aware fallback, keeping autocomplete focus. The caller
        # still checks actual selection/date state; this never implies success.
        js("((s,v)=>{const e=document.querySelector(s);e.focus();Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,v);e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}))})("+json.dumps(selector)+','+json.dumps(str(value))+')')


def rf_write(row, value):
    selector, kind = row['selector'], row['kind']
    if kind == 'text':
        js("""((s,v)=>{const e=document.querySelector(s);e.focus();const p=e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(p,'value').set.call(e,v);e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));e.blur()})(""" + json.dumps(selector) + ',' + json.dumps(str(value)) + ')')
    elif kind == 'date':
        rf_type(selector, value)
        press_key('Enter')
    elif kind == 'select':
        js("""((s,v)=>{const e=document.querySelector(s);const os=Array.from(e.options).filter(o=>o.textContent.trim()===v);if(os.length!==1)throw Error('exact option count '+os.length);e.value=os[0].value;e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}))})(""" + json.dumps(selector) + ',' + json.dumps(str(value)) + ')')
    elif kind in ('checkbox', 'radio'):
        if rf_read(row) != value:
            rf_click(selector)
    elif kind in ('custom', 'autocomplete'):
        if kind == 'autocomplete':
            rf_type(selector, value)
        else:
            js('(s=>document.querySelector(s).click())(' + json.dumps(selector) + ')')
        wait(0.4)
        js("""((s,v)=>{const es=Array.from(document.querySelectorAll(s)).filter(e=>e.getClientRects().length&&getComputedStyle(e).display!=='none'&&getComputedStyle(e).visibility!=='hidden'&&e.innerText.trim()===v);if(es.length!==1)throw Error('visible exact option count '+es.length);const e=es[0];if(e.getAttribute('role')!=='option'&&!/option/i.test(e.className))throw Error('target is not an option');e.click()})(""" + json.dumps(row['option_selector']) + ',' + json.dumps(str(value)) + ')')
    wait(0.2)
    actual = rf_read(row)
    if actual != value:
        raise RuntimeError('VERIFY_MISMATCH: ' + row['key'])
    return actual

def rf_preflight(row, value):
    meta = rf_inspect(row['selector'])
    allowed_identity = row.get('sensitive_authorized') and row.get('value_from')=='profile:basic.id_card' and re.search(r'cardnum|idcard|身份证|证件号',meta['name']+' '+meta['label'],re.I) and meta['type']!='password'
    if SENSITIVE.search(meta['name'] + ' ' + meta['label'] + ' ' + meta['type']) and not allowed_identity:
        raise RuntimeError('SENSITIVE_FIELD: enter manually')
    kind = row['kind']
    if kind in ('text', 'date') and (meta['tag'] not in ('input', 'textarea') or meta['type'] in ('file', 'password', 'checkbox', 'radio', 'submit', 'button', 'hidden')):
        raise RuntimeError('CONTROL_KIND_MISMATCH: ' + row['key'])
    if kind == 'select' and meta['tag'] != 'select':
        raise RuntimeError('CONTROL_KIND_MISMATCH: ' + row['key'])
    if kind in ('checkbox', 'radio') and (meta['type'] != kind or not isinstance(value, bool)):
        raise RuntimeError('CONTROL_KIND_MISMATCH: ' + row['key'])
    if kind == 'custom' and meta['type'] != 'custom' and meta['type'] != 'combobox':
        raise RuntimeError('CONTROL_KIND_MISMATCH: ' + row['key'])
    if kind == 'autocomplete' and meta['tag'] != 'input':
        raise RuntimeError('CONTROL_KIND_MISMATCH: ' + row['key'])
    if row['label'] and row['label'] not in meta['label']:
        raise RuntimeError('LABEL_CHANGED: ' + row['key'])
    if meta['maxLength'] and isinstance(value, str) and len(value) > meta['maxLength']:
        raise RuntimeError('TOO_LONG: ' + row['key'])
    actual = rf_read(row)
    if actual == value:
        return 'already_equal'
    if meta['disabled'] or meta['readonly']:
        raise RuntimeError('DISABLED_OR_READONLY: ' + row['key'])
    if re.search(r'同意|申请须知|隐私|consent|terms', meta['label'], re.I):
        raise RuntimeError('CONSENT_REQUIRES_USER: ' + row['key'])
    if actual != row['expected'] and not (allowed_identity and row['expected']=='<redacted>' and row.get('overwrite_confirmed')):
        raise RuntimeError('PAGE_VALUE_CHANGED: ' + row['key'])
    if actual not in ('', None, False) and not row.get('overwrite_confirmed'):
        raise RuntimeError('NONEMPTY_CONFLICT: ' + row['key'])
    return 'fill'
