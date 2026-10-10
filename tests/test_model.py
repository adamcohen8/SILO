from contextlib import contextmanager
import copy
import http.server
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from local_ai_appliance.model import AgentError, LocalChatModel, json_bytes, strict_json


def completion(text="Local reply", calls=None, reason=None):
    message = {"role": "assistant", "content": text}
    if calls is not None:
        message["tool_calls"] = calls
    return {"choices": [{"message": message, "finish_reason": reason or ("tool_calls" if calls else "stop")} ]}


def tool(name, arguments, id="call1"):
    return {"id": id, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}


@contextmanager
def fixture(handler):
    requests = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            requests.append((self.path, dict(self.headers), json.loads(body)))
            status, payload, headers = handler(requests[-1][2])
            self.send_response(status)
            self.send_header("Content-Length", headers.get("Content-Length", str(len(payload))))
            for name, value in headers.items():
                if name != "Content-Length":
                    self.send_header(name, value)
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class ModelTests(unittest.TestCase):
    def test_windows_context_measurement_uses_tool_template_and_rejects_invalid_tokens(self):
        from local_ai_appliance.windows_model import WindowsSocketChatModel
        model = object.__new__(WindowsSocketChatModel)
        messages = [{'role': 'user', 'content': 'Synthetic question.'}]
        tools = [{'type': 'function', 'function': {'name': 'list_files'}}]
        with patch.object(model, '_post', side_effect=[json_bytes({'prompt': 'Rendered tools and question'}),
                                                       json_bytes({'tokens': [1, 2, 3]})]) as post:
            self.assertEqual(model.prompt_tokens(messages, tools), 3)
            self.assertEqual(json.loads(post.call_args_list[0].args[1])['tools'], tools)
            self.assertEqual(post.call_args_list[1].args[0], '/tokenize')
        for tokens in ([True], [-1], [1.5], 'invalid'):
            with patch.object(model, '_post', side_effect=[json_bytes({'prompt': 'Synthetic'}),
                                                          json_bytes({'tokens': tokens})]):
                with self.assertRaisesRegex(AgentError, 'context measurement failed'):
                    model.prompt_tokens(messages, tools)

    def test_endpoint_rejects_remote_dns_proxy_credentials_and_ambiguous_urls(self):
        for endpoint in ("https://api.openai.com/v1", "http://localhost:8080", "http://192.168.1.2:8080",
                         "http://127.0.0.2:8080", "http://127.0.0.1", "http://127.0.0.1:0",
                         "http://user:pass@127.0.0.1:8080", "http://127.0.0.1:8080/other",
                         "http://127.0.0.1:8080/v1?x=y", "http://127.0.0.1:8080/#fragment",
                         "http://2130706433:8080", "http://127.0.0.1:08080", "http://[::ffff:127.0.0.1]:8080"):
            with self.subTest(endpoint=endpoint), patch.object(socket.socket, "connect") as connect:
                with self.assertRaises(AgentError):
                    LocalChatModel(endpoint, "local-model")
                connect.assert_not_called()

    def test_literal_ipv6_loopback_and_v1_forms_accepted(self):
        for endpoint in ("http://[::1]:8080", "http://127.0.0.1:8080/", "http://127.0.0.1:8080/v1/"):
            LocalChatModel(endpoint, "local-model")

    def test_invalid_alias_timeout_and_limits_rejected(self):
        for kwargs in ({"model": "bad\nmodel"}, {"model": ""}, {"timeout": float("nan")},
                       {"timeout": 301}, {"timeout": 0}, {"max_response_bytes": True}):
            with self.assertRaises(AgentError):
                LocalChatModel("http://127.0.0.1:8080", **({"model": "local"} | kwargs))

    def test_protocol_uses_loopback_without_dns_proxy_credentials_or_retry(self):
        with fixture(lambda _: (200, json_bytes(completion()), {})) as (endpoint, requests), \
                patch.dict(os.environ, {"HTTP_PROXY": "http://198.51.100.1:9999",
                                       "ALL_PROXY": "http://198.51.100.1:9999", "OPENAI_API_KEY": "unused"}), \
                patch.object(socket, "getaddrinfo", side_effect=AssertionError("DNS attempted")):
            result = LocalChatModel(endpoint, "test-local").complete([{"role": "user", "content": "hello"}], [])
            self.assertEqual(result.text, "Local reply")
            self.assertEqual(len(requests), 1)
            path, headers, body = requests[0]
            self.assertEqual(path, "/v1/chat/completions")
            self.assertNotIn("Authorization", headers)
            self.assertEqual(body["model"], "test-local")
            self.assertFalse(body["stream"])
            self.assertFalse(body["parallel_tool_calls"])
            self.assertFalse(body["cache_prompt"])

    def test_explicit_session_token_and_profile_generation_limit(self):
        token = "synthetic_explicit_session_token_123"
        with fixture(lambda _: (200, json_bytes(completion()), {})) as (endpoint, requests):
            LocalChatModel(endpoint, "test", api_token=token, max_tokens=1024,
                           temperature=0.6, top_p=0.95).complete([], [])
            self.assertEqual(requests[0][1]["Authorization"], "Bearer " + token)
            self.assertEqual(requests[0][2]["max_tokens"], 1024)
            self.assertEqual(requests[0][2]["temperature"], 0.6)
            self.assertEqual(requests[0][2]["top_p"], 0.95)
        for kwargs in ({"api_token": "bad\r\nheader"}, {"max_tokens": True},
                       {"max_tokens": 0}, {"temperature": float("nan")}, {"top_p": 0}):
            with self.assertRaises(AgentError):
                LocalChatModel("http://127.0.0.1:8080", "test", **kwargs)

    def test_redirect_and_http_error_are_not_followed_or_retried(self):
        for status in (302, 307, 429, 500):
            with fixture(lambda _: (status, b"private server diagnostics", {
                    "Location": "https://example.com/exfil"})) as (endpoint, requests):
                with self.assertRaises(AgentError) as error:
                    LocalChatModel(endpoint, "test").complete([], [])
                self.assertNotIn("private", str(error.exception))
                self.assertEqual(len(requests), 1)

    def test_oversized_and_compressed_responses_rejected(self):
        for payload, headers in ((b"a" * 2048, {}), (b"compressed", {"Content-Encoding": "gzip"})):
            with fixture(lambda _: (200, payload, headers)) as (endpoint, _):
                with self.assertRaises(AgentError):
                    LocalChatModel(endpoint, "test", max_response_bytes=1024).complete([], [])

    def test_timeout_is_safe_and_not_retried(self):
        def delayed(_):
            time.sleep(0.15)
            return 200, json_bytes(completion()), {}
        with fixture(delayed) as (endpoint, requests):
            with self.assertRaisesRegex(AgentError, "timed out"):
                LocalChatModel(endpoint, "test", timeout=0.03).complete([], [])
            self.assertEqual(len(requests), 1)

    def test_oversized_request_denied_before_connection(self):
        with patch.object(socket.socket, "connect") as connect:
            with self.assertRaises(AgentError):
                LocalChatModel("http://127.0.0.1:8080", "test", max_request_bytes=1024).complete(
                    [{"role": "user", "content": "a" * 2048}], [])
            connect.assert_not_called()

    def test_short_http_body_rejected_even_when_json_is_complete(self):
        payload = json_bytes(completion())
        with fixture(lambda _: (200, payload, {"Content-Length": str(len(payload) + 20)})) as (endpoint, _):
            with self.assertRaisesRegex(AgentError, "declared length"):
                LocalChatModel(endpoint, "test").complete([], [])

    def test_slow_header_drip_cannot_extend_request_indefinitely(self):
        ready = threading.Event()
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(1)
        endpoint = f"http://127.0.0.1:{listener.getsockname()[1]}"
        def drip():
            try:
                connection, _ = listener.accept()
                with connection:
                    connection.recv(8192)
                    ready.set()
                    for byte in b"HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\n":
                        connection.sendall(bytes([byte]))
                        time.sleep(0.005)
            except (OSError, BrokenPipeError):
                pass
        thread = threading.Thread(target=drip, daemon=True)
        thread.start()
        try:
            started = time.monotonic()
            with self.assertRaises(AgentError):
                LocalChatModel(endpoint, "test", timeout=0.05).complete([], [])
            self.assertLess(time.monotonic() - started, 0.5)
            self.assertTrue(ready.is_set())
        finally:
            listener.close()
            thread.join(timeout=1)

    def test_malformed_incomplete_and_duplicate_json_denied(self):
        valid = completion()
        forged = copy.deepcopy(valid)
        forged["choices"][0]["message"]["role"] = "system"
        invalid_calls = completion(None, [tool("read_text", {})])
        invalid_calls["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"] = '{"x":1,"x":2}'
        for data in (b"not-json", b'{"choices": [], "choices": []}', json_bytes({"choices": []}),
                     json_bytes(forged), json_bytes(completion(reason="length")), json_bytes(invalid_calls),
                     json_bytes(completion(None, [tool("x", {})] * 5)), json_bytes(completion(["bad"]))):
            with self.subTest(data=data[:80]), self.assertRaises(AgentError):
                LocalChatModel._parse(data)

    def test_tool_call_is_parsed_without_evaluation(self):
        payload = "__import__('os').system('echo unsafe')"
        result = LocalChatModel._parse(json_bytes(completion(None, [tool("propose_text", {"text": payload})])))
        self.assertEqual(result.calls[0].arguments["text"], payload)

    def test_nonfinite_json_denied(self):
        with self.assertRaises(ValueError):
            strict_json('{"x": NaN}')

    @unittest.skipUnless(os.name == "posix", "POSIX development adapter only")
    def test_http_graph_broker_and_review_end_to_end_with_synthetic_service(self):
        try:
            import langgraph.graph
        except ImportError:
            self.skipTest("Install optional agent dependencies")
        from local_ai_appliance.agent import DocumentAgent
        from local_ai_appliance.workspace import Workspace
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            source, drafts = root / "reference", root / "drafts"
            source.mkdir()
            drafts.mkdir()
            (source / "guide.txt").write_text("Synthetic original.\n")
            workspace = Workspace()
            try:
                ro, rw = workspace.grant(source, "read-only"), workspace.grant(drafts, "editable")
                def respond(body):
                    last = body["messages"][-1]
                    if last["role"] == "user":
                        reply = completion(None, [tool("read_text", {"folder_id": ro.id, "path": "guide.txt"})])
                    else:
                        output = json.loads(last["content"])["result"]
                        if "sha256" in output:
                            reply = completion(None, [tool("propose_text", {
                                "destination_folder": rw.id, "destination_path": "revised.txt",
                                "text": "Synthetic revised.\n", "source_folder": ro.id,
                                "source_path": "guide.txt", "source_sha256": output["sha256"]}, id="call2")])
                        else:
                            reply = completion("Proposed a revision based on the original. [source:S1]")
                    return 200, json_bytes(reply), {}
                with fixture(respond) as (endpoint, requests):
                    result = DocumentAgent(workspace, LocalChatModel(endpoint, "synthetic-fixture")).run("Revise")
                    self.assertEqual(len(requests), 3)
                    self.assertEqual(result.citations[0].text, "Synthetic original.\n")
                    self.assertFalse((drafts / "revised.txt").exists())
                    workspace.approve(result.proposals[0].id)
                    self.assertEqual((drafts / "revised.txt").read_text(), "Synthetic revised.\n")
                    self.assertEqual((source / "guide.txt").read_text(), "Synthetic original.\n")
            finally:
                workspace.close()
