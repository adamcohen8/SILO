"""Explicit offline staging of the reviewed CPU runtime for development checkouts."""
from pathlib import Path
import tempfile

from .asset_integrity import cpu_runtime_pins, CPU_RUNTIME_DIRECTORY, ordinary, verify_tree
from .evaluation_install import copy_pinned, installed_config, unpack


def prepare_cpu_runtime(root, archive):
    root = Path(root)
    ordinary(root, directory=True)
    if installed_config(root) is not None:
        raise RuntimeError('Installed releases are immutable; prepare a new installer transaction with the CPU runtime.')
    pins = cpu_runtime_pins(root)
    destination = root/CPU_RUNTIME_DIRECTORY
    if destination.exists():
        verify_tree(destination, pins['extracted_runtime'])
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    ordinary(destination.parent, directory=True)
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix='.cpu-runtime-') as temporary:
        temporary = Path(temporary)
        local = temporary/pins['assets'][0]['name']
        copy_pinned(Path(archive), local, pins['assets'][0])
        staged = temporary/'runtime'
        staged.mkdir()
        unpack(local, staged)
        verify_tree(staged, pins['extracted_runtime'])
        # RenameDirectory on the Windows target never replaces an existing tree.
        # On development hosts, an existing verified/nonempty tree also blocks rename.
        if destination.exists():
            raise RuntimeError('CPU runtime destination appeared during preparation; existing files were preserved.')
        staged.rename(destination)
    verify_tree(destination, pins['extracted_runtime'])
    return destination
