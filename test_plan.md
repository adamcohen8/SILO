# SILO Windows validation handoff

Updated 11 October 2026 for offline environments, build execution, reviewed
repository mutation, private-copy Git and language navigation. Run from
current GitHub main **after this PR is merged**. This is a procedure, not evidence.
The Mac implemented and tested portable contracts; it did not qualify native
Windows, real inference, code execution or CUI use. The user will separately tell
Windows Codex to begin. Preserve historical `windows_test_report.md` observations.

## Instructions for Windows Codex

Read `AGENTS.md`, this file, `README.md`, then:

- `docs/SILO-LONG-WORK-AND-CODING.md` for implemented behavior and remaining work.
- `docs/SILO-CODING-WORKFLOW.md` for the new commands, receipt schemas and SDK limits.
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
git switch -c codex/windows-coding-workflow-validation
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
with/without a final newline. This external host operation does not prove SILO
ran tests or qualified its new repository/Git operations. Test those source
candidates separately using the matrices below; no Git push/merge tool is exposed.

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

## 9. Offline environments and the separate build boundary

With an inert or independently reviewed offline bundle, test
`prepare_toolchain_bundle.py --source PATH --manifest-sha256 INDEPENDENT_DIGEST`
and optional `--destination NEW_PATH --command COMMAND_ID --entrypoint FILE`.
Verify exact inventory/imported bytes, manifest/payload drift, extras, links,
existing destination, unsupported command/path and absent review rejection.
This operation previews data; it never executes a package installer or compiler.
`activate` must remain denied, including for caller-authored passed JSON.

The legacy `ToolchainBundle.activate` must remain denied. The next implementation
uses `OfflineEnvironment` and `WindowsBuildRunner`, not inherited Python/inference
acceptance. It implements data-only preparation, exact supplied wheel closure,
fixed SDK adapters and a separate LPAC process-tree candidate; **native acceptance
has not passed**. Never fabricate/enroll passed records or relax the older workers
to get execution. Obtain independently approved prerequisites, or report blocked.

### 9.1 Prepare real Python/NumPy bytes without executing them

Use an independently inspected host interpreter and exact reviewed source. Choose
an existing ordinary cache and new target directories outside OneDrive, roaming
and private state. Compare the profile SHA with the reviewed source artifact:

```powershell
$HostPython = Join-Path $CandidateRoot 'payload\host\python.exe' # Actual verified candidate root.
$PreparationProfile = Join-Path $SourceRoot 'profiles\windows-python-numpy-build.json'
$PreparationHash = (Get-FileHash -LiteralPath $PreparationProfile -Algorithm SHA256).Hash.ToLowerInvariant()
$AssetCache = Join-Path $TestParent 'reviewed-asset-cache'
$NewEnvironment = Join-Path $TestParent ('numpy-prepared-' + $RunId)
& $HostPython "$SourceRoot\scripts\prepare_numpy_environment.py" --profile $PreparationProfile --profile-sha256 $PreparationHash --cache $AssetCache --destination $NewEnvironment --online
if ($LASTEXITCODE -ne 0) { throw 'NumPy preparation failed' }
$EnvironmentHash = (Get-FileHash "$NewEnvironment\silo-environment.json" -Algorithm SHA256).Hash.ToLowerInvariant()
& $HostPython "$SourceRoot\scripts\prepare_offline_environment.py" --source $NewEnvironment --manifest-sha256 $EnvironmentHash --operation test --entrypoint test_numpy.py
```

Explicit online acquisition is a host preparation step. Repeat into another new
directory without `--online`, using the complete cache; require identical manifest
and payload hashes. Test wrong pins, truncated archives, wrong CP/ABI/platform
wheels, missing/conflicting transitive requirements, environment markers, direct
URLs/extras, DLL/executable drift, extra files, alias/link/reparse paths, destination
collision and interrupted copy. No target interpreter, pip/package hook or generated
program may execute during preparation. Report actual wheel METADATA/licenses,
bundled native libraries and hashes; package names alone are not closure evidence.

Licensing and administrator-protected deployment are separate. Changing a manifest
review field changes its digest. Independently sign/approve that final exact digest,
protected roots and closure. Prepare/enroll the signed expiring environment registry
using `enroll_coding.py --kind environment --signed-record ACTUAL_INDEPENDENT_RECORD`.
Do not grant a worker writable access to runtime/model/release/SDK roots.

### 9.2 Qualify every exact build environment

Provision a new approved bounded NTFS pool for the accepted `BuildPolicy`, recording
account, volume/GUID/serial/capacity and ACLs. The default build profile permits
eight processes, 180 s, 2,048 MiB aggregate job memory, 256 KiB combined output and
64 MiB workspace. An existing smaller pool is a different configuration; provision
or qualify explicitly, never rewrite records to claim larger capacity. Preparation
is an explicit administrator action; ordinary launches must never run DiskPart.

Inspect the actual `BUILD_CHECKS` constant and require all entries, separately from
the original Python receipt. Use fixed developer-authored probes first through
trusted candidate validation, preserving observations and OS positive controls.
Do not expose the private candidate method to model tools or ordinary callers.
Record each expected/actual result and raw local evidence hash:

- LPAC token, zero network capabilities, private registry/profile storage and
  desktop/IPC controls; parent and every descendant retain the same restrictions.
- IPv4 TCP/UDP, IPv6, DNS, loopback, IPC and outside-filesystem denial with reachable
  controlled positive controls; no original folder, credential, user profile,
  inference/parser process or runtime/config storage authority.
- Children/grandchildren, process limit, child escape/breakaway attempts, concurrent
  memory allocations and **aggregate** job memory, combined stdout/stderr flood,
  disk/caches, timeout, Ctrl+C and a root process that exits while children retain
  pipe handles. All owned jobs/handles must be gone before outputs return.
- Immutable SDK/input trees, package/DLL closure, changed release/OS/SDK/policy/volume,
  expiry/revocation/anchor substitution, unsigned/incomplete/caller-authored receipts.
- Cleanup after compilation, syntax failure, successful/failed tests, startup
  failure, interruption/reboot and excessive output inventories. Specifically
  verify the support library is under `work\silo_plot`, is read-only and is removed
  with the owned work tree. Unknown cleanup must retain a marker/lease and block
  new runs; do not delete it merely to obtain a pass.

Independent build acceptance binds exact release, OS, environment ID/hash,
bootstrap/plot hashes, volume identity and resource policy. Enrollment uses
`--kind build`; ordinary `/code-build ENV_ID` must reject missing/expired/mismatched
acceptance. After actual qualification, test `/build run|test|check ENTRY`, NumPy
import/native DLLs, array calculations and unchanged unittest oracles. Check that
nonzero exits remain failed even with a printed success claim. Inspect bounded
feedback and reviewed artifacts; caches/binaries must not become saved authority.

### 9.3 Exercise the other fixed adapters independently

Use `inventory_build_environment.py`, `assemble_build_environment.py` and
`prepare_offline_environment.py` on pre-acquired reviewed SDKs, following the new
workflow document. Record complete inventories, fixed commands, package/vendor
closure, notices, licenses, required runtimes and native dependencies. No pinned
Node/TypeScript/Cargo/Clang distribution or server is shipped by this source PR;
provide reviewed assets before testing. Their prepared descriptors cannot inherit
Python/NumPy acceptance or download missing components during tasks.

For Node test run/test/check with addons disabled; TypeScript check/build; Cargo
frozen/offline check/test/build/run with a complete vendor tree and bounded build
scripts; Clang syntax/build and optional pinned driver compile/run/test. Confirm
entrypoints beginning with `-` stay literal paths, host PATH/proxy/credential
variables are absent, absent dependencies fail offline, and every descendant stays
contained. Preserve unsupported project configurations as limitations. Repeat the
entire build matrix for each environment, not just a happy-path compilation.

## 9A. Native reviewed repository application and recovery

Run `tests/test_windows_repository_mutation.py` on an approved ordinary local NTFS
fixture. These tests observe native sharing/publication; they are not independent
acceptance. Add controlled namespace/race/crash cases and obtain the separate
`repository-apply` capability before public in-place application. Use Reference
and writable target copies with identical frozen preimages. Read-only grants,
unreviewed/replayed/wrong-digest transactions and source/target drift must deny.

Test add/edit/delete, nested parents, newline variants, case aliases, hardlinks,
reparse/offline/cloud recall, volume changes, revoked grants, second writers and
target rename/replacement between metadata inspection and file-ID reopen. No data
read may recall a cloud file or follow a changed target. Concurrent creation and
changed foreign bytes must be preserved. Test backing up the old name before
publication, failure to publish/restore, a crash after each journal write and each
kernel effect, partial temporary writes and per-file interruption in a large set.

Exercise `/repository prepare`, `review`, exact-digest `apply`, `inspect`,
`transactions`, explicit `reconcile ... keep|rollback`. Restart/reopen the project,
restore the same identity-verified writable grant and a fresh editing-only code
workspace, then reconcile without restored approval. Recovery may retire only
receipted backup/temporary identities with expected bytes (or a recorded temporary
prefix). Refuse substituted remnants/foreign edits. Record remaining empty parent
directories and unknown outcomes honestly; a multi-file set is not atomic.
Verify encrypted backup/recovery/GC retain required blobs and journals, project
deletion removes private recovery records, and original user files stay preserved.

## 9B. Native private-copy Git

Prepare the complete independently reviewed Git distribution under the signed
managed release's `payload\git`. Enroll its exact executable pin and separate
`git-host` receipt for `private-git-lpac-1`, including the current code-volume
record digest and fixed resource/snapshot policy; caller PATH or a user-writable Git
install must not work. The receipt must include every check in `git_workflow.py`.
Use a normal existing branch on a writable synthetic copy within the 64 MiB,
768-node snapshot limits. Report larger/linked/submodule/unborn/detached cases as
unsupported rather than relaxing the profile.

Test status/diff/prepare/commit/discard. Prove Git parses only the owned LPAC copy:
the original folder receives no worker ACL/mount. Hooks, external diffs/textconv,
filters, includes, signing helpers, credential commands, remotes/network, outside
paths, helper children and oversized/malformed metadata must not gain authority.
Record actual process-tree/filesystem/network/memory/disk evidence, positive
controls and protected SDK handles. Verify complete SDK file pins before launch.

Prepare only selected literal paths and explicit author/message. Original staging
must remain unchanged until approved publication; existing staging is refused.
Review binds tree, parent, branch, patch and paths; test mutable request objects,
source/index/HEAD/loose-ref/packed-ref races, source changes after private snapshot,
wrong digest, consumed review replay and malformed compressed/hash-mismatched
objects. Publish verified loose objects first, reviewed index next, branch last.
Native HEAD/config/packed-ref leases and exact branch preimages must protect the
final compare. Inject interruptions at every publication step; inspect HEAD/index
and retained objects instead of automatically committing again. No push/merge runs.

Exercise cancellation before/at launch, blocked pipes, container/profile cleanup
failure and crash/unknown volume lease. `/git discard`, a non-Git command, model or
project change and application exit must revoke the review/remove only owned copy.
The shared volume must be available for subsequent code execution after successful
cleanup. Failed cleanup must block it until inspected administrative reconciliation.

## 9C. Built-in navigation and contained language servers

Exercise `/navigate` and model `code_navigate` on Python and JS/TS/Rust/C/C++ source:
symbols, definitions, name references, syntax errors, UTF-8 names, file edits/
deletions, incremental SHA reuse, >128-file inventory pages, >100-result pages,
oversized/partial files and permission drift. Built-in lexical/name-occurrence
results must not claim semantic binding resolution. No import/source execution.

Provide a reviewed server `lsp` command/dependencies inside each actual SDK and
obtain separate exact-environment `language-service` acceptance. Test real servers
supporting the client's documentSymbol/definition/references/pull-diagnostic
operations via `/language ACTION PATH LINE COLUMN` and `code_semantic`. Server
operation errors remain failures, not empty successful findings.

Verify private inherited pipes, read-only disposable tree, no host grants/network,
UTF-16 source positions, frame headers/duplicate lengths/wrong IDs, unsupported
encodings, server requests and external URI/path traversal, oversized/deep replies,
combined stdout/stderr floods, idle/whole-query timeout, cancellation and server
descendants retaining pipes. Commands/edits must never execute/apply. Query cleanup
must kill the job, close pipes/profile and retire the volume before model changes
or new runs. A server needing writable cache storage is unsupported by this
read-only profile until a separately reviewed implementation exists.

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
