"""Resolve explicit file-list requests with permission-scoped directory metadata."""
import re

from .agent import AgentResult
from .folders import AccessDenied

_REQUEST = re.compile(
    r'(?:please\s+)?list\s+(?:the\s+)?(?:files|contents)\s+'
    r'(?:under|in|inside|of)\s+(?:the\s+)?(.+?)(?:\s+(?:folder|directory))?[.!?]?',
    re.IGNORECASE)


def list_directory_request(workspace, prompt, *, references=(), max_directories=32, max_depth=4):
    """Handle a complete listing request; return None for other document work.

    A basename selects the nearest matching directory below the grants. All
    directories at that depth are considered; ambiguous or incomplete searches
    require a relative path. Explicit relative paths are never rewritten.
    """
    match = _REQUEST.fullmatch(prompt.strip())
    if not match:
        return None
    requested = match[1].strip().strip('`"\'')
    referenced = next((r for r in references if r['token'].strip('`"\'').rstrip('.!?') == requested.rstrip('.!?')), None)
    if referenced:
        if referenced['kind'] != 'directory':
            return None
        revision = workspace.broker.revision
        folder = next((f for f in workspace.broker.folders() if f.id == referenced['folder_id']), None)
        if folder is None:
            raise AccessDenied('Folder reference is no longer granted.')
        result = workspace.broker.list_directory(folder.id, referenced['path'])
        if workspace.broker.revision != revision:
            raise AccessDenied('Folder permissions changed; start a fresh request')
        return AgentResult(_listing_answer(folder, referenced['path'], result), (), (), 0, 1)
    if not requested or requested in {'.', '..'} or any(c in requested for c in '\\:\r\n\0'):
        return None
    broker = workspace.broker
    revision = broker.revision
    calls = 0

    def check():
        if broker.revision != revision:
            raise AccessDenied('Folder permissions changed; start a fresh request')

    def listing(folder, path):
        nonlocal calls
        check()
        calls += 1
        result = broker.list_directory(folder.id, path)
        check()
        return result

    folders = tuple(broker.folders())
    matches = []
    incomplete = False
    if '/' in requested:
        # The broker validates traversal and absolute-path syntax.
        for folder in folders:
            if calls >= max_directories:
                incomplete = True
                break
            try:
                result = listing(folder, requested)
                matches.append((folder, requested, result))
            except AccessDenied:
                check()
    else:
        level = [(folder, '') for folder in folders]
        for depth in range(max_depth+1):
            candidates = [(folder, path) for folder, path in level
                if (path.rsplit('/', 1)[-1] if path else folder.name).casefold() == requested.casefold()]
            if candidates:
                for folder, path in candidates:
                    if calls >= max_directories:
                        incomplete = True
                        break
                    try:
                        matches.append((folder, path, listing(folder, path)))
                    except AccessDenied:
                        check()
                break
            if depth == max_depth:
                incomplete = bool(level)
                break
            children = []
            for folder, path in level:
                if calls >= max_directories:
                    incomplete = True
                    break
                try:
                    result = listing(folder, path)
                except AccessDenied:
                    check()
                    continue
                # Enumerate the complete level before choosing a named child.
                incomplete |= result['truncated']
                children.extend((folder, '/'.join(filter(None, (path, entry['name']))))
                    for entry in result['entries'] if entry['kind'] == 'directory')
            if incomplete or not children:
                break
            level = children
    check()
    if incomplete:
        answer = 'The folder search reached its limit. Specify the folder’s relative path within a granted folder.'
    elif len(matches) > 1:
        answer = 'More than one folder matches. Specify one of these relative paths:\n\n'+'\n'.join(
            f'- {folder.name}: {path or "(root)"}' for folder, path, _ in matches)
    elif not matches:
        answer = f'Could not find “{requested}” in the permitted directories searched. Check the relative path or add the folder.'
    else:
        folder, path, result = matches[0]
        answer = _listing_answer(folder, path, result)
    return AgentResult(answer, (), (), 0, calls)


def _listing_answer(folder, path, result):
    files = [entry['name'] for entry in result['entries'] if entry['kind'] == 'file']
    directories = [entry['name'] for entry in result['entries'] if entry['kind'] == 'directory']
    answer = f'Files in {folder.name} / {path or "(root)"} ({len(files)} listed):\n\n'
    answer += '\n'.join('- '+name for name in files) or 'No files were returned by this listing.'
    if directories:
        answer += '\n\nSubfolders:\n'+'\n'.join('- '+name+'/' for name in directories)
    if result['truncated']:
        answer += '\n\nThe listing is truncated.'
    return answer
