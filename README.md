# SILO

**Super Intelligence for Local Offline Operations**

*Air-gapped intelligence. Anywhere.*

<img src="assets/branding/silo.png" alt="SILO vault-window robot" width="192">

A project to build a reproducible, one-command offline installation of a local AI document assistant for environments that handle Controlled Unclassified Information (CUI).

The host computer remains connected while the AI processes are isolated from external networks. The tagline describes the project's ambition; this evaluation does not establish a physical air gap or authorization to process CUI.

## Status

Development prototype. A folder-permission broker, reviewed draft-copy workflow, bounded LangGraph document agent and PDF/DOCX ingestion are implemented. The [Windows real-agent evaluation](docs/WINDOWS-AGENT-ISOLATION-2026-10-06.md) passed 15 synthetic checks with the GPU runtime, graph and parsers in AppContainer jobs: text/PDF/Word citations, host-reviewed saves, blocked approved external IPv4 TCP checks and retained host connectivity. It also records 68 regression passes and two POSIX-only skips. Broader isolation, native Windows/UI qualification, signed bundle and fresh-machine installer acceptance remain pending. This repository does not establish authorization to process CUI.

For a new Windows evaluation installation, extract the reviewed source ZIP, open native 64-bit PowerShell in the folder containing this README, and run:

```powershell
.\installer\Install-Evaluation.ps1
```

The [evaluation installer](docs/EVALUATION-INSTALLER.md) supplies application-local Python, downloads and verifies pinned assets, runs a mandatory native preflight, and creates a **SILO** desktop and Start menu shortcuts. It supports offline caches, retry, repair and rollback. The new CPython 3.14 configuration still needs qualification on Windows. Script execution must be permitted through the unit's approved process; no policy bypass is included.

An [anonymous curl bootstrap](docs/PUBLIC-BOOTSTRAP.md) is now prepared for public release distribution. Its generated command downloads and verifies the bootstrap and source before installing, from any folder. The repository is public at [adamcohen8/SILO](https://github.com/adamcohen8/SILO); versioned bootstrap release assets still need publication before the anonymous installation URL is live.

The [Windows evaluation interface](docs/WINDOWS-DESKTOP.md) provides a folder sidebar and scrolling local GPU chat, with citations and unsaved draft text. Selected folders and their access levels are remembered across restarts, with fresh native identity checks on restoration. Follow-ups remember the current conversation while the app is open; **Clear chat** starts fresh without restarting the model or removing folders. History is not saved after closing. On the prepared workstation, double-click **Start-LocalAI.cmd**, wait for **Ready**, and choose **Load sample folders** to try it with synthetic data. **Open AGENTS.md** opens the assistant's startup preferences in Notepad; save edits and **Restart model** to apply them (clears chat). **Enter** sends; **Shift+Enter** adds a new line. The earlier [desktop preview](docs/DESKTOP-PREVIEW.md) remains a manual text-only prototype.

The desktop also supports **Review draft… → Review changes → Save reviewed copy**. It shows the source, editable destination and diff, then saves only the explicitly reviewed bytes to a new file. Edits invalidate review; changed sources, revoked grants, filename collisions and replayed approval are rejected.

The [agent development harness](docs/AGENT-DEVELOPMENT.md) connects LangGraph to an already-running local chat server. It can list granted directories, read bounded text/PDF/DOCX excerpts with source locators, and propose new documents. The trusted user reviews and approves saves through terminal commands. It starts with no grants and retains no conversation between requests. The Windows evaluation interface uses a separately contained graph worker with the same host-owned tool and approval boundaries.

A separate [Windows folder candidate](docs/WINDOWS-FOLDERS.md) implements native handle-relative access for synthetic validation and the explicit Windows evaluation interface; the ordinary application still refuses Windows access. The [offline bundle checker](docs/OFFLINE-BUNDLE.md) validates manifest structure and payload integrity on POSIX, without downloading, executing, installing, or granting deployment readiness. Neither component is qualified for deployment.

The [portable Windows test kit](docs/WINDOWS-TEST-KIT.md) packages committed source, synthetic PDF/DOCX/text fixtures, standard-library native validation runners, and two optional hash-pinned parser wheels. It includes a [candidate inference profile](docs/INFERENCE-PROFILE.md), [isolation acceptance plan](docs/ISOLATION-VALIDATION.md), and [installer framework](docs/INSTALLER-FRAMEWORK.md) for private verified staging/checkpoints/reboot gating/rollback. No model/runtime is included or launched, and production activation remains unavailable.

## Accepted first-version requirements

- One local user on the unit's Windows workstation.
- No document access by default. The user selects or drops folders into **read-only** or **editable** categories through a trusted local interface.
- Read-only grants permit document access but no modification. Editable grants permit reading and creating documents; existing-file changes require a user-reviewed edit workflow.
- The model cannot grant itself access or write documents outside editable folders.
- No shell or generated-code execution in this iteration. Coding assistance can be added later.
- Administrator installation and required Windows feature changes/reboots are allowed.
- Initial development took place on macOS. Windows target testing began on 6 October 2026; [session results](docs/TARGET-SESSION-2026-10-06.md) record 13 native folder passes with one privilege-dependent skip and six native installer passes. Complete Windows/GPU/isolation evidence remains required before deployment claims.

See [architecture and decisions](docs/ARCHITECTURE.md) and [target validation](docs/TARGET-VALIDATION.md).

## Goals

- Install from a signed, versioned offline bundle with pinned dependencies and model hashes.
- Prevent external communications by the AI stack while preserving the host computer's permitted connectivity.
- Search, compare, and draft from local documents with verifiable document and page citations.
- Support replaceable models and inference runtimes through a common local interface and tested model profiles.
- Produce installation, configuration, isolation, and functional test evidence.

The long-term aspiration is to contribute to or integrate with GenAI.mil. This is an independent project with no current affiliation, endorsement, or integration.

## First hardware target

- Windows 11 Pro 25H2
- Intel Core i9-14900KF
- NVIDIA GeForce RTX 4090, 24 GB VRAM
- 64 GB system RAM
- Approximately 1 TB storage

Nemotron 3 Nano 30B-A3B and LangGraph are initial candidates. The pinned IQ4_XS quantization and native Windows llama.cpp CUDA build passed the synthetic contained document workflow with all 53 layers on the GPU. Broader model quality and the complete isolation acceptance matrix remain subject to testing. WSL2 remains an alternative requiring separate evaluation.

## Storage and development boundaries

This repository contains source code, configuration templates, manifests, documentation, and public or synthetic test fixtures only.

Do not commit CUI, operational documents, extracted text, embeddings or indexes derived from CUI, user conversations, sensitive logs, credentials, or private signing keys. Do not include those materials in GitHub issues, pull requests, attachments, or build outputs.

Model weights, dependencies, and full installation bundles belong in separate artifact storage. The repository should record their versions, licenses, provenance, and hashes. Deployed data and backups belong within the organization's authorized storage boundary.

The installed AI must not require GitHub connectivity or GitHub credentials.

## First milestone

Use public or synthetic data on the target workstation to demonstrate GPU inference, blocked external communications across the complete application, retained host connectivity, and document answers with valid citations. Package the verified configuration only after those results are established.

## Development checks

The current folder adapter is POSIX-only and deliberately refuses Windows access until a native Windows implementation is available.

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Optional agent and UI dependencies enable their corresponding tests; missing extras are reported as skips. The agent tests exercise real LangGraph orchestration with scripted replies and a synthetic local HTTP service. They do not establish inference quality, Windows installation, or OS network isolation. See the [agent development instructions](docs/AGENT-DEVELOPMENT.md) for pinned setup.
