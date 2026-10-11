"""Phase 1 execution specification. No shell, interpreter, or subprocess launch."""
from dataclasses import dataclass

from .folders import AccessDenied


@dataclass(frozen=True)
class ExecutionPolicy:
    version: int = 1
    network: str = 'deny'
    timeout_seconds: int = 60
    memory_mib: int = 512
    max_output_bytes: int = 64 * 1024
    max_processes: int = 1
    max_workspace_bytes: int = 16 * 1024 * 1024

    def __post_init__(self):
        if type(self.version) is not int or self.version != 1 or self.network != 'deny':
            raise ValueError('Only the version 1 offline execution policy is defined')
        for value, lower, upper in ((self.timeout_seconds, 1, 180), (self.memory_mib, 128, 2048),
                                    (self.max_output_bytes, 1024, 256 * 1024), (self.max_processes, 1, 1),
                                    (self.max_workspace_bytes, 1024, 64 * 1024 * 1024)):
            if type(value) is not int or not lower <= value <= upper:
                raise ValueError('Execution resource limit is outside the defined policy')


class DisabledExecutionService:
    """A policy object is not proof of containment and cannot enable execution."""
    available = False

    def execute(self, *args, **kwargs):
        raise AccessDenied('Code execution is unavailable until the native runner boundary is implemented and qualified')
