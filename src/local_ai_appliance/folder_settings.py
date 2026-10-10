"""Host-owned remembered folder selections; no chats, documents or handles."""
import os
from pathlib import Path
import tempfile

from .folders import AccessDenied
from .model import json_bytes, strict_json
from .windows_folders import selected_path


class FolderSettings:
    MAX_BYTES = 512*1024
    MAX_FOLDERS = 64

    def __init__(self, path):
        self.path = Path(path)

    @classmethod
    def validate(cls, value):
        if (not isinstance(value, dict) or set(value) != {'version', 'folders'}
                or type(value['version']) is not int or value['version'] != 1
                or not isinstance(value['folders'], list) or len(value['folders']) > cls.MAX_FOLDERS):
            raise ValueError('Invalid folder settings')
        seen = set()
        for entry in value['folders']:
            if (not isinstance(entry, dict) or set(entry) != {'path', 'access', 'volume', 'index'}
                    or not isinstance(entry['path'], str) or entry['access'] not in ('read-only', 'editable')
                    or type(entry['volume']) is not int or not 0 <= entry['volume'] < 2**32
                    or type(entry['index']) is not int or not 0 < entry['index'] < 2**64):
                raise ValueError('Invalid saved folder')
            drive, components = selected_path(entry['path'])
            key = (drive+'\\'.join(components)).casefold()
            if key in seen:
                raise ValueError('Duplicate saved folder')
            seen.add(key)
        return value['folders']

    def load(self):
        try:
            with self.path.open('rb') as source:
                payload = source.read(self.MAX_BYTES+1)
        except FileNotFoundError:
            return []
        try:
            if len(payload) > self.MAX_BYTES:
                raise ValueError()
            return self.validate(strict_json(payload))
        except (ValueError, TypeError, KeyError, RecursionError, AccessDenied) as error:
            raise RuntimeError('Saved folder settings are invalid. Add the folders again.') from error

    def save(self, entries):
        value = {'version': 1, 'folders': entries}
        self.validate(value)
        payload = json_bytes(value)
        if len(payload) > self.MAX_BYTES:
            raise ValueError('Folder settings exceed the size limit')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.path.parent, prefix='.folders-', suffix='.tmp', delete=False) as output:
                temporary = Path(output.name)
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
