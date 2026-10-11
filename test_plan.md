# SILO Windows installation test handoff

Prepared 10 October 2026 for Codex on the Windows test computer. Run this plan
after the **Future Capabilities** work is finished and merged into
`https://github.com/adamcohen8/SILO`. This file is a procedure, not test evidence.
Refresh commands and expected behavior against the actual merged source before
running them. Updated after six-model PR #11 merged: the verified GitHub main
baseline is `61d2ccb1047f9f6c48d51afe54a4b56cc77aa549`. No new installer release
was published by that merge.

## Start here: instructions to Windows Codex

The user intends to test SILO installation on this Windows computer, fix issues
here, and submit a PR with necessary changes. Help complete that workflow. Read
this file and the applicable `AGENTS.md`, inspect the checkout and machine, then
work through the stages below. Explain the first failure clearly, reproduce it,
make a focused source fix, and rerun the affected stage. Preserve unrelated work.
Do not stop at a suggested plan when you can perform the next authorized test.

Use public/synthetic inputs throughout. Codex is the connected development
assistant; SILO is the local system being tested. Keep SILO's workers contained
while the host and Codex remain connected. Do not grant SILO the repository,
Codex configuration, home directory, credentials, or operational documents.

Run as the ordinary Windows user in native 64-bit PowerShell. Inspect an
execution-policy block rather than bypassing it. Do not change global PATH,
firewall, network adapters, WSL settings, drivers, or unrelated installations to
make a test pass. A needed machine-level change is a separate decision to explain
to the user. Do not edit installed immutable payloads to apply a source fix.
Reinstall from the fixed source instead. Do not manufacture acceptance records,
lower a containment gate, replace pinned hashes with downloaded bytes, or use a
mock/preview as a passing installation or model test.

A useful opening prompt for the new Codex chat is:

> Read test_plan.md and AGENTS.md. The Future Capabilities work is now merged.
> Test this Windows installation using synthetic data, record the exact source
> and native evidence, and help me fix failures in a dedicated branch for a PR.
> Start by verifying the merged revision and inventorying this computer.

## 1. Establish the source and the installation route

Read these files in the Windows checkout, in order:

1. `README.md`, `docs/EVALUATION-INSTALLER.md`, `docs/PUBLIC-BOOTSTRAP.md`.
2. `docs/SILO-MODEL-SUPPORT.md`, `profiles/model-catalog.json`,
   `docs/SILO-MODEL-VALIDATION.json`.
3. `docs/SILO-PHASE-2.md`, `docs/SILO-REMAINING-PHASES.md`,
   `docs/SILO-OPERATIONS.md`.
4. `docs/ISOLATION-VALIDATION.md`, `docs/SILO-EXECUTION-BOUNDARY.md`.
5. The installer/launcher and relevant test source before executing each stage.

`context.md` is private local continuity material and may not be present in the
Windows checkout. This handoff supplies the necessary intent without requiring
it. Do not upload that file. The product is **Super Intelligence for Local
Offline Operations**: documents, analysis, coding and repeatable work with
host-enforced permissions and local inference. Installation acceptance, model
quality, execution containment and organizational CUI authorization are distinct.

### Check version identity before spending time on the wrong installer

The current [release installation command](https://github.com/adamcohen8/SILO/releases/download/evaluation-2026.10.11-silo.2/INSTALL.md)
installs `evaluation-2026.10.11-silo.2`, merged source
`f7995d48cdbfecc15145e2e91f2d1ddb6dd80e68`, update sequence 2. It includes
the Windows redirected-input and legacy-output repairs in PR #17, model menu
and terminal updater. Sequence-1 installations can receive this release with
`/update check` and Ctrl+U. Installations without the updater need the verified
bootstrap once at the same root. Earlier
release/version observations below remain historical evidence; they do not
qualify this exact release. See the terminal update validation section below.
Use this handoff from current GitHub main; immutable release ZIPs retain the
documentation snapshot from their source commit. Read `windows_test_report.md`
for the repeat native run, preserved failures and remaining coverage gaps.

At preparation, the published `evaluation-2026.10.10-silo.1` installer was pinned
to source `899284b8412a7d29299000d0cff837b36bca3059`; it did **not** contain the
later platform/TUI/six-model work. Phase work was merged as `9002b56`, followed
by six-model implementation `6f50430` and validation `7087f0b` on
`codex/six-model-support`. Six-model PR #11 subsequently merged as
`61d2ccb1047f9f6c48d51afe54a4b56cc77aa549`. Verify that SHA is an ancestor of
the Windows checkout and record the actual test revision if main has advanced.

Merging a PR does not rebuild a published installer. Record the actual merged
commit, release tag, bootstrap hash, source archive hash and installed source ID
where applicable. Compare the release's `release.json`/tagged source to the
intended merged tree. Do not assume README's one-command installer is current.

| Route | When to use it | What it establishes |
| --- | --- | --- |
| Versioned public bootstrap | A published release actually contains the intended merged work | Download/bootstrap plus installation of that release |
| Installer from an exact clean checkout/source snapshot | New work is merged but no matching release is published | Installation of merged source; public bootstrap for that source remains untested |
| GitHub Code → Download ZIP | Source only, extracted to the folder containing README/installer/scripts | Manual source install; no prepared model/cache/test-kit assets |
| Generated target test kit | A separately prepared kit has a trusted manifest/hash | Its bounded fixture tests; not a full application installation |

For the bootstrap route, use the complete release-specific command from the
verified matching `INSTALL.md`; do not invent a new URL/hash or execute a moving
branch. If only the old release exists, use the merged-source route for new
capabilities and report bootstrap coverage separately. This test task does not
itself authorize publishing a new release.

### Prepare the development checkout

Use the existing Windows Git checkout if suitable. Otherwise clone the public
repository into an approved development directory. Git is needed for the fix/PR
workflow, but should not be a prerequisite of the public installer.

```powershell
git clone https://github.com/adamcohen8/SILO.git SILO
Set-Location .\SILO
git status --short --branch
git remote -v
git fetch origin
git log -8 --oneline origin/main
```

Do not switch or pull through a dirty checkout. In a clean checkout, update with
`git switch main` then `git pull --ff-only`, verify the intended work is present,
and create `codex/windows-install-validation` (or a fresh distinct branch if it
already exists). Record `git rev-parse HEAD` and `git status --porcelain`.
If GitHub/thread history is unavailable, obtain the intended merge SHA from the
user; do not guess that merge completion occurred.

Keep the installer source free of unrelated `.py`/`.ps1` files, including files
named `... 2.py` or `... 2.ps1`. The current installer inventories matching files
from the filesystem, not just tracked files. Do not delete unknown duplicates;
use a fresh checkout/snapshot. Copy this plan separately if it was not committed.
It is not expected to be copied into the installed application payload.

## 2. Inventory and choose disposable test locations

Run the following read-only commands. Retain details locally, with personal
paths/usernames redacted from any PR summary.

```powershell
$PSVersionTable
[Environment]::Is64BitProcess
Get-ExecutionPolicy -List
Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,OSArchitecture
Get-CimInstance Win32_ComputerSystem | Select-Object TotalPhysicalMemory
Get-CimInstance Win32_Processor | Select-Object Name,AddressWidth
Get-Command curl.exe,git.exe,python.exe,py.exe,nvidia-smi.exe -ErrorAction SilentlyContinue | Select-Object Name,Source
Get-Volume | Select-Object DriveLetter,FileSystem,DriveType,SizeRemaining,Size
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits
```

Confirm x64 Windows, a fixed local NTFS volume, GPU visibility and sufficient
space. The initial target is Windows 11 Pro, RTX 4090 with 24 GiB VRAM and about
64 GiB RAM. Verify the actual machine rather than assuming it matches earlier
observations. The installer currently pins CPython **3.14.8**; previous 3.12
observations do not qualify it. Record policy/antivirus/EDR blocks as such.

Allow at least **45 GB** for the default model/cache/installation; the installer
calculates its requirement. Multiple roots, repair versions, offline copies and
additional model imports need more. Measure free space before each large copy.
Do not download all six models at once or delete unrelated caches for space.

Choose a short approved test parent on NTFS, outside OneDrive/network/roaming
storage, for example `C:\SILO-Test`. Adjust all examples to that choice. Use a
new run ID and never reuse an existing directory blindly:

```powershell
$SourceRoot = (Get-Location).Path
$RunId = Get-Date -Format 'yyyyMMdd-HHmmss'
$TestParent = 'C:\SILO-Test'
$InstallRoot = Join-Path $TestParent ('online-' + $RunId)
$OfflineRoot = Join-Path $TestParent ('offline-' + $RunId)
$EvidenceRoot = Join-Path $TestParent ('evidence-' + $RunId)
New-Item -ItemType Directory -Path $EvidenceRoot -ErrorAction Stop | Out-Null
```

Let the installer create its own private installation directories and ACLs.
Keep evidence outside immutable payloads. Inspect an existing default install
and its running processes before choosing whether to test an upgrade. Do not
uninstall Python/Codex to simulate a clean system: verify the installer uses
its own interpreter. A real no-Python fresh-machine claim needs a separate
clean Windows environment; this workstation may only establish a new-root test.

## 3. Fresh online installation and native preflight

Close SILO instances using the intended test state. For merged-source testing,
run from `$SourceRoot`:

```powershell
Set-Location $SourceRoot
.\installer\Install-Evaluation.ps1 -InstallRoot $InstallRoot -NoLaunch
```

This downloads pinned assets on the host, verifies them, prepares separate
`payload\host`, `payload\worker` and `payload\code` interpreters, and runs
mandatory native preflight before activating the version. No existing Python,
pip setup hooks, global PATH change or Codex runtime should be needed. Workers
must not download anything during inference. Record the error and stage if it
fails; preserve `.pending-*`, resumable cache and preflight evidence.

Inspect success using the actual installer paths:

```powershell
$Active = Get-Content -LiteralPath (Join-Path $InstallRoot 'active.json') -Raw | ConvertFrom-Json
$VersionRoot = Join-Path (Join-Path $InstallRoot 'versions') $Active.version
$AppRoot = Join-Path $VersionRoot 'payload\app'
$HostPython = Join-Path $VersionRoot 'payload\host\python.exe'
$StateRoot = Join-Path $InstallRoot 'state'
$Active
Get-Content -LiteralPath (Join-Path $StateRoot 'installation-preflight.json') -Raw
Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $VersionRoot 'release-manifest.json')
& $HostPython -I -B (Join-Path $SourceRoot 'scripts\install_evaluation.py') --identity-only
```

The last command's source ID must equal `$Active.source_id`. The manifest hash
must equal `$Active.manifest_sha256`. Check the installed
`evaluation-installation.json` points to this private state, and the installed
model/configuration catalogs and terminal launcher match the intended source.
Verify interpreter version/architecture using the manifest and preflight.

Expected preflight fields are all true: `complete_installed_files`,
`host_ui_imports`, `full_gpu`, `default_deny`, `cited_document_answer`,
`contained_pdf_parser`, `contained_docx_parser`, `no_remaining_grants`,
`contained_tokens`, `cleanup`. `failure` must be null and
`evaluation_preflight_passed` true. The preflight text question expects **37
crates**, unrelated to the later **108 kg** milestone. Token evidence must show
AppContainer, zero capabilities and no profile loopback exemption.
`deployment_ready` and `full_isolation_accepted` remain false.

If preflight fails, no new active version should replace an earlier good one.
When appropriate, reproduce preflight from the prepared app without editing it:

```powershell
& $HostPython -I -B (Join-Path $AppRoot 'scripts\check_evaluation_install.py') --manifest-sha256 $Active.manifest_sha256
```

That command overwrites the state's latest preflight report; preserve the
previous report first. After repair/rollback, refresh all path variables from
`active.json` before using them again.

Verify SILO desktop/Start menu shortcuts and icon. They must target this
installation's launcher and not overwrite an unrelated shortcut. If testing
multiple roots, record that they share shortcut names; check the target each
time. `-NoShortcut` is currently documented as suppressing Start menu integration,
but inspect the wrapper: it skips both shortcut locations in this revision.

## 4. Desktop and terminal smoke tests with real local inference

Launch the installed desktop:

```powershell
& (Join-Path $InstallRoot 'Start-LocalAI.cmd')
```

Wait for Ready; record cold startup time in seconds and baseline/peak GPU memory
in MiB with `nvidia-smi`. Close one client before starting another measurement.
Use synthetic sample folders or newly created synthetic Reference/Draft folders.

For the capacity example below, prepare these folders in the host PowerShell
session. If they already exist, inspect ownership/content and choose new names
instead of overwriting them. Keep the independent expected result outside the
model's grant:

```powershell
$ReferenceRoot = Join-Path $TestParent 'Synthetic Reference'
$DraftRoot = Join-Path $TestParent 'Synthetic Results'
New-Item -ItemType Directory -Path $ReferenceRoot,$DraftRoot -ErrorAction Stop | Out-Null
foreach ($Name in @('policy.txt','inventory.csv','missing-capacity.csv','invalid-quantity.csv','malformed.csv')) {
    Copy-Item -LiteralPath (Join-Path $SourceRoot ('tests\fixtures\silo-milestone\' + $Name)) -Destination $ReferenceRoot -ErrorAction Stop
}
```

The five fixture inputs contain only fictional data. Show the user the resolved
paths and enter those literal paths in SILO; the examples below assume the
default `C:\SILO-Test` parent. Do not enter `$ReferenceRoot` inside SILO.

| Check | Required behavior |
| --- | --- |
| First launch | No document grants until the user grants them; local model starts without cloud fallback |
| References | Bounded text/PDF/DOCX reads cite actual line/page/paragraph locators; no invented fact when evidence is absent |
| Draft review | Proposal stays unsaved; review shows exact text/destination/diff; separate approval writes a new copy |
| Invalidation | Editing a reviewed draft, source change, revoked grant, filename collision or replay refuses stale approval |
| Original preservation | Reference bytes/hashes and existing destination files remain unchanged |
| Follow-ups/clear | Follow-up works; Clear chat removes context and pending approvals while grants remain under host control |
| Preferences | Open/edit state AGENTS.md, restart, verify effect; preferences never expand permission |
| Cancel/close | UI stays responsive, owned work stops, no pending save survives, cleanup finishes; restart succeeds |
| Display | Scaling/resizing, long paths, Unicode, copy/paste and citations remain usable on native Windows |

For each save/revocation/source-change test, use disposable synthetic files and
record their before/after hashes. Never prompt the model to operate on real data
for a negative permission test.

Close the desktop and launch the actual terminal, not `preview_terminal.py`:

```powershell
Set-Location $AppRoot
.\Start-SILO-Terminal.cmd --plain
```

Inside SILO (paths are literal; do not quote them or use PowerShell variables):

```text
/help
/folders
/reference C:\SILO-Test\Synthetic Reference
/draft C:\SILO-Test\Synthetic Results
Read policy.txt and inventory.csv. Calculate eligible capacity in kg, explain exclusions, and cite the sources. Do not run code.
/sources
/models
/hardware
/code
```

Without accepted native code evidence, `/code` must refuse execution. Reference
and Draft grants must still work. Verify Enter sends, Alt+Enter adds a newline,
PageUp/PageDown scroll, resizing preserves text, Ctrl+C cancels and requires
restart after native cancellation, and Ctrl+D/`/quit` waits for cleanup. Test
`--scrollback` in a separate launch. Record limitations of remote-console keys
separately from application failures. Terminal control sequences from documents
or model output must display safely.

## 5. Installation lifecycle and failure cases

Close clients before installer operations. Use the same clean source and exact
cache pins. Preserve receipts and synthetic state between operations.

| Case | Procedure | Pass condition |
| --- | --- | --- |
| Idempotent rerun | Repeat the fresh command against `$InstallRoot` | Same source ID/version reused after verification; no unexpected replacement or duplicate state |
| Interrupted download | Cancel one owned install during a large download, then rerun | `.partial` retained; verified resume or explicit safe rejection; old active installation unchanged until success |
| Concurrent install | Start a second installer for the same root during preparation | Serialized or refused; no mixed transaction or competing activation |
| Offline success | Use reviewed source plus a populated verified cache, as below | No download attempts; preflight passes and the new root activates |
| Offline missing asset | Use a separate incomplete disposable cache with `-Offline` | Explicit failure, no network acquisition or activation; source cache remains intact |
| Corrupt cache | Change bytes only in a disposable test cache | Hash rejection before extraction/execution; no new activation |
| Payload drift | With SILO stopped, change/add/remove one harmless file in a disposable installed version | Desktop and terminal launch gates reject drift; do not regenerate manifest to permit it |
| Repair | Run `-Repair` against the test root | Fresh verified version; old version retained, synthetic state/preferences/exports preserved |
| Rollback | After successful repair, run `-Rollback` | Previous verified payload becomes active; state survives; changed previous payload is refused |
| Bad location | Try a disposable non-NTFS/UNC/reparse/overlong path only if available | Clear refusal, no broad ACL reset or unsafe fallback |
| Restart/lifecycle | Clean close/relaunch, then user-timed sleep/resume and reboot | Fresh verification, cleanup/reconciliation and functional retest; host connectivity preserved |

For offline installation reuse the online installer cache (verify its actual
location first):

```powershell
Set-Location $SourceRoot
$CachePath = Join-Path $InstallRoot 'cache'
.\installer\Install-Evaluation.ps1 -InstallRoot $OfflineRoot -Offline -CachePath $CachePath -NoLaunch -NoShortcut
.\installer\Install-Evaluation.ps1 -InstallRoot $InstallRoot -Repair -NoLaunch
.\installer\Install-Evaluation.ps1 -InstallRoot $InstallRoot -Rollback
```

An `-Offline` run on a connected host validates refusal/acquisition behavior.
A completely disconnected fresh install is a separate test if practicable;
do not disconnect the user's remote session to prove it. Bootstrap source
download itself requires connectivity; transfer reviewed source for offline use.
Do not corrupt the only model cache or active working install. Prefer a small
disposable asset for negative integrity tests; record exact owned paths/hashes.
No automatic uninstall/cache pruning exists: cleanup only exact test-owned
resources after preserving evidence and confirming no process/volume is active.

## 6. Native regression checks and skip accounting

Keep test writes out of installed payloads. Run source tests with the installed
host interpreter or a separately prepared matching development interpreter.
The embedded interpreter ignores ambient `PYTHONPATH` in isolated mode; use
the provided runners, which insert their source paths themselves:

```powershell
Set-Location $SourceRoot
& $HostPython -I -B .\scripts\validate_windows_folders.py
& $HostPython -I -B .\scripts\validate_windows_installation.py
.\scripts\test_evaluation_bootstrap.ps1
```

Current runners expect 14 folder tests and six ACL/staging tests with no skips.
They reject non-Windows qualification. A symlink privilege skip is incomplete
coverage, not a pass; do not elevate the entire application to erase it. The
PowerShell bootstrap fixture is synthetic and does not test live public downloads.

For focused and full source regressions, create a small local harness outside
the payload so discovery resolves the checkout correctly:

```powershell
$Harness = Join-Path $EvidenceRoot 'run-source-tests.py'
@'
import json, os, pathlib, sys, unittest
sys.dont_write_bytecode = True
root = pathlib.Path(sys.argv[1]).resolve()
pattern = sys.argv[2]
os.chdir(root)
sys.path[:0] = [str(root / name) for name in ('src', 'tests', 'scripts')]
suite = unittest.defaultTestLoader.discover(str(root / 'tests'), pattern=pattern)
result = unittest.TextTestRunner(verbosity=2).run(suite)
summary = {
    'pattern': pattern, 'tests_run': result.testsRun,
    'passed': result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),
    'failures': len(result.failures), 'errors': len(result.errors),
    'skips': [{'test': str(test), 'reason': reason} for test, reason in result.skipped],
    'regressions_passed': result.wasSuccessful(), 'deployment_ready': False,
}
pathlib.Path(sys.argv[3]).write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
raise SystemExit(0 if result.wasSuccessful() and result.testsRun else 1)
'@ | Set-Content -LiteralPath $Harness -Encoding UTF8
& $HostPython -I -B $Harness $SourceRoot 'test_model_support.py' (Join-Path $EvidenceRoot 'model-support-tests.json')
& $HostPython -I -B $Harness $SourceRoot 'test_windows_projects.py' (Join-Path $EvidenceRoot 'native-project-tests.json')
& $HostPython -I -B $Harness $SourceRoot 'test_*.py' (Join-Path $EvidenceRoot 'source-tests.json')
```

Inspect every failure and skip. Some Qt tests require writable checkout scratch
directories such as `artifacts/windows-ui`; read their setup and create only
the exact required test directories. Historical container/parser tests expect
`artifacts/isolation-evaluation/python`; source tests may skip them even after
a standalone install succeeds. Record that staging mismatch and use or develop
a source-bound native test adapter in the fix PR, without modifying immutable
installed trees or disabling skip decorators to claim a pass. POSIX-only skips
are expected on Windows. Missing optional readers are separate coverage gaps.

The pre-merge portable six-model result was 318 passes / 151 skips / zero
failures; do not use those counts as the expected native result. Full discovery
includes scripted/mocked cases even on Windows. Classify native OS observations,
real-model behavior and simulated contract tests separately.

## 7. Saved projects and finished artifacts

After basic installation works, exercise these new capabilities with one saved
synthetic project in each client. Read `/help` and the current operating guide
for precise commands.

- Create/open/close a project, restart the app and resume it. Confirm DPAPI/NTFS
  protection, bounded retained context and saved folder identity checks. Revoke
  or replace a disposable source: old retained facts/grants must invalidate.
  Pending approvals and disposable Code workspaces must not return on reopen.
- Create DOCX/XLSX/PPTX drafts from a tiny synthetic table. Review and approve
  each new artifact; inspect values, formulas where applicable, source locators,
  fonts, clipping and page/slide layout in installed Office or an independent
  local reader. Missing Office means Office compatibility remains untested.
  Linked content must not cause external fetches.
- Save/run a bounded workflow. Test a schedule only in a disposable project;
  verify it runs when that project is open, does not approve exports, and cannot
  replay an uncertain interrupted slot. Full-screen terminal scheduling and
  scrollback `/schedule tick` differ; no desktop background service is assumed.
- Back up/restore synthetic projects to a separate empty private test vault;
  verify authentication, source rechecks and disabled restored schedules.
  Account-bound backup and password recovery are different paths. Never export
  `vault.key`, policy keys or recovery passwords in a report/PR.
- Test retention/deletion only on test-created projects. Original references
  and approved outputs must survive project deletion. Avoid changing the OS
  clock to force expiry; use focused fixtures if practical expiry is unavailable.
- OCR requires its separately prepared signed offline runtime/policy. If absent,
  verify explicit unavailability and mark OCR not run; do not download a runtime
  implicitly or substitute an uncontained OCR process.

## 8. Six actual models: staged evaluation

First confirm the default Nemotron install/preflight. Then prioritize **Gemma
4 26B-A4B**, followed by **Muse Glimmer 30B**, as requested in Future Capabilities.
Test the other profiles sequentially if hardware, space and transferred weights
allow. Every model not executed must remain not run.

| Model | Exact embedded profile ID |
| --- | --- |
| Gemma 4 26B-A4B | `gemma4-26b-a4b-q4-evaluation-1` |
| Muse Glimmer 30B | `muse-glimmer-30b-q4-evaluation-1` |
| Gemma 4 31B | `gemma4-31b-q4-evaluation-1` |
| gpt-oss-20b | `gpt-oss-20b-mxfp4-evaluation-1` |
| Gemma 4 12B Unified | `gemma4-12b-q4-evaluation-1` |
| Nemotron 3 Nano 30B-A3B | `nemotron-4090-cp314-evaluation-1` |

Acquire the exact permitted files through an approved host/transfer process;
use size/SHA-256/URL from the merged `profiles/model-catalog.json`. Import must
copy and verify bytes; SILO inference must not fetch models. The `/model install`
menu also permits an explicit host download when network access is authorized.
Catalog memory
floors are candidates, not measured guarantees. Do not change quantization,
runtime, context or GPU offload to make an existing profile fit silently.

Inside SILO, with the actual transferred path:

```text
/model import gemma4-26b-a4b-q4-evaluation-1 D:\Models\gemma-4-26B_q4_0-it.gguf
/model switch gemma4-26b-a4b-q4-evaluation-1
```

Confirm immediate switching, selected ID/hash and full GPU placement. Repeat source reads,
multi-step tool calls, citations, draft review, cancellation and cleanup for
each model. Record cold load time (s), response time (s), peak VRAM (MiB), RAM
(MiB), measured throughput (tokens/s only if available), correct/incorrect facts
and malformed/truncated/tool-error behavior at fixed context limits. Unknown
measurements stay unknown. gpt-oss reasoning must stay private, survive only
unfinished tool sequences and disappear from final answers/saved history.
Muse reasoning/tool turns must complete without a premature stop.

Test the `/model` menu in full-screen and `--scrollback` modes:

| Check | Expected behavior |
| --- | --- |
| Main menu | `switch`, `install`, `remove`; number/action choices; invalid replies never call inference |
| Switch | Only installed permitted models; immediate load, exact selected ID and full GPU placement; no app restart |
| Continuity | Chat/reviews/disposable code cleared; project instructions retained; only unchanged folder identities restored |
| Failed switch | Missing/corrupt weights or insufficient hardware leave current model running; failed load restores previous model when possible |
| Install | Only missing permitted profiles; explicit pinned HTTPS host download, progress, exact size/SHA-256/GGUF, no automatic switch |
| Cancel install | Ctrl+C stops transfer/verification and removes temporary files; current model remains usable; retry works |
| Offline install | Network failure leaves no installed file; `/model import ID PATH` still works |
| Remove | No deletion before `yes`; `no`/`/cancel` preserve bytes; removal frees the managed file's space |
| Active/last removal | Owned model process and ACL leases close first; menu remains usable without a model; install/switch works afterward and after reopening |
| Application verification | New installs keep default weights in `state_root/models`; deleting them leaves the immutable payload valid |
| Legacy installation | Old payload weights cannot be deleted through the menu; repair with this source supplies removable storage |
| Menu isolation | `/back`, `/cancel` and idle Ctrl+C work; scheduled workflows wait while a menu is open or operation is running |

Retain evidence for native process cleanup, actual disk-space change, cancellation
during a stalled transfer and switching after removing the last model. Portable
fixtures establish controller behavior only. Installer caches and older rollback
releases are preserved, so their copies still consume disk space. Fresh-install
preflight expects default Nemotron weights; removal after installation is separate.

Test missing/corrupt/unapproved model import/selection with disposable files.
Selection must not silently substitute Nemotron. Recover
selection using the trusted host interpreter while SILO is closed if necessary:

```powershell
$VaultRoot = Join-Path $StateRoot 'projects'
& $HostPython -I -B (Join-Path $AppRoot 'scripts\manage_silo.py') models --root $AppRoot
& $HostPython -I -B (Join-Path $AppRoot 'scripts\manage_silo.py') select-model --root $AppRoot --state $VaultRoot --id nemotron-4090-cp314-evaluation-1
```

An enrolled organization policy can reject these profiles and is authoritative;
do not enroll/change one just to complete an embedded-catalog test. Synthetic
signed-policy fixtures do not establish organizational signing/approval.

## 9. Isolation and code execution: separate native gates

Use the full `docs/ISOLATION-VALIDATION.md` matrix: N01–N09, H01 and I01–I02.
Cover inference, graph, parser/OCR when present, permitted descendants and host
IPC. Test IPv4/IPv6 TCP/UDP, DNS, loopback/LAN relays, proxy/environment routes,
host interoperation, embedded resources, malformed/replayed IPC, cleanup and
restart/sleep/reboot/network changes. Use only approved controlled responders.
Establish reachable host positive controls and actual OS enforcement evidence;
a worker timeout or unavailable responder is not a denial pass. Preserve host
connectivity before/during/after. Mark unsupported/unavailable vectors not run.
Older 6 October observations do not qualify this interpreter/current application.

The generated-code candidate has **19** exact checks in
`windows_code_runner.BOUNDARY_TESTS`:
`token`, `inputs_readonly`, `runtime_readonly`, `outside_filesystem`,
`profile_storage`, `registry_storage`, `network_ipv4_tcp`, `network_ipv4_udp`,
`network_ipv6`, `dns`, `loopback`, `ipc`, `child_process`, `memory`, `output`,
`disk`, `timeout`, `cleanup`, `recovery`.

Start with fixed developer-authored probes, not model-generated programs:

```powershell
Set-Location $AppRoot
& $HostPython -I -B .\scripts\validate_code_boundary.py --output (Join-Path $EvidenceRoot 'code-candidate-observations.json')
$env:SILO_NATIVE_TEST_ROOT = $AppRoot
& $HostPython -I -B $Harness $SourceRoot 'test_windows_code_runner.py' (Join-Path $EvidenceRoot 'native-code-tests.json')
Remove-Item Env:\SILO_NATIVE_TEST_ROOT
```

Review native probe source first. It uses an LPAC/fixed NTFS VHD candidate;
DiskPart provisioning may fail for an ordinary user. Record that failure and
fix the provisioning design if needed; running all of SILO as administrator is
not evidence of its intended boundary. Candidate observations and these tests
cover only part of the matrix and must not enable `/code`.

Only a complete independently reviewed acceptance record for the exact release,
Windows/toolchain/policy, plus its independently trusted digest, may enable code.
Use the documented `--acceptance` and `--acceptance-sha256` launcher arguments
then. If no qualified record exists, record coding as blocked by acceptance
and continue the independent installation/document/model tests.

### First real-model coding milestone, after acceptance

Use the five synthetic Reference inputs prepared in stage 4 (verify their
hashes still match the frozen fixtures). Keep `expected.json` with the
independent reviewer. Grant a new empty Draft destination, then accepted
`/code`; use that destination's actual path in the checker command below.

Ask the actual local model to read and stage the five sources, write
`analyze.py` and `tests.py`, run normal/negative/test cases, inspect errors and
produce `results.json`, `capacity.png` and a sourced `report.md`. The separate
offline runner has the standard library and `silo_plot.write_bar_chart`; it
does not provide pip, NumPy or matplotlib. Maximum eight runs; default limits
are 60 s/run, 512 MiB memory, 16 MiB fixed disk, 64 KiB combined output and one
process. Do not relax them without new bound acceptance.

Independent result: **108 kg**, with SYN-001 = **48 kg**, SYN-002 = **60 kg**;
SYN-003 retired and SYN-004 quarantined are excluded. Missing capacity, negative
quantity and malformed CSV must fail explicitly. Inspect chart pixels/labels,
units and actual report citation. Include a separate controlled-error task
showing the real model diagnosing/repairing a failure and rerunning current
scripts. Review/approve the exact artifact ZIP through the host.

```powershell
& $HostPython -I -B (Join-Path $AppRoot 'scripts\check_code_milestone.py') 'C:\SILO-Test\Synthetic Results\capacity-artifacts.zip'
```

Bind the ZIP to the trusted review hash and selected model ID/hash. The checker
rejects simulation and verifies fixtures/results/runs/artifacts, but does not
independently establish model authorship, containment or organizational approval.

## Terminal updates: native validation

Read [TERMINAL-UPDATES.md](docs/TERMINAL-UPDATES.md) for the release protocol,
host trust assumptions and recovery limits. The published update pair is:

| Role | Release | Source commit | Sequence |
| --- | --- | --- | ---: |
| Earlier installed release | `evaluation-2026.10.11-silo.1` | `f018f0d62f2baefaebf71c947b1bf8678ca9369f` | 1 |
| Current update target | `evaluation-2026.10.11-silo.2` | `f7995d48cdbfecc15145e2e91f2d1ddb6dd80e68` | 2 |

Both releases are published; no new publication is required for this matrix.
Anonymous downloads, GitHub asset digests, tagged source and production updater
discovery from sequence 1 to 2 were verified. The complete native interactive
pair update/rollback matrix remains pending. Do not publish or mutate a test
release implicitly; any additional publication needs release-owner authorization.
The 10 October installer without the updater requires a one-time bootstrap
upgrade. The repeat report's Git-source-to-sequence-1 activation and repaired
source terminal tests do not establish this published-pair matrix.

1. Install the earlier release. Launch `Start-SILO-Terminal.cmd`. Create an
   explicitly saved synthetic project with a completed cited exchange, folder
   grant and task instructions. Select a supported model, and record private
   vault/model hashes, selection and active version/manifest. Remove a different
   installed model; it must stay absent after the update.
2. Verify sequence 2 is still latest stable with matching generated
   `release.json`/source ZIP and GitHub API SHA-256 digests. Observe startup
   notification and `/update check`. Verify background checks leave inference
   usable and transmit only public release requests from the host.
3. Press Ctrl+U during inference, with unsent input, a model menu, an unsaved
   draft and an open code workspace. Each must preserve the work and block
   installation. Resolve each condition and verify Ctrl+C during source
   download leaves the current terminal running. An unretained chat must
   require explicit `/clear`, never become retained automatically.
4. With empty input and idle work, press Ctrl+U. Record owned process cleanup,
   parent exit, updater window, native selected-model preflight, version
   activation and restarted Ready. Verify selected weights and selection are
   unchanged, project/instructions resume with source checks, removed weights
   remain absent, and a cited synthetic request works. Inspect the private
   result/preflight receipt and `active.previous.json`.
5. Repeat with `--scrollback --plain`, a smaller selected model, no selected
   model, and an enrolled policy with `--required-policy-key-sha256`. Preserve
   the anchor across restart; expired/revoked/substituted policy must fail
   preflight and keep the old version. With no model, verify parser checks
   pass while GPU/inference checks remain explicitly not applicable.
   Use an actual interactive console for the real Ctrl+U path. Separately test
   redirected scrolling input/output at sequence 2 and strict legacy encoding:
   menu/quit, resumed grants, a sourced answer with narrow spaces and intact
   citation tags. Sequence 1's redirected prompt failure is historical and
   expected; do not substitute redirected automation for the interactive path.
6. Exercise offline/blocked HTTPS, missing GitHub digest, corrupt cache/staged
   ZIP, changed publication after notification, low disk, concurrent installer
   or second SILO session, preflight failure, and activation/launch failure.
   Keep the old active version and verify recovery without resurrecting drafts
   or code acceptance. Use synthetic fixtures/fault injection, not real user
   files. Repeat a claimed ticket: it must not execute a second installation.
7. Verify previous/manual rollback, interrupted-update recovery, and reboot.
   Confirm neither update networking nor restarting creates worker external
   connectivity; rerun the release's native isolation matrix. Record real
   outcomes and unavailable cases separately. Portable mocked activation tests
   do not establish NTFS lock/ACL, AppContainer/GPU or native restart behavior.

## 10. Evidence, fixes and the PR handoff

Keep a local result ledger with one row per stage/case and statuses **passed,
failed, blocked, not run, skipped**. Record expected/actual behavior, exit status,
source commit, installation source ID/manifest hash, model/runtime/profile,
Windows build/driver/interpreter, start/end times, cleanup and local evidence
path/hash. Preserve the first failure before patching. Do not rewrite earlier
failed results as passing after a fix; record the new commit/run separately.

Create a concise `windows_test_report.md` in the development checkout when
testing concludes. Include only reviewed synthetic/metadata evidence suitable
for the public repository. Keep raw machine inventory, personal paths, process
command lines, prompts/logs, packet captures and state/key material local. Never
commit model weights, wheel caches, installed payloads, project vaults, private
keys, passwords or `context.md`.

For each confirmed defect:

1. Identify whether it is acquisition, PowerShell/paths/ACLs, interpreter/DLLs,
   vendoring, GPU/model startup, preflight, UI/backend, state, containment or
   lifecycle. Read the actual failing source, not just a generic error message.
2. Make the smallest source fix in the dedicated branch. Add a regression test
   where it verifies the failure; preserve pins and fail-closed behavior.
3. Run the focused test, reinstall/repair from the revised clean source, and
   repeat the native failing operation. A passing mocked test alone does not
   close a native bug. Refresh active/path/manifest identities after reinstall.
4. Once fixes settle, run relevant broader regressions and `git diff --check`.
   Review every skip and the exact final diff. Stage only intended source/tests
   and the sanitized report; never use a blanket add over local test artifacts.
5. Help the user submit a PR against `adamcohen8/SILO` main with the trigger,
   before/after behavior, final tested SHA/configuration, native evidence,
   failure recovery and remaining coverage. This handoff anticipates a PR;
   confirm the user's publishing scope in the Windows chat before pushing or
   opening it if not already authorized there. Do not merge/release implicitly.

If a fix changes the runtime, weights, adapter, toolchain or boundary, review
which pins and acceptance evidence need regeneration and independent review.
Do not carry forward an acceptance record for a different configuration.

Finish with distinct outcomes: (a) installation/lifecycle, (b) desktop/terminal
workflows, (c) each real model, (d) full network/IPC isolation, (e) native coding
milestone, and (f) remaining signing/licensing/organizational gates. A successful
synthetic Windows install is useful evidence; it does not authorize CUI use.
