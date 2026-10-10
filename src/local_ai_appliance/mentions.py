"""Bounded, name-only folder/file mentions resolved by the trusted host."""
from dataclasses import dataclass
import json
import re

from .folders import AccessDenied


_MENTION = re.compile(r'(?<![\w@/\\:])([@/])(?:"([^"\r\n]+)"|([^\s"<>()[\]{};,!?:]+))')


def mention_token(sigil, name):
    return sigil+(json.dumps(name, ensure_ascii=False) if re.search(r'[\s"<>()[\]{};,!?:]', name) else name)


def parsed_mentions(text):
    return [(m.group(0), m.group(1), m.group(2) or m.group(3)) for m in _MENTION.finditer(text)]


@dataclass(frozen=True)
class Mention:
    alias: str
    folder_id: str
    path: str
    kind: str

    @property
    def name(self):
        return '/'.join(filter(None, (self.alias, self.path)))

    @property
    def token(self):
        return mention_token('/' if self.kind == 'directory' else '@', self.name)


class MentionCatalog:
    def __init__(self, broker, *, max_directories=32, max_depth=4, max_entries=512):
        self.revision = broker.revision
        folders = broker.folders()
        self.locations = {folder.id: saved['path'] for folder, saved in zip(folders, broker.saved_grants())}
        counts = {}
        for folder in folders:
            counts[folder.name.casefold()] = counts.get(folder.name.casefold(), 0)+1
        used, numbers = set(), {}
        self.roots, self.items, self.incomplete = [], [], False
        for folder in folders:
            name = folder.name
            if counts[name.casefold()] > 1:
                numbers[name.casefold()] = numbers.get(name.casefold(), 0)+1
                name += f' ({numbers[folder.name.casefold()]})'
            while name.casefold() in used or (name != folder.name and name.casefold() in counts):
                name += ' (folder)'
            used.add(name.casefold())
            root = Mention(name, folder.id, '', 'directory')
            self.roots.append(root)
            self.items.append(root)
        queue = [(root, '', 0) for root in self.roots]
        calls, entries = 0, 0
        while queue and calls < max_directories and entries < max_entries:
            root, path, depth = queue.pop(0)
            self.check(broker)
            try:
                listing = broker.list_directory(root.folder_id, path, limit=min(128, max_entries-entries))
            except AccessDenied:
                self.incomplete = True
                continue
            calls += 1
            self.incomplete |= listing['truncated']
            for entry in listing['entries']:
                relative = '/'.join(filter(None, (path, entry['name'])))
                self.items.append(Mention(root.alias, root.folder_id, relative, entry['kind']))
                entries += 1
                if entry['kind'] == 'directory':
                    if depth < max_depth:
                        queue.append((root, relative, depth+1))
                    else:
                        self.incomplete = True
        self.incomplete |= bool(queue)
        self.check(broker)

    def check(self, broker):
        if self.revision != broker.revision:
            raise AccessDenied('Folder access changed. Choose the reference again.')

    def suggestions(self, sigil, query):
        kind = 'directory' if sigil == '/' else 'file'
        query = query.strip('"').casefold()
        return sorted((item for item in self.items if item.kind == kind and query in item.name.casefold()),
                      key=lambda item: (bool(item.path), item.name.casefold()))[:40]

    def resolve(self, broker, text):
        self.check(broker)
        results = []
        parsed = parsed_mentions(text)
        if len(parsed) > 32:
            raise AccessDenied('Use at most 32 folder/file references per request.')
        for token, sigil, name in parsed:
            kind = 'directory' if sigil == '/' else 'file'
            # An explicit grant alias and relative path can exceed preview bounds.
            root = next((r for r in self.roots if name.casefold() == r.alias.casefold()
                         or name.casefold().startswith(r.alias.casefold()+'/')), None)
            if root:
                path = name[len(root.alias):].lstrip('/')
                if kind == 'directory':
                    path = path.rstrip('/')
                try:
                    actual = 'directory' if not path else broker.describe_path(root.folder_id, path)
                except AccessDenied:
                    # A sentence-ending full stop is not part of a Windows name.
                    if not path.endswith('.'):
                        raise
                    path = path[:-1]
                    actual = broker.describe_path(root.folder_id, path)
                if actual != kind:
                    raise AccessDenied(f'{token} is not a {"folder" if kind == "directory" else "file"}.')
                item = Mention(root.alias, root.folder_id, path, kind)
            else:
                candidates = [item for item in self.items if item.kind == kind and
                              (item.path.rsplit('/', 1)[-1] if item.path else item.alias).casefold() == name.casefold().rstrip('.')]
                if len(candidates) != 1 or self.incomplete:
                    raise AccessDenied(f'Choose {token} from autocomplete or use its full folder/file reference.')
                item = candidates[0]
                if item.path and broker.describe_path(item.folder_id, item.path) != kind:
                    raise AccessDenied('The referenced file or folder changed. Choose it again.')
            self.check(broker)
            results.append({'token': token, 'folder_id': item.folder_id, 'path': item.path, 'kind': kind})
        return results
