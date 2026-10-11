"""Read-only, bounded table analysis and cross-document retrieval."""
from pathlib import Path

from .folders import AccessDenied
from .model import strict_json
from .office_artifacts import summarize_column

STRUCTURED = {'.pdf','.docx','.csv','.xlsx','.pptx'}
TEXT = {'.txt','.md','.py','.json','.log'}


def analyze_table(workspace, folder_id, path, column, sheet=None):
    if Path(path).suffix.lower() not in {'.csv','.xlsx'}:
        raise AccessDenied('Table analysis accepts CSV or XLSX')
    workspace.checkpoint()
    document = workspace.open_document(folder_id, path)
    records = [strict_json(unit) for unit in document.units]
    names = list(dict.fromkeys(row['sheet'] for row in records))
    if sheet is None:
        if len(names) != 1:
            raise AccessDenied('Select a sheet explicitly: '+', '.join(names))
        sheet = names[0]
    selected = [(i, row) for i,row in enumerate(records,1) if row['sheet'] == sheet]
    if len(selected) < 2:
        raise AccessDenied('Sheet requires a header and at least one data row')
    headers = selected[0][1]['values']
    if (not all(isinstance(h,str) and h.strip() for h in headers)
            or len(set(headers)) != len(headers) or column not in headers):
        raise AccessDenied('Select a unique text column header')
    index = headers.index(column)
    rows = [row['values'] + [None]*max(0,len(headers)-len(row['values'])) for _,row in selected[1:]]
    if any(len(row) != len(headers) for row in rows):
        raise AccessDenied('Table contains rows wider than its header')
    statistics = summarize_column(rows,index)
    return document, selected[0][0], selected[-1][0], {'sheet':sheet, 'column':column,
        'headers':headers, 'data_rows':len(rows), 'statistics':statistics,
        'worksheet_row_range':[selected[0][1]['row'],selected[-1][1]['row']],
        'citation_unit_note':'Citation row units are ordered parsed records; sheet and physical row numbers are explicit metadata.',
        'interpretation':'Literal values only; formulas are rejected. Missing and nonnumeric cells are counted separately.'}


def search_folder(workspace, folder_id, query, path=''):
    if not isinstance(query,str) or not 1 <= len(query.strip()) <= 128 or len(query.split()) > 8:
        raise AccessDenied('Use a bounded keyword or phrase')
    import re
    pattern = re.compile(r'\s+'.join(re.escape(word) for word in query.split()), re.IGNORECASE)
    pending, visited, documents, partial = [(path,0)], 0, 0, False
    while pending and visited < 32 and documents < 16:
        workspace.checkpoint()
        directory, depth = pending.pop(0)
        listing = workspace.broker.list_directory(folder_id, directory, limit=100)
        visited += 1; partial |= listing['truncated']
        for entry in listing['entries']:
            workspace.checkpoint()
            relative = '/'.join(filter(None,(directory,entry['name'])))
            if entry['kind'] == 'directory':
                if depth < 6 and len(pending) < 32: pending.append((relative,depth+1))
                else: partial = True
                continue
            suffix = Path(relative).suffix.lower()
            if suffix not in STRUCTURED | TEXT: continue
            if documents >= 16: partial = True; break
            documents += 1
            try:
                if suffix in STRUCTURED:
                    source = workspace.open_document(folder_id,relative)
                    units, kind = source.units, source.unit_kind
                else:
                    source = workspace.open_text(folder_id,relative)
                    units, kind = source.text.splitlines(), 'line'
            except (AccessDenied,OSError):
                partial = True; continue
            for number, unit in enumerate(units,1):
                workspace.checkpoint()
                match = pattern.search(unit)
                if match:
                    left,right = max(0,match.start()-160), min(len(unit),match.end()+260)
                    return source, kind, number, unit[left:right], {'found':True,
                        'searched_documents':documents, 'searched_directories':visited,
                        'search_complete':False, 'excerpt_is_partial': True}
    return None, None, None, None, {'found':False, 'searched_documents':documents,
        'searched_directories':visited, 'search_complete':not (partial or pending),
        'limits':{'documents':16,'directories':32,'depth':6},
        'note':'No literal match in inspected readable documents; a partial search cannot establish absence.'}
