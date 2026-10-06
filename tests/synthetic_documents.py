"""Small deterministic, non-operational document fixtures. No model required."""

from io import BytesIO
import zipfile


def docx_bytes(texts=("Synthetic exercise: ALPHA.", "The training deadline is 15 October."), *, extra=None):
    from xml.sax.saxutils import escape
    document = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body>' + ''.join('<w:p><w:r><w:t>' + escape(t) + '</w:t></w:r></w:p>' for t in texts)
                + '</w:body></w:document>')
    files = {
        '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        '_rels/.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
        'word/document.xml': document,
    }
    files.update(extra or {})
    output = BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_STORED) as archive:
        for name, value in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            archive.writestr(info, value)
    return output.getvalue()


def pdf_bytes(texts=("Synthetic exercise ALPHA.", "Training deadline: 15 October.")):
    # Literal printable ASCII fixture, exact xref offsets; no parser dependency.
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'']
    kids = []
    for text in texts:
        page = len(objects) + 1
        content = page + 1
        kids.append(f'{page} 0 R')
        literal = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        stream = f'BT /F1 12 Tf 72 720 Td ({literal}) Tj ET'.encode('ascii')
        objects.extend([
            f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> /Contents {content} 0 R >>'.encode(),
            b'<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'\nendstream',
        ])
    objects[1] = f'<< /Type /Pages /Kids [{" ".join(kids)}] /Count {len(kids)} >>'.encode()
    output, offsets = bytearray(b'%PDF-1.4\n'), [0]
    for i, value in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f'{i} 0 obj\n'.encode() + value + b'\nendobj\n')
    start = len(output)
    output.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]:
        output.extend(f'{offset:010d} 00000 n \n'.encode())
    output.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode())
    return bytes(output)
