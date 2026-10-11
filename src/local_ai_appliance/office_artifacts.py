"""Bounded, deterministic office writers. No macros, formulas or external links.

Only validated structured content is accepted. The host builds the bytes; model
output cannot provide ZIP parts, templates, executable content or save authority.
"""
import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
import math
from xml.sax.saxutils import escape
import zipfile

from .folders import AccessDenied
from .model import json_bytes, strict_json

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
S = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'


@dataclass(frozen=True)
class OfficeArtifact:
    data: bytes
    preview: str
    format: str


def text(value, *, limit=4096):
    if (not isinstance(value, str) or len(value.encode('utf-8')) > limit
            or any(ord(c) < 32 and c not in '\n\t' or 0xD800 <= ord(c) <= 0xDFFF
                   or ord(c) in {0xFFFE, 0xFFFF} for c in value)):
        raise AccessDenied('Artifact contains invalid or oversized text')
    return value


def exact(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise AccessDenied('Artifact structure has missing or unsupported fields')


def cell(value):
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if not math.isfinite(value) or abs(value) > 1e15:
            raise AccessDenied('Cell number is non-finite or too large')
        return value
    return text(value, limit=512)


def table(value):
    exact(value, {'headers', 'rows'})
    headers, rows = value['headers'], value['rows']
    if (not isinstance(headers, list) or not 1 <= len(headers) <= 32
            or not isinstance(rows, list) or not 1 <= len(rows) <= 500):
        raise AccessDenied('Table requires 1 to 32 columns and 1 to 500 rows')
    headers = [text(h, limit=128) for h in headers]
    if any(not h.strip() for h in headers) or len(set(headers)) != len(headers):
        raise AccessDenied('Table headers must be nonempty and unique')
    if any(not isinstance(row, list) or len(row) != len(headers) for row in rows):
        raise AccessDenied('Table row width differs from headers')
    return headers, [[cell(c) for c in row] for row in rows]


def package(parts, main_types):
    types = ('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="xml" ContentType="application/xml"/>' + ''.join(
                 f'<Override PartName="/{name}" ContentType="{kind}"/>' for name, kind in main_types) + '</Types>')
    parts = {'[Content_Types].xml': types, **parts}
    result = BytesIO()
    with zipfile.ZipFile(result, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(parts.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, data.encode('utf-8'))
    data = result.getvalue()
    if len(data) > 1024*1024:
        raise AccessDenied('Artifact exceeds 1 MiB')
    return data


def relationships(rows):
    return f'<Relationships xmlns="{PKG}">' + ''.join(
        f'<Relationship Id="{identifier}" Type="{R}/{kind}" Target="{target}"/>'
        for identifier, kind, target in rows) + '</Relationships>'


def paragraph(value, *, bold=False, size=22, style=None):
    props = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ''
    return (f'<w:p>{props}<w:r><w:rPr><w:sz w:val="{size}"/>' + ('<w:b/>' if bold else '') +
            '</w:rPr><w:t xml:space="preserve">' + escape(value) + '</w:t></w:r></w:p>')


def render_docx(spec, source_notes=()):
    exact(spec, {'title', 'sections'})
    title = text(spec['title'], limit=256)
    sections = spec['sections']
    if not isinstance(sections, list) or not 1 <= len(sections) <= 40:
        raise AccessDenied('Document requires 1 to 40 sections')
    body, preview = [paragraph(title, bold=True, size=36, style='Title')], [title]
    for section in sections:
        if not isinstance(section, dict) or set(section) - {'heading', 'paragraphs', 'table'} or not {'heading', 'paragraphs'} <= set(section):
            raise AccessDenied('Invalid document section')
        heading = text(section['heading'], limit=256)
        paragraphs = section['paragraphs']
        if not isinstance(paragraphs, list) or len(paragraphs) > 40:
            raise AccessDenied('Too many document paragraphs')
        body.append(paragraph(heading, bold=True, size=28, style='Heading1')); preview.append(heading)
        for item in paragraphs:
            item = text(item)
            # Actual paragraph boundaries, no literal XML/newline formatting injection.
            for line in item.split('\n'):
                body.append(paragraph(line)); preview.append(line)
        if 'table' in section:
            headers, rows = table(section['table'])
            width = 9360 // len(headers)
            body.append('<w:tbl><w:tblPr><w:tblW w:w="9360" w:type="dxa"/><w:tblBorders>' +
                ''.join(f'<w:{edge} w:val="single" w:sz="4" w:color="C8D0DA"/>'
                        for edge in ('top','left','bottom','right','insideH','insideV')) + '</w:tblBorders></w:tblPr>' +
                '<w:tblGrid>' + f'<w:gridCol w:w="{width}"/>'*len(headers) + '</w:tblGrid>' + ''.join(
                    '<w:tr>' + ''.join(f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/></w:tcPr>' +
                        paragraph('' if c is None else str(c), bold=i == 0) + '</w:tc>' for c in row) + '</w:tr>'
                    for i, row in enumerate([headers, *rows])) + '</w:tbl>')
            preview.extend(' | '.join('' if c is None else str(c) for c in row) for row in [headers, *rows])
    body.append('<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>')
    if source_notes:
        body.insert(-1, paragraph('Supporting files', bold=True, size=28, style='Heading1'))
        for note in source_notes: body.insert(-1, paragraph(note, size=18))
        preview.extend(['Supporting files', *source_notes])
    styles = f'<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/></w:rPr></w:rPrDefault></w:docDefaults>' + ''.join(
        f'<w:style w:type="paragraph" w:styleId="{name}"><w:name w:val="{name}"/><w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/></w:pPr></w:style>'
        for name in ('Title', 'Heading1')) + '</w:styles>'
    parts = {'_rels/.rels': relationships([('rId1','officeDocument','word/document.xml')]),
             'word/document.xml': f'<w:document xmlns:w="{W}"><w:body>'+''.join(body)+'</w:body></w:document>',
             'word/styles.xml': styles,
             'word/_rels/document.xml.rels': relationships([('rId1','styles','styles.xml')])}
    return OfficeArtifact(package(parts, [('word/document.xml','application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'),
        ('word/styles.xml','application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml')]), '\n\n'.join(preview), 'docx')


def column(number):
    value = ''
    while number:
        number, remainder = divmod(number-1, 26); value = chr(65+remainder)+value
    return value


def render_table(spec, kind, source_notes=()):
    exact(spec, {'title', 'headers', 'rows'})
    title = text(spec['title'], limit=256)
    headers, rows = table({'headers': spec['headers'], 'rows': spec['rows']})
    preview = title + '\n' + '\n'.join(' | '.join('' if c is None else str(c) for c in row) for row in [headers, *rows])
    if kind == 'csv':
        output = StringIO(newline='')
        writer = csv.writer(output, lineterminator='\r\n')
        def safe(value):
            if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
                return "'" + value
            return '' if value is None else value
        writer.writerows([[safe(c) for c in row] for row in [headers,*rows]])
        return OfficeArtifact(output.getvalue().encode('utf-8'), preview, kind)
    sheet = []
    for i, row in enumerate([headers, *rows], 1):
        cells = []
        for j, value in enumerate(row, 1):
            ref = column(j)+str(i)
            style = ' s="1"' if i == 1 else ''
            if value is None:
                item = f'<c r="{ref}"/>'
            elif isinstance(value, bool):
                item = f'<c r="{ref}" t="b"{style}><v>{int(value)}</v></c>'
            elif isinstance(value, (int,float)):
                item = f'<c r="{ref}"{style}><v>{value}</v></c>'
            else:
                item = f'<c r="{ref}" t="inlineStr"{style}><is><t xml:space="preserve">{escape(value)}</t></is></c>'
            cells.append(item)
        sheet.append(f'<row r="{i}">'+''.join(cells)+'</row>')
    styles = f'<styleSheet xmlns="{S}"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2"><xf fontId="0" fillId="0" borderId="0" xfId="0"/><xf fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'
    parts = {'_rels/.rels': relationships([('rId1','officeDocument','xl/workbook.xml')]),
        'xl/workbook.xml': f'<workbook xmlns="{S}" xmlns:r="{R}"><sheets><sheet name="Results" sheetId="1" r:id="rId1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels': relationships([('rId1','worksheet','worksheets/sheet1.xml'),('rId2','styles','styles.xml')]),
        'xl/styles.xml': styles,
        'xl/worksheets/sheet1.xml': f'<worksheet xmlns="{S}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>' +
            f'<col min="1" max="{len(headers)}" width="24" customWidth="1"/></cols><sheetData>'+''.join(sheet)+f'</sheetData><autoFilter ref="A1:{column(len(headers))}{len(rows)+1}"/></worksheet>'}
    overrides = [('xl/workbook.xml','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml'),
        ('xl/worksheets/sheet1.xml','application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml'),
        ('xl/styles.xml','application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml')]
    if source_notes:
        parts['xl/workbook.xml'] = parts['xl/workbook.xml'].replace('</sheets>', '<sheet name="Sources" sheetId="2" r:id="rId3"/></sheets>')
        parts['xl/_rels/workbook.xml.rels'] = relationships([('rId1','worksheet','worksheets/sheet1.xml'),('rId2','styles','styles.xml'),('rId3','worksheet','worksheets/sheet2.xml')])
        parts['xl/worksheets/sheet2.xml'] = f'<worksheet xmlns="{S}"><cols><col min="1" max="1" width="100" customWidth="1"/></cols><sheetData>' + ''.join(
            f'<row r="{i}"><c r="A{i}" t="inlineStr"><is><t>{escape(note)}</t></is></c></row>' for i,note in enumerate(source_notes,1)) + '</sheetData></worksheet>'
        overrides.append(('xl/worksheets/sheet2.xml','application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml'))
        preview += '\n\nSupporting files:\n'+'\n'.join(source_notes)
    return OfficeArtifact(package(parts, overrides), preview, kind)


def shape(identifier, name, value, *, y, height, size):
    lines = value.split('\n')
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{identifier}" name="{name}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="685800" y="{y}"/><a:ext cx="10820400" cy="{height}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>'
        '<p:txBody><a:bodyPr wrap="square"/><a:lstStyle/>' + ''.join(
            f'<a:p><a:r><a:rPr lang="en-US" sz="{size}"/><a:t>{escape(line)}</a:t></a:r></a:p>' for line in lines) + '</p:txBody></p:sp>')


def presentation_support_parts():
    """Fixed, internal-only master/layout/theme required by native PowerPoint."""
    tree = ('<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
            '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>')
    colors = [('dk1','000000'),('lt1','FFFFFF'),('dk2','253858'),('lt2','F4F6F8'),
              ('accent1','2463A6'),('accent2','548235'),('accent3','A65E24'),
              ('accent4','8064A2'),('accent5','4BACC6'),('accent6','C0504D'),
              ('hlink','0563C1'),('folHlink','954F72')]
    solid = '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
    theme = (f'<a:theme xmlns:a="{A}" name="SILO"><a:themeElements><a:clrScheme name="SILO">'
             + ''.join(f'<a:{name}><a:srgbClr val="{color}"/></a:{name}>' for name,color in colors)
             + '</a:clrScheme><a:fontScheme name="SILO">'
             + ''.join(f'<a:{kind}><a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/></a:{kind}>'
                       for kind in ('majorFont','minorFont'))
             + '</a:fontScheme><a:fmtScheme name="SILO"><a:fillStyleLst>'+solid*3+'</a:fillStyleLst>'
             + '<a:lnStyleLst>'+''.join(f'<a:ln w="{width}" cap="flat" cmpd="sng" algn="ctr">'
               +solid+'<a:prstDash val="solid"/><a:miter lim="800000"/></a:ln>' for width in (6350,12700,19050))
             + '</a:lnStyleLst><a:effectStyleLst>'+'<a:effectStyle><a:effectLst/></a:effectStyle>'*3
             + '</a:effectStyleLst><a:bgFillStyleLst>'+solid*3+'</a:bgFillStyleLst></a:fmtScheme>'
             + '</a:themeElements><a:objectDefaults/><a:extraClrSchemeLst/></a:theme>')
    ns = f'xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}"'
    parts = {
        'ppt/presProps.xml': f'<p:presentationPr {ns}/>',
        'ppt/slideMasters/slideMaster1.xml': f'<p:sldMaster {ns}><p:cSld><p:spTree>'+tree
            + '</p:spTree></p:cSld><p:clrMap accent1="accent1" accent2="accent2" accent3="accent3" '
            + 'accent4="accent4" accent5="accent5" accent6="accent6" bg1="lt1" bg2="lt2" '
            + 'folHlink="folHlink" hlink="hlink" tx1="dk1" tx2="dk2"/>'
            + '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
            + '<p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles></p:sldMaster>',
        'ppt/slideMasters/_rels/slideMaster1.xml.rels': relationships([
            ('rId1','slideLayout','../slideLayouts/slideLayout1.xml'),('rId2','theme','../theme/theme1.xml')]),
        'ppt/slideLayouts/slideLayout1.xml': f'<p:sldLayout {ns} type="blank" preserve="1">'
            + '<p:cSld name="Blank"><p:spTree>'+tree+'</p:spTree></p:cSld>'
            + '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>',
        'ppt/slideLayouts/_rels/slideLayout1.xml.rels': relationships([
            ('rId1','slideMaster','../slideMasters/slideMaster1.xml')]),
        'ppt/theme/theme1.xml': theme,
    }
    overrides = [(name,'application/vnd.openxmlformats-officedocument.'+kind+'+xml') for name,kind in (
        ('ppt/presProps.xml','presentationml.presProps'),
        ('ppt/slideMasters/slideMaster1.xml','presentationml.slideMaster'),
        ('ppt/slideLayouts/slideLayout1.xml','presentationml.slideLayout'),
        ('ppt/theme/theme1.xml','theme'))]
    return parts, overrides


def render_pptx(spec, source_notes=()):
    exact(spec, {'title','slides'})
    title = text(spec['title'], limit=256)
    slides = spec['slides']
    if not isinstance(slides, list) or not 1 <= len(slides) <= 30:
        raise AccessDenied('Presentation requires 1 to 30 slides')
    if source_notes:
        # Fixed typography: short source notes per slide, rather than squeezing long paths.
        from textwrap import wrap
        lines = [line for note in source_notes for line in wrap(note,width=95)]
        if len(lines) > 36: raise AccessDenied('Presentation source notes exceed six supporting-file slides')
        slides = [*slides,*[{'title':'Supporting files','bullets':lines[i:i+6]} for i in range(0,len(lines),6)]]
    parts = {'_rels/.rels': relationships([('rId1','officeDocument','ppt/presentation.xml')])}
    overrides = [('ppt/presentation.xml','application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml')]
    support, support_types = presentation_support_parts()
    parts.update(support); overrides.extend(support_types)
    preview, ids = [title], []
    rels = [('rIdMaster','slideMaster','slideMasters/slideMaster1.xml'),
            ('rIdProperties','presProps','presProps.xml')]
    for i, slide in enumerate(slides, 1):
        exact(slide, {'title','bullets'})
        heading = text(slide['title'], limit=100)
        bullets = slide['bullets']
        if not isinstance(bullets, list) or not 1 <= len(bullets) <= 6:
            raise AccessDenied('Each slide requires 1 to 6 bullets')
        bullets = [text(item, limit=180) for item in bullets]
        preview.append(f'Slide {i}: {heading}\n'+'\n'.join('• '+item for item in bullets))
        name = f'ppt/slides/slide{i}.xml'
        tree = '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        parts[name] = f'<p:sld xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}"><p:cSld><p:spTree>'+tree+shape(2,'Title',heading,y=457200,height=914400,size=3200)+shape(3,'Body','\n'.join('• '+item for item in bullets),y=1600200,height=4572000,size=2200)+'</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'
        parts[f'ppt/slides/_rels/slide{i}.xml.rels'] = relationships([
            ('rIdLayout','slideLayout','../slideLayouts/slideLayout1.xml')])
        ids.append(f'<p:sldId id="{255+i}" r:id="rId{i}"/>')
        rels.append((f'rId{i}', 'slide', f'slides/slide{i}.xml'))
        overrides.append((name,'application/vnd.openxmlformats-officedocument.presentationml.slide+xml'))
    parts['ppt/presentation.xml'] = f'<p:presentation xmlns:p="{P}" xmlns:r="{R}"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rIdMaster"/></p:sldMasterIdLst><p:sldIdLst>'+''.join(ids)+'</p:sldIdLst><p:sldSz cx="12192000" cy="6858000" type="screen16x9"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>'
    parts['ppt/_rels/presentation.xml.rels'] = relationships(rels)
    return OfficeArtifact(package(parts, overrides), '\n\n'.join(preview), 'pptx')


def build_artifact(kind, content, *, sources=()):
    if not isinstance(content, str) or len(content.encode('utf-8')) > 64*1024:
        raise AccessDenied('Structured artifact content exceeds 64 KiB')
    try:
        spec = strict_json(content)
        from .agent import DocumentAgent
        DocumentAgent._citations(content,sources)
        notes = list(dict.fromkeys(f'{source.path} · {source.locator} · SHA-256 {source.sha256}' for source in sources))
        import re
        def replace_citations(value):
            if isinstance(value,str):
                def reference(match):
                    source=DocumentAgent._citations(match.group(0),sources)[0]
                    return '['+source.path+', '+source.locator+']'
                return re.sub(r'\[source:[^\]\r\n]*\]',reference,value)
            if isinstance(value,list):return [replace_citations(item) for item in value]
            if isinstance(value,dict):return {key:replace_citations(item) for key,item in value.items()}
            return value
        spec = replace_citations(spec)
        if kind == 'docx': return render_docx(spec,notes)
        if kind in {'csv','xlsx'}: return render_table(spec, kind,notes)
        if kind == 'pptx': return render_pptx(spec,notes)
    except (ValueError, TypeError, OverflowError) as error:
        raise AccessDenied('Malformed structured artifact content') from error
    raise AccessDenied('Choose DOCX, XLSX, CSV, or PPTX')


def summarize_column(rows, column_index):
    """No expression evaluation, coercion of dates, or formula execution."""
    values, missing, rejected = [], 0, 0
    for row in rows:
        value = row[column_index]
        if value is None or value == '': missing += 1; continue
        if isinstance(value, bool): rejected += 1; continue
        try:
            number = Decimal(str(value))
            if not number.is_finite() or abs(number) > Decimal('1e15'):
                raise InvalidOperation()
            values.append(number)
        except (InvalidOperation, ValueError): rejected += 1
    return {'numeric_count':len(values), 'missing_count':missing, 'rejected_count':rejected,
            'sum':str(sum(values,Decimal(0))), 'minimum':str(min(values)) if values else None,
            'maximum':str(max(values)) if values else None,
            'mean':str(sum(values,Decimal(0))/len(values)) if values else None}
