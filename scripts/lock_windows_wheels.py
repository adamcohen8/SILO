"""Verify local pinned Windows wheels against PyPI metadata before installation."""
import email
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
WHEELS = ROOT / "artifacts" / "windows-evaluation" / "wheels"
expected = {}
for line in (ROOT / "requirements" / "agent-dev.txt").read_text().splitlines():
    if line.strip() and not line.startswith("#"):
        name, version = line.split("==")
        expected[name.replace("_", "-").lower()] = version
expected.update(pypdf="6.19.0", defusedxml="0.7.1")
inventory, requirements, seen = [], [], set()
for wheel in sorted(WHEELS.glob("*.whl")):
    with zipfile.ZipFile(wheel) as archive:
        metadata = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
        if len(metadata) != 1:
            raise ValueError("Ambiguous wheel metadata")
        value = email.message_from_bytes(archive.read(metadata[0]))
        name, version = value["Name"].replace("_", "-").lower(), value["Version"]
        if name in seen or expected.get(name) != version:
            raise ValueError("Wheel differs from reviewed version pins")
        seen.add(name)
        license_entries = [n for n in archive.namelist() if ".dist-info/" in n and
                           ("license" in n.lower() or "notice" in n.lower() or "copying" in n.lower())]
        licenses = [{"path": n, "sha256": hashlib.sha256(archive.read(n)).hexdigest()} for n in license_entries]
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    with urllib.request.urlopen(url, timeout=30) as response:
        published = json.load(response)
    entry = next(v for v in published["urls"] if v["filename"] == wheel.name)
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    if wheel.stat().st_size != entry["size"] or digest != entry["digests"]["sha256"]:
        raise ValueError("Wheel does not match publisher size/hash")
    inventory.append({"name": name, "version": version, "filename": wheel.name,
                      "size": entry["size"], "sha256": digest, "url": entry["url"],
                      "license_expression": value.get("License-Expression"),
                      "license_files": licenses})
    requirements.append(f"{name}=={version} --hash=sha256:{digest}")
if seen != set(expected):
    raise ValueError("Incomplete pinned wheel set")
lock = {"platform": "Windows x64 CPython 3.12", "evaluation_only": True,
        "deployment_ready": False, "wheels": inventory}
(ROOT / "profiles" / "windows-python312-wheels.json").write_text(json.dumps(lock, indent=2) + "\n")
(ROOT / "requirements" / "windows-evaluation-offline.txt").write_text(
    "# Verified Windows x64 / CPython 3.12 evaluation wheels; not a complete installer lock.\n"
    + "\n".join(requirements) + "\n")
print(json.dumps({"publisher_verified_wheels": len(inventory), "deployment_ready": False}))
