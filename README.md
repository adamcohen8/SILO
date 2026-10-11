# SILO

**Super Intelligence for Local Offline Operations**

*Local intelligence. Contained by design.*

<img src="assets/branding/silo.png" alt="SILO vault-window robot" width="192">

A project to build a reproducible, one-command offline installation of a local AI document assistant for environments that handle Controlled Unclassified Information (CUI).

The host computer remains connected while the AI processes are isolated from external networks. The current evaluation status and qualification limits are described below.

The [SILO vision and phased implementation plan](docs/SILO-VISION-AND-IMPLEMENTATION-PLAN.md) describes the broader document, analysis, and coding assistant, the current foundation, remaining work, and the first complete contained workflow. Capabilities in that roadmap are planned unless identified as implemented.

[Six-model support](docs/SILO-MODEL-SUPPORT.md) adds pinned offline profiles for Gemma 4 26B-A4B, Muse Glimmer 30B, Gemma 4 31B, gpt-oss-20b, Gemma 4 12B Unified, and the existing Nemotron 3 Nano. Each uses reviewed model settings through the shared contained harness. Native Windows/model measurements remain pending; image/audio inputs are not enabled.

The published evaluation terminal's [`/model` menu](docs/SILO-MODEL-SUPPORT.md#model-menu-and-offline-import) switches installed models immediately, installs explicitly selected supported models through pinned host downloads, and removes models after confirmation. Offline imports remain available. New installations store all weights outside the immutable application payload; legacy bundled weights require an installer repair before removal.

The published standalone terminal [checks for published updates](docs/TERMINAL-UPDATES.md) at startup and hourly. **Update available — Ctrl+U to install** offers a verified application update and restart, preserving installed models and saved projects. `/update check` checks manually. This release includes the updater. Older installations need a one-time bootstrap upgrade; native Windows update testing remains pending.

[Phase 1](docs/SILO-PHASE-1.md) adds a shared session API, bounded terminal follow-up memory, reviewed-save authority, a pinned development configuration catalog, frozen synthetic milestone inputs, and the [generated-code boundary design](docs/SILO-EXECUTION-BOUNDARY.md). LangGraph remains the default after a reproducible harness comparison. Code grants/execution remain disabled; native Windows acceptance is pending.

[Phase 2](docs/SILO-PHASE-2.md) implements a shared Windows terminal, disposable code tools, a separate offline Python toolchain, reviewed artifact ZIP publication, and a native LPAC/fixed-VHD runner candidate. Code execution requires complete independently reviewed native boundary evidence and remains disabled by default. Native acceptance and the actual local-model milestone are pending; these source changes are included in the published evaluation installer.

[Phases 3–5](docs/SILO-REMAINING-PHASES.md) implement encrypted saved projects, desktop project controls, the full-window TUI, table analysis, reviewed office artifacts, bounded retrieval, optional signed offline image OCR, model policy/import/selection, reusable workflows, local schedules, and signed-release/readiness tooling. Portable tests and office sample rendering are verified; Windows/native acceptance, real model qualification, organization signing/license decisions and CUI authorization remain pending. See [operating procedures](docs/SILO-OPERATIONS.md). These changes are included in the published evaluation installer.

## Status

Development prototype. A folder-permission broker, reviewed draft-copy workflow, bounded LangGraph document agent and PDF/DOCX ingestion are implemented. The [Windows real-agent evaluation](docs/WINDOWS-AGENT-ISOLATION-2026-10-06.md) passed 15 synthetic checks with the GPU runtime, graph and parsers in AppContainer jobs: text/PDF/Word citations, host-reviewed saves, blocked approved external IPv4 TCP checks and retained host connectivity. It also records 68 regression passes and two POSIX-only skips. Broader isolation, native Windows/UI qualification, signed bundle and fresh-machine installer acceptance remain pending. This repository does not establish authorization to process CUI.

For a new Windows evaluation installation, open **native 64-bit Windows PowerShell**, from any folder, and paste this single command. No prior repository download, GitHub account, Git installation or existing Python is required.

```powershell
$b=Join-Path $env:TEMP ('local-ai-'+[guid]::NewGuid().ToString('N')+'.ps1'); curl.exe --disable --fail --silent --show-error --location --proto '=https' --proto-redir '=https' --connect-timeout 15 --max-time 180 --retry 2 --max-filesize 15658 'https://github.com/adamcohen8/SILO/releases/download/evaluation-2026.10.11-silo.1/install.ps1' --output $b; if($LASTEXITCODE -ne 0){throw 'Bootstrap download failed'}; Set-Content -LiteralPath ($b+':Zone.Identifier') -Encoding ASCII -Value "[ZoneTransfer]`r`nZoneId=3"; $f=[IO.File]::Open($b,'Open','Read','Read'); $h=[Security.Cryptography.SHA256]::Create(); try { if(([BitConverter]::ToString($h.ComputeHash($f))).Replace('-','') -ne '7d631a5ed917a7f4c5a8915c6d9dd22330697d212f9f42cb33b44b9f4a8a3b1d'){throw 'Bootstrap integrity failed'}; & $b } finally {$h.Dispose(); $f.Dispose()}
```

The command belongs to the [published SILO evaluation release](https://github.com/adamcohen8/SILO/releases/tag/evaluation-2026.10.11-silo.1). It is also available in the downloadable [INSTALL.md](https://github.com/adamcohen8/SILO/releases/download/evaluation-2026.10.11-silo.1/INSTALL.md). Setup needs Internet access to download the pinned source, Python, dependencies and model; it verifies the bootstrap and source before installation. Close SILO before using this command for a one-time upgrade at the same installation root. It retains private state and caches, prepares a separate version, and runs native preflight before activation. It installs/verifies the default Nemotron weights; subsequent Ctrl+U application updates preserve the managed model inventory.

The [evaluation installer](docs/EVALUATION-INSTALLER.md) supplies application-local Python, downloads and verifies pinned assets, runs a mandatory native preflight, and creates **SILO** desktop and Start menu shortcuts. It supports offline caches, retry, repair and rollback. The exact release, including terminal updating, still needs native Windows qualification. This release is unsigned; script execution must be permitted through the unit's approved process, and no policy bypass is included.

See the [curl bootstrap documentation](docs/PUBLIC-BOOTSTRAP.md) for integrity and distribution details, or the [manual/offline installer](docs/EVALUATION-INSTALLER.md) for installation from an already-reviewed source ZIP.

The [published Windows evaluation interface](docs/WINDOWS-DESKTOP.md) provides a folder sidebar and scrolling local GPU chat, with citations and unsaved draft text. Selected folders and their access levels are remembered across restarts, with fresh native identity checks on restoration. Follow-ups remember the current conversation while the app is open; **Clear chat** starts fresh without restarting the model or removing folders. Chat history is retained only through explicitly saved encrypted projects using **Projects**; unsaved chats are not retained after closing. On the prepared workstation, double-click **Start-LocalAI.cmd**, wait for **Ready**, and choose **Load sample folders** to try it with synthetic data. **Open AGENTS.md** opens the assistant's startup preferences in Notepad; save edits and **Restart model** to apply them. **Enter** sends; **Shift+Enter** adds a new line. The earlier [desktop preview](docs/DESKTOP-PREVIEW.md) remains a manual text-only prototype.

The desktop also supports **Review draft… → Review changes → Save reviewed copy**. It shows the source, editable destination and diff, then saves only the explicitly reviewed bytes to a new file. Edits invalidate review; changed sources, revoked grants, filename collisions and replayed approval are rejected.

The [agent development harness](docs/AGENT-DEVELOPMENT.md) connects LangGraph to an already-running local chat server. It can list granted directories, read bounded text/PDF/DOCX/CSV/XLSX/PPTX excerpts with source locators, analyze table columns, search granted folders, and propose structured office artifacts. Optional image OCR requires its separate signed runtime. The trusted user reviews and approves saves through terminal commands. It starts with no grants and retains bounded follow-up context in memory; `/clear` erases it. The Windows evaluation interface uses a separately contained graph worker with the same host-owned tool and approval boundaries. Native projects and schedules are host services around this harness.

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
