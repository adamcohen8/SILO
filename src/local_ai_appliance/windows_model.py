"""Explicit evaluation-only Windows local-socket chat transport.

The host supplies a session-owned endpoint and ephemeral token. No TCP, DNS,
proxy, redirect, download, or fallback connection is available on this path.
Endpoint ACL/identity and broader IPC qualification remain host obligations.
"""
import ctypes as C
import http.client
import os
from pathlib import Path
import select
import socket

from .model import AgentError, LocalChatModel, json_bytes, strict_json


class WindowsUnixConnection(http.client.HTTPConnection):
    def __init__(self, path, *, timeout=5):
        super().__init__('localhost', timeout=timeout)
        self.path = str(path)

    def connect(self):
        self.sock = socket.socket(1, socket.SOCK_STREAM)  # Native Winsock AF_UNIX.
        self.sock.settimeout(self.timeout)
        try:
            class Address(C.Structure):
                _fields_ = [('family', C.c_ushort), ('path', C.c_char * 108)]
            encoded = self.path.encode('utf-8')
            if len(encoded) >= 108 or b'\0' in encoded:
                raise AgentError('Invalid private local socket path')
            address = Address(1, encoded)
            winsock = C.WinDLL('Ws2_32')
            winsock.connect.argtypes = [C.c_size_t, C.c_void_p, C.c_int]
            winsock.connect.restype = C.c_int
            winsock.WSAGetLastError.restype = C.c_int
            if winsock.connect(self.sock.fileno(), C.byref(address), C.sizeof(address)) == -1:
                error = winsock.WSAGetLastError()
                if error != 10035:
                    raise OSError(error, 'Private local socket connection failed')
                _, writable, exceptional = select.select([], [self.sock], [self.sock], self.timeout)
                error = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                if not writable or exceptional or error:
                    raise OSError(error or 10060, 'Private local socket connection failed')
        except BaseException:
            self.sock.close()
            self.sock = None
            raise


class WindowsSocketChatModel(LocalChatModel):
    max_prompt_tokens = 8192 - 2048 - 64
    def __init__(self, path, model, *, api_token, evaluation=False, **options):
        if os.name != 'nt' or evaluation is not True:
            raise AgentError('Explicit Windows socket evaluation required')
        if not isinstance(api_token, str):
            raise AgentError('An explicit private session token is required')
        path = Path(path)
        if not path.is_absolute() or len(str(path).encode('utf-8')) >= 108 or '\0' in str(path):
            raise AgentError('Invalid private local socket path')
        super().__init__('http://127.0.0.1:1/v1', model, api_token=api_token, **options)
        self.socket_path = path

    def _connection(self):
        return WindowsUnixConnection(self.socket_path, timeout=self.timeout)

    def prompt_tokens(self, messages, tools):
        """Count the actual pinned server template, including registered tools."""
        try:
            rendered = strict_json(self._post('/apply-template', json_bytes({
                'messages': messages, 'tools': tools, 'tool_choice': 'auto',
                'parallel_tool_calls': False,
                **(self.adapter.template_parameters() if getattr(self, 'adapter', None) else {})})))
            if not isinstance(rendered, dict) or not isinstance(rendered.get('prompt'), str):
                raise ValueError()
            value = strict_json(self._post('/tokenize', json_bytes({
                'content': rendered['prompt'], 'add_special': True, 'parse_special': True})))
            tokens = value['tokens']
            if (not isinstance(tokens, list) or len(tokens) > 100_000
                    or any(type(token) is not int or token < 0 for token in tokens)):
                raise ValueError()
            return len(tokens)
        except (ValueError, TypeError, KeyError, RecursionError) as error:
            raise AgentError('Local model context measurement failed') from error
