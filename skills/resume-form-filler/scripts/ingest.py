"""Local document extraction and reviewed profile persistence. No hosted API."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from context import ROOT, STATE, PROFILE, init_state, private_dir

FORMATS = {'.pdf', '.tex', '.docx', '.doc'}

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def read_md(path):
    blocks = re.findall(r'^```json\s*\n(.*?)\n```', Path(path).read_text(encoding='utf-8'), re.S | re.M)
    if len(blocks) != 1:
        raise ValueError('Profile must contain exactly one JSON fenced block')
    return json.loads(blocks[0])

def write_profile(path, data):
    temporary = Path(path).with_suffix('.tmp')
    temporary.write_text('# Local resume profile\n\n```json\n' + json.dumps(data, ensure_ascii=False, indent=2) + '\n```\n', encoding='utf-8')
    try:
        temporary.chmod(0o600)
    except OSError:
        pass
    temporary.replace(path)

def extract_tex(path):
    """Expand input/include only inside the main document's directory; never execute TeX."""
    from pylatexenc.latex2text import LatexNodes2Text
    base = path.parent.resolve()
    seen = set()
    sources = []
    total = 0
    def expand(file, stack):
        nonlocal total
        file = file.resolve()
        if base not in file.parents or file.suffix.lower() != '.tex':
            raise ValueError('LaTeX include must be a .tex file inside the main document directory')
        if file in stack or len(stack) > 20:
            raise ValueError('Cyclic or excessively deep LaTeX include')
        if file.stat().st_size > 5_000_000:
            raise ValueError('LaTeX input too large')
        total += file.stat().st_size
        if total > 20_000_000:
            raise ValueError('Expanded LaTeX input too large')
        raw = file.read_text(encoding='utf-8-sig')
        if file not in seen:
            seen.add(file)
            sources.append(file)
        raw = re.sub(r'(?m)(?<!\\)%.*$', '', raw)
        def include(match):
            name = match.group(1).strip()
            target = file.parent / name
            if not target.suffix:
                target = target.with_suffix('.tex')
            return '\n' + expand(target, stack + [file]) + '\n'
        return re.sub(r'\\(?:input|include)\s*\{([^{}]+)\}', include, raw)
    expanded = expand(path, [])
    # No input directory is configured for pylatexenc: external TeX reads disabled.
    text = LatexNodes2Text().latex_to_text(expanded)
    return text, sources, ['Custom LaTeX macros may lose text; compare source and extracted text before profile review.']

def extract(path):
    path = Path(path).expanduser().resolve()
    if not path.is_file() or path.name.startswith('._'):
        raise ValueError('Choose an existing resume file, excluding AppleDouble metadata')
    if path.suffix.lower() not in FORMATS:
        raise ValueError('Supported resume formats: .pdf, .tex, .docx, .doc')
    if path.stat().st_size > 30_000_000:
        raise ValueError('Resume exceeds the 30 MB import limit')
    warnings, sources = [], [path]
    if path.suffix.lower() == '.pdf':
        from pypdf import PdfReader
        reader = PdfReader(path)
        if reader.is_encrypted:
            raise ValueError('Password-protected PDF: export an unlocked local copy first')
        chunks = []
        for number, page in enumerate(reader.pages, 1):
            content = page.extract_text() or ''
            if not content.strip():
                warnings.append('Page %d has no text layer; review/OCR is required.' % number)
            chunks.append('[Page %d]\n%s' % (number, content))
        text = '\n\n'.join(chunks)
        if not any((p.extract_text() or '').strip() for p in reader.pages):
            raise ValueError('OCR_REQUIRED: PDF contains no extractable text. Supply OCR PDF, Word, or LaTeX.')
    elif path.suffix.lower() == '.docx':
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph
        document = Document(path)
        def blocks(container):
            for item in container.iter_inner_content():
                if isinstance(item, Paragraph):
                    yield item.text
                elif isinstance(item, Table):
                    for row in item.rows:
                        yield ' | '.join('\n'.join(blocks(cell)) for cell in row.cells)
        parts = list(blocks(document))
        for section in document.sections:
            parts.extend(blocks(section.header))
            parts.extend(blocks(section.footer))
        text = '\n'.join(parts)
        warnings.append('Review text boxes, shapes, images and layout against the original Word file; these may not appear in extracted text.')
    elif path.suffix.lower() == '.tex':
        text, sources, warnings = extract_tex(path)
    else:
        if sys.platform == 'darwin' and shutil.which('textutil'):
            result = subprocess.run(['textutil', '-convert', 'txt', '-stdout', str(path)], check=True, capture_output=True, timeout=60)
            text = result.stdout.decode('utf-8')
        else:
            office = shutil.which('libreoffice') or shutil.which('soffice')
            if not office:
                raise ValueError('DOC_CONVERTER_REQUIRED: legacy .doc needs LibreOffice or macOS textutil. Export as .docx; no system software is installed automatically.')
            with tempfile.TemporaryDirectory(prefix='rff-doc-') as tmp:
                profile = (Path(tmp) / 'office-profile').as_uri()
                subprocess.run([office, '-env:UserInstallation=' + profile, '--headless', '--convert-to', 'txt:Text', '--outdir', tmp, str(path)], check=True, capture_output=True, timeout=60)
                text = (Path(tmp) / (path.stem + '.txt')).read_text(encoding='utf-8-sig')
        warnings.append('Legacy .doc conversion may lose tables or layout; compare with the source.')
    if not text.strip():
        raise ValueError('EMPTY_EXTRACTION: use a text-based PDF, .docx or .tex file')
    return text, sources, warnings

def import_resume(resume):
    init_state()
    text, sources, warnings = extract(resume)
    folder = private_dir(STATE / 'imports' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    records = [{'path': str(p), 'sha256': digest(p)} for p in sources]
    extracted = folder / 'resume.txt'
    extracted.write_text(text, encoding='utf-8')
    manifest = {'sources': records, 'warnings': warnings, 'text_sha256': digest(extracted)}
    write_json(folder / 'manifest.json', manifest)
    draft = {
        'schema_version': 1, 'status': 'draft', 'sources': records,
        'facts': {'basic': {'name': None, 'email': None, 'phone': None, 'location': None},
                  'education': [], 'work': [], 'projects': [], 'skills': [], 'languages': [],
                  'publications': [], 'awards': [], 'self_description': None, 'attachments': {}},
        'pending_confirmations': {},
        'workflow_preferences': {'save_each_module': True, 'identity_storage_and_fill_authorized': False},
        'evidence': {},
    }
    write_json(folder / 'profile.draft.json', draft)
    result = {'state': 'profile_review_required', 'import_dir': str(folder), 'text': str(extracted), 'draft': str(folder / 'profile.draft.json'), 'warnings': warnings,
              'next': 'The calling AI assistant reads the extracted text and source, fills the draft with evidence-backed facts, then runs review-profile. Unknown facts remain null/pending. No form can be filled yet.'}
    return result

def validate_profile(data):
    if data.get('schema_version') != 1:
        raise ValueError('Unsupported profile schema')
    facts = data.get('facts', {})
    if not isinstance(facts.get('basic'), dict) or not isinstance(facts['basic'].get('name'), str) or not facts['basic']['name'].strip():
        raise ValueError('A source-checked name is required')
    for key in ('education', 'work', 'projects', 'skills', 'languages', 'publications', 'awards'):
        if not isinstance(facts.get(key), list):
            raise ValueError('Expected list: facts.' + key)
    for key in ('education', 'work', 'projects', 'publications', 'awards'):
        if any(not isinstance(row, dict) for row in facts[key]):
            raise ValueError('Expected records in facts.' + key)
    if not isinstance(data.get('pending_confirmations'), dict) or not isinstance(data.get('workflow_preferences'), dict):
        raise ValueError('Missing pending confirmations/preferences')
    if not data.get('sources'):
        raise ValueError('Profile must retain imported source fingerprints')
    for record in data['sources']:
        path = Path(record['path'])
        if not path.is_file() or digest(path) != record['sha256']:
            raise ValueError('CV_SOURCE_CHANGED: re-import and reconcile before review')
    def sensitive(value, path=''):
        if isinstance(value, dict):
            for key, item in value.items():
                if re.search(r'password|secret|token|otp|passport|ssn|id.?card|身份证', key, re.I) and item not in (None, ''):
                    if not (path == 'facts.basic' and key == 'id_card' and data['workflow_preferences'].get('identity_storage_and_fill_authorized') is True and re.fullmatch(r'\d{17}[\dXx]', str(item))):
                        raise ValueError('Sensitive fact requires manual entry or explicit supported identity opt-in')
                sensitive(item, path + '.' + key if path else key)
        elif isinstance(value, list):
            for item in value:
                sensitive(item, path)
    sensitive(facts, 'facts')

def review_profile(draft, source, replace=False):
    """Accept an explicitly reviewed draft tied to its immutable import manifest."""
    draft = Path(draft).resolve()
    imports = (STATE / 'imports').resolve()
    if imports not in draft.parents:
        raise ValueError('Review the draft inside this project import directory')
    manifest = json.loads((draft.parent / 'manifest.json').read_text(encoding='utf-8'))
    data = json.loads(draft.read_text(encoding='utf-8'))
    if data.get('sources') != manifest['sources']:
        raise ValueError('Source fingerprints differ from original import manifest')
    if digest(draft.parent / 'resume.txt') != manifest['text_sha256']:
        raise ValueError('Extracted text changed; re-import the source')
    if not source.strip():
        raise ValueError('Provide the basis of the source review')
    validate_profile(data)
    if PROFILE.exists() and not replace:
        raise ValueError('PROFILE_EXISTS: reconcile existing facts and use --replace-reviewed to back up and replace')
    if PROFILE.exists():
        backup = private_dir(STATE / 'profile-backups') / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.md')
        shutil.copyfile(PROFILE, backup)
    data.update(status='ready', reviewed_at=datetime.now(timezone.utc).isoformat(), review_source=source,
                import_dir=str(draft.parent))
    write_profile(PROFILE, data)
    return {'state': 'ready', 'profile': str(PROFILE), 'pending': list(data['pending_confirmations'])}
