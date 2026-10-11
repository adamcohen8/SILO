"""Reviewed model behavior, independent of folder and execution authority.

The pinned llama.cpp server renders embedded templates and parses native tool
syntax. The host selects a fixed adapter; neither model output nor a profile
can supply arbitrary server flags, templates, endpoints, or stop tokens.
"""
from dataclasses import dataclass
from pathlib import Path

from .model import AgentError


@dataclass(frozen=True)
class ModelAdapter:
    id: str
    temperature: float
    top_p: float
    top_k: int
    min_p: float
    reasoning_budget: int
    reasoning_effort: str | None = None
    reasoning_strength: str | None = None
    retain_tool_reasoning: bool = False
    context_tokens: int = 8192
    generation_tokens: int = 2048
    enable_thinking: bool | None = None
    template_reasoning_budget: bool = False

    def template_parameters(self):
        parameters = {}
        if self.reasoning_effort:
            parameters['reasoning_effort'] = self.reasoning_effort
        template = {}
        if self.reasoning_strength:
            template['reasoning_strength'] = self.reasoning_strength
        if self.enable_thinking is not None:
            template['enable_thinking'] = self.enable_thinking
        if self.template_reasoning_budget:
            template['reasoning_budget'] = self.reasoning_budget
        if template:
            parameters['chat_template_kwargs'] = template
        return parameters

    def request_parameters(self):
        return dict(self.template_parameters(), top_k=self.top_k, min_p=self.min_p,
                    reasoning_format='deepseek')

    def client_options(self):
        return {'adapter': self.id, 'max_tokens': self.generation_tokens,
                'temperature': self.temperature, 'top_p': self.top_p}

    def server_parameters(self):
        from .model import json_bytes
        parameters = ['--ctx-size', str(self.context_tokens), '--predict', str(self.generation_tokens),
            '--temp', str(self.temperature), '--top-p', str(self.top_p), '--top-k', str(self.top_k),
            '--min-p', str(self.min_p), '--jinja', '--reasoning', 'on',
            '--reasoning-format', 'deepseek', '--reasoning-budget', str(self.reasoning_budget),
            '--reasoning-preserve' if self.retain_tool_reasoning else '--no-reasoning-preserve']
        if self.reasoning_effort:
            parameters += ['--reasoning-effort', self.reasoning_effort]
        template = self.template_parameters().get('chat_template_kwargs')
        if template:
            parameters += ['--chat-template-kwargs', json_bytes(template).decode()]
        return parameters


ADAPTERS = {
    'nemotron3': ModelAdapter('nemotron3', .6, .95, 40, .05, 512),
    'nemotron_cascade2': ModelAdapter('nemotron_cascade2', 1., .95, 0, 0., 1024,
                                    enable_thinking=True, template_reasoning_budget=True),
    'nemotron35': ModelAdapter('nemotron35', 1., .95, 0, 0., 1024,
                              enable_thinking=True),
    'gemma4': ModelAdapter('gemma4', 1., .95, 64, 0., 1024),
    'muse_glimmer': ModelAdapter('muse_glimmer', 1., .95, 64, 0., 1024, reasoning_strength='high'),
    'gpt_oss': ModelAdapter('gpt_oss', 1., 1., 0, .01, 1024,
                            reasoning_effort='medium', retain_tool_reasoning=True),
}


@dataclass(frozen=True)
class ExecutionLimits:
    startup_seconds: int
    request_seconds: int
    document_seconds: int
    code_seconds: int
    memory_mib: int


EXECUTION_LIMITS = {
    'cuda': ExecutionLimits(120, 60, 180, 300, 32768),
    'cpu': ExecutionLimits(300, 300, 900, 1200, 8192),
}


def execution_limits(backend):
    if not isinstance(backend, str) or backend not in EXECUTION_LIMITS:
        raise AgentError('Unknown inference execution limits')
    return EXECUTION_LIMITS[backend]


def model_adapter(identifier):
    if not isinstance(identifier, str) or identifier not in ADAPTERS:
        raise AgentError('Unknown reviewed model adapter')
    return ADAPTERS[identifier]


def server_command(runtime, model, endpoint, key, adapter='nemotron3', *, execution_backend='cuda', cpu_threads=None):
    """Explicit CPU or full CUDA placement on the same contained private socket."""
    if execution_backend == 'cuda' and cpu_threads is None:
        placement = ['--device', 'CUDA0', '--n-gpu-layers', '999', '--flash-attn', 'on']
    elif execution_backend == 'cpu' and type(cpu_threads) is int and cpu_threads == 4:
        placement = ['--device', 'none', '--n-gpu-layers', '0', '--flash-attn', 'off',
                     '--threads', '4', '--threads-batch', '4', '--no-kv-offload']
    else:
        raise AgentError('Unknown or unreviewed inference execution configuration')
    return [str(Path(runtime)/'llama-server.exe'), '--model', str(model),
        '--alias', 'contained-synthetic', '--host', str(endpoint),
        *model_adapter(adapter).server_parameters(),
        '--parallel', '1', *placement,
        '--fit', 'off', '--offline', '--no-ui', '--no-agent',
        '--no-ui-mcp-proxy', '--api-key-file', str(key), '--no-context-shift',
        '--log-colors', 'off', '--log-verbosity', '4']
