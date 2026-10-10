"""Bounded development PDF/DOCX ingestion through a disposable subprocess."""

import base64
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from .folders import AccessDenied
from .model import strict_json


@dataclass(frozen=True)
class Document:
    folder_id: str
    path: str
    sha256: str
    format: str
    unit_kind: str
    units: tuple[str, ...]


def parse_document(folder_id, path, data, *, timeout=10, windows_validation=False):
    if os.name == "nt" and not windows_validation:
        raise AccessDenied("Windows parser process containment is unqualified; use synthetic validation only")
    kind = Path(path).suffix.lower().lstrip(".")
    if kind not in {"pdf", "docx"} or not isinstance(data, bytes) or not 0 < len(data) <= 8 * 1024 * 1024:
        raise AccessDenied("Select a bounded PDF or DOCX document")
    if not isinstance(timeout, (int, float)) or not 0 < timeout <= 10:
        raise AccessDenied("Invalid parser deadline")
    request = json.dumps({"format": kind, "data": base64.b64encode(data).decode("ascii")}).encode("ascii")
    # Keep only Windows OS runtime variables, never proxy/tracing/Python paths.
    environment = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR") if key in os.environ}
    worker = Path(__file__).with_name("parser_worker.py")
    try:
        result = subprocess.run([sys.executable, "-I", "-B", str(worker)], input=request,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=timeout, env=environment, close_fds=True, cwd=worker.parent,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode != 0 or len(result.stdout) > 4 * 1024 * 1024:
            raise ValueError()
        value = strict_json(result.stdout)
        units = value["units"]
        expected = "page" if kind == "pdf" else "paragraph"
        if (set(value) != {"ok", "unit_kind", "units"} or value["ok"] is not True
                or value["unit_kind"] != expected or not isinstance(units, list)
                or not 1 <= len(units) <= (100 if kind == "pdf" else 2000)
                or not all(isinstance(t, str) for t in units)
                or sum(len(t.encode("utf-8")) for t in units) > 512 * 1024):
            raise ValueError()
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError) as e:
        raise AccessDenied("Document parsing failed or exceeded limits; no document text was logged") from e
    return Document(folder_id, path, hashlib.sha256(data).hexdigest(), kind, expected, tuple(units))
