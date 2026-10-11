"""Development parser subprocess: bytes in, bounded text out; no path input.

Process separation and POSIX limits are defensive measures, not OS containment.
The Windows job/process containment gate is still pending.
"""

import base64
from io import BytesIO
import json
import os
import sys
import zipfile

MAX_INPUT = 8 * 1024 * 1024
MAX_TEXT = 512 * 1024
MAX_UNITS = 2000
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def xml(data):
    from defusedxml.ElementTree import fromstring
    return fromstring(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)


def checked_archive(data):
    archive = zipfile.ZipFile(BytesIO(data))
    try:
        entries = archive.infolist()
        if not 1 <= len(entries) <= 256:
            raise ValueError()
        seen, expanded = set(), 0
        for item in entries:
            name = item.filename
            if (name.casefold() in seen or name.startswith(("/", "\\"))
                    or "\\" in name or ":" in name or any(p in {"", ".", ".."} for p in name.rstrip("/").split("/"))
                    or item.flag_bits & 1 or item.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                    or (item.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError()
            seen.add(name.casefold())
            expanded += item.file_size
            if (expanded > 16 * 1024 * 1024 or item.file_size > 4 * 1024 * 1024
                    or item.file_size > max(1, item.compress_size) * 200
                    or any(s in name.casefold() for s in ("vbaproject", "activex/", "embeddings/"))):
                raise ValueError()
            # Relationships are parsed as data only; refuse external targets.
            if name.endswith(".rels"):
                if any(node.get("TargetMode", "").casefold() == "external" for node in xml(archive.read(item)).iter()):
                    raise ValueError()
        return archive
    except BaseException:
        archive.close()
        raise


def docx(data):
    with checked_archive(data) as archive:
        types = xml(archive.read("[Content_Types].xml"))
        document_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
        if not any(node.get("PartName") == "/word/document.xml" and node.get("ContentType") == document_type
                   for node in types.iter()):
            raise ValueError()
        root = xml(archive.read("word/document.xml"))
        body = root.find(W + "body")
        if root.tag != W + "document" or body is None:
            raise ValueError()
        if any(node.tag in {W + "ins", W + "del", W + "altChunk", W + "object"} for node in body.iter()):
            raise ValueError()
        units = []
        for paragraph in body.iter(W + "p"):
            text = "".join(node.text or "" if node.tag == W + "t" else
                           "\t" if node.tag == W + "tab" else "\n" if node.tag in {W + "br", W + "cr"} else ""
                           for node in paragraph.iter())
            units.append(text)
            if len(units) > MAX_UNITS:
                raise ValueError()
        return "paragraph", units


def pdf(data):
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(data), strict=True)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= 100:
        raise ValueError()
    units, count = [], 0
    for page in reader.pages:
        contents = page.get_contents()
        # Decoding can itself allocate; the process memory/deadline controls are
        # needed in addition to the post-decompression stream size bound.
        if contents is not None and len(contents.get_data()) > 4 * 1024 * 1024:
            raise ValueError()
        text = page.extract_text() or ""
        count += len(text.encode("utf-8"))
        if count > MAX_TEXT:
            raise ValueError()
        units.append(text)
    if not any(unit.strip() for unit in units):
        raise ValueError()  # No OCR or invented text for image-only documents.
    return "page", units



def csv_document(data):
    import csv
    from io import StringIO
    csv.field_size_limit(4096)
    rows = []
    for row in csv.reader(StringIO(data.decode('utf-8-sig'), newline=''), strict=True):
        if len(rows) >= MAX_UNITS: raise ValueError()
        rows.append(row)
    if not 1 <= len(rows) <= MAX_UNITS or not rows[0] or len(rows[0]) > 32:
        raise ValueError()
    if any(len(row) != len(rows[0]) for row in rows):
        raise ValueError()
    return 'row', [json.dumps({'sheet': 'CSV', 'row': i, 'values': row}, ensure_ascii=True)
                   for i, row in enumerate(rows, 1)]


def xlsx(data):
    import posixpath
    from decimal import Decimal
    S = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
    with checked_archive(data) as archive:
        types = xml(archive.read('[Content_Types].xml'))
        if not any(node.get('PartName')=='/xl/workbook.xml' and node.get('ContentType')==
                   'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml' for node in types):
            raise ValueError()
        workbook = xml(archive.read('xl/workbook.xml'))
        if workbook.tag != S+'workbook': raise ValueError()
        rels = xml(archive.read('xl/_rels/workbook.xml.rels'))
        mapping = {node.get('Id'): node.get('Target') for node in rels}
        shared = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            shared = [''.join(n.text or '' for n in item.iter(S+'t'))
                      for item in xml(archive.read('xl/sharedStrings.xml')).iter(S+'si')]
            if len(shared) > 64000: raise ValueError()
        sheets = list(workbook.iter(S+'sheet'))
        if not 1 <= len(sheets) <= 16: raise ValueError()
        units = []
        for sheet in sheets:
            name = sheet.get('name')
            target = mapping[sheet.get(R+'id')]
            path = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            if not path.startswith('xl/worksheets/') or not path.endswith('.xml'):
                raise ValueError()
            for row in xml(archive.read(path)).iter(S+'row'):
                number = int(row.get('r'))
                if not 1 <= number <= 1000000: raise ValueError()
                values, occupied = [], set()
                for item in row.findall(S+'c'):
                    ref = item.get('r','')
                    import re
                    match = re.fullmatch(r'([A-Z]{1,3})([1-9][0-9]{0,6})', ref)
                    if not match or int(match[2]) != number or item.find(S+'f') is not None:
                        raise ValueError()  # Never trust cached formula results as measured values.
                    index = 0
                    for letter in match[1]: index = index*26 + ord(letter)-64
                    if not 1 <= index <= 32 or index in occupied: raise ValueError()
                    occupied.add(index)
                    while len(values) < index: values.append(None)
                    raw = item.findtext(S+'v')
                    kind = item.get('t','n')
                    if kind == 'inlineStr': value = ''.join(n.text or '' for n in item.iter(S+'t'))
                    elif kind == 's': value = shared[int(raw)] if raw is not None and int(raw) >= 0 else None
                    elif kind == 'b':
                        if raw not in {'0','1'}: raise ValueError()
                        value = raw == '1'
                    elif kind == 'n':
                        if raw is None: value = None
                        else:
                            number_value = Decimal(raw)
                            if not number_value.is_finite() or abs(number_value) > Decimal('1e15'): raise ValueError()
                            value = raw  # Preserve decimals; numeric analysis uses Decimal.
                    elif kind == 'str': value = raw or ''
                    else: raise ValueError()  # Dates/errors require an explicit supported interpretation.
                    if isinstance(value,str) and len(value.encode('utf-8')) > 4096: raise ValueError()
                    values[index-1] = value
                units.append(json.dumps({'sheet': name, 'row': number, 'values': values}, ensure_ascii=True))
                if len(units) > MAX_UNITS: raise ValueError()
        return 'row', units


def pptx(data):
    import posixpath
    P = '{http://schemas.openxmlformats.org/presentationml/2006/main}'
    A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
    R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
    with checked_archive(data) as archive:
        types = xml(archive.read('[Content_Types].xml'))
        if not any(node.get('PartName')=='/ppt/presentation.xml' and node.get('ContentType')==
                   'application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml' for node in types):
            raise ValueError()
        presentation = xml(archive.read('ppt/presentation.xml'))
        if presentation.tag != P+'presentation': raise ValueError()
        rels = xml(archive.read('ppt/_rels/presentation.xml.rels'))
        mapping = {node.get('Id'): node.get('Target') for node in rels}
        slides = list(presentation.iter(P+'sldId'))
        if not 1 <= len(slides) <= 100: raise ValueError()
        units = []
        for slide in slides:
            target = mapping[slide.get(R+'id')]
            path = target.lstrip('/') if target.startswith('/') else posixpath.normpath('ppt/'+target)
            if not path.startswith('ppt/slides/') or not path.endswith('.xml'): raise ValueError()
            root = xml(archive.read(path))
            units.append('\n'.join(''.join(n.text or '' for n in paragraph.iter(A+'t'))
                                   for paragraph in root.iter(A+'p')))
        return 'slide', units


def main():
    if os.name == "posix":
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        if sys.platform.startswith("linux"):
            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    try:
        request = json.loads(sys.stdin.buffer.read(12 * 1024 * 1024 + 1))
        if set(request) != {"format", "data"}:
            raise ValueError()
        data = base64.b64decode(request["data"], validate=True)
        if not 0 < len(data) <= MAX_INPUT:
            raise ValueError()
        if request["format"] == "pdf" and data.startswith(b"%PDF-"):
            kind, units = pdf(data)
        elif request["format"] == "docx" and data.startswith(b"PK\x03\x04"):
            kind, units = docx(data)
        elif request['format'] in {'xlsx','pptx'} and data.startswith(b'PK\x03\x04'):
            kind, units = (xlsx if request['format'] == 'xlsx' else pptx)(data)
        elif request['format'] == 'csv':
            kind, units = csv_document(data)
        else:
            raise ValueError()
        if not units or sum(len(t.encode("utf-8")) for t in units) > MAX_TEXT:
            raise ValueError()
        result = {"ok": True, "unit_kind": kind, "units": units}
    except Exception:
        # Never return parser exception text, source fragments, paths, or logs.
        result = {"ok": False, "error": "Document is unsupported, malformed, empty, or exceeds parser limits"}
    sys.stdout.write(json.dumps(result, ensure_ascii=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
