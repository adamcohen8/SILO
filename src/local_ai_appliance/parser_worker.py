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


def docx(data):
    with zipfile.ZipFile(BytesIO(data)) as archive:
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
