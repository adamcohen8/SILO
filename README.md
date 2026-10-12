# SILO

**Super Intelligence for Local Offline Operations**

*Local intelligence. Contained by design.*

<img src="assets/branding/silo.png" alt="SILO vault-window robot" width="192">

SILO is a local AI work assistant for documents, analysis, coding, and repeatable
project workflows. It combines replaceable local models with a shared agent
backend, a full-window terminal, and a Windows desktop interface. Users choose
which folders it can read and review the exact outputs it may publish.

The Windows architecture contains inference, document parsing, and separately
approved code tools while the host computer retains its permitted connectivity.
The current source is an **evaluation implementation for public or synthetic
material**. Complete native containment, deployment readiness, and organizational
CUI authorization remain pending. Ask your security manager before installation.

## What SILO implements today

This table describes current `main`, reviewed on **12 October 2026**. The
published installer is an earlier snapshot; see [installation](#installation-and-updates).

| Area | Current source capability | Practical limits |
| --- | --- | --- |
| Documents and analysis | Read and search text, PDF, DOCX, CSV, XLSX, and PPTX; cite lines, pages, paragraphs, rows, and slides; calculate statistics for table columns | Bounded excerpts and literal search; partial coverage is explicit. Formulas, macros, and complete document fidelity are unsupported |
| Reviewed artifacts | Propose text, Word documents, spreadsheets, CSV files, and presentations; review and save the stored bytes | Drafts remain unsaved until host approval. Document saves create new copies; the model cannot approve them |
| Projects and long work | Encrypted saved projects, instructions, task journals, code snapshots, retention, backup/recovery, reusable workflows, and local schedules | Saving is explicit. Source/grant changes invalidate retained context; uncertain actions require reconciliation. Schedules run while the project is open |
| Terminal and desktop | Shared host services; full-window terminal with project sidebar, completion, file mentions, progress, provisional streaming, diffs, and cancellation; desktop sources/draft/project controls | Mac preview is scripted. Current managed Windows startup requires protected enrollment; latest model/UI acceptance is blocked |
| Models and hardware | Eleven pinned text-input profiles, hardware-based preparation defaults and policy-filtered recommendations, verified offline imports, model switching/install/removal | Capacity estimates are not quality or placement acceptance. Image/audio model inputs are disabled |
| Repository editing | Disposable text snapshots; hash-checked edits, patches, deletes and renames; reviewed patch export; incremental Python/lexical source navigation | Editing can run with execution disabled. Originals stay outside the code workspace; binary assets and arbitrary shell commands are unsupported |
| Coding execution and publication | Separate Python runner; pinned Python/NumPy preparation; fixed JS/TS/Rust/C++ build adapters; test feedback; recoverable repository apply; private-copy Git commits; read-only LSP queries | Native execution, public repository apply, Git, and LSP each require independent acceptance. These gates remain closed; other SDKs/servers still need reviewed assets |
| Managed security | Protected release/model policy, signed acceptance, LPAC/job controls, approved storage, native project encryption, audit and maintenance tooling | Implementation and fixture passes do not qualify the full configuration or authorize CUI use |

Interactive work has **no lifetime token, model-call, tool-call, or execution-attempt
quota**. Context windows, individual message sizes, idle detection, repeated-action
checks, and per-process resource limits still apply. Explicit benchmarks retain
reproducible caps. See [long-running work](docs/SILO-LONG-WORK-AND-CODING.md).

Fresh source preparation selects **Nemotron 3.5 Lightning 30B-A3B** on Windows x64
with at least **32 GiB RAM** and **24 GiB nominal VRAM on the first NVIDIA GPU**.
Smaller compatible machines select **GPT-OSS 20B** (16 GiB VRAM / 32 GiB RAM),
**Gemma 4 12B** (12 GiB VRAM / 16 GiB RAM), or **Gemma 4 E4B on CPU**
(16 GiB nominal RAM and four CPU threads). If no profile fits, preparation stops
before model downloads. Saved selections take precedence. `/model recommend` shows
permitted choices and hardware requirements without switching or downloading. See the
[model catalog and default behavior](docs/SILO-MODEL-SUPPORT.md).

## Validation and remaining work

The [latest Windows report](windows_test_report.md) records fixes for native file
replacement/nested publication and installed NumPy preparation. Its final installed
data fixtures passed **36/36**, exercising NTFS handles, encrypted storage,
navigation, and recovery. The full Windows source suite recorded **463 successful
method executions, 368 skip records, and zero failures/errors** across 828 tests;
those counts include duplicate discovery/subtests and are explained in the report.

Actual model/UI runs and contained code/build/Git/language-server qualification
were **blocked by missing managed enrollment and independently signed acceptance**.
Prepared Python/NumPy bytes were verified without executing that target environment.
Earlier model evaluations remain historical evidence, not qualification of current
`main`. No measured actual-model coding scores exist for the current benchmark.

The first complete coding milestone remains a contained local-model workflow
that repairs the synthetic repository, passes four unchanged tests, calculates
**108 kg**, and creates a chart and cited report for review. See the
[current status](docs/SILO-STATUS.md), [coding workflow](docs/SILO-CODING-WORKFLOW.md),
and [Windows test plan](test_plan.md) for the outstanding gates.

## Installation and updates

This PR candidate adds a reviewed `-Activate` path and fixes bootstrap
mode forwarding. It is unpublished and needs signing plus native
Windows validation. See [one-command installation and activation](docs/ONE-COMMAND-INSTALLATION.md)
for the approval inputs, local tooling and remaining gates.

**Current source and the published installer have different behavior.**

- Current `main` requires `-PrepareOnly`, builds an inactive candidate, and creates
  no active record, shortcut, or model launch. Managed activation needs separate
  administrator protection, trust/policy enrollment, and signed native acceptance.
- The latest published release is
  [evaluation-2026.10.11-silo.3](https://github.com/adamcohen8/SILO/releases/tag/evaluation-2026.10.11-silo.3),
  an earlier unsigned evaluation artifact. It does not contain the current managed
  security, Lightning default, long-work, or expanded coding changes. Updating
  source or merging a PR does not update that installer.

From an extracted, reviewed **current source** folder, use native 64-bit Windows
PowerShell to prepare public assets:

```powershell
.\installer\Install-Evaluation.ps1 -PrepareOnly
```

Setup can download pinned assets on the trusted host; `-Offline` requires a
complete verified cache. There are no task-time dependency downloads or cloud
fallback. Follow [source preparation](docs/EVALUATION-INSTALLER.md) and
[managed activation](docs/SILO-SECURITY-HARDENING.md). Preparation alone cannot
start an interactive evaluation of the latest source.

For the **older published evaluation**, its existing download command is retained
below. Review its [release-specific installation instructions](https://github.com/adamcohen8/SILO/releases/download/evaluation-2026.10.11-silo.3/INSTALL.md)
and permitted script-execution process before using it. It verifies an exact
bootstrap/source snapshot; it does not install current `main`.

```powershell
$b=Join-Path $env:TEMP ('local-ai-'+[guid]::NewGuid().ToString('N')+'.ps1'); curl.exe --disable --fail --silent --show-error --location --proto '=https' --proto-redir '=https' --connect-timeout 15 --max-time 180 --retry 2 --max-filesize 15658 'https://github.com/adamcohen8/SILO/releases/download/evaluation-2026.10.11-silo.3/install.ps1' --output $b; if($LASTEXITCODE -ne 0){throw 'Bootstrap download failed'}; Set-Content -LiteralPath ($b+':Zone.Identifier') -Encoding ASCII -Value "[ZoneTransfer]`r`nZoneId=3"; $f=[IO.File]::Open($b,'Open','Read','Read'); $h=[Security.Cryptography.SHA256]::Create(); try { if(([BitConverter]::ToString($h.ComputeHash($f))).Replace('-','') -ne '4e43dab5186bbfe3a39336093358397aa1298163a6b18c4768a93d13c977b75e'){throw 'Bootstrap integrity failed'}; & $b } finally {$h.Dispose(); $f.Dispose()}
```

The published terminal supports `/update check` and Ctrl+U installation of a
published application update while idle, preserving managed models and saved
projects. This checks published releases; it cannot deliver unreleased source.
See [updates](docs/TERMINAL-UPDATES.md) and
[bootstrap identities](docs/PUBLIC-BOOTSTRAP.md).

## Documentation

- [Current status and evidence](docs/SILO-STATUS.md): what is implemented, observed, blocked, and shipped.
- [Coding workflow](docs/SILO-CODING-WORKFLOW.md) and [long-running work](docs/SILO-LONG-WORK-AND-CODING.md): commands, recovery, offline environments, and limits.
- [Model support](docs/SILO-MODEL-SUPPORT.md): pinned profiles, hardware floors, and model management.
- [Operating procedures](docs/SILO-OPERATIONS.md): storage, retention, backup/recovery, policy, and deployment.
- [Terminal interface](docs/TERMINAL-UI.md) and [Windows desktop](docs/WINDOWS-DESKTOP.md): current interfaces and historical preview/evaluation paths.
- [Architecture](docs/ARCHITECTURE.md), [agent development](docs/AGENT-DEVELOPMENT.md), and [document ingestion](docs/DOCUMENT-INGESTION.md): source responsibilities and developer setup.
- [Vision and implementation plan](docs/SILO-VISION-AND-IMPLEMENTATION-PLAN.md): product direction and phase exit criteria.

SILO is independent, with no GenAI.mil affiliation, endorsement, or integration.

## Development and data boundaries

The first Windows evaluation target is Windows 11 Pro x64 with an i9-14900KF,
RTX 4090 (24 GB VRAM), 64 GB RAM, and about 1 TB storage. Other profiles need their
own measurements. macOS supports portable development and UI previews; those
checks do not establish native Windows containment.

From a prepared development environment at the repository root:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Optional dependencies/platform prerequisites produce explicit skips. Scripted
model replies and loopback fixtures test orchestration, not inference quality.
See [development setup](docs/AGENT-DEVELOPMENT.md) for dependency instructions.

Keep model weights, dependencies, and installation bundles outside Git. Never
commit CUI, operational documents, derived private indexes, conversations,
sensitive logs, credentials, or signing keys. Project data and backups belong
within the approved storage boundary. Runtime work requires no GitHub credentials;
explicit host acquisition/update operations are separate from AI-runtime access.
