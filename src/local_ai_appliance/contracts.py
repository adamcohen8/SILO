"""Shared host contracts. These types do not grant filesystem or process access."""
from dataclasses import dataclass
from enum import Enum
import re
from typing import Callable, Protocol, runtime_checkable

from .agent import AgentResult
from .workspace import Proposal


class WorkspaceKind(str, Enum):
    REFERENCE = 'reference'
    DRAFT = 'draft'
    CODE = 'code'


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    data_scope: str = 'synthetic'

    def __post_init__(self):
        if not isinstance(self.id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', self.id):
            raise ValueError('Invalid project ID')
        if (not isinstance(self.name, str) or not 1 <= len(self.name) <= 128
                or any(ord(c) < 32 for c in self.name)):
            raise ValueError('Invalid project name')
        if self.data_scope not in {'public', 'synthetic'}:
            raise ValueError('Phase 1 projects are public or synthetic evaluations only')


@dataclass(frozen=True)
class Progress:
    """Fixed metadata only: never contains prompts, paths, output, or source text."""
    stage: str
    model_calls: int = 0
    tool_calls: int = 0

    def __post_init__(self):
        if self.stage not in {'starting', 'model', 'tools', 'complete', 'cancelled', 'failed', 'closed'}:
            raise ValueError('Invalid progress stage')
        if any(type(n) is not int or n < 0 for n in (self.model_calls, self.tool_calls)):
            raise ValueError('Invalid progress counters')


ProgressSink = Callable[[Progress], None]


class Harness(Protocol):
    def run(self, prompt: str, *, history=(), sources=()) -> AgentResult: ...


@runtime_checkable
class SessionBackend(Protocol):
    """Trusted interface API, deliberately absent from the model tool registry."""
    project: Project

    def start(self) -> None: ...
    def ask(self, prompt: str) -> AgentResult: ...
    def grant(self, path, kind: WorkspaceKind): ...
    def revoke(self, folder_id: str) -> None: ...
    def review(self, proposal_id: str) -> Proposal: ...
    def approve(self, proposal_id: str) -> Proposal: ...
    def discard(self, proposal_id: str) -> None: ...
    def clear_chat(self) -> None: ...
    def cancel(self) -> None: ...
    def close(self) -> None: ...
