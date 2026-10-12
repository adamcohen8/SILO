"""Replaceable chat-model contract and a loopback-only development transport.

This client is not an OS network boundary. The separately started inference
server and its dependencies must also be isolated before operational use.
"""

from dataclasses import dataclass, field, replace
import http.client
import json
import math
import re
import socket
import threading
import time
from typing import Protocol
from urllib.parse import urlsplit


class AgentError(ValueError):
    """A bounded, user-safe failure without document or server diagnostics."""


def json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("utf-8")


def strict_json(data: str | bytes) -> object:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("Non-finite JSON number")

    return json.loads(data, object_pairs_hook=pairs, parse_constant=constant)


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass(frozen=True)
class ModelReply:
    text: str = ""
    calls: tuple[ToolCall, ...] = ()
    reasoning: str = field(default="", repr=False)  # Transient tool-turn state.
    truncated: bool = False


class ChatModel(Protocol):
    def complete(self, messages: list[dict], tools: list[dict]) -> ModelReply: ...


class _NumericConnection(http.client.HTTPConnection):
    def connect(self):
        # No hostname resolver, environment proxy, or tunnel support.
        family = socket.AF_INET6 if self.host == "::1" else socket.AF_INET
        self.sock = socket.socket(family, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        try:
            self.sock.connect((self.host, self.port))
        except BaseException:
            self.sock.close()
            self.sock = None
            raise


class LocalChatModel:
    """OpenAI-compatible chat endpoint on literal 127.0.0.1 or ::1 only.

    Never downloads models, reads credentials, follows redirects, or retries.
    The administrator supplies the already-running server's model alias.
    """

    def __init__(self, endpoint: str, model: str, *, timeout: float = 120,
                 max_response_bytes: int = 256 * 1024, max_request_bytes: int = 512 * 1024,
                 api_token: str | None = None, max_tokens: int | None = None,
                 temperature: float = 0, top_p: float = 1, adapter: str | None = None,
                 on_text=None, idle_timeout=None):
        from .model_adapters import model_adapter
        self.adapter = model_adapter(adapter) if adapter is not None else None
        try:
            url = urlsplit(endpoint)
            port = url.port
        except (ValueError, TypeError) as e:
            raise AgentError("Invalid local model endpoint") from e
        if (url.scheme != "http" or url.hostname not in {"127.0.0.1", "::1"}
                or port is None or not 1 <= port <= 65535 or url.username is not None
                or url.password is not None or url.path not in {"", "/", "/v1", "/v1/"}
                or url.query or url.fragment
                or url.netloc not in {f"127.0.0.1:{port}", f"[::1]:{port}"}):
            raise AgentError("Use http://127.0.0.1:PORT or http://[::1]:PORT, optionally /v1")
        if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,200}", model):
            raise AgentError("A bounded local model alias is required")
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 300:
            raise AgentError("Model timeout must be between zero and 300 seconds")
        for limit in (max_response_bytes, max_request_bytes):
            if type(limit) is not int or not 1024 <= limit <= 2 * 1024 * 1024:
                raise AgentError("Invalid model transport size limit")
        if api_token is not None and (not isinstance(api_token, str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{16,256}", api_token)):
            raise AgentError("Invalid explicit local session token")
        if max_tokens is not None and (type(max_tokens) is not int or max_tokens < 1):
            raise AgentError("Invalid generation token limit")
        for value, upper in ((temperature, 2), (top_p, 1)):
            if type(value) not in {int, float} or not math.isfinite(value) or not 0 <= value <= upper:
                raise AgentError("Invalid local sampling settings")
        if top_p == 0:
            raise AgentError("Invalid local sampling settings")
        self.host, self.port, self.model = url.hostname, port, model
        if idle_timeout is not None and (type(idle_timeout) not in {int, float} or not math.isfinite(idle_timeout) or idle_timeout <= 0):
            raise AgentError("Invalid model idle timeout")
        self.idle_timeout = idle_timeout
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self.max_request_bytes = max_request_bytes
        self._api_token = api_token
        if on_text is not None and not callable(on_text):
            raise AgentError('Invalid model display sink')
        self.on_text = on_text
        self.max_tokens, self.temperature, self.top_p = ((max_tokens if max_tokens is not None else self.adapter.generation_tokens,
            self.adapter.temperature, self.adapter.top_p) if self.adapter else (max_tokens, temperature, top_p))

    def complete(self, messages: list[dict], tools: list[dict]) -> ModelReply:
        payload = json_bytes({"model": self.model, "messages": messages, "tools": tools,
                              "tool_choice": "auto", "parallel_tool_calls": False,
                              "stream": self.on_text is not None, "cache_prompt": False, "temperature": self.temperature,
                              "top_p": self.top_p, **({"max_tokens": self.max_tokens} if self.max_tokens is not None else {}),
                              **(self.adapter.request_parameters() if self.adapter else {})})
        if self.on_text is None:
            data = self._post('/v1/chat/completions', payload)
        else:
            from .model_stream import ChatStream
            stream = ChatStream(self.on_text, limit=self.max_response_bytes)
            self._post('/v1/chat/completions', payload, on_block=stream.feed)
            data = stream.result()
        reply = self._parse(data)
        if not (self.adapter and self.adapter.retain_tool_reasoning and reply.calls):
            reply = replace(reply, reasoning='')
        return reply

    def _post(self, path: str, payload: bytes, *, on_block=None) -> bytes:
        """One bounded request on the configured local transport, without retry."""
        if len(payload) > self.max_request_bytes:
            raise AgentError("Model request exceeds the configured limit")
        connection = self._connection()
        deadline = time.monotonic() + self.timeout
        transport_socket = None
        # SSE framing costs more bytes than the assembled response; both remain bounded.
        wire_limit = min(2 * 1024 * 1024, self.max_response_bytes * 4) if on_block else self.max_response_bytes

        def interrupt_timeout():
            active_socket = transport_socket or connection.sock
            if active_socket is not None:
                try:
                    active_socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

        timer = threading.Timer(self.timeout, interrupt_timeout)
        timer.daemon = True
        if self.idle_timeout is None: timer.start()
        try:
            headers = {"Content-Type": "application/json", "Connection": "close"}
            if self._api_token is not None:
                headers["Authorization"] = "Bearer " + self._api_token
            connection.request("POST", path, body=payload, headers=headers)
            transport_socket = connection.sock
            transport_socket.settimeout(self.idle_timeout or max(0.001, deadline - time.monotonic()))
            response = connection.getresponse()
            if response.status != 200:
                raise AgentError("Local model returned an unsuccessful response; no retry or redirect")
            if response.getheader("Content-Encoding", "identity").lower() != "identity":
                raise AgentError("Compressed model responses are unsupported")
            if on_block and response.getheader('Content-Type', '').split(';')[0].strip().lower() != 'text/event-stream':
                raise AgentError('Local model did not return an event stream; no retry')
            data = bytearray()
            while True:
                remaining = self.idle_timeout or deadline - time.monotonic()
                if remaining <= 0:
                    raise AgentError("Local model response timed out")
                transport_socket.settimeout(remaining)
                block = response.read1(min(8192, wire_limit + 1 - len(data)))
                data.extend(block)
                if len(data) > wire_limit:
                    raise AgentError("Local model response exceeds the configured limit")
                if on_block and block:
                    on_block(block)
                if not block or response.isclosed():
                    break
            if response.length not in {None, 0}:
                raise AgentError("Local model response ended before its declared length")
            return bytes(data)
        except (OSError, http.client.HTTPException) as e:
            raise AgentError("Local model connection failed or timed out") from e
        finally:
            timer.cancel()
            connection.close()

    def _connection(self):
        return _NumericConnection(self.host, self.port, timeout=self.timeout)

    @staticmethod
    def _parse(data: bytes) -> ModelReply:
        try:
            result = strict_json(data)
            choices = result["choices"]
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError()
            choice = choices[0]
            message = choice["message"]
            if message.get("role") != "assistant":
                raise ValueError()
            text = message.get("content")
            if text is None:
                text = ""
            if not isinstance(text, str):
                raise ValueError()
            reasoning = message.get('reasoning_content', '')
            if reasoning is None:
                reasoning = ''
            if not isinstance(reasoning, str) or len(reasoning.encode('utf-8')) > 64 * 1024:
                raise ValueError()
            raw_calls = message.get("tool_calls", [])
            if not isinstance(raw_calls, list) or len(raw_calls) > 4:
                raise ValueError()
            calls = []
            for item in raw_calls:
                if item["type"] != "function":
                    raise ValueError()
                function = item["function"]
                arguments = strict_json(function["arguments"])
                calls.append(ToolCall(item["id"], function["name"], arguments))
            finish = choice.get("finish_reason")
            truncated = finish == "length"
            if truncated:
                if calls or not text.strip(): raise ValueError()
            elif finish != ("tool_calls" if calls else "stop"):
                raise ValueError()
            return ModelReply(text, tuple(calls), reasoning, truncated)
        except (ValueError, TypeError, KeyError, IndexError, RecursionError) as e:
            raise AgentError("Local model returned malformed or incomplete chat/tool data") from e
