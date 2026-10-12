"""Verified local toolchain bundles and structured command plans, without execution.

Candidate manifests confer no runtime approval. A native execution receipt must
bind bundle bytes, command policy and process-tree controls before activation.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
from .asset_integrity import ordinary, verify_tree
from .folders import AccessDenied
from .model import json_bytes, strict_json
from .windows_folders import parts


@dataclass(frozen=True)
class CommandPlan:
    bundle_sha256: str
    executable: str
    arguments: tuple[str, ...]
    cwd: str
    network: str = 'deny'


class ToolchainBundle:
    def __init__(self, root, expected_sha256):
        self.root=Path(root)
        ordinary(self.root,directory=True)
        from .asset_integrity import digest_file
        manifest = self.root/'silo-toolchain.json'
        if ordinary(manifest).st_size > 1024*1024 or digest_file(manifest) != expected_sha256:
            raise AccessDenied('Toolchain manifest differs from independent reviewed digest')
        data=manifest.read_bytes()
        if len(data)>1024*1024 or hashlib.sha256(data).hexdigest()!=expected_sha256:
            raise AccessDenied('Toolchain manifest differs from independent reviewed digest')
        value=strict_json(data)
        if (not isinstance(value,dict) or set(value)!={'format','id','platform','license_review','files','commands'}
                or value['format']!=1 or value['platform'] not in {'windows-x64','linux-x64','macos-arm64'}
                or value['license_review'] not in {'pending','reviewed'}
                or not isinstance(value['files'],list) or not value['files']
                or not isinstance(value['commands'],dict) or not value['commands']):
            raise AccessDenied('Invalid toolchain manifest')
        self.value,self.digest=value,expected_sha256
        self.verify()
        pins={pin['path'] for pin in value['files']}
        for name,command in value['commands'].items():
            if (not isinstance(name,str) or not name.isidentifier() or not isinstance(command,dict)
                    or set(command)!={'executable','prefix','suffixes'} or command['executable'] not in pins
                    or not isinstance(command['prefix'],list) or not all(isinstance(a,str) for a in command['prefix'])
                    or not isinstance(command['suffixes'],list) or not all(isinstance(a,str) and a.startswith('.') for a in command['suffixes'])):
                raise AccessDenied('Invalid fixed toolchain command')

    def verify(self):
        # Manifest is outside the enumerated immutable toolchain subtree.
        from .asset_integrity import digest_file
        if digest_file(self.root/'silo-toolchain.json') != self.digest:
            raise AccessDenied('Toolchain manifest changed after review')
        verify_tree(self.root/'payload',self.value['files'])

    def plan(self, command_id, entrypoint, *, cwd='.'):
        self.verify()
        command=self.value['commands'].get(command_id)
        if command is None: raise AccessDenied('Command is not in the reviewed bundle')
        if len(parts(entrypoint))>8 or Path(entrypoint).suffix not in command['suffixes']:
            raise AccessDenied('Select a workspace entrypoint matching the command profile')
        if cwd!='.': parts(cwd)
        return CommandPlan(self.digest,command['executable'],tuple(command['prefix']+[entrypoint]),cwd)

    def activate(self, acceptance):
        # Native backend activation is deliberately unavailable from a data-only
        # manifest or caller-authored passed JSON. Windows integration follows
        # independent process-tree, filesystem and network qualification.
        raise AccessDenied('Toolchain execution needs separately enrolled native acceptance; no portable or caller-approved fallback')


def candidate_manifest(root, *, identifier, platform, commands):
    """Inventory already acquired inert/public toolchain files; downloads are separate."""
    from .release_readiness import inventory
    return {'format':1,'id':identifier,'platform':platform,'license_review':'pending',
            'files':inventory(Path(root)/'payload'),'commands':commands}


def import_bundle(source, destination, expected_sha256):
    """Copy and rehash an independently reviewed offline bundle. Never execute it."""
    import shutil
    source=ToolchainBundle(source,expected_sha256)
    destination=Path(destination).absolute()
    ordinary(destination.parent,directory=True)
    destination.mkdir(mode=0o700)  # Exclusive: never overwrite an earlier bundle.
    try:
        (destination/'payload').mkdir(mode=0o700)
        for pin in source.value['files']:
            original=source.root/'payload'/pin['path']
            ordinary(original)
            target=destination/'payload'/pin['path']
            target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            with original.open('rb') as reader, target.open('xb') as writer:
                shutil.copyfileobj(reader,writer,1024*1024)
        with (destination/'silo-toolchain.json').open('xb') as writer:
            writer.write((source.root/'silo-toolchain.json').read_bytes())
        imported=ToolchainBundle(destination,expected_sha256)
        source.verify()
        return imported
    except BaseException:
        # Only the exclusively created destination belongs to this operation.
        shutil.rmtree(destination)
        raise
