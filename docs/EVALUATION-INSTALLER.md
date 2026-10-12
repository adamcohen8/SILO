# Windows evaluation preparation and installation

**Current source:** the installer supports `-Activate` with
an independently reviewed exact-host plan; default source/bootstrap preparation
remains inactive. This has not been published or qualified as a native activation.
See [one-command installation](ONE-COMMAND-INSTALLATION.md) for commands, signing
order, approval requirements and the Windows acceptance checklist. The published release snapshot below describes an older installer.

Current source review: 12 October 2026. **Current `main` prepares inactive
candidates; the published sequence-3 installer is an older unsigned snapshot.**
Merging source does not update the downloadable installer. See
[current status](SILO-STATUS.md), [published bootstrap identities](PUBLIC-BOOTSTRAP.md),
and [managed activation](SILO-SECURITY-HARDENING.md).

Ask your security manager before installation. These paths use public/synthetic
material and do not establish deployment readiness, complete isolation, or CUI
authorization. Script execution must follow the permitted process; the source
installer does not set execution policy or unblock scripts.

## Prepare current source

From the extracted, reviewed folder containing `README.md`, run native 64-bit
Windows PowerShell:

```powershell
.\installer\Install-Evaluation.ps1 -PrepareOnly
```

Choose exactly one of `-PrepareOnly` or `-Activate`. Use `-PrepareOnly` when
independently approved activation inputs are unavailable. `-Activate` requires
an approved elevated session for the same target account and the reviewed plan
plus its independently supplied digest; it does not launch a model. The source
installer refuses automatic elevation and `-Rollback`. Preparation supplies
pinned application-local host Python and prepares the
application/inference/worker/code payloads and selected model, and verifies the
complete inventory. It retains versions/state/cache in private current-user NTFS
storage. No pip/package lifecycle hooks, global PATH changes, firewall changes,
model launch, shortcut, active record or native acceptance are produced.

Preparation still executes the verified host interpreter to assemble/check data;
it is not a generated-code or prepared NumPy execution test. The separate
[Python/NumPy environment](SILO-CODING-WORKFLOW.md#offline-environments) is assembled
without running that target interpreter/packages. The installed preparation
profile is included in the source and payload inventories.

Fresh source preparation selects Lightning on the capable first-GPU/RAM target;
smaller compatible machines choose GPT-OSS 20B, Gemma 12B, or CPU Gemma E4B.
Saved choices take precedence. If no model fits, preparation stops before model/runtime
asset downloads; the PowerShell bootstrap interpreter is already obtained for checks.
`-ModelId PROFILE_ID` explicitly overrides the fresh-install choice after catalog
and hardware checks; application-only updates reject that override. See
[model requirements](SILO-MODEL-SUPPORT.md). Preparation's capacity checks do not
qualify actual placement or model quality. Free-space requirements depend on
selected assets, cached copies and retained versions; the installer computes
its requirement. Allow for both download/cache and installed bytes.

The pinned host is native x64 CPython 3.14.8 with Windows-compatible reviewed
wheel/runtime inventories. No existing Python or Git installation is required
for this PowerShell preparation path. Runtime work never downloads missing assets.

```powershell
# Use a shorter approved path when required by the private transport.
.\installer\Install-Evaluation.ps1 -PrepareOnly -InstallRoot 'D:\AI-Evaluation'

# Require the complete already-populated, verified cache.
.\installer\Install-Evaluation.ps1 -PrepareOnly -Offline -CachePath 'D:\Approved\EvaluationCache'

# Prepare another immutable candidate while retaining prior versions/state.
.\installer\Install-Evaluation.ps1 -PrepareOnly -Repair
```

`-NoLaunch`/`-NoShortcut` do not activate a candidate; current preparation already
creates no launch or shortcuts. Acquire assets explicitly on a permitted host:

```powershell
python .\scripts\download_evaluation_assets.py --cache 'D:\Approved\EvaluationCache'
# Explicitly acquire the capable-source default for an offline transfer:
python .\scripts\download_evaluation_assets.py --cache 'D:\Approved\EvaluationCache' --model-id nemotron35-lightning-30b-q4-evaluation-1
```

Transfer reviewed source and cache through the approved process. Source ZIPs do
not include interpreter/model/wheel payloads. Keep acquired bytes outside Git.
A populated cache is not a signed redistributable or an independently licensed
SDK. Offline preparation refuses missing assets rather than fetching them.

## Activation, retry, and recovery

Current activation requires administrator-protected deployment, independently
verified release/model/reviewer anchors, signed policy/native acceptance, approved
storage/audit configuration, and separately provisioned execution pools when used.
Follow [managed security](SILO-SECURITY-HARDENING.md); ordinary sessions cannot
create their own trust or supply a passed receipt to bypass a gate. Rollback of a
managed installation follows those administrative procedures, not the refused
source `-Rollback` switch.

Preparation verifies payload bytes, preserves earlier candidates/state/cache,
and keeps incomplete `.pending-*` transactions for inspection. Corrupt/unowned
assets are refused. The source installer serializes operations with an OS file
lock and creates a fresh version, including a new suffix when an identity already
exists. Repeated preparation does not silently activate or overwrite that version.
There is no automatic uninstall or cache pruning.

Mutable preferences, grants, model inventory and explicitly saved encrypted
project/task/code records live outside the immutable payload. Unsaved chat remains
in memory; pending reviews and execution authority never survive restart. See
[storage and recovery](SILO-OPERATIONS.md).

## Published evaluation snapshot

The latest published artifact remains
[evaluation-2026.10.11-silo.3](https://github.com/adamcohen8/SILO/releases/tag/evaluation-2026.10.11-silo.3),
targeting `e3da3c10b96120744c130236f9e62bba83d033d3`. Its release-specific bootstrap
prepares its older snapshot and runs a native document/model preflight before
publishing an active evaluation and shortcuts. It does not include the current
managed-security, Lightning-default, long-work or expanded coding source.

Use its [INSTALL.md](https://github.com/adamcohen8/SILO/releases/download/evaluation-2026.10.11-silo.3/INSTALL.md)
for that artifact's behavior. Published terminal `/update check`/Ctrl+U checks
published versions, not latest GitHub source. Existing models/projects are retained
by the update design; exact native update/rollback acceptance remains separate.

The latest [Windows run](../windows_test_report.md) prepared/reinstalled current
source successfully but could not activate models/UI because protected enrollment
and independently signed acceptance were absent. Historical preflight and launch
results below apply only to their recorded configuration.

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

## Historical unsigned-evaluation trust and acceptance limits

For the older unsigned evaluation, trust starts with the reviewed source and its committed publisher pins. Current managed source additionally requires independently protected machine anchors and exact signed deployment/acceptance records. The
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

## Historical local development validation (10 October)

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
