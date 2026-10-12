# SILO Windows validation handoff

Updated 11 October 2026 for the long-work and coding implementation. Run from
current GitHub main **after this PR is merged**. This is a procedure, not evidence.
The Mac implemented and tested portable contracts; it did not qualify native
Windows, real inference, code execution or CUI use. The user will separately tell
Windows Codex to begin. Preserve historical `windows_test_report.md` observations.

## Instructions for Windows Codex

Read `AGENTS.md`, this file, `README.md`, then:

- `docs/SILO-LONG-WORK-AND-CODING.md` for implemented behavior and remaining work.
- `docs/SILO-SECURITY-HARDENING.md` for the actual preparation/enrollment path.
- `docs/SILO-MODEL-SUPPORT.md`, `profiles/model-catalog.json`, and
  `docs/SILO-NEMOTRON-ADDITIONS.md` for exact model assets/defaults.
- `docs/ISOLATION-VALIDATION.md`, `docs/SILO-EXECUTION-BOUNDARY.md`,
  `docs/SILO-PHASE-2.md`, and `docs/SILO-OPERATIONS.md` for native gates.

Use only public/synthetic inputs. Inspect source and the machine before each
stage. Record the first failure, fix confirmed source defects on a dedicated
`codex/` branch, reinstall the changed source, and repeat the failing native
operation. Preserve unrelated work and all earlier receipts. Do not patch the
installed immutable payload, bypass execution policy, relax a boundary or carry
forward acceptance for changed bytes. Missing prerequisites are **blocked**,
not passes. Do not commit keys, vaults, model binaries, personal paths/raw logs,
packet captures or private `context.md`.

The currently published unsigned installer is an older artifact. It cannot test
these source changes. Current `Install-Evaluation.ps1` requires `-PrepareOnly`
and prepares an inactive candidate; it does not activate an application, create
shortcuts, run preflight or produce native acceptance. A merge does not publish
an installer release. Do not use historical `active.json` instructions as the
current enrollment route.

## 1. Freeze source, hardware and evidence locations

Inspect an existing checkout before updating. Use a clean checkout/worktree if
it contains concurrent changes or duplicate `... 2.py` files. In a clean checkout:

```powershell
git fetch origin main
git switch main
git pull --ff-only
git rev-parse HEAD
git status --porcelain
git switch -c codex/windows-long-work-validation
$SourceRoot = (Get-Location).Path
$RunId = Get-Date -Format 'yyyyMMdd-HHmmss'
$TestParent = 'C:\SILO-Test' # Substitute an approved short local NTFS parent.
$InstallRoot = Join-Path $TestParent ('candidate-' + $RunId)
$EvidenceRoot = Join-Path $TestParent ('evidence-' + $RunId)
New-Item -ItemType Directory -Path $EvidenceRoot -ErrorAction Stop | Out-Null
```

Record the actual commit, source ID, Windows build, 64-bit interpreter, CPU,
physical RAM, all GPUs/driver/VRAM, NTFS volume identities, network/VPN state,
existing SILO processes and protected policy state. Keep raw inventory local.
Do not uninstall Python/Codex or delete an existing installation. A new-root test
on a machine with Python does not establish no-Python fresh-machine acceptance.
Choose approved reference/draft roots outside OneDrive/network/roaming/private
state, and freeze synthetic input hashes.

## 2. Prepare and enroll the current candidate

From source, as the ordinary account, subject to the approved PowerShell policy:

```powershell
Set-Location $SourceRoot
.\installer\Install-Evaluation.ps1 -InstallRoot $InstallRoot -PrepareOnly -NoLaunch -NoShortcut
```

Record the printed inactive candidate directory and its preparation manifest.
Use the actual named directory to resolve `payload\app`, `payload\host\python.exe`
and private state; do not guess a version ID or reuse an older executable.
Inspect candidate identity before executing its interpreter. Verify pinned
host/worker/code Python assets, complete inventory and private/public separation.
Missing cache assets, corrupt files, low disk and interrupted preparation must
preserve earlier versions/state and never produce an active record.

Follow **Preparation and managed enrollment** in `SILO-SECURITY-HARDENING.md`:
protect the named release under Program Files, correct state locations before
signing, verify the independent release inventory/anchors, register/test the audit
source, enroll signed model policy, authenticated SBOM/advisory/maintenance review,
and approved storage roots. Use existing independently approved keys/fingerprints;
do not create organizational trust or invent a technical pass. Record which
prerequisites are available. A controlled administrator-enrolled candidate can
collect evidence, but normal sessions must refuse missing technical acceptance.
Candidate privileges never qualify ordinary-user containment.

For each actual model, run the current controlled validator only after candidate
enrollment, using a dedicated existing approved synthetic fixture root:

```powershell
& $HostPython -I -B (Join-Path $AppRoot 'scripts\check_evaluation_install.py') `
  --manifest-sha256 $PreparationManifestSha256 --candidate `
  --fixture-root $SyntheticFixtureRoot --model-id $ExactModelId
```

Resolve the variables from recorded candidate metadata/enrollment, not historical
examples. Inspect this script's actual success fields; CPU placement is distinct
from CUDA placement. Preserve each report before another validator invocation.
A failure must not activate the candidate or suppress the failure in a receipt.

## 3. Run source regressions with accurate skip accounting

The installed embedded host interpreter ignores ambient PYTHONPATH; use the
source runner, whose arguments explicitly select the checkout:

```powershell
& $HostPython -I -B (Join-Path $SourceRoot 'scripts\run_windows_regressions.py') `
  --source $SourceRoot --pattern 'test_long_work.py,test_tui_polish.py,test_tui_security_integration.py,test_code_workspace.py,test_model_support.py,test_projects.py' `
  --output (Join-Path $EvidenceRoot 'focused-regressions.json')
& $HostPython -I -B (Join-Path $SourceRoot 'scripts\run_windows_regressions.py') `
  --source $SourceRoot --output (Join-Path $EvidenceRoot 'full-regressions.json')
```

Review every skip and error. POSIX-only broker fixtures intentionally skip on
Windows; their Mac pass is not native NTFS/CNG evidence. Run applicable native
folder, projects, installation, code-storage and UI tests under their documented
fixtures. `SILO_NATIVE_TEST_ROOT`, when a test explicitly needs it, must name the
prepared/protected synthetic installation. Never point a destructive fixture at
an operational root. Record successful methods directly rather than subtracting
skip subtests from test counts.

The old `validate_windows_ui.py` assumes writable source and references in private
state. Replace incompatible validator assumptions with managed paths, approved
synthetic roots, the exact selected model and actual CPU/GPU placement. A mocked
UI pass cannot close a native validator/ACL failure.

## 4. Test Lightning defaults and actual model behavior

Fresh source preparation on Windows x64 with >=32 GiB RAM and >=24 GiB nominal
VRAM on the first NVIDIA GPU should choose
`nemotron35-lightning-30b-q4-evaluation-1`. Verify exact pinned weight size/hash,
selected-state record and full GPU placement. Existing saved selections must
win. Test lower-capacity/CPU hardware only where available; otherwise retain
portable hardware-selection coverage and mark the native cases not run.

Use all hardware-compatible profiles from the actual catalog, including Nano,
Cascade 2, Lightning, Muse, gpt-oss and compatible Gemma profiles. Super requires
its documented first-GPU/RAM capacity and complete shard pins; do not force it
onto insufficient hardware or claim a CPU fallback. Record model/runtime/adapter,
context, sampling, peak RAM/VRAM, latency, correctness and human intervention.
The previous document-task winner is not proof of coding quality.

Repeat the 37-crate preflight and sourced document/draft tasks. Exact citations
must correspond to successful reads; named draft requests need actual proposals,
not an assistant's assertion that it saved a file. Inspect actual content, save
only through host review and preserve the earlier Muse/gpt-oss failure cases.

## 5. Long-work, context and interruption acceptance

Test terminal live display on/off, full-screen and scrollback, then the desktop
shared backend where applicable. Inspect actual server flags/requests locally:
interactive generation omits `max_tokens`; prediction/reasoning quotas are
`-1`. Cascade's template must accept its disabled reasoning quota. No raw private
reasoning may appear in display, task journal, persisted conversation or audits.

Use a saved synthetic project and independently prepared numbered notes/pages:

- Complete a meaningful task requiring >16 model calls and >48 distinct tools.
  Cross 128 display/RPC frames and the previous whole-request deadline while
  producing real progress. Verify objective retention, complete tool pairs and
  source re-reading after several context rollovers; correctness must be checked
  against the independent notes, not inferred from call counts.
- Produce output beyond the old 2,048-generation/512–1,024-reasoning quotas where
  the actual model supports it. Record EOS, context-boundary or other finish
  reasons. Complete text marked `length` must continue and remain partial until
  accepted. A truncated tool request must not execute, even once.
- Test a silent model, EOF/malformed SSE, an oversized frame and repeated identical
  tool failures. Healthy progress should continue; true stalls/errors should
  stop clearly. Single-message/context/physical resource limits still apply.
  Larger output should use paginated files/sections rather than disabling guards.
- Run an explicit fixed-budget benchmark separately and record the limits. Do
  not impose those benchmark limits on normal user sessions.
- Ctrl+C during thinking, tool read, code edit, accepted execution and cleanup;
  inspect owned process/job/pipe shutdown before recovery. Repeated cancellation,
  crash, sleep/resume and reboot must not resurrect authority or uncertain work.

## 6. Task journal, snapshots, retention and recovery

Use `/project new`, then `/task new OBJECTIVE`, `/task show`, `list`, `pause`,
`resume ID`, `continue`, `stop`, and a new task. Reopen the project/application;
verify complete objectives/events persist encrypted and no pending approval or
process resumes. The active context may be shorter than the retained journal.

Inject controlled failures before intent, after intent/before action, after
action/before result, and between event/head publication. An interrupted intent
or orphan checkpoint must become **unknown**. Verify owned execution has ended,
inspect outputs/preimages and use explicit `/task reconcile ID`; reconciliation
must skip the uncertain action. A failed cleanup must block reuse. Never delete
an unknown lease or accept an operator assertion as native cleanup proof.

Test grant revocation/replacement, source edits/removal, instruction/model changes,
policy revocation, expiry and two clients. Changed authority/source bytes must
block resuming the old task. Historical opaque folder IDs must remap only through
matching native grant identities. Concurrent requests must not interleave tasks.

`/code-save` then switch/reopen the model/project. `/code-restore edit` must restore
files and repository preimages with execution disabled; qualified restoration
requires fresh acceptance. Changed source/blob/grant/policy must fail before
publishing bound restored state. `/code-restore files` may recover file bytes
after source/grant drift only with execution disabled, no inputs/repository
binding/source authority/runs/approvals; verify a new task re-reads current sources. Verify Windows CNG/DPAPI encryption, ciphertext
relocation/tamper rejection, account-bound and password-protected recovery,
archive collisions and limits. Restored schedules stay disabled. Expiry/prune and
project deletion must remove task heads/events/codework/blobs while preserving
original documents and approved outputs. `/clear` clears chat/reviews; deleting
the saved project is the operation that removes its task/code records.

## 7. Repository editing and patch/Git review without execution

Copy `tests\fixtures\coding-repository` into a new approved synthetic Reference
root; keep a separate untouched oracle. Include inert synthetic `.env`, `.git`,
linked/aliased/recalled and deep/large-directory cases under controlled fixtures.
Use an empty approved Draft folder. In the terminal:

```text
/project new Synthetic repository repair
/reference ACTUAL_SYNTHETIC_REFERENCE_PATH
/draft ACTUAL_EMPTY_DRAFT_PATH
/code-edit
/repository import ACTUAL_REFERENCE_ID
```

Ask SILO to diagnose and repair the first-row defect in `calculator.py` while
preserving `test_calculator.py`. Editing-only mode must explicitly report that
it has not executed code/tests. `run_python` remains denied. Original hashes and
Git metadata must remain unchanged. Test paginated inventory/line reads/search,
new files, unique-preimage patches, hash mismatches, delete/rename collisions,
case aliases, unsupported/secret paths and partial import refusal.

Inspect `/repository status`, `diff`, `patch`, then:

```text
/repository export ACTUAL_DRAFT_ID repair.patch
/review ACTUAL_PROPOSAL_ID
/approve ACTUAL_PROPOSAL_ID
```

Verify no file exists before approval, exact reviewed bytes afterward, collision
and replay denial, dependency drift rejection and no original overwrite. In a
separate disposable host Git branch/copy, run `git apply --check repair.patch`,
then inspect/apply only the reviewed patch. Test additions/deletions and files
with/without a final newline. This host operation does not prove SILO ran tests
or implemented in-place application. Native held-handle transactional repository
application, Git commit/push UI and language-server indexing are not available.

## 8. Qualify offline Python before actual generated execution

Ordinary operational runs must not invoke DiskPart or mount/detach a VHD.
Follow the explicit administrator preparation in security hardening:
`provision_code_volume.py --user-sid EXACT_TARGET_ACCOUNT_SID --size-mib 16`.
It creates only a new owned pool, accepts no physical-disk selector and does not
replace an existing record. Inspect image/GUID/serial/pool/account/capacity and
ACLs. Preserve provisioning failures; running the whole app as administrator
cannot substitute for the ordinary-user test.

Run `validate_code_boundary.py --output NEW_LOCAL_REPORT` from the protected
candidate using its host interpreter. It runs fixed developer-authored code and
provides candidate observations only. Test every actual `BOUNDARY_TESTS` entry:
`token`, `inputs_readonly`, `runtime_readonly`, `outside_filesystem`,
`profile_storage`, `registry_storage`, `network_ipv4_tcp`, `network_ipv4_udp`,
`network_ipv6`, `dns`, `loopback`, `ipc`, `child_process`, `memory`, `output`,
`disk`, `timeout`, `cleanup`, `recovery`. Use reachable controlled host positive
controls and OS evidence; missing services/timeouts are not denial passes.

Collect the separate 23-check technical matrix from `machine_security`, all
applicable network/IPC vectors in `ISOLATION-VALIDATION.md`, and the release
readiness matrix. Cover every role and supported transport, audit failure,
expiry/revocation/drift, route/VPN/interface changes, crash/reboot/sleep, storage
leases and CNG recovery. Independently reviewed/signature-protected exact release,
OS, runtime, volume and resource evidence is required. Candidate observations,
portable passes and caller-authored JSON cannot enable `/code`.

Only after ordinary-user qualification/enrollment, use `/code`, repeat the
unchanged repository four-test oracle and the five-source `silo-milestone` task:
108 kg total, SYN-001 48 kg + SYN-002 60 kg, retired/quarantined exclusions,
explicit missing/negative/malformed-input failures, actual tests, inspected JSON,
chart and sourced report. Check the host-reviewed ZIP with
`scripts/check_code_milestone.py ARTIFACT_ZIP`. Exercise >8 actual accepted runs;
per-run limits and cleanup remain unchanged, and old omitted run receipts must
be identified in exports. Add real error diagnosis/repair and re-execution.

## 9. Offline toolchain preparation and broader build status

With an inert or independently reviewed offline bundle, test
`prepare_toolchain_bundle.py --source PATH --manifest-sha256 INDEPENDENT_DIGEST`
and optional `--destination NEW_PATH --command COMMAND_ID --entrypoint FILE`.
Verify exact inventory/imported bytes, manifest/payload drift, extras, links,
existing destination, unsupported command/path and absent review rejection.
This operation previews data; it never executes a package installer or compiler.
`activate` must remain denied, including for caller-authored passed JSON.

NumPy/npm/Cargo/C++ execution, an offline dependency resolver and a multi-process
native/VM runner are **not implemented/qualified** by this PR. Do not loosen the
inference/parser boundary, increase its child-process allowance, or mark these
capabilities tested. Report the concrete next implementation/integration needs,
including pinned package closure, licenses, immutable environment, bounded
process-tree/filesystem/network/resource controls and independent acceptance.
Any future implementation needs its own reviewed runner/profile and evidence.

## 10. Results, fixes and handoff

For each case record **passed, failed, blocked, not run or skipped**, expected and
actual result, exit status, tested commit/source ID, release-envelope/preparation
hashes, model/runtime/adapter, OS/driver/interpreter, time, resource use, human
intervention, cleanup and local evidence path/hash. Separate fixture/simulated
contracts from actual local-model/native results. Use the cases/metrics in
`tests\fixtures\coding-benchmark-cases.json`; do not score an unexecuted test pass.

Create a sanitized `windows_test_report.md` describing final tested configuration,
preserved first failures, focused fixes, retest evidence, every remaining native
case and blocked broader feature. Fix confirmed defects in source, reinstall,
and rerun the exact native trigger; then relevant/full regressions and diff
review. Stage only intended source/tests/sanitized report. PR/push/merge scope
must follow the authorization in the Windows chat; this document alone does not
authorize publishing machine state or new releases. Return distinct outcomes for
preparation/enrollment, documents/UI, long work/recovery, editing/patches,
qualified execution, actual model coding quality and remaining organizational
signing/licensing/CUI prerequisites.
