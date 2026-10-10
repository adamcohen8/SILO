"""Bounded, host-loaded startup preferences for the local assistant."""
from pathlib import Path

MAX_INSTRUCTIONS_BYTES = 8 * 1024


def load_instructions(root):
    """Read one startup snapshot; document grants never supply this configuration."""
    try:
        with (Path(root)/'AGENTS.md').open('rb') as stream:
            data = stream.read(MAX_INSTRUCTIONS_BYTES + 1)
    except OSError:
        raise RuntimeError('Cannot read AGENTS.md in the application folder. Restore the file and restart the model.') from None
    if len(data) > MAX_INSTRUCTIONS_BYTES:
        raise RuntimeError('AGENTS.md exceeds 8 KiB. Shorten the file and restart the model.')
    try:
        instructions = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise RuntimeError('AGENTS.md must be saved as UTF-8. Save it and restart the model.') from None
    if '\x00' in instructions:
        raise RuntimeError('AGENTS.md must be a plain UTF-8 text file. Save it and restart the model.')
    return instructions
