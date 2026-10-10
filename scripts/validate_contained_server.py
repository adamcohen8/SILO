"""Synthetic AppContainer GPU inference over a disposable local Unix socket.

Development compatibility evidence only: not a complete isolated agent.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import secrets
import shutil
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
from local_ai_appliance.windows_container import AppContainer
from local_ai_appliance.windows_model import WindowsUnixConnection as UnixConnection
from validate_gpu_baseline import verified_files, RUNTIME

STATE = ROOT / 'artifacts' / 'isolation-evaluation'


def main():
    report = {'deployment_ready': False, 'full_stack_isolation_accepted': False, 'errors': []}
    try:
        model, _ = verified_files()
        with ExitStack() as cleanup:
            parent = (ROOT / 'artifacts').resolve()
            directory = parent / ('i-' + secrets.token_hex(4))
            def delete_owned_ipc():
                if directory.parent.resolve() != parent or directory.is_symlink():
                    raise ValueError('IPC cleanup target is outside the artifact directory')
                if directory.exists():
                    shutil.rmtree(directory)
            cleanup.callback(delete_owned_ipc)
            endpoint = directory / 's.sock'
            if len(str(endpoint).encode('utf-8')) >= 108:
                raise ValueError('Private socket pathname exceeds the Windows limit')
            container = cleanup.enter_context(AppContainer(evaluation=True))
            container.allow_read(RUNTIME, directory=True)
            container.allow_read(model)
            container.create_private_ipc(directory)
            token = secrets.token_urlsafe(32)
            key = directory / 'token'
            key.write_text(token)
            # Never put a session token in process command-line arguments.
            command = [str(RUNTIME / 'llama-server.exe'), '--model', str(model), '--alias', 'contained-synthetic',
                '--host', str(endpoint), '--ctx-size', '8192', '--predict', '2048', '--parallel', '1',
                '--device', 'CUDA0', '--n-gpu-layers', '999', '--fit', 'off', '--flash-attn', 'on',
                '--jinja', '--reasoning', 'on', '--reasoning-budget', '512', '--no-reasoning-preserve',
                '--offline', '--no-ui', '--no-agent', '--no-ui-mcp-proxy', '--api-key-file', str(key),
                '--no-context-shift', '--log-colors', 'off', '--log-verbosity', '4']
            process = container.launch(command, cwd=RUNTIME, memory_mib=32768)
            report['token'] = process.token_evidence
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(process.communicate, timeout=180)
            try:
                started = time.monotonic()
                while time.monotonic() - started < 90:
                    if future.done():
                        code, out, err = future.result()
                        raise ValueError(f'Contained server exited during startup: {code}')
                    connection = UnixConnection(endpoint, timeout=2)
                    try:
                        connection.request('GET', '/health', headers={'Authorization': 'Bearer '+token})
                        response = connection.getresponse()
                        if response.status == 200:
                            break
                    except OSError:
                        pass
                    finally:
                        connection.close()
                    time.sleep(0.5)
                else:
                    raise TimeoutError('Contained server did not become ready')
                report['server_ready_s'] = round(time.monotonic()-started, 3)
                payload = {'model': 'contained-synthetic', 'messages': [
                    {'role': 'system', 'content': 'Answer only from the supplied synthetic excerpt. Include its exact source token.'},
                    {'role': 'user', 'content': 'line 1: The approved capacity is 37 crates. [source:S1:line:1]\nWhat is the capacity?'}],
                    'max_tokens': 1024, 'temperature': 0.6, 'top_p': 0.95, 'stream': False, 'cache_prompt': False}
                connection = UnixConnection(endpoint, timeout=60)
                try:
                    connection.request('POST', '/v1/chat/completions', body=json.dumps(payload).encode(),
                        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer '+token})
                    response = connection.getresponse()
                    raw = response.read(256*1024+1)
                    if response.status != 200 or len(raw) > 256*1024:
                        raise ValueError('Contained completion response failed bounds/status')
                    answer = json.loads(raw)['choices'][0]['message']['content']
                    report['answer'] = answer
                    report['synthetic_answer_passed'] = '37' in answer and '[source:S1:line:1]' in answer
                finally:
                    connection.close()
            finally:
                container.kernel.TerminateJobObject(process.job, 126)
                code, out, err = future.result(timeout=25)
                executor.shutdown(wait=True)
                logs = out + err
                (STATE / 'contained-server.log').write_bytes(logs)
                report['gpu_layers_53_of_53'] = b'offloaded 53/53 layers to GPU' in logs
                report['server_stopped'] = True
                report['server_exit_after_host_stop'] = code
        report['cleanup_complete'] = True
        report['contained_inference_passed'] = bool(report.get('synthetic_answer_passed') and report.get('gpu_layers_53_of_53'))
    except Exception as e:
        report['errors'].append(f'{type(e).__name__}: {e}')
        (STATE / 'contained-server-error.txt').write_text(traceback.format_exc())
        report['contained_inference_passed'] = False
    report['source_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (STATE / 'contained-server-results.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report), flush=True)
    return 0 if report['contained_inference_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
