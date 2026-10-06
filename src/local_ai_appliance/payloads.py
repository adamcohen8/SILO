"""Handle-anchored payload reads for candidate staging; no payload execution."""

from contextlib import contextmanager
import hashlib
import hmac
import os

from .bundle import (BundleError, MANIFEST_NAME, MAX_MANIFEST_BYTES, MAX_PAYLOAD_BYTES,
                     _root, _file, _inventory, _HASH, parse_manifest)
from .windows_folders import selected_path, parts
from .windows_native import NativeFiles


class Payloads:
    def __init__(self, path, expected_hash, *, windows_validation=False):
        if not isinstance(expected_hash, str) or not _HASH.fullmatch(expected_hash):
            raise BundleError("An independently supplied manifest SHA-256 is required")
        self.native, self.handles = None, []
        try:
            if os.name == 'nt':
                if not windows_validation:
                    raise BundleError('Native Windows payload handling requires explicit synthetic validation mode')
                self.native = NativeFiles()
                drive, components = selected_path(path)
                self.handles.append(self.native.open_drive(drive))
                self.device = self.check(self.handles[-1], directory=True).volume
                if self.native.filesystem(self.handles[-1]).upper() != 'NTFS':
                    raise BundleError('Local NTFS storage is required')
                for name in components:
                    self.handles.append(self.native.open_child(self.handles[-1], name, directory=True))
                    self.check(self.handles[-1], directory=True)
                self.root = self.handles[-1]
            else:
                self.root = _root(path)
                self.handles.append(self.root)
                self.device = os.fstat(self.root).st_dev
            data = self.bytes(MANIFEST_NAME, MAX_MANIFEST_BYTES)
            if not hmac.compare_digest(hashlib.sha256(data).hexdigest(), expected_hash):
                raise BundleError('Manifest does not match the independently supplied hash')
            self.manifest = parse_manifest(data)
            self.manifest_data, self.manifest_hash = data, expected_hash
            self.inventory()
        except BaseException:
            self.close()
            raise

    def check(self, handle, *, directory=None, limit=MAX_PAYLOAD_BYTES):
        info = self.native.info(handle)
        if (not info.disk or info.reparse or info.offline or
                (hasattr(self, 'device') and info.volume != self.device) or
                (directory is not None and info.directory != directory) or
                (not info.directory and (info.links != 1 or info.size > limit))):
            raise BundleError('Payload is linked, recalled, nonlocal, or unsupported')
        return info

    @contextmanager
    def file(self, path):
        if self.native is None:
            fd = _file(self.root, path, self.device)
            with os.fdopen(fd, 'rb') as stream:
                yield stream
            return
        opened = []
        try:
            parent = self.root
            for name in parts(path)[:-1]:
                parent = self.native.open_child(parent, name, directory=True)
                opened.append(parent); self.check(parent, directory=True)
            metadata = self.native.open_child(parent, parts(path)[-1], directory=False)
            opened.append(metadata)
            expected = self.check(metadata, directory=False)
            data = self.native.open_read(metadata); opened.append(data)
            actual = self.check(data, directory=False)
            if (actual.volume, actual.index, actual.size) != (expected.volume, expected.index, expected.size):
                raise BundleError('Payload identity changed')
            yield data
            after = self.check(data, directory=False)
            if after != actual:
                raise BundleError('Payload changed while being read')
        finally:
            for handle in reversed(opened): self.native.close(handle)

    def read(self, handle, count):
        return self.native.read_chunk(handle, count) if self.native else handle.read(count)

    def bytes(self, path, limit):
        with self.file(path) as handle:
            result = bytearray()
            while len(result) <= limit:
                block = self.read(handle, min(65536, limit + 1 - len(result)))
                if not block: break
                result.extend(block)
            if len(result) > limit: raise BundleError('Payload exceeds the bounded read limit')
            return bytes(result)

    def inventory(self):
        expected = {MANIFEST_NAME} | {a.path for a in self.manifest.artifacts}
        if not self.native:
            _inventory(self.root, self.device, expected); return
        directories = {'/'.join(path.split('/')[:end]) for path in expected
                       for end in range(1, len(path.split('/')))}
        seen, count = set(), 0
        def visit(parent, prefix=''):
            nonlocal count
            for name in self.native.names(parent):
                if name in {'.', '..'}: continue
                count += 1
                if count > 8192: raise BundleError('Payload inventory exceeds the limit')
                parts(name); path = prefix + name
                handle = self.native.open_child(parent, name)
                try:
                    info = self.check(handle)
                    if info.directory and path in directories:
                        directory = self.native.open_child(parent, name, directory=True)
                        try: visit(directory, path + '/')
                        finally: self.native.close(directory)
                    elif not info.directory and path in expected: seen.add(path)
                    else: raise BundleError('Undeclared payload content is forbidden')
                finally: self.native.close(handle)
        visit(self.root)
        if seen != expected: raise BundleError('Payload is incomplete')

    def copy(self, artifact, write):
        with self.file(artifact.path) as handle:
            size = self.native.info(handle).size if self.native else os.fstat(handle.fileno()).st_size
            if size != artifact.size: raise BundleError('Payload size differs from the manifest')
            digest, total = hashlib.sha256(), 0
            while block := self.read(handle, min(1024 * 1024, artifact.size + 1 - total)):
                total += len(block)
                if total > artifact.size: raise BundleError('Payload grew during staging')
                digest.update(block); write(block)
            if total != artifact.size or not hmac.compare_digest(digest.hexdigest(), artifact.sha256):
                raise BundleError('Payload digest differs from the manifest')

    def close(self):
        for handle in reversed(self.handles):
            if self.native: self.native.close(handle)
            else: os.close(handle)
        self.handles = []

    def __enter__(self): return self
    def __exit__(self, *_): self.close()
