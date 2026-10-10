"""Synthetic zero-capability AppContainer probes; no production acceptance."""
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from local_ai_appliance.windows_container import AppContainer

STATE = ROOT / "artifacts" / "isolation-evaluation"
PYTHON = STATE / "python"
RUNTIME = ROOT / "artifacts" / "inference" / "runtime-b11433-cuda12.4"

PROBE = r'''
import json, os, socket, subprocess, sys
p = json.loads(sys.stdin.buffer.read(65536))
r = {"network": [], "files": [], "dns": []}
for test in p["network"]:
    s = socket.socket(test["family"], test["kind"])
    s.settimeout(3)
    try:
        if test["kind"] == socket.SOCK_DGRAM:
            s.sendto(b"local-ai-synthetic-marker", (test["address"], test["port"]))
        else:
            s.connect((test["address"], test["port"]))
        result = {"id": test["id"], "allowed": True}
    except OSError as e:
        result = {"id": test["id"], "allowed": False, "winerror": getattr(e, "winerror", None), "errno": e.errno}
    finally:
        s.close()
    r["network"].append(result)
for path, mode, name in [(p["sentinel"], "rb", "ungranted_read"),
                         (p["write_target"], "xb", "software_write")]:
    try:
        with open(path, mode) as f:
            if mode == "rb": f.read(32)
        result = {"id": name, "allowed": True}
    except OSError as e:
        result = {"id": name, "allowed": False, "winerror": getattr(e, "winerror", None), "errno": e.errno}
    r["files"].append(result)
try:
    subprocess.run([sys.executable, "-I", "-B", "-c", "pass"], timeout=5,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=True)
    r["child_process"] = {"allowed": True}
except (OSError, subprocess.SubprocessError) as e:
    r["child_process"] = {"allowed": False, "winerror": getattr(e, "winerror", None), "errno": getattr(e, "errno", None)}
for host in ("github.com", "pypi.org"):
    try:
        values = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        r["dns"].append({"host": host, "resolved": bool(values)})
    except OSError as e:
        r["dns"].append({"host": host, "resolved": False, "winerror": getattr(e, "winerror", None), "errno": e.errno})
try:
    import langgraph.graph
    import langsmith
    import pypdf
    import defusedxml
    r["stack_imported"] = True
except Exception as e:
    r["stack_imported"] = False
    r["import_error_type"] = type(e).__name__
sys.stdout.write(json.dumps(r))
'''


def stage_python():
    PYTHON.mkdir(parents=True, exist_ok=True)
    base = Path(sys.base_prefix)
    for name in ("python.exe", "python312.dll", "vcruntime140.dll", "vcruntime140_1.dll"):
        if (base / name).exists():
            shutil.copy2(base / name, PYTHON / name)
    for name in ("Lib", "DLLs"):
        shutil.copytree(base / name, PYTHON / name, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "site-packages"))
    site = Path(sys.prefix) / "Lib" / "site-packages"
    shutil.copytree(site, PYTHON / "Lib" / "site-packages", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "pip", "pip-*.dist-info",
                                                   "PySide6*", "pyside6*", "shiboken6*"))
    return PYTHON / "python.exe"


def host_controls():
    controls, probes = [], []
    for host in ("github.com", "pypi.org"):
        connection = http.client.HTTPSConnection(host, timeout=10)
        try:
            connection.request("HEAD", "/")
            response = connection.getresponse()
            controls.append({"host": host, "https_status": response.status, "reachable": True})
        except OSError as e:
            controls.append({"host": host, "reachable": False, "error_type": type(e).__name__})
        finally:
            connection.close()
        seen = set()
        for family, kind, _, _, address in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM):
            if family not in {socket.AF_INET, socket.AF_INET6} or family in seen:
                continue
            seen.add(family)
            control = socket.socket(family, kind)
            control.settimeout(3)
            try:
                control.connect(address)
                reachable = True
            except OSError:
                reachable = False
            finally:
                control.close()
            controls.append({"host": host, "family": family, "literal_tcp_reachable": reachable})
            if reachable:
                probes.append({"id": f"external_{host}_{family}", "family": family, "kind": kind,
                               "address": address[0], "port": 443})
    return controls, probes


def main():
    if os.name != "nt":
        raise SystemExit("Native Windows required")
    STATE.mkdir(parents=True, exist_ok=True)
    report = {"deployment_ready": False, "full_stack_isolation_accepted": False,
              "boundary": "AppContainer zero capabilities, low integrity, child policy + one-process job",
              "observations": {}, "errors": []}
    listeners = []
    try:
        executable = stage_python()
        report["host_before"], probes = host_controls()
        for family, address in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
            for kind in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
                listener = socket.socket(family, kind)
                try:
                    listener.bind((address, 0))
                    if kind == socket.SOCK_STREAM:
                        listener.listen(4)
                    else:
                        listener.settimeout(1)
                    host = socket.socket(family, kind)
                    host.settimeout(2)
                    try:
                        if kind == socket.SOCK_STREAM:
                            host.connect(listener.getsockname())
                            accepted, _ = listener.accept()
                            accepted.close()
                        else:
                            host.sendto(b"local-ai-host-control", listener.getsockname())
                            listener.recvfrom(128)
                    finally:
                        host.close()
                    probes.append({"id": f"loopback_{family}_{kind}", "family": family,
                                   "kind": kind, "address": address, "port": listener.getsockname()[1]})
                    listeners.append(listener)
                except OSError as error:
                    listener.close()
                    report["observations"][f"loopback_{family}_{kind}"] = {"not_run": type(error).__name__}
        sentinel = STATE / "ungranted-synthetic.txt"
        sentinel.write_text("Synthetic ungranted marker.\n")
        request = {"network": probes, "sentinel": str(sentinel), "write_target": str(PYTHON / "forbidden-write.txt")}
        lock = json.loads((ROOT / "profiles" / "nemotron-30b-4090-assets.json").read_text())
        for entry in lock["extracted_runtime"]:
            path = RUNTIME / entry["path"]
            if path.stat().st_size != entry["size"] or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError("Runtime asset changed")
        with AppContainer(evaluation=True, private_desktop=True) as container:
            report["loopback_policy"] = container.verify_no_loopback_exemption()
            report["private_desktop_qualified"] = False
            container.allow_read(PYTHON, directory=True)
            probe = container.launch([str(executable), "-I", "-B", "-c", PROBE], cwd=PYTHON)
            report["token"] = probe.token_evidence
            code, stdout, stderr = probe.communicate(json.dumps(request).encode(), timeout=60)
            report["probe_exit"] = code
            if code != 0:
                (STATE / "probe-error.txt").write_bytes(stderr)
                report["observations"]["python_initialization_failed"] = hex(code)
            else:
                report["observations"].update(json.loads(stdout))
            # A successful UDP send API does not establish delivery: WFP can
            # silently drop it. Inspect the controlled receivers as well.
            received = []
            for listener in listeners:
                listener.settimeout(0.3)
                test_id = f"loopback_{listener.family}_{listener.type}"
                try:
                    if listener.type == socket.SOCK_STREAM:
                        accepted, _ = listener.accept()
                        accepted.close()
                    else:
                        listener.recvfrom(128)
                    delivered = True
                except socket.timeout:
                    delivered = False
                received.append({"id": test_id, "delivered": delivered, "host_control_succeeded": True})
            report["controlled_receivers"] = received
            curl = container.launch([str(Path(os.environ["SYSTEMROOT"]) / "System32" / "curl.exe"), "-q", "--version"], cwd=PYTHON)
            curl_code, curl_out, curl_err = curl.communicate(timeout=15)
            report["system_curl_initialization"] = {"exit": curl_code, "started": b"curl " in curl_out}
            container.allow_read(RUNTIME, directory=True)
            gpu = container.launch([str(RUNTIME / "llama-cli.exe"), "--list-devices"], cwd=RUNTIME, memory_mib=32768)
            code, stdout, stderr = gpu.communicate(timeout=30)
            (STATE / "contained-cuda-devices.txt").write_bytes(stdout + stderr)
            report["contained_cuda"] = {"exit": code, "cuda0_enumerated": b"CUDA0" in stdout+stderr,
                                        "token": gpu.token_evidence}
        report["container_cleanup_complete"] = True
        report["host_after"], _ = host_controls()
        network = report["observations"].get("network", [])
        external = [n for n in network if n["id"].startswith("external_")]
        report["external_ipv4_tcp_denied"] = len(external) >= 2 and all(
            not n["allowed"] and n.get("winerror") == 10013 for n in external)
        report["controlled_loopback_not_delivered"] = (len(received) == 4
            and not any(n["delivered"] for n in received)
            and report["loopback_policy"]["profile_loopback_exempt"] is False)
        report["network_kernel_denial"] = (report["external_ipv4_tcp_denied"]
                                           and report["controlled_loopback_not_delivered"])
        report["coverage_pending"] = ["external IPv6 responder", "external UDP responder",
            "WFP block event/counter inspection", "complete inference and parser workload",
            "restart/reboot/resume and network changes", "host-worker IPC adversarial matrix"]
        print(json.dumps({"network_kernel_denial": report["network_kernel_denial"],
                          "contained_cuda": report["contained_cuda"], "observations": report["observations"]}), flush=True)
    except Exception as error:
        (STATE / "launcher-error.txt").write_text(traceback.format_exc())
        report["errors"].append(f"{type(error).__name__}: {error}")
        print(json.dumps({"error": report["errors"][-1]}), flush=True)
    finally:
        for listener in listeners:
            listener.close()
        report["launcher_sha256"] = hashlib.sha256((ROOT / "src" / "local_ai_appliance" / "windows_container.py").read_bytes()).hexdigest()
        (STATE / "appcontainer-results.json").write_text(json.dumps(report, indent=2) + "\n")
    return 0 if report.get("network_kernel_denial") and report.get("contained_cuda", {}).get("cuda0_enumerated") and not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
