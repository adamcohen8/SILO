"""Separate resource contract for offline builds; never changes Python policy v1."""
from dataclasses import dataclass


@dataclass(frozen=True)
class BuildPolicy:
    version: int = 1
    network: str = 'deny'
    timeout_seconds: int = 180
    memory_mib: int = 2048
    max_output_bytes: int = 256 * 1024
    max_processes: int = 8
    max_workspace_bytes: int = 64 * 1024 * 1024

    def __post_init__(self):
        if type(self.version) is not int or self.version != 1 or self.network != 'deny':
            raise ValueError('Only offline build policy version 1 is supported')
        for value, low, high in ((self.timeout_seconds,1,300),(self.memory_mib,128,32768),
                (self.max_output_bytes,1024,4*1024*1024),(self.max_processes,1,32),
                (self.max_workspace_bytes,1024,1024*1024*1024)):
            if type(value) is not int or not low <= value <= high:
                raise ValueError('Build resource limit is outside the supported range')
