"""Read only explicitly selected documents. Never execute their contents."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from xml.etree import ElementTree

MAX_BYTES = 10 * 1024 * 1024
MAX_CHARS = 45000
TEXT_TYPES = {'.txt', '.md', '.markdown', '.xc', '.py', '.js', '.ts', '.tsx', '.jsx', '.json', '.csv', '.log', '.yaml', '.yml', '.toml', '.ini', '.css', '.html', '.xml', '.c', '.cpp', '.h', '.rs', '.go', '.java', '.sql'}


def read_document(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError('Choose a file no larger than 10 MB.')
    suffix = path.suffix.casefold()
    if suffix not in TEXT_TYPES | {'.pdf', '.docx'}:
        raise ValueError('I can learn from text, Markdown, code, PDF, and DOCX files.')
    with path.open('rb') as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('The file exceeds 10 MB.')
    truncated = False
    if suffix == '.pdf':
        sys.path.insert(0, str(Path(__file__).parent / 'vendor'))
        from pypdf import PdfReader
        import io
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(''):
            raise ValueError('Unlock this PDF before sharing it.')
        chunks, total = [], 0
        for page in reader.pages[:20]:
            chunk = page.extract_text() or ''
            chunks.append(chunk)
            total += len(chunk)
            if total >= MAX_CHARS:
                break
        text = '\n'.join(chunks)
        truncated = len(reader.pages) > len(chunks)
    elif suffix == '.docx':
        with zipfile.ZipFile(path) as archive:
            info = archive.getinfo('word/document.xml')
            if info.file_size > 8 * 1024 * 1024:
                raise ValueError('This document is too large when expanded.')
            root = ElementTree.fromstring(archive.read(info))
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        text = '\n'.join(''.join(p.itertext()) for p in root.findall('.//w:p', ns))
    else:
        if data.startswith((b'\xff\xfe', b'\xfe\xff')):
            text = data.decode('utf-16')
        else:
            if b'\x00' in data:
                raise ValueError('This looks like a binary file, not readable text.')
            try:
                text = data.decode('utf-8-sig')
            except UnicodeDecodeError:
                raise ValueError('Save this text file as UTF-8 or UTF-16 before sharing it.') from None
    if not text.strip():
        raise ValueError('No readable text found. Scanned PDFs need OCR first.')
    truncated = truncated or len(text) > MAX_CHARS
    return {'name': path.name, 'text': text[:MAX_CHARS], 'sha256': hashlib.sha256(data).hexdigest(), 'truncated': truncated}


def extract_document(path, timeout=20):
    # A separate, bounded reader keeps malformed documents from blocking the GUI.
    executable = Path(sys.executable)
    if executable.name.lower() == 'pythonw.exe':
        executable = executable.with_name('python.exe')
    result = subprocess.run([str(executable), '-X', 'utf8', str(Path(__file__).resolve()), str(path)],
        capture_output=True, text=True, encoding='utf-8', timeout=timeout,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise ValueError(result.stderr.strip()[-700:] or 'The document could not be read.')
    return json.loads(result.stdout)


if __name__ == '__main__':
    try:
        print(json.dumps(read_document(sys.argv[1]), ensure_ascii=True))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)