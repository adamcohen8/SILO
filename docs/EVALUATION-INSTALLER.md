# One-command Windows evaluation installer

For a command that downloads the source automatically, see
[PUBLIC-BOOTSTRAP.md](PUBLIC-BOOTSTRAP.md) and the [published SILO evaluation release](https://github.com/adamcohen8/SILO/releases/tag/evaluation-2026.10.11-silo.3). The anonymous download-first command is available in the repository README and release notes. The manual source ZIP entry point remains available below.

From the extracted, reviewed source folder containing `README.md`, run this in
native 64-bit Windows PowerShell:

```powershell
.\installer\Install-Evaluation.ps1
```

The host downloads pinned public assets, supplies application-local Python,
prepares separate host and contained-worker dependency trees, and runs a native
GPU/document preflight. After it passes, the installer creates **SILO** shortcuts
on the current user's desktop and Start menu, with the selected vault-window
robot icon, and opens the desktop. Subsequent launches use
`%LOCALAPPDATA%\LocalAI-Evaluation\Start-LocalAI.cmd`.

This is an evaluation using public or synthetic documents. `deployment_ready`
and `full_isolation_accepted` remain false. Signing, broader isolation acceptance,
redistribution review and organizational authorization remain separate gates.
The installer has been tested portably with synthetic payloads, real Windows
wheel vendoring and PowerShell parsing; native installation is not yet qualified.

## What the command does

1. Creates new private, current-user-owned installation/cache/state storage on a
   fixed local NTFS drive. Existing unexpected ACLs, reparse points, recalled
   storage and concurrent installations are rejected; existing ACLs are not reset.
2. Verifies the pinned Python.org interpreter archive before executing it. No
   existing Python installation, Codex runtime, administrator installation,
   global PATH change or pip invocation is required.
3. Downloads the locked model, llama.cpp/CUDA archives and 42 Windows wheels.
   Completed assets are size/SHA-256 checked; interrupted downloads retain
   `.partial` files and use verified range resumption on retry. Offline mode
   refuses every missing asset without initiating a download.
4. Vendors library files without executing wheel/setup hooks. CLI wrappers are
   omitted; `.pth` hooks, archive escapes, aliases, links, unexpected collisions
   and oversized expansion are rejected. Assets read from a selected shared
   cache are copied into private staging and checked again before extraction.
   Qt is absent from the worker tree.
5. Enumerates and hashes the complete application, interpreter, dependency,
   worker, model and runtime payload. Undeclared or changed files prevent launch.
6. Imports the host UI modules, starts the model with all 53 layers on the GPU,
   verifies zero-capability/no-loopback-exemption worker tokens, answers a cited
   synthetic text question, parses synthetic PDF/DOCX in contained jobs, and
   checks revocation/cleanup. Publication as the active evaluation requires all
   these checks; this preflight does not complete the network isolation matrix.
7. Publishes a versioned installation and launcher. The launch gate verifies the
   complete payload before starting Python. The session also independently checks
   inference pins and the complete runtime inventory before launching workers.

Downloads occur on the trusted host before inference. Running model, graph and
parser jobs use the existing AppContainer boundary; no cloud fallback, network
adapter shutdown, global firewall change, driver install or Windows feature
change is performed. No document folder is granted by the installer. Its
preflight never loads remembered user folder selections.

## Prerequisites and storage

The first target is native x64 Windows 11 with the installed NVIDIA driver,
RTX 4090 and 64 GiB RAM. Internet access is needed only for online installation.
The pinned model is approximately 18.2 GB. Allow at least **45 GB** free on the
installation volume for the resumable cache, installed copy and extracted
software; the installer computes its own space requirement.

The standalone profile uses **CPython 3.14.8**, pinned from the
[official Python.org Windows index](https://www.python.org/ftp/python/index-windows.json),
and CP314/compatible Windows wheels with the project's existing package versions.
The prior workstation evidence used CPython 3.12.14 and does not qualify this
new interpreter. The mandatory preflight must establish the new configuration
on the target. Embedded Python dependencies are application-managed as described
in [Python's Windows distribution documentation](https://docs.python.org/3/using/windows.html#the-embeddable-package).

Script execution must be permitted through the unit's approved process. If
Windows rejects the script, stop and use that process; this installer and its
launcher never set execution policy, unblock files or use bypass flags.

Optional arguments:

```powershell
# Install to a shorter approved local NTFS path; finish without opening the UI.
.\installer\Install-Evaluation.ps1 -InstallRoot 'D:\AI-Evaluation' -NoLaunch

# Fully offline installation from an already populated, verified asset cache.
.\installer\Install-Evaluation.ps1 -Offline -CachePath 'D:\Approved\EvaluationCache'

# Repair into a fresh version, retaining the old version and mutable state.
.\installer\Install-Evaluation.ps1 -Repair

# Restore the previous byte-verified version after an upgrade.
.\installer\Install-Evaluation.ps1 -Rollback
```

`-NoShortcut` suppresses Start Menu integration. To prepare the public asset
cache on an approved connected build computer with Python already available:

```powershell
python .\scripts\download_evaluation_assets.py --cache 'D:\Approved\EvaluationCache'
```

Transfer the reviewed source and cache through the approved local transfer
process, then use the offline installation command. The source ZIP alone has
no model/interpreter/wheels. Model weights, caches and prepared installations
must remain outside Git. This workflow is not a signed redistributable bundle.
The inference lock retains license URLs and hashes from the earlier evaluation;
this installer does not package those separately captured license pages.

## Retry, rollback and state

The same source installation is idempotent: its complete payload is checked
before reuse. A failed download or preflight does not replace the active version.
Incomplete `.pending-*` transactions remain for inspection; rerunning creates a
fresh transaction and reuses the verified/resumable cache. Corrupt cached assets
are refused rather than overwritten. Existing modified/unowned files must be
inspected before recovery. The installer serializes operations with an OS file
lock; a stale lock-file name alone does not block recovery after process exit.

Repair never overwrites an existing version. The previous active version is
retained for rollback. Neither rollback nor repair deletes documents in granted
folders or resets preferences. There is no automatic uninstall or cache pruning.

Mutable `state` contains editable `AGENTS.md`, saved folder selections, synthetic
samples and metadata-only `installation-preflight.json`. Conversation and draft
text remain in memory. State is outside the immutable payload, so editing
preferences does not invalidate its release manifest. Restart applies them.

## Desktop reviewed saves

After a model proposes a draft, select it and click **Review draft…**. The
separate window shows the editable destination, new filename, source/hash,
editable draft text and plain-text diff. **Review changes** rechecks the source
and destination. **Save reviewed copy** then approves exactly those stored bytes.
Changing the text, filename or destination invalidates review. Changed sources,
revoked permissions, a competing destination file and replayed approval are
rejected. Existing files remain unchanged. Discard, a new question, permission
changes, Clear chat, cancellation and shutdown clear pending write authority.
The worker protocol still contains no approval or permission-management operation.

## Trust and acceptance limits

Trust starts with the reviewed source and its committed publisher pins. The
inference lock is additionally bound to a canonical SHA-256 in the verifier;
an empty/edited downloaded inventory cannot redefine it. Complete installed
payload hashes detect drift within the evaluation workflow. Private ACLs protect
against other ordinary users; these mutable per-user manifests are not signed
trust anchors against a compromised same-user host or an administrator.

Remaining deployment work includes independent signing/trust anchors, the full
[isolation matrix](ISOLATION-VALIDATION.md), reboot/sleep/VPN/network-change gates,
broader native filesystem/parser stress, resource/power-loss recovery, complete
fresh-install/repair/rollback qualification and redistribution/licensing review.
No passing development test or evaluation preflight authorizes CUI processing.

## Local development validation

On 10 October 2026, the macOS synthetic suite completed 312 tests: 196 passed
and 116 platform-dependent checks skipped. Coverage includes the empty runtime
inventory regression, pinned-byte drift, unsafe extraction, offline preparation,
range resumption, shared-cache changes, failed-preflight reporting, and actual Qt review/save controls with
synthetic POSIX folders. The real model was not executed during these tests.

All 42 real Windows wheels passed their exact size/hash checks, Windows CP314
dependency-closure checks and safe vendoring. The longest relative wheel path
was 118 characters. Eight PowerShell sources parsed using PowerShell 7.6.6 on
macOS; 11 unsafe paths and four synthetic archive cases behaved as expected,
wrong-digest bytes were denied before extraction, and the pinned official
Windows interpreter ZIP extracted successfully. These checks did not execute
Windows binaries or establish PowerShell 5.1/native ACL behavior.

Portable PowerShell checks can be repeated from the source folder:

```powershell
.\scripts\test_evaluation_bootstrap.ps1
# Optionally also check a cached official interpreter archive:
.\scripts\test_evaluation_bootstrap.ps1 -PythonArchive 'D:\Approved\EvaluationCache\python-3.14.8-embeddable-amd64.zip'
```

Next native acceptance should cover a fresh install with no existing Python,
offline installation, interrupted download/retry, idempotent reuse, startup
drift rejection, reviewed saves, repair and rollback. The installer enforces
its synthetic native preflight before publication; neither that mechanism nor
these macOS results establish that the full Windows acceptance has passed.
