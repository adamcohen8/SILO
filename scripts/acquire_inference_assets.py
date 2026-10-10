"""Explicit pinned-asset acquisition for synthetic GPU evaluation, never activation."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "artifacts" / "inference"
DOWNLOADS = STATE / "downloads"
DOWNLOADS.mkdir(parents=True, exist_ok=True)
PROFILE = json.loads((ROOT / "profiles" / "nemotron-30b-4090-candidate.json").read_text())
EXPECTED_RUNTIME = {
    "llama-b11433-bin-win-cuda-12.4-x64.zip": (264475988, "ca560fd770cd849195c7aed269d65c23107486dbf4655b1d64df894c6549e09a"),
    "cudart-llama-bin-win-cuda-12.4-x64.zip": (391443627, "8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6"),
}

def request(url, headers=None):
    return urllib.request.urlopen(urllib.request.Request(url, headers={
        "User-Agent": "LocalAI-Appliance-Validation/0.1", **(headers or {})}), timeout=60)

def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()

def download(asset):
    destination = DOWNLOADS / asset["name"]
    if destination.exists():
        if destination.stat().st_size != asset["size"] or sha256(destination) != asset["sha256"]:
            raise ValueError("Existing asset does not match: " + asset["name"])
        print(json.dumps({"asset": asset["name"], "verified": True, "cached": True}), flush=True)
        return {**asset, "verified": True}
    part = destination.with_name(destination.name + ".partial")
    offset = part.stat().st_size if part.exists() else 0
    if offset > asset["size"]:
        raise ValueError("Partial asset is oversized")
    if offset < asset["size"]:
        headers = {"Range": f"bytes={offset}-"} if offset else {}
        with request(asset["url"], headers) as response:
            if offset and (response.status != 206 or not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-")):
                raise ValueError("Server did not honor the resume range")
            received, started, last = offset, time.monotonic(), 0.0
            with part.open("ab" if part.exists() else "xb") as stream:
                while block := response.read(8 * 1024 * 1024):
                    received += len(block)
                    if received > asset["size"]:
                        raise ValueError("Received oversized asset")
                    stream.write(block)
                    now = time.monotonic()
                    if now - last >= 20:
                        print(json.dumps({"asset": asset["name"], "received_bytes": received,
                                          "total_bytes": asset["size"], "percent": round(100*received/asset["size"],1),
                                          "mib_per_second": round((received-offset)/max(now-started,0.001)/1048576,1)}), flush=True)
                        last = now
    if part.stat().st_size != asset["size"] or sha256(part) != asset["sha256"]:
        raise ValueError("Downloaded asset failed size/hash validation: " + asset["name"])
    part.rename(destination)
    print(json.dumps({"asset": asset["name"], "verified": True, "size": asset["size"]}), flush=True)
    return {**asset, "verified": True}

def extract_verified(asset, destination):
    destination.mkdir(parents=True, exist_ok=True)
    entries = []
    with zipfile.ZipFile(DOWNLOADS / asset["name"]) as archive:
        if sum(i.file_size for i in archive.infolist()) > 2 * 1024**3:
            raise ValueError("Runtime archive expansion exceeds limit")
        for info in archive.infolist():
            name = info.filename
            if ("\\" in name or ":" in name or name.startswith("/")
                    or any(c in {"", ".", ".."} for c in name.rstrip("/").split("/"))
                    or (info.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError("Unsafe archive path")
            target = destination / name
            if info.is_dir():
                target.mkdir(exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source:
                contents = source.read(info.file_size + 1)
            if len(contents) != info.file_size:
                raise ValueError("Archive entry size mismatch")
            digest = hashlib.sha256(contents).hexdigest()
            if target.exists():
                if target.stat().st_size != len(contents) or sha256(target) != digest:
                    raise ValueError("Runtime archive collision/changed extracted file")
            else:
                with target.open("xb") as stream:
                    stream.write(contents)
            entries.append({"path": name, "size": len(contents), "sha256": digest})
    return entries

with request("https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/b11433") as response:
    RELEASE = json.load(response)
if RELEASE["target_commitish"] != PROFILE["runtime"]["source_revision"]:
    raise ValueError("Release/source mismatch")
(STATE / "runtime-release.json").write_text(json.dumps(RELEASE, indent=2) + "\n")

licenses = STATE / "licenses"
licenses.mkdir(exist_ok=True)
license_sources = {
    "NVIDIA-Nemotron-Open-Model-License.html": "https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-nemotron-open-model-license/",
    "NVIDIA-Open-Model-License.html": "https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/",
    "NVIDIA-Trustworthy-AI-Terms.html": "https://www.nvidia.com/en-us/agreements/trustworthy-ai/terms/",
    "llama.cpp-LICENSE.txt": "https://raw.githubusercontent.com/ggml-org/llama.cpp/" + PROFILE["runtime"]["source_revision"] + "/LICENSE",
    "CUDA-12.4-EULA.html": "https://docs.nvidia.com/cuda/archive/12.4.0/eula/index.html",
}
license_inventory = []
for name, url in license_sources.items():
    with request(url) as response:
        text = response.read(2*1024*1024 + 1)
    if len(text) > 2*1024*1024:
        raise ValueError("License source limit exceeded")
    (licenses / name).write_bytes(text)
    license_inventory.append({"path": name, "source": url, "sha256": hashlib.sha256(text).hexdigest()})

with request("https://api.github.com/repos/ggml-org/llama.cpp/git/ref/tags/b11433") as response:
    tag = json.load(response)
if tag["object"]["type"] != "commit" or tag["object"]["sha"] != PROFILE["runtime"]["source_revision"]:
    raise ValueError("Runtime tag does not resolve to the expected source commit")
assets = []
for name in ("llama-b11433-bin-win-cuda-12.4-x64.zip", "cudart-llama-bin-win-cuda-12.4-x64.zip"):
    published = next(a for a in RELEASE["assets"] if a["name"] == name)
    if not published["digest"].startswith("sha256:"):
        raise ValueError("Missing publisher archive hash")
    if (published["size"], published["digest"].split(":")[1]) != EXPECTED_RUNTIME[name]:
        raise ValueError("Release asset differs from the reviewed pin")
    assets.append({"name": name, "size": published["size"], "sha256": published["digest"].split(":")[1],
                   "url": published["browser_download_url"], "role": "runtime"})
model = PROFILE["model"]
assets.append({"name": model["file"], "size": model["size"], "sha256": model["sha256"], "role": "model",
               "url": "https://huggingface.co/" + model["quantization_repository"] + "/resolve/"
                      + model["quantization_revision"] + "/" + model["file"]})
if shutil.disk_usage(STATE).free < sum(a["size"] for a in assets) + 4*1024**3:
    raise ValueError("Insufficient space for verified inference assets")
lock = {"profile_id": PROFILE["profile_id"], "deployment_ready": False,
        "runtime_release": "b11433", "runtime_source_revision": PROFILE["runtime"]["source_revision"],
        "license_review": "both_model_license_sources_preserved_internal_synthetic_evaluation_redistribution_pending",
        "licenses": license_inventory, "assets": assets}
(STATE / "acquisition-plan.json").write_text(json.dumps(lock, indent=2) + "\n")
with ThreadPoolExecutor(max_workers=3) as executor:
    lock["assets"] = list(executor.map(download, assets))
runtime = STATE / "runtime-b11433-cuda12.4"
lock["extracted_runtime"] = []
for asset in lock["assets"]:
    if asset["role"] == "runtime":
        lock["extracted_runtime"].extend(extract_verified(asset, runtime))
(STATE / "verified-assets.json").write_text(json.dumps(lock, indent=2) + "\n")
print(json.dumps({"acquisition_complete": True, "verified_assets": len(assets),
                  "runtime_files": len(lock["extracted_runtime"]), "deployment_ready": False}), flush=True)
