"""Literal Markdown presentation. No HTML, link fetching, or executable markup."""
from dataclasses import dataclass
import io
import keyword
import re
import tokenize
import unicodedata

from .terminal_ui import literal


def width(text):
    return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in 'WF' else 1
               for c in text)


def cells(text, size):
    """Wrap display cells without deleting or changing cell contents."""
    result, current = [], ''
    for c in text:
        if current and width(current + c) > size:
            result.append(current); current = ''
        current += c
    return result + [current]


def table(headers, rows, *, columns=88):
    values = [[literal(str(c)).replace('\n', ' ↵ ').expandtabs(4) for c in row]
              for row in [headers, *rows]]
    if not rows:
        return ['No entries.']
    count = len(headers)
    if columns < count * 6:
        return ['; '.join(f'{h}: {c}' for h, c in zip(values[0], row)) for row in values[1:]]
    widths = [max(width(row[i]) for row in values) for i in range(count)]
    budget = max(count, columns - 3 * (count - 1))
    while sum(widths) > budget:
        index = widths.index(max(widths))
        widths[index] -= 1
    output = []
    for index, row in enumerate(values):
        wrapped = [cells(c, size) for c, size in zip(row, widths)]
        for part in range(max(map(len, wrapped))):
            pieces = [value[part] if part < len(value) else '' for value in wrapped]
            output.append(' │ '.join(c + ' ' * max(0, size - width(c)) for c, size in zip(pieces, widths)).rstrip())
        if index == 0:
            output.append('─┼─'.join('─' * size for size in widths))
    return output


@dataclass(frozen=True)
class RenderedLine:
    text: str
    tone: str = 'body'
    spans: tuple = ()


def inline(text):
    spans, position = [], 0
    for match in re.finditer(r'(\*\*([^*]+)\*\*|`([^`]+)`|\[source:[^\]\n]+\])', text):
        spans.append(('', text[position:match.start()]))
        if match.group(2) is not None: spans.append(('class:bold', match.group(2)))
        elif match.group(3) is not None: spans.append(('class:code', match.group(3)))
        else: spans.append(('class:citation', match.group(0)))
        position = match.end()
    spans.append(('', text[position:]))
    return tuple(spans)


def code_spans(text, language):
    if language not in {'python', 'py', 'json'}:
        return (('class:code', text),)
    try:
        result, position = [], 0
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.start[0] != 1 or token.type in {tokenize.ENDMARKER, tokenize.NEWLINE, tokenize.NL}:
                continue
            start, end = token.start[1], token.end[1]
            result.append(('class:code', text[position:start]))
            tone = ('string' if token.type == tokenize.STRING else 'number' if token.type == tokenize.NUMBER
                    else 'comment' if token.type == tokenize.COMMENT else 'keyword'
                    if keyword.iskeyword(token.string) or token.string in {'true', 'false', 'null'} else 'code')
            result.append(('class:' + tone, text[start:end])); position = end
        result.append(('class:code', text[position:]))
        return tuple(result)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return (('class:code', text),)


def markdown(text, *, columns=88):
    lines = literal(text).expandtabs(4).split('\n')
    output, fence, index = [], None, 0
    while index < len(lines):
        line = lines[index]
        marker = re.match(r'^\s*(```+|~~~+)(.*)$', line)
        if marker:
            if fence is None:
                fence = (marker[1][0], marker[2].strip().lower())
                output.append(RenderedLine('  ' + (fence[1] or 'code'), 'muted'))
            elif marker[1][0] == fence[0]:
                fence = None
            else:
                output.append(RenderedLine(line, 'code', code_spans(line, fence[1])))
        elif fence is not None:
            output.append(RenderedLine(line, 'code', code_spans(line, fence[1])))
        elif (index + 1 < len(lines) and '|' in line
              and re.fullmatch(r'\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*', lines[index + 1])):
            headers = [c.strip() for c in line.strip().strip('|').split('|')]
            rows = []; index += 2
            while index < len(lines) and '|' in lines[index]:
                row = [c.strip() for c in lines[index].strip().strip('|').split('|')]
                if len(row) != len(headers): break
                rows.append(row); index += 1
            output += [RenderedLine(row, 'table') for row in table(headers, rows, columns=columns)]
            continue
        else:
            heading = re.match(r'^#{1,6}\s+(.*)', line)
            if heading: line, tone = heading[1], 'bold'
            elif re.match(r'^\s*[-*+]\s', line): line, tone = re.sub(r'^(\s*)[-*+]\s', r'\1• ', line), 'body'
            elif line.startswith('> '): line, tone = '│ ' + line[2:], 'muted'
            else: tone = 'body'
            spans = inline(line)
            output.append(RenderedLine(''.join(t for _, t in spans), tone, spans))
        index += 1
    return output
