"""Product continuation preferences are separate from reproducible test limits."""
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkPolicy:
    mode: str = 'interactive'
    model_calls: int | None = None
    tool_calls: int | None = None
    execution_attempts: int | None = None

    def __post_init__(self):
        if self.mode not in {'interactive', 'benchmark'}:
            raise ValueError('Unknown work mode')
        for value in (self.model_calls, self.tool_calls, self.execution_attempts):
            if value is not None and (type(value) is not int or value < 1):
                raise ValueError('Optional work limits must be positive integers')

    @classmethod
    def benchmark(cls):
        return cls('benchmark', 16, 48, 8)
