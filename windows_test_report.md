# Windows run 7: PR #29 installation and hardware-selection validation

12 October 2026. Public/synthetic inputs only. **Preparation and data fixtures passed; managed activation, actual-model/UI first use and execution qualification remain blocked.** This run publishes no release and merges no PR.

Frozen main: `dda82437d3a932a35526df23b238687c7aac88af`. Tested source/tests/docs commit: `5e7a3189f37bdc9b2f3dd67e7eefe2ae98274ab1`. Checkout/installed source ID: `362c654408d5729c`. The report-only commit does not change runtime bytes. Exact method IDs, skip reasons, source/module hashes, inventories and every blocked matrix are in [the sanitized receipt](docs/windows-run7-validation.json). All earlier reports are preserved below.

## Results

| Check | Result |
| --- | --- |
| Required full pinned-host source suite | 864 executions; 485 recorded successes; zero failures/errors; 378 distinct skipped methods / 382 skip records |
| Priority installer/hardware suite, including new native refusals | 95 executions; 47 successes; 48 skipped methods/records; zero failures/errors |
| Required long-work focused suite | 103 executions; 30 successes; 73 skipped methods/records; zero failures/errors |
| Installed NTFS/CNG/DPAPI/navigation/recovery data fixtures | 36/36 passed, no skips/errors; developer-authored/scripted inputs and execution disabled |
| New native PowerShell 5.1 installer refusals | 8/8 passed: missing/conflicting modes, rollback, activation fields/digest, ordinary-user installer/direct-activation denial and incomplete offline cache |
| Real Python 3.14.8 / NumPy 2.4.3 data checks | 22/22 expected results; source online/offline and installed default-profile manifests identical; no target interpreter/package execution |
| Native PowerShell 5.1 installer parsing | 14 scripts, zero parse errors |
| Real preparation | Automatic Lightning and explicit E2B CPU override both passed online and complete-cache offline; manifests identical within each model |
| Interruption/retry and concurrency | Owned download interrupted with partial cache retained and no active record; resumed successfully; competing native installer denied by held OS file lock |
| Local exact-commit archive | Built, extracted, verified and application-only prepared offline; unpublished/unsigned; archive source identity separately bound |
| Actual managed/model/Qt startup | Blocked: model preflight exit 1 at candidate_security/AccessDenied; managed launcher exit 1 at SYSTEM/Admin ownership; Qt validator exit 1 at administrative candidate enrollment |

Successes are counted directly by addSuccess; no subtraction of skip subtests from discovered counts. Duplicate discovery and parameterized skip records explain differing totals; distinct successful IDs are recorded separately in the receipt. Skips never qualify a native capability.

## Preparation identities

- Automatic Lightning online/offline manifest: `ec48b83dc1127dddb3dd9a4a23f04b03098c0c9f114e6454ce766889987005f8`.
- Explicit E2B CPU online/offline manifest: `185ee1dcaa2ae97802270bdf917f53615cf4f69a4d74a3f6b5f10ca8dae51f85`.
- Auxiliary verified code/runtime-only host manifest: `4de81d3d93c687d7d297136398d8ae56f2325e89b048024a14f9728b8506b6f3`; no weights/default introduced.
- Final extracted exact-commit archive source ID: `4b7f8c4e41c56b24`; archived code/runtime-only candidate manifest `8a5af3e5db90f6bfdeafd818fc34157a65cbe5eedb463dd0206b01a834c555dd`. Archive origin metadata and committed-vs-checkout bytes are distinct inputs. Command-builder wrong-archive/plan and atomic complete-shard publication contracts passed with inert fixtures; real Super shards remain untested.
- NumPy profile SHA-256: `dbd2e33fdfaaecc6f2cba7369c8f98163bf0c09dbd76e3f445578602bc768c1b`. All prepared NumPy manifests: `3e254d03c9f357d19c1a330156d0fed554a61ba625cbe50ac0f3c7711dd46a30`; 970 files / 65,353,485 bytes. Actual wheel metadata/license entries and native DLL/PYD hashes are recorded. Licensing, protected deployment, native imports and independent build acceptance remain pending.

Every native installer preparation stayed inactive: no active.json, shortcut or model session. Offline repeats retained prior candidates/state and reused fully pinned weights. Lightning's 18,898,091,584-byte and E2B's 3,349,516,256-byte weights were completely verified during preparation. The original application was never used as the test installation or modified.

## Machine, first attempts and changes

Windows 11 Pro x64 build 26200; i9-14900KF / 32 logical threads; 65,348 MiB detected RAM; RTX 4090 / 24,564 MiB VRAM / driver 591.86; fixed local NTFS; Ethernet up, Wi-Fi/Bluetooth disconnected. Native hardware selection recommends Lightning. Ten catalog profiles meet declared capacity floors; Super fails RAM/first-GPU floors and native prepare refused before downloads. Actual CUDA0 placement, performance and other native hardware tiers remain untested.

The first full run used the existing Python 3.12 environment: 856 executions, 328 successes, one failure and six error records due to unavailable agent/terminal dependencies. Nothing was installed globally; the inventoried pinned-host rerun resolved those failures. The first authored native fixture path was too long and correctly stopped at the transport-path guard; shortening its disposable prefix yielded all eight passes. Both first attempts are preserved in the receipt.

This PR adds native installer refusal regressions and corrects stale README/installer-guide statements that described preparation as the sole mode. No runtime/boundary defect was confirmed, and no security gate or execution policy was weakened. Source ID remains unchanged because the added test and prose are outside the runtime inventory. The current catalog/runtime/profile and prior native mutation/NumPy fixes were retested.

## Remaining gates and coverage

No trusted Authenticode certificate/signatures, independent trust/release/reviewer anchors, signed exact inventory/model policy/advisory/maintenance review, release/OS-bound technical receipt, approved activation plan/storage settings, audit enrollment or protected managed release exist. Activation/ordinary-user first launch, upgrade/retry after enrollment, shortcut preservation, live recommendations/saved selection and all 11 actual-model document/coding/UI runs are blocked. No replacement organizational trust or passed receipt was fabricated.

Every original Python, build, technical, release-readiness, repository-apply, private-Git and language-service check remains individually blocked in the receipt. The 36 installed native data fixtures establish specified NTFS/storage/navigation/recovery primitives. They do not establish public repository application, LPAC generated execution, compiler/Git/LSP containment or actual-model quality. All seven benchmark cases have no scores. Real-model long-work/cancellation/context, the 108 kg milestone, inspected artifacts, placement, latency and RAM/VRAM measurements await qualified enrollment. The signed-policy/atomic-enrollment managed installer fixtures are POSIX-only skips.

Owned host IPv4/IPv6 TCP and UDP loopback controls and approved GitHub/PyPI HTTPS controls passed. They do not establish worker denial. External UDP/IPv6, LAN and proxy responders are unavailable. Full transport/IPC, crash/reboot/sleep, VPN/interface change and lifecycle matrices remain open. No DiskPart, VHD provisioning, admin application, prepared NumPy execution, pip/hooks, generated program, compiler, real private Git worker or LSP server ran. Other SDK/server assets and licenses remain unavailable. An existing-Python host does not qualify a clean no-Python installation.

## Cleanup handoff

The disposable root was absent at start. Original application files and persistent PowerShell policies were baselined locally; only task-owned downloads/checkouts/models/fixtures/receipts were created. No machine enrollment or storage provisioning occurred. Cleanup runs after this PR is confirmed open, with original-file/policy/resource checks and removal of the owned root. Its confirmed result is returned in the task handoff; this pre-cleanup report does not claim removal already occurred.

---
# Windows release validation — run 6, 12 October 2026

The current GitHub source was prepared and tested in a separate disposable
installation. Native file publication and NumPy preparation defects were fixed,
reinstalled, and retested. The final full source suite records **463
successful methods, zero failures and zero errors** across 828
executions. 364 distinct methods produced 368
skip records; skips are not acceptance. Skip records include four Office subtests and one duplicate discovered
method ID. Successes are recorded directly (454 distinct IDs across 463
successful method executions), never derived by subtracting skips. The final installed native data fixtures passed **36/36**, with
no skips, and 21 offline-environment data checks met their expected results.

Managed activation, actual models/UI and qualified generated/build execution
remain **blocked**. No model, prepared NumPy interpreter, generated program,
compiler, private-copy Git worker or real language server was launched. The
original application was not executed or changed. Source/fixture observations do
not qualify any execution boundary or authorize CUI use.

## Frozen configuration and preparation

- GitHub main at start: `6d957be7d0904496570b1db6714a175a44193418`.
- Final tested source: `f7af8d1bc172930fed750350a694d2466c903062`; subsequent
  reporting changes do not change the installed source inventory.
- Baseline source ID: `8121e934bc9ee44f`; first repaired ID:
  `f71278615daabbbe`; final ID: `3f795029951e3bc5`.
- Final preparation manifest SHA-256:
  `5e213b3813f26198ef6bbfc739946a4480156737cf5336e394d7ff5bb99d02f5`. Complete host/worker/code Python, dependency,
  CUDA/CPU runtime, application and new NumPy-profile inventories were verified.
- Windows 11 Pro x64 build 26200, i9-14900KF, 65,348 MiB detected RAM,
  RTX 4090 24,564 MiB, NVIDIA driver 591.86, embedded CPython 3.14.8 x64,
  ordinary non-elevated account, fixed local NTFS. Ethernet remained available;
  Wi-Fi/Bluetooth were disconnected at baseline. Routes/VPN were not changed.
- Native Windows PowerShell 5.1 used only the previously authorized process-only
  `RemoteSigned`. No persistent policy, firewall, driver, audit, machine trust,
  Program Files release or ProgramData enrollment was changed.

The published release API still reports `evaluation-2026.10.11-silo.3`, targeting
`e3da3c10b96120744c130236f9e62bba83d033d3`. It is the older unsigned artifact, so
this run installed the current source with `-PrepareOnly -NoLaunch -NoShortcut`.
Baseline and both repaired preparations succeeded, preserving prior candidate
versions/state. No shortcut or active record was produced. Synthetic/inert source
regressions cover invalid pins, preparation failures, update rollback and state
preservation; those are separate from three real successful preparations.

Fresh preparation selected Lightning, as expected for this actual first-GPU/RAM
configuration. Its 18,898,091,584-byte weight was downloaded and fully checked
against `61f87e75974e4b535dcdf9aad056541a9514f1dfa4538b463b081d19b7a00e3c`
during preparation. First permitted launch selection and actual GPU placement
could not be tested because managed enrollment is absent. Existing-selection and
lower-hardware behavior have source coverage only.

## Preserved first failures and fixes

1. The baseline full suite recorded 445 successes, one failure and two errors
   across 813 executions; 364 methods/368 skip records were retained. Existing
   file replacement failed at native rename with `0xC000000D`: an NTFS handle
   opened by file ID cannot perform this name mutation. `NativeFiles.open_edit`
   now pairs a named metadata/DELETE lease with a checked file-ID data handle
   retaining no-recall/no-follow flags. Named opens have no data authority;
   content identity is rechecked before reads. Combined sharing blocks foreign
   reads/writes/deletes/renames. Both handles close on success/failure.
2. Retesting the unchanged original native trigger uncovered `0xC0000043` when
   publishing into a newly created parent. New directory handles now use the
   same read/write sharing as retained existing parents and omit unnecessary
   DELETE access; file publication remains exclusive and refuses replacement.
3. The exact test-plan NumPy command under the embedded host failed with
   `ModuleNotFoundError: build_python_environment`. The preparer now explicitly
   adds its reviewed sibling-script directory, including under `-I`/embedded
   `_pth` startup. A subprocess regression exercises isolated startup.
4. The installed script's default preparation profile was absent from the first
   repaired payload. The optional existing NumPy profile is now included in the
   installer source snapshot and complete payload inventory. Its bytes/hash
   change the source ID; a regression verifies binding, exact installed bytes
   and manifest coverage. Final default-profile preparation succeeds offline.
5. Two source fixtures had Windows incompatibilities: an LSP test hard-coded a
   POSIX URI, and a fixed bootstrap test assumed `-S` overrode embedded host
   `import site`. The URI derives from the actual fixture path. The bootstrap
   test uses a disposable stdlib-only interpreter copy while preserving the
   host's configuration and retaining the real isolated/no-site bootstrap gate.

The runtime/resource/acceptance policies and model/runtime pins remain unchanged.
No independent passed receipt was created or enrolled to force a test through.

## Final regression and native data evidence

| Run | Executions | Successful methods | Skipped methods / records | Failures / errors |
| --- | ---: | ---: | ---: | ---: |
| Required focused source suite | 103 | 30 | 73 / 73 | 0 / 0 |
| Final full source suite | 828 | 463 | 364 / 368 | 0 / 0 |
| Final installed native data fixtures | 36 | 36 | 0 / 0 | 0 / 0 |

The embedded host ran the source runner with an explicit checkout; ambient
PYTHONPATH was not used. Separate installed-native discovery imported the final
payload's modules, verified their locations/hashes, and used external committed
fixture assertions. Native results comprise 12 repository mutation tests, five
coding data tests and 19 long-work tests. They exercise actual NTFS held handles,
DPAPI and Windows CNG, encrypted snapshots/task journals, reviewed patch export
and real external host `git apply --check` fixtures. All writes stayed in owned
synthetic roots, and execution services stayed disabled.

Native repository cases cover replace/delete/create/nested publication,
preimage/conflict preservation, read-only/hardlink denial, exclusive reads/writes/
rename, name replacement before file-ID data acquisition, publication failure
with original restoration, concurrent creation with preserved backup, identity
substitution refusal, partial temporary-prefix recovery and empty/Unicode/newline
bytes. A fixed developer-authored host child actually exited after publishing
the backup name; the surviving native identities/bytes were inspected and
recovered. This is one real process-crash case, not an LPAC or public multi-file
controller qualification. Remaining per-effect crashes/races are still required.

Built-in navigation exercised Python UTF-8 names, incremental hash reuse,
140 added source files with inventory pages, 126 name occurrences with result
pages, deletion/syntax changes, lexical JS/TS/Rust/C++ symbols, oversized partial
files, denied execution and revoked grants. Name occurrences/lexical symbols do
not claim semantic binding. Build snapshots restored with disabled execution and
no run/review authority. Public repository application refused missing signed
acceptance even with the development flag on Windows.

Long-work fixtures retain their actual native storage/broker evidence but use
scripted model replies, including 56 model calls/55 tools, context rollover,
truncated-tool refusal, encrypted unknown/orphan intent, pagination, backups,
retention, source drift and patch preimages. They are not measured inference or
proof of useful >16-call actual-model work. All skip reasons/details are retained
in the sanitized JSON: POSIX fixtures, absent managed native worker/code roots,
privilege-dependent native cases and unavailable optional/platform features.

## Real NumPy bytes and data-only checks

Profile SHA-256: `dbd2e33fdfaaecc6f2cba7369c8f98163bf0c09dbd76e3f445578602bc768c1b`.
The pinned CPython 3.14.8 archive and NumPy 2.4.3 cp314/win_amd64 wheel were
verified and assembled without pip, package hooks or target execution. Source
online acquisition and offline preparation matched; the final installed script's
online-enabled/cache and offline runs also matched. The default installed profile
was separately retested without `--profile`.

All environments produced manifest
`3e254d03c9f357d19c1a330156d0fed554a61ba625cbe50ac0f3c7711dd46a30`, covering **970
files / 65,353,485 payload bytes**. Actual wheel METADATA/WHEEL, empty declared
transitive requirements, notices/licenses and native DLL/PYD inventory hashes are
recorded in `docs/windows-run6-validation.json`. License review remains pending;
file inventories are not native import/DLL-load or redistributability acceptance.

Twenty-one data checks cover exact import/preview, wrong profile/asset digests,
conflicting/missing closure, extras/direct URLs, wrong CP/ABI/platform tags,
truncated archive, executable/DLL/manifest drift, extra files, hardlinks, existing
destination preservation, unknown activation/traversal and an injected copy
exception with incomplete-directory cleanup. No prepared target ran. The copy
exception is not power-loss acceptance. No reviewed Node/TypeScript/Cargo/Clang
SDK/server was supplied; fixed adapter/closure contracts passed source tests only.

## Blocked native acceptance and actual-model results

The final candidate model preflight exits 1 at `candidate_security` with
`AccessDenied`. Only `complete_installed_files` is true; all nine session checks
are false. The managed PowerShell launcher exits 1 at its SYSTEM/Administrator
ownership gate before launching Python. The Qt validator exits 1 at candidate
administrative access before a window/model/evidence session exists. No fallback,
fake anchors/acceptance, permission relaxation or administrator app run was used.

Missing prerequisites include independent approved release/reviewer/model
anchors/signatures, protected deployment, signed policy/SBOM/advisory/maintenance
review, registered/tested audit configuration, approved storage and separately
prepared bounded code/build pools. Candidate mode also requires explicit
administrator enrollment/access; it waives only technical acceptance, not these
prerequisites. The user was unavailable and no new enrollment approval was sought.

| Test-plan area | Final outcome |
| --- | --- |
| Actual Lightning/default, 37-crate reads, exact citations/drafts, Muse/gpt-oss retests, model switching | Blocked; prepared default/pins and source contracts passed |
| All eleven actual-model document/coding profiles | Blocked; ten pass capacity estimates, not load/quality; Super additionally fails 128 GiB RAM / 96 GiB CUDA0 floor |
| Actual long work, generation/streaming/rollover/cancellation and UI | Blocked; source/scripted and native storage fixtures only |
| Task/snapshot recovery and editing/patch data | Applicable native fixtures passed; managed interactive/controller cases blocked |
| Original Python execution boundary | All 19 acceptance checks blocked; no VHD provision/mount or generated execution |
| Separate build boundary/NumPy arrays/native test execution | All 23 `BUILD_CHECKS` blocked; data preparation passed, protected licensed environment/pool/signed acceptance absent |
| Reviewed public in-place repository application | Separate nine-check capability absent; native primitives passed, no public capability enrollment |
| Private-copy Git | Separate 13-check capability and protected complete Git distribution/pool absent; existing host Git used only for checkout/fixture/PR work |
| Actual language services | Separate seven-check receipt and real reviewed servers absent; scripted framing and built-in navigation only |
| Technical security/readiness | All 23 technical checks and release readiness remain blocked |

GitHub/PyPI host HTTPS controls and owned IPv4/IPv6 loopback controls passed.
They are host connectivity, not worker-denial evidence. Controlled external
UDP/IPv6/LAN/proxy services were unavailable. No worker, reboot/sleep/resume,
network/VPN change, aggregate job-memory/process-tree enforcement, real SDK/DLL
load or every crash/lease cleanup matrix was qualified. The seven independent
coding benchmark cases retain **no scores**; source pass counts are not model
quality. Signing, licensing and CUI authorization remain separate unresolved work.

## Report preservation and restoration

The original application baseline covers 2,836 eligible files by SHA-256 and
8 larger files by size only, excluding `.git`, virtual environments and Python
caches. No original application execution or writes were performed. All acquired
checkouts, versions, models/caches, synthetic inputs and local receipts are under
one newly owned disposable root. No VHD, enrolled key/policy, active record or
persistent execution-policy change was created.

Raw receipts remain local until PR confirmation, then are removed with the test
root as the user requested. The sanitized JSON preserves task-relative receipt
hashes and individual status/skip/matrix observations; it contains no raw logs,
keys, vaults, model bytes or personal paths. Final root/process/profile/policy and
original-file restoration checks are reported in the task handoff after cleanup.
No future cleanup is asserted as already complete in this pre-cleanup report.

The historical report below is preserved byte-for-byte from the baseline Git
blob. Its older passes do not qualify this release.

---

# Long-work Windows validation — 11 October 2026 (run 5)

**Preparation and available fixtures passed after focused fixes. Managed model/UI,
ordinary-user containment and generated-code acceptance remain blocked.** This run
follows current `test_plan.md`; previous receipts below retain their original
versions and limitations. The sanitized [case receipt](docs/windows-run5-validation.json)
records exact counts, skip reasons, all 19 code/23 technical gates, benchmark gaps
and hashes of temporary local evidence. Raw logs, weights and vaults are not committed.

## Frozen configuration and preparation

Fetched main `279dded509c0b75ce66c53bf46bc99f65a739798`. Deployed application fixes are commit
`0ed641ea9cfd51a962bc1e321fcbdcd913e7f8db`; standalone bootstrap-harness follow-up is
`e7aba2f58bc304b609f114c9639f3f5c92484dd3`. Later report-only changes do not change deployed bytes.
The published `evaluation-2026.10.11-silo.3` remains older source `e3da3c10b96120744c130236f9e62bba83d033d3`;
this run prepared current reviewed source, not that artifact. No release was published.

Ordinary, non-elevated Windows 11 Pro x64 build 26200; i9-14900KF, approximately
64 GiB RAM, RTX 4090 reporting 24,564 MiB, driver 591.86, fixed local NTFS.
Pinned embedded CPython 3.14.8 x64, 47 wheels and pinned b11433 CUDA/CPU runtime
assets were prepared. The machine already has Python/Codex; this is not a clean
no-Python-machine test. Existing authorization was used only for temporary
native PowerShell 5.1 RemoteSigned processes. Persistent policies, global PATH,
firewall, network adapters, drivers and the original application were not changed.

| Preparation | Source ID | Manifest SHA-256 | Exit / duration |
| --- | --- | --- | --- |
| Fresh online | `1c037a52c1a9eb82` | `153b2b261927afbb6388563d0d57dc4e0c98fb2c525fa65e6f7ed13e205a2d1c` | 0 / 694.718 s |
| Fixed source, offline same-root new candidate | `b03cc22e10b22220` | `a5109c40fca15d36f6037361d951d5ba033eb7f4810e92a543e8f503c0f774db` | 0 / 224.219 s |

Complete inventory contains 6,188 immutable payload files. Interpreter identity
and installer inventory verification preceded execution. The second candidate
preserved the first manifest and existing small state files. Both remain inactive;
no active record or application shortcut/model launch was produced. Preparation
executes the verified bootstrap interpreter; the installer status now correctly
says no **application/model** launch.

The actual hardware chose the Lightning prepared-default hint
`nemotron35-lightning-30b-q4-evaluation-1`. Its complete mutable weight file was
independently hashed: **18,898,091,584 bytes**, SHA-256
`61f87e75974e4b535dcdf9aad056541a9514f1dfa4538b463b081d19b7a00e3c`.
This verifies prepared assets/default metadata, not a saved managed selection or
GPU placement. No model was launched. Current Super requires 128 GiB RAM and
96 GiB on the first NVIDIA GPU, three pinned shards totaling 82,541,168,480 bytes.
This machine fails those floors; no Super weights or CPU fallback were attempted.

## Preserved failures, fixes and retests

- Baseline required focus: 102 executions, 28 successes, 73 skip records, one
  failure. Full baseline: 752 executions, 381 successes, 350 skip records,
  two failures and 22 errors. First receipts are preserved in the evidence hashes.
- Terminal cancellation could publish idle state before a queued provisional-text
  clear ran. Owner-loop text updates now run synchronously; worker callbacks still
  dispatch to the loop. Existing cancellation/recovery and the new immediate-clear
  regression pass. The newly prepared immutable terminal module passed both exact
  trigger tests under its own host (2/2, 0.195 s); the host is scripted, not real inference.
- Inert preparation/updater fixtures probed real Windows hardware against their
  deliberately synthetic catalog. They now select an explicit fixture default;
  the separate Lightning case still verifies exact selected pins. Production
  hardware selection and catalog verification are unchanged.
- A recovery test patched inherited `object.__new__`; restoration polluted the
  WindowsSession allocation slot and caused three later native constructor errors.
  A local fixture subclass now leaves the production class intact. Recovery plus
  real native byte-range locks pass 7/7. The first attempted mock correction was
  insufficient and remains a failed intermediate receipt (167-case focus and
  774-case full each had one failure). It created an inert one-byte-lock fixture
  outside the test tree; its exact contents/timestamps were audited and removed.
- Installed batch-launcher fixtures expected the obsolete direct Python route.
  They now exercise an inert managed PowerShell gate and propagate child exit 23;
  the separate legacy route retains literal space/Unicode argument checks.
- The configured native-worker adapter required removed `active.json`, reproducing
  FileNotFoundError on the actual candidate. It now authenticates the explicit
  managed candidate instead of trusting an unsigned activation record. Mocked
  routing/closure regressions pass; the real unenrolled candidate now gives
  AccessDenied, with no worker returned. That refusal is a blocked prerequisite.
- Standalone bootstrap checks also called removed `Write-ActiveLaunchers` and
  failed before archive coverage. They now exercise only an inert local shortcut
  target and explicitly report activation unavailable. Native PS5.1 retest passed:
  14 scripts parsed, 11 unsafe paths rejected, four archive cases, bad digest
  refused before extraction, actual pinned archive extraction and native icon
  preservation. The shortcut was confined to the disposable fixture and removed.

## Available-case ledger

| Case | Status | Result and scope |
| --- | --- | --- |
| Final required focus, new installed host | passed | 103 executions, 30 successful methods, 73 skips, 0 failures/errors; 3.121 s. |
| Final full suite, new installed host | passed | 774 executions, 427 successful methods (418 distinct IDs), 346 skipped methods / 350 skip records, 0 failures/errors; 112.173 s. |
| Prior final source suite | passed | Same 774 executions / 427 successes / 350 skips / 0 failures/errors; 118.974 s. |
| Supplementary native crypto/vault/lock fixtures | passed / skipped | Bundled CPython 3.12: 58 executions, 32 successes, 26 skips, 0 failures/errors; 1.532 s. Actual CNG AES-GCM interoperability/tamper and same-account DPAPI/NTFS fixtures; not FIPS or cross-account qualification. |
| New Windows long-work fixture | passed | All 19 methods run with native CNG/DPAPI, private NTFS and Windows held-handle broker. Encrypted journals, tamper/scope denial, unknown intents/orphans, retention/deletion, code/task backup, files-only recovery without authority, preimages/drift, exclusions, aliases and pagination. Execution stays disabled. |
| Continuation contracts | passed fixture | Scripted 56 model calls / 55 tools through context rollover, 140 retained journal events and 130 code files. Objectives/tool pairs and explicit benchmark/stall/truncated-request guards are checked. No actual model quality score is inferred. |
| Patch/Git syntax | passed fixture | Actual host Git check/apply in an owned copy covers Unicode names, empty additions/deletions and missing final newline; original fixture bytes stay unchanged. Not an actual terminal-approved/model-generated repair. |
| Inert offline toolchain CLI | passed | 12 native data-only checks: exact import/preview and rejection of missing/wrong review digest, manifest/payload/extra drift, hard links, existing destination, unknown command, traversal and suffix mismatch. Caller-passed JSON cannot activate execution. |
| Native preparation negatives | passed | Six cases: missing PrepareOnly, rollback, missing/corrupt offline cache, long socket path and competing lock. Expected nonzero exits, no activation/publication; existing candidate/state retained. |
| Candidate model preflight | blocked | Baseline and corrected preflight exit 1 at candidate_security / AccessDenied. Complete installed-file check is true; nine session/inference checks remain false, acceptance false. No model/grants were created. |
| Qt and managed launcher | blocked | Qt exits 1 before QApplication/evidence; first-stage launcher exits 1 at administrator ownership. Synthetic folders stay empty. No mocked UI pass closes these gates. |
| Original application / policy audit | passed before cleanup | 2,836 eligible file hashes identical; eight larger files checked by size only, no new eligible files. Baseline excludes .git, .venv, venv and __pycache__. Native/Core PowerShell policies unchanged; protected enrollment/release directories remain absent. |

Successes are recorded directly. Parameterized skip records are not subtracted
from method counts. Every final skip reason is in the sanitized receipt: POSIX
broker/vault/UI/graph fixtures, unavailable staged contained interpreters,
explicit native-code installation/provisioning and unavailable symlink privilege.
A skipped method or a source-only pass is never native acceptance. No requested
approval, human intervention, private reasoning capture or user document use
occurred during this run.

## Remaining plan coverage and prerequisites

The account is not elevated; no protected Program Files release or
ProgramData SILO-Security enrollment exists. Independently approved release,
trust and reviewer anchors, signed model policy, authenticated SBOM/advisory/
maintenance review, audit source/ACL/retention and approved synthetic storage
are unavailable. Creating organizational trust or caller-authored technical
passes would violate the plan. Administrator enrollment and independent approval
are needed before managed candidate observations; ordinary-user qualification
is a separate step. Signed release-envelope hash is therefore unavailable.

All hardware-compatible profiles' actual document/draft/model-menu tests,
37-crate sourced preflight, live terminal/Qt behavior, unrestricted interactive
output/finish reasons, >16 real model calls/>48 tools/>128 RPC frames, independent
numbered-note correctness, live context rollovers, real cancellation/jobs, two
clients, model/policy/grant changes, sleep/resume/crash/reboot and hardware-floor
alternatives are **blocked or not run**. Source and native storage contracts above
are partial evidence only. Prior Muse/gpt-oss and capacity failures remain
historical; they were not rerun or erased. Peak RAM/VRAM, tokens/s, model latency,
correctness and benchmark scores are unmeasured; all seven coding-benchmark
cases have no actual-model score in the receipt.

Administrator-owned code-volume provisioning and independently signed
ordinary-user acceptance are absent. No DiskPart/VHD/pool/lease preparation,
generated execution or `/code` was attempted. Every one of the 19 BOUNDARY_TESTS
(token, readonly inputs/runtime, outside filesystem, profile/registry, IPv4 TCP/
UDP, IPv6, DNS, loopback, IPC, children, memory, output, disk, timeout, cleanup,
recovery) and all 23 machine-security technical checks remain **blocked**, individually
listed in the receipt. The full role/transport network/IPC matrix, controlled
external UDP/IPv6/LAN/proxy responders, route/VPN changes, audit failure and exact
release readiness remain unqualified. No current containment-denial observations
or broader isolation acceptance are claimed.

The 108 kg artifact/ZIP milestone, unchanged four-test repository oracle under
SILO execution, more than eight accepted runs and actual-model coding/repair
quality therefore remain blocked. NumPy/npm/Cargo/C++ execution, dependency
resolution, multi-process runner, in-place held-handle repository application,
Git commit/push UI and language-server indexing remain unimplemented/unqualified.
Next integration needs pinned dependency closure/license review, immutable
environments and a separately reviewed bounded process-tree/filesystem/network/
resource runner with independent native acceptance. Signing, redistribution,
organizational CUI use and manual DPI/display acceptance remain outstanding.

## Cleanup handoff

Only the dedicated disposable tree contains cloned source, downloaded assets,
candidates, synthetic vaults and raw receipts. They will be deleted after the PR
and remote branch are confirmed. The accidental inert fixture is already absent.
No original installation, preexisting runtime or policy is removed. Final deletion,
owned-process/profile/VHD absence, original-file and policy rechecks are reported
in the task handoff after cleanup; this pre-publication report does not claim that
future deletion has already occurred.

---

# Cascade 2 / Lightning native Windows validation — 11 October 2026

This fourth run follows the merged `test_plan.md` and Nemotron additions handoff. The original application was kept separate from all testing. Fresh checkout, model acquisitions, installations, synthetic grants and private receipts were confined to an owned disposable tree. Historical results below are preserved for their recorded versions. Cleanup confirmation is recorded in the task handoff after the PR is created.

## Identities, changes and limits

Fetched GitHub main: `09f3447b3ba7a206fcf6a971e54c23bc2ba500d9` (merged PR #21). The published latest remained `evaluation-2026.10.11-silo.3`, source `e3da3c10b96120744c130236f9e62bba83d033d3`, which lacks Cascade 2 and Lightning. This run installed reviewed merged source; the updater was not used to replace it with an older catalog. No release assets were published or altered.

Focused validator/docs commit: `3841b23898be960f6a43a8b326a23d1e92176971`. Final additional negative assertion test commit: `55ce55a5fa11aff2701215e4822df4da1a9b5662`. The application runtime, adapters, catalog, pinned payloads, permissions and tool/correction budgets are unchanged. The changes are confined to the Qt validator and its host-observation helper, the native Office validator, four regression-test files, and installer wheel-count documentation before this report.

The Qt driver previously accepted a capacity citation with start line 2 but a broader end line, did not verify the full fact/units or exact PDF page/DOCX paragraph, and could continue to review a proposal without checking its actual name/source/hash. It now shares the stricter model assertion helpers, binds its receipt to the active installed identity and actual loaded profile, and optionally requires `--model-id` before granting folders. A documented isolated (`-I`) CLI regression covers helper imports. The added broad-end negative subcase rejects line 2–3. Focused tests passed 5/5. The current installer download list is corrected from 42 to 47 wheels; historical 42-wheel observations remain intact.

A later real GPT-OSS Qt run lost its JSON receipt when the final PyPI TLS handshake timed out inside `finally`. Commit `be4cda04c034d914a8c5282113e4791b36eecbb3` adds a bounded host-observation helper: network OSError/URLError records the phase and exception type and returns false, so connectivity still fails while the remaining evidence is written. Three source regressions cover HTTP 200, non-200, and timeout preservation; the isolated Qt CLI regression also exercises the new import. The model CLI already guards its final host observation and was left unchanged. The native timeout-negative test is explicitly fault injected, not passing connectivity/model-task evidence.

Ordinary x64 Windows 11 Pro build 26200; i9-14900KF, approximately 64 GiB RAM, RTX 4090 (24,564 MiB), driver 591.86, local fixed NTFS. CPython 3.14.8, pinned llama.cpp b11433 CUDA 12.4; runtime lock `35339d83085d7a0ce78dbd58f4051f776412a30948aa51aa9eb2b686e995abd9`. All installs used `-NoShortcut -NoLaunch`; native PowerShell 5.1 used only the previously authorized process-scoped RemoteSigned. No persistent policy/global PATH/firewall/adapters/WSL/drivers were changed.

Baseline installed source `6136541d11c3ed4a`, manifest `8b610c7d0ecb5dc5f180d0efa4098fe1460a34ce48c7b573aebd504a70d48c39`. Native model/terminal and original Qt trials ran that baseline application. The corrected Qt driver was applied by native installer repair, never by editing immutable files. Final source identity and repair/rollback manifests are recorded below.

## Case ledger

### PR review correction after the native run

Review reproduced a false success in `validate_windows_office.py`: when the
Office helper exited without a receipt but left an owner record, successful
process teardown supplied the only check and the driver exited 0. The driver
now retains missing-receipt and helper-exit failures, requires the selected
Office case's actual compatibility checks, and makes process-query errors
terminate the teardown check. Teardown cannot substitute for compatibility.

Portable CLI regressions exercise missing/empty/partial receipts, unsuccessful
helper exits, all five Office cases, failed teardown, and explicit failure
status. The focused suite recorded 23 passes and one Qt-dependency skip on macOS.
These are simulated subprocess regressions, not a rerun of native Office or
model acceptance. The native counts and observations below remain bound to
their originally tested revisions; rerun native Office checks for this change.

| Case | Status | Actual evidence / limits |
| --- | --- | --- |
| Baseline source suite | passed | 565 executions, 318 successful methods, 250 skip records, 0 failures, 0 errors; 113.822 s. |
| First corrected Qt source suite | passed | 566 executions, 319 successful methods, 250 skip records, 0 failures, 0 errors; 109.246 s. |
| Exact-model focused tests | passed | 5 executions, 5 successful methods, 0 skip records, 0 failures, 0 errors; 0.389 s. |
| Connectivity timeout regressions | passed | 3 executions, 3 successful methods, 0 skip records, 0 failures, 0 errors; 0.059 s. |
| First receipt-fix full suite | failed | 569 executions, 321 successful methods, 250 skip records, 1 failures, 0 errors; 92.38 s. |
| Wrapped-signature bootstrap fixtures | passed | 9 executions, 8 successful methods, 1 skip records, 0 failures, 0 errors; 6.372 s. |
| Complete receipt-fix source suite | passed | 569 executions, 322 successful methods, 250 skip records, 0 failures, 0 errors; 78.08 s. |
| Final Office-wait source suite | passed | 569 executions, 322 successful methods, 250 skip records, 0 failures, 0 errors; 84.937 s. |
| Source-suite accounting | explicit | Parameterized skip records are not subtracted as if each were a separate test method. The earlier 566-case suite ran the first exact-validator commit; the later test-only broad-end subcase passed its focused rerun. The final 569-case suite covers all source/test changes. The intervening full suite had one brittle PowerShell signing-message assertion failure; unsigned execution remained blocked and no marker was written. Normalizing gutter/whitespace formatting fixed only that assertion. Source skips do not establish native acceptance. |
| Fresh reviewed-source installation | passed | Online install exit 0; all ten applicable native preflight checks true. Pinned Python, 47 wheels, runtime and default Nano downloaded/verified. Evaluation only, deployment/full isolation false. No interruption/resume was forced in this run; prior resume evidence remains historical. |
| Bootstrap/source fixtures | passed | Eleven PS scripts parsed; eleven unsafe paths denied; four archive fixtures; digest refused before extraction; real pinned archive extraction, temporary shortcut/icon and atomic launcher replacement checked. Synthetic helper fixtures are distinct from public bootstrap acceptance. |
| Concurrent installer | passed | Same-root competing native installer refused without activation. |
| Offline/location negatives | passed | Missing cache, copied corrupt Python cache, and overlong private-socket root each refused exit 1 without activation. A real owned NTFS junction root was refused; its target stayed empty; verified alias removed. |
| Public Zone-3 bootstrap | blocked | Anonymous release asset size/hash verified; unsigned Zone-marked bootstrap refused by native PS5.1 process RemoteSigned. No unblocking or weaker policy. Latest source installation used instead. |
| Native container/document/vault/session fixtures | passed / skips | 41 executions: 39 successful methods, two inapplicable POSIX review skips, zero failures/errors. Includes real Windows byte-range lock cleanup/refusal and DPAPI/private-NTFS vault lifecycle. |
| Native folder/ACL staging runners | partial / passed | Folder runner: 14 executions, 13 successes, one privilege-1314 symlink skip; acceptance correctly incomplete/exit 1. ACL/staging runner: six successes. Separate initial private `windows_workspace` pattern found zero tests and exited 1; it is a harness setup failure, not a passing suite. |
| Network/filesystem/child observations | passed observations / partial | Host GitHub/PyPI HTTPS and literal IPv4 TCP reachable before/during/after; contained worker literal external IPv4 TCP denied with WinError 10013, child creation denied with 367, ungranted read/runtime writes refused, zero-capability token/no loopback exemption and cleanup true. |
| Loopback / full isolation | not qualified | Owned IPv4/IPv6 TCP controls worked; contained TCP timed out. UDP send API returned success but responders saw no delivery. These outcomes are not qualified denial results. Controlled external UDP/IPv6/LAN/proxy/COM, full inference/graph/parser/OCR, reboot/sleep/VPN matrix not run. Full isolation remains false. |
| Native code boundary / 108 kg milestone | blocked | Trusted DiskPart guard refused before any VHD creation (`0x40020`, regular file, two links, reparse tag zero). All 19 acceptance cases pending; native code suite: zero successes, nine prerequisite errors (one trusted-tool, eight unreconciled lease). Gate retained; no model-generated code executed. Failed-provisioning leases are reconciled only after confirming absence of owned images/drive/processes. |
| Organization restrictions | partial | Portable source policy fixtures cover revocation/omission/publisher/quantizer restriction. Required-anchor omission is tested natively below. No independently enrolled organization policy/CUI authorization is claimed. |
| Interactive updater / manual display | not run this version | Actual redirected terminal and offscreen native Qt are tested below. Default-console Ctrl+U updater-window/restarted Ready, manual DPI/display and native update fault/reboot matrix remain unqualified; historical release-2→3 checks are preserved below. |
| Native lifecycle | passed | 9/9 checks true; false checks: none. |
| Installed payload drift | passed | 6/6 checks true; false checks: none. |
| New-model import/selection negatives | passed | 15/15 checks true; false checks: none. |
| Actual model menu: remove different model | passed | 5/5 checks true; false checks: none. |
| Actual model menu: remove/reinstall last model | passed | 7/7 checks true; false checks: none. |
| Fault-injected native Qt receipt finalization | passed | 7/7 checks true; false checks: none. |
| Visual Office export review | passed | 4/4 checks true; false checks: none. |

Native lifecycle steps: final-validator-reinstall exit 0 (288.851 s); idempotent-rerun exit 0 (76.144 s); source-repair exit 0 (313.218 s); rollback-corrupt exit 1 (0.442 s); rollback-valid exit 0 (72.104 s); fresh-offline exit 0 (343.194 s).

Active installation after lifecycle tests: `{"deployment_ready": false, "evaluation_only": true, "evaluation_preflight_passed": true, "format_version": 1, "full_isolation_accepted": false, "manifest_sha256": "edeaf61785c4e32d4fddd504c569000ee37ad9d4edf552e8a3109591bec9233e", "source_id": "339b85a1f1525131", "version": "339b85a1f1525131"}`.

The exact vault-file/model/instructions hash snapshots survived idempotent reinstall, fresh repair and valid rollback. Corrupt previous-manifest rollback refused before activation. Fresh offline installation used the verified owned cache.

The original GPT-OSS Qt process exited 1 after a final HTTPS timeout and wrote no interface-results JSON. Its log and process receipt are retained; it is an incomplete/lost-receipt run, not a fully assessed Qt result. The later corrected-source run has its own receipt. The second GPT-OSS model trial returned a named proposal that did not qualify under the strict helper; its original receipt lacks proposal body/source fields, so the precise cause of that failure remains unlocalized. The subsequent terminal genuine-draft check passed without relaxing the helper.

## Exact model candidates and repeated real trials

Both new models were anonymously acquired through the production pinned downloader, fully hash/size verified, imported through the installed manager and explicitly selected. Neither profile substitutes Nano. Both offloaded 53/53 layers to CUDA0. Cascade uses `nemotron_cascade2`; Lightning uses `nemotron35`; thinking is enabled, reasoning budget 1,024 (Cascade template consumes it), temperature 1.0, top-p 0.95, top-k/min-p disabled. Context 8,192, maximum generation 2,048, one slot; no model-specific budget relaxation. Exact publisher/upstream/license metadata remains in the catalog.

| Profile | Model bytes | SHA-256 |
| --- | ---: | --- |
| `nemotron-cascade2-30b-iq4-xs-evaluation-1` | 18166698432 | `871a80bfd682289f2efa1b4fdee899576b5a768681f2b2ad74a15b59af6a510e` |
| `nemotron35-lightning-30b-q4-evaluation-1` | 18898091584 | `61f87e75974e4b535dcdf9aad056541a9514f1dfa4538b463b081d19b7a00e3c` |

| Profile / trial | Result | True checks | Failed checks | Not run | Cold ready (s) | Observed peak machine GPU (MiB) |
| --- | --- | ---: | --- | --- | ---: | ---: |
| cascade2-01 | passed | 18/18 | none | none | 102.434 | 18600 |
| cascade2-02 | passed | 18/18 | none | none | 81.9 | 18600 |
| cascade2-03 | failed | 17/18 | heading_search_capacity_citation | none | 47.979 | 18600 |
| gemma26-01 | passed | 18/18 | none | none | 51.455 | 15614 |
| gptoss-01 | failed | 17/18 | pdf_docx_deadline_citations | none | 48.309 | 12494 |
| gptoss-02 | failed | 13/15 | heading_search_capacity_citation, unsaved_model_draft | review_required, approved_exact_bytes, approval_single_use | 38.855 | 12494 |
| gptoss-03 | failed | 17/18 | correct_capacity_citation | none | 38.607 | 12494 |
| lightning-01 | passed | 18/18 | none | none | 58.371 | 19128 |
| lightning-02 | passed | 18/18 | none | none | 50.896 | 19128 |
| lightning-03 | passed | 18/18 | none | none | 50.555 | 19128 |
| muse-01 | passed | 18/18 | none | none | 55.795 | 16862 |
| muse-02 | passed | 18/18 | none | none | 45.88 | 16862 |
| muse-03 | passed | 18/18 | none | none | 45.626 | 16862 |
| nano-01 | passed | 18/18 | none | none | 70.808 | 18562 |

Each 18-case trial independently checks actual profile/full GPU/default deny; exact 37 crates and line 2 directly and after heading search; ordinary and quoted-instruction scope; 15 October on PDF page 2 and DOCX paragraph 2; genuine named sourced unsaved draft, review-before-save/exact bytes/single-use approval; original preservation/revocation/cancel/restart/cleanup/host connectivity. Failed receipts are retained alongside later passing outcomes. Smaller-model repeats are limited to the actual listed Gemma 26B control. Gemma 31B and 12B were not rerun for this focused catalog update.

Latency and model/tool-call totals below are public result metadata. Returned private reasoning is neither retained nor uploaded. Correction reasons/counts were not separately instrumented; call totals do not prove a correction. Tokens/s and per-model peak host RAM were not measured; GPU values are sampled whole-machine usage, not per-process attribution. The driver cold-ready field measures a fresh session/process including verification; OS disk caches were not flushed between trials.

| Trial | Capacity s (model/tool calls) | Heading s (model/tool calls) | Deadline s (model/tool calls) | Draft s (model/tool calls) |
| --- | --- | --- | --- | --- |
| cascade2-01 | 8.757 (2/1) | 9.574 (2/1) | 10.277 (3/2) | 22.363 (3/2) |
| cascade2-02 | 9.863 (2/1) | 9.519 (2/1) | 12.076 (3/2) | 21.388 (3/2) |
| cascade2-03 | 6.332 (2/1) | 10.674 (unavailable/unavailable) refused | 8.165 (3/2) | 20.55 (4/3) |
| gemma26-01 | 4.509 (2/1) | 5.493 (2/1) | 5.856 (3/2) | 10.69 (3/2) |
| gptoss-01 | 6.097 (3/1) | 3.408 (2/1) | 8.365 (unavailable/unavailable) refused | 11.55 (3/2) |
| gptoss-02 | 4.583 (3/1) | 6.35 (unavailable/unavailable) refused | 4.556 (3/2) | 5.194 (3/2) |
| gptoss-03 | 4.941 (unavailable/unavailable) refused | 3.613 (2/1) | 5.766 (3/2) | 6.901 (3/2) |
| lightning-01 | 5.652 (2/1) | 5.748 (3/2) | 8.869 (3/2) | 8.971 (3/2) |
| lightning-02 | 5.293 (2/1) | 4.364 (2/1) | 7.631 (3/2) | 10.235 (4/3) |
| lightning-03 | 6.223 (2/1) | 8.225 (4/3) | 7.117 (3/2) | 10.369 (3/2) |
| muse-01 | 13.655 (2/1) | 27.512 (3/2) | 19.81 (3/2) | 27.583 (3/2) |
| muse-02 | 12.649 (2/1) | 33.001 (3/2) | 22.658 (3/2) | 34.27 (3/2) |
| muse-03 | 13.847 (2/1) | 16.991 (2/1) | 23.278 (3/2) | 34.919 (3/2) |
| nano-01 | 7.524 (2/1) | 8.679 (2/1) | 15.638 (5/4) | 13.591 (3/2) |

## Production terminal and actual Qt windows

| Interface / profile | Result | True checks | Failed checks | Errors |
| --- | --- | ---: | --- | ---: |
| terminal-cascade2 | passed | 13/13 | none | 0 |
| terminal-gptoss | failed / incomplete | 9/13 | capacity_exact, heading_exact, deadlines_exact, all_six_requests_attempted | 3 |
| terminal-lightning | passed | 13/13 | none | 0 |
| terminal-muse | passed | 13/13 | none | 0 |
| qt-cascade2 | passed | 43/43 | none | 0 |
| qt-final-cascade2 | passed | 45/45 | none | 0 |
| qt-final-gptoss | passed | 45/45 | none | 0 |
| qt-final-lightning | passed | 45/45 | none | 0 |
| qt-final-muse | passed | 45/45 | none | 0 |
| qt-lightning | passed | 43/43 | none | 0 |
| qt-muse | passed | 43/43 | none | 0 |
| qt-timeout-final-negative | expected refusal | 1/3 | requested_model_loaded, host_connectivity_preserved | 1 |
| qt-wrong-profile-negative | expected refusal | 1/3 | requested_model_loaded, host_connectivity_preserved | 1 |

The first GPT-OSS terminal receipt has an observer bookkeeping error: `all_six_requests_attempted` counted successful replies only. Its three successful replies plus three recorded request errors establish that all six tasks were attempted; a separate accounting receipt preserves the original digest and enumerates the six unique cases. This extra false check is a harness defect, not a fourth application task failure. Terminal tests run the actual installed scrolling/plain command loop with strict cp1252 redirected input/output; external observers record real adapter replies and cleanup, without replacing inference. Six independent cleared requests exercise exact capacity/search, scope, deadline and genuine pending draft. `/models`, `/hardware`, grants and `/code` refusal are actual commands. Model removal No/Yes/cancel/invalid-input checks use the real menu; no menu reply is passed to inference. Full-screen keyboard/display acceptance is separate.

The original Qt trials use the baseline looser driver. `qt-final-*` use the stricter reinstalled driver and explicit model IDs. The wrong-profile negative must fail before grants/tasks while retaining cleanup. Offscreen Qt exercises actual native windows, buttons, model workers and rendered snapshots, resize responsiveness, file/source drift and collisions, edited-review invalidation, model-authored Office artifacts, schedule approval/reconciliation, revoke/cancel/restart. It does not qualify manual display/DPI.

## Independent Office checks

| Profile / reader | Status | Evidence |
| --- | --- | --- |
| office-independent-cascade2-baseline | passed | 7/7 checks; false: none. Exact approved outputs opened with independent DOCX/XLSX/PPTX readers. |
| office-independent-cascade2 | passed | 7/7 checks; false: none. Exact approved outputs opened with independent DOCX/XLSX/PPTX readers. |
| office-independent-gptoss | passed | 7/7 checks; false: none. Exact approved outputs opened with independent DOCX/XLSX/PPTX readers. |
| office-independent-lightning-baseline | passed | 7/7 checks; false: none. Exact approved outputs opened with independent DOCX/XLSX/PPTX readers. |
| office-independent-lightning | passed | 7/7 checks; false: none. Exact approved outputs opened with independent DOCX/XLSX/PPTX readers. |
| office-independent-muse | passed | 7/7 checks; false: none. Exact approved outputs opened with independent DOCX/XLSX/PPTX readers. |
| office-native-cascade2 / excel | passed | Checks {'no_formulas': True, 'values': True, 'no_external_links': True, 'pdf_export': True}; errors []; timeout cleanup not applicable. |
| office-native-cascade2 / powerpoint-control | passed | Checks {'new_empty_presentation': True}; errors []; timeout cleanup not applicable. |
| office-native-cascade2 / powerpoint | failed / incomplete | Checks {}; errors ['An existing Office instance prevents isolated testing']; timeout cleanup not applicable. |
| office-native-cascade2 / word-control | passed | Checks {'new_empty_document': True}; errors []; timeout cleanup not applicable. |
| office-native-cascade2 / word | blocked | Checks {}; errors []; timeout cleanup 0. |
| office-native-cascade2-rerun / powerpoint-control | passed | Checks {'new_empty_presentation': True, 'owned_process_exited': True}; errors []; timeout cleanup not applicable. |
| office-native-cascade2-rerun / powerpoint | passed | Checks {'geometry': True, 'values': True, 'owned_process_exited': True}; errors []; timeout cleanup not applicable. |
| office-native-gptoss / excel | passed | Checks {'no_formulas': True, 'values': True, 'no_external_links': True, 'pdf_export': True}; errors []; timeout cleanup not applicable. |
| office-native-gptoss / powerpoint | passed | Checks {'geometry': True, 'values': True}; errors []; timeout cleanup not applicable. |
| office-native-gptoss / word | blocked | Checks {}; errors []; timeout cleanup 0. |
| office-native-independent-word-control / word | blocked | Checks {}; errors []; timeout cleanup 0. |
| office-native-lightning / excel | passed | Checks {'no_formulas': True, 'values': True, 'no_external_links': True, 'pdf_export': True}; errors []; timeout cleanup not applicable. |
| office-native-lightning / powerpoint | passed | Checks {'geometry': True, 'values': True}; errors []; timeout cleanup not applicable. |
| office-native-lightning / word | blocked | Checks {}; errors []; timeout cleanup 0. |
| office-native-muse / excel | passed | Checks {'no_formulas': True, 'values': True, 'no_external_links': True, 'pdf_export': True}; errors []; timeout cleanup not applicable. |
| office-native-muse / powerpoint | passed | Checks {'geometry': True, 'values': True}; errors []; timeout cleanup not applicable. |
| office-native-muse / word | blocked | Checks {}; errors []; timeout cleanup 0. |

Artifact provenance belongs to actual Qt propose/review/exact-byte approval; the Office helper does not generate model-qualification evidence. Excel string-cell/no-formula behavior does not establish numerical-cell/formula compatibility. Each native Office operation has a 120-second bound and only its recorded PID/start-time Automation/Embedding instance is eligible for cleanup. All eight native Excel PDF pages and all eight native PowerPoint slides were visually reviewed after export. The values 48, 60 and 108 kg and data.csv provenance/hash are readable without clipping or overlap. Excel prints the values on page 1 and provenance on page 2; cells are strings and numerical/formula acceptance remains unqualified. Word exports are unavailable for the timed-out operations.

## Office sequencing revalidation

A native empty-presentation control passed but returned before its recorded PowerPoint instance exited; the immediately following Cascade artifact test therefore refused with an existing-instance error. Commit `dbcc4c23e78afc5d14c1167d26ae57c48b6fbeb4` adds a 15-second wait after the PowerShell child exits, validating the exact recorded PID/name/start-time and Automation/Embedding identity. It does not terminate an unknown Office process or weaken isolation. The original refusal is retained. Only the affected Office stage was rerun after installing this change; the strict Qt/model receipts remain bound to their recorded source `339b85a1f1525131`.

Repair and affected-PowerPoint-stage receipt (the independent Word operation remains blocked): `{"checks": {"control_then_powerpoint": true, "native_repair": true}, "installed_identity": {"deployment_ready": false, "evaluation_only": true, "evaluation_preflight_passed": true, "format_version": 1, "full_isolation_accepted": false, "manifest_sha256": "8cc435b4fad2e46e5d79cfb330e0e008bf3ae8bc350970daaf41ee718f6381a0", "source_id": "9b879519f4b72f06", "version": "9b879519f4b72f06"}, "passed": true, "steps": [{"case": "office-wait-native-repair", "exit": 0, "seconds": 285.999}, {"case": "office-native-cascade2-rerun", "exit": 0, "seconds": 9.826}, {"case": "office-native-independent-word-control", "exit": 1, "seconds": 120.411}], "utc": "2026-10-11T21:13:39.896654+00:00"}`.

All four model-authored DOCX files timed out at the 120-second native Word open/export stage; each recorded owned instance was reconciled with cleanup exit 0. An independently produced one-paragraph DOCX control was tested separately. Its result is listed above. The independently generated control also timed out at 120 seconds with owned cleanup exit 0, so Word file-open/export remains a native prerequisite failure shared by that control and all four actual approved outputs. No Word PDF or visual compatibility result is claimed. A timeout is not Office compatibility acceptance, and these observations do not establish a model-specific defect.

## Private receipt witnesses

The following SHA-256 values identify the locally reviewed synthetic receipts before required cleanup. Raw receipts, synthetic vaults, prompts/responses, credentials and model weights are not added to Git. Witness hashes permit identification of the run records but do not make deleted raw evidence independently recoverable.

| Receipt | SHA-256 |
| --- | --- |
| acquire-gemma4-26b-a4b-q4-evaluation-1.json | `a97ba85cbf4b09a797c8f5f7c5d2a078007a99f0ae06d05c7d44cb1c4e5c5105` |
| acquire-gpt-oss-20b-mxfp4-evaluation-1.json | `0a011000e72d6e9dd92e10b3a1f28999a05a048f18f4abfab6172566ba2e90d0` |
| acquire-muse-glimmer-30b-q4-evaluation-1.json | `96a9452229063133df7ec8abf32f7580f4aabc92324a8cc5e4213711f4b23aa1` |
| acquire-nemotron-cascade2-30b-iq4-xs-evaluation-1.json | `e46e29ea07a03a951cb3b6607cbf56de47b8e25e38e16c13ce16dd77cf8d0866` |
| acquire-nemotron35-lightning-30b-q4-evaluation-1.json | `5b3046e69f0e1e7d36d1d0a9e7b9d830e3c37301a6f39a3ea9f0cfc2fd952920` |
| close-project-cascade2-process.json | `6f5bb9cdae1e03839471bbfc4477381a21277f45bdd9e819999170d28fa0e043` |
| close-project-gptoss-process.json | `dc1f417777a06dd9fe35c82dbfa7711fefd848662d621231dc593ef489103645` |
| close-project-lightning-process.json | `c160f8da24e9f492c418962871384d56ef42b6c7f9230f4ad3c7ca2baac4806c` |
| close-project-muse-process.json | `2a5c7ca123b9a8c582fd50086c1a477b91dc34235f70d684ef1dd44fa6016cb6` |
| code-candidate-process.json | `4b3612f36d9d926bfe7469dd3cd4514dd287f8b32004b12e7cebd31afe34ff1f` |
| code-candidate.json | `517c1be5447c1125515856bff408a964012a1fd6f92fcfa2ca0756ab54fecaff` |
| concurrent-install.json | `07c6bf0d83e959d6a4f9c98d22ffb5bfe947edde3144a317a4a9778431697238` |
| extra-native-complete.json | `37f734e96256ff905d6e831fb69f4f1b2a5a74e4d406848952cbf478f3146cc3` |
| final-close-project-cascade2-process.json | `9bfad510f65e12212e0f845ebfefe19e6d185d09adad29adce137e94004d393b` |
| final-close-project-gptoss-process.json | `183778f5a1c264f61c0ad65c0ade9e30d90bcac2eb3a14131d9806facbe31062` |
| final-close-project-lightning-process.json | `f9e32d38ccf55dc7f0436086b1f7ed7661033ebc196f84814b1b7a72a9d118bc` |
| final-close-project-muse-process.json | `e43cd72c2f9248ef4333c9510267604850626fc1f89af9e93bc7b4110a3dd61f` |
| final-native-complete.json | `959d98899035796adf5dac54779fc8e61689ba4cbf0fcf414fdc98f2e2ca6eaf` |
| final-select-cascade2-process.json | `8268e12d6d9562927db2ebe4a13e31528f0d6b961766b6dbe0da388e5e237132` |
| final-select-gptoss-process.json | `f18646ddac6d23cb1a219b9a43125e03e36889d5105e9b5ae7d0b9089c3a465e` |
| final-select-lightning-process.json | `6b29a42ae0e7ad055ee3669d9209b4c4a43ef8cc35f5151e5fa01a3e223fff52` |
| final-select-muse-process.json | `0105ae1a0e3a9955913cef85a6793e24115bc3be9847e19751fce61acf092bc3` |
| focused-bootstrap-wrap.json | `927f71252d6a1bb5fa383ddabf6a4b3356228e3d147789cafeca7323a085a9cb` |
| focused-connectivity.json | `cdb4fb11023270b9cb3ec19fd1b45a266ff4ec2588e2de25226c38129067b91e` |
| focused-qt-broad-locator.json | `411e5181b81d04211ff812bad41239e504d80dc1517fc18d09c81edc01d55446` |
| focused-qt-validation-final.json | `9e6c1f015d6b304de710709289e5c5f0523cd97b83c00696724c6572941c5869` |
| focused-qt-validation.json | `8d3072fdaa66d4f91d27a1f8d10039f30cfa5aaee0a4f7b40669ead4a68bc17a` |
| historical-report-verification.json | `de0639291e6fa056ff4b1e08ec87f6351d4c7028a3fabfac58e05faf8ff893e9` |
| import-cascade2-process.json | `979e61cb93f72a32860a71ad9da374114dfc66a7b499090310bc0cd1790c4097` |
| import-gemma26-process.json | `9f4db8d40723208e7e9052bb57f26e086c76006512d0e4dc42f2990cff371484` |
| import-gptoss-process.json | `b63bd30c5b9846abcaa2da41f8e6afc098a5e35e6af542ae03ac00a266eddee6` |
| import-lightning-process.json | `5e04f2d81457e6897e651fd90a37cff72d8c465e8577bac839766086e05610a9` |
| import-muse-process.json | `b41f7cc1cfbc15d55bbc041a3d487870ea3d17ea4ee3657dd78d95a97411a49f` |
| installer-negatives.json | `e6c7bccd1eb6cbbbdadb0aae6db4ca65a76e984be5b35a8e01f7bc5008c0fac4` |
| inventory.json | `9d27a2aee586d0e28d7de719920149c99649079de05bdcf814dca9157bd86974` |
| latest-release.json | `11809ba69bdce4fa237ffa52f1c17954f690278ad9a6c93c63396d8345e8fe53` |
| launch-drift.json | `bfd1e201a15e2902fc72595608a92bfe7803f2e38f1a7223495846b4107307c4` |
| lifecycle.json | `45056aef0dfc861217afac1392c6e08dfddb6dcd43513f1465d698641adb571f` |
| menu-different-process.json | `7ce13db6b844c8f8cd5444825693a30adfd8a201224a8f40cd28127aae700a14` |
| menu-different.json | `f7124d33c2151946c3c0e6f01e66068ffa82e2a3b3056748e6aca9f523751a4c` |
| menu-last-process.json | `b1042db01d7129887158ed893fdf1a3859769dda3c1370d7335180d2588a9fa3` |
| menu-last.json | `83774b2f9873fcdea6813dc6c1d652f88c88dc63db6f301b9dcf65afac377f99` |
| model-cascade2-01-process.json | `a8bea577ca1b7f96302f9bf095e87210cb4574534b3dc46cfd4b8a7d25b68e2d` |
| model-cascade2-01.json | `c8a445057e9aa3d56b7515c5c5268bbb6e7d4e8d2ac337020dbe5889955240bc` |
| model-cascade2-02-process.json | `37fcf9460aa1c9652452c49a11f8ef1d7bd55656706217ae8498c6ca517ed8e3` |
| model-cascade2-02.json | `68506ef576418fc3439f5eeb365bcd51d45ec9bddcd559abf9680ea066c27c98` |
| model-cascade2-03-process.json | `7064d2eb7170d5aaee2555f4363f88803922468c1b676d3ed416e7d5818991ed` |
| model-cascade2-03.json | `dd76cb0c86d97b24bdbdec2ac0b38a09372642582a539e247abb7017b2256a18` |
| model-gemma26-01-process.json | `b7e5bda1f9c3ec7f32945ec031cfa179505e745a6af1d331bc67962ce71cfb9a` |
| model-gemma26-01.json | `28664ab7f1d9ea138a1080f75ef29bac48ee5a0ccda6e1ecd5975d24aa2a9c47` |
| model-gptoss-01-process.json | `133cad811524e45cd3711865851382c89062b81b2244e2604870a3ad740f27eb` |
| model-gptoss-01.json | `1935f4016bc4be772cb7c62a1722b72b9e2dd16b910c2c88a1ee3c85b1f6e592` |
| model-gptoss-02-process.json | `f198ebbef5aaeb02d32b79360f08f254608e73417f78e9e134b77b1978fddc6d` |
| model-gptoss-02.json | `5e9e9f3f1c072dbc0c54cb7fbba67b6a31de3fc43aba232e6765a6f831d23243` |
| model-gptoss-03-process.json | `df288a635fd37859a3189804ba27ad87dc8e3b14ab38065010000d3a5ad759a5` |
| model-gptoss-03.json | `13b7a36a9071b04e9e6e7bf2af04d42c32c043ca9fa9ac74a4d1343bdcd91749` |
| model-lightning-01-process.json | `28f9b2f4299c5e0c3e9e3aabdae07c05107b7209a0f74795cf4bbb0076d01f3f` |
| model-lightning-01.json | `d14344221885d01eecd6bee84905129da20edae1b401cb2441e03501b395cf5e` |
| model-lightning-02-process.json | `5626b015602a3c045f05ea5ddee88eceee29430255bdb40c045be3456b12308a` |
| model-lightning-02.json | `03525f025f54ca0586a80dd4554d155e799215e65939028f3a7de00da7e56a95` |
| model-lightning-03-process.json | `500652a9274366afb3907407d3dcb95333a49cc1c1ced7811b4f38befaa147bb` |
| model-lightning-03.json | `bedb7b2b2525cefd220c24a8a9ef0fae06a51bb68655aef171e00e61de21ac69` |
| model-muse-01-process.json | `747673d3891a768f7a3bf26371c61eac892a1f16a6a739c8d0ced59ccf698b07` |
| model-muse-01.json | `fa57c87ce87120b1b41b20f37d87ed0ecc3cf446fc5760a9da259d8cae84b418` |
| model-muse-02-process.json | `660128d7a1b753311ba9cc1e0b781a4c2792d909551a758aeb8fc63e820ab87e` |
| model-muse-02.json | `f13f12363d174519249b4594fd131a0759838d64cce6b82c684e781ad68d4e50` |
| model-muse-03-process.json | `e83b37202e9026a2221130affe28b193bb600ec38d9289588ba5beb106f2717d` |
| model-muse-03.json | `44167f5e9d461404c2c9fa5afaa5fb48acc771e25f9223fdb765dfa0450c43af` |
| model-nano-01-process.json | `56be7fdda3bab7ca8918b26bdcbf3a0a7d5fea45956c838f16527a64b57b6fc8` |
| model-nano-01.json | `f42f624d832cd7ea0f4ded38c7da1527074c608bb6eb3f5577d21de9f04a0a76` |
| native-code-fixtures-process.json | `af87ed398eb3ca5eda7717abe1b86b20accfc44f65470d5868ee0a280ad734e3` |
| native-code-fixtures.json | `6c8db54ea8a637bc8edf84d8f6289859667b30d05d40748a78d5136ec757ceb6` |
| native-documents-process.json | `d5314ea6f2382a64d3fdce389298f285761f7103d9a29183e3955105139e7a41` |
| native-documents.json | `1cf5878306fc54d37d7e41c96aedcc674953be696011fdad654816262ecdbc3b` |
| native-model-pipeline-complete.json | `2dac1b82952fc2472bee26bf9f164221adfe87c3c55db8963e887c2162eba39f` |
| native-windows_contained_parsers-process.json | `4e2c79e167f31062da4dd5f026f14281309be9c3a0cdf5e7748a40279ded8694` |
| native-windows_contained_parsers.json | `eefdddb3073814d59b325421e9b7a8bbb431d54c936dcc346f0b381fdbc95960` |
| native-windows_container-process.json | `616464f912434562add0632cf6c5058d9e0b1122528f67ffbba3894ccedf361a` |
| native-windows_container.json | `e5b7d8b5687f90b47d6dd1976bc2bc555a98fc4b94baafc2519ba1d3d54421a8` |
| native-windows_session_lock-process.json | `a8c8e2670aabf8e059dc589ca9ac033ebe8820ba2eafc347de682caebea2dcbc` |
| native-windows_session_lock.json | `b6d51dd4b28a1c357115378e4a614a3ad17523ee0d0c4d1a2dc8d1fc4ae2b86f` |
| native-windows_vault_lifecycle-process.json | `9bd775c32c9b26da2f0b8c0ae26f1b0e8bb5c27b03137c12dc4f48ec62b81802` |
| native-windows_vault_lifecycle.json | `cbf9fbf93f6e246c9d1d4fd9c74c2655c7d5e104c50e855211c477b7d0e69908` |
| native-windows_workspace-process.json | `101b311c80216dbac0a39312ba734eba31da9e82c66a97ff451b5e1801e0d755` |
| native-windows_workspace.json | `4da5aa80dc27d5eacef8d7782201651a600ebd60ffd9720b1ed6e4ee5d8dd429` |
| negative-junction.json | `33a09467ea9847b1cbe23d32a19210cc5573ecb040cef19eabd4e8b599a2cd1d` |
| network-observations.json | `8a4bb0a0c58bdc570da4cf9a09cb593a5d34c31a3a7a6d6d02ce71ed57d4f597` |
| new-model-native-negatives-process.json | `979271ec87dc7af08672b4c867b90fbaa221b6af89d6bd48c1b75f721614f73f` |
| new-model-native-negatives.json | `b404b448440f9f039bd4919c5cb12f1a2d661184d00a2e3e71912c40b5737f14` |
| office-independent-cascade2-baseline.json | `de58344a3d2ae3067b2350ac4e86595e63b4a2f7c5350bb58d9e40c3883fe56f` |
| office-independent-cascade2-process.json | `469bb6a8518f6a81f92adef69b3fd9a994bd3a4445c3c3ab0e078b9e4f5c5022` |
| office-independent-cascade2.json | `792476716c594b117047b04f574578e625352c17026ff46b3662f9fb87e21bc2` |
| office-independent-gptoss-process.json | `7f05dd502f38a1d28dbb923621b039d14b7a2352bd18afefef3be7d62113256a` |
| office-independent-gptoss.json | `d4ea2e645918164a7e4d78139d62fb3e601b54a3642ac4fdae06801784267116` |
| office-independent-lightning-baseline.json | `c9623bb7301afd137d5f41e982b61e4c1481f5a5b6b9f90444fa7f378b3655f5` |
| office-independent-lightning-process.json | `bfbeb2ef4e43810ef30e1c97c2ac3e23f6ddf2a4f936a3e862b0aa1abb9209cc` |
| office-independent-lightning.json | `fc0e88e1866f098470233e6a96af7a1bcf9fec18d4632ad03608f26e479c5afb` |
| office-independent-muse-process.json | `afb807606713ccc2cee4cbb346103d94244ab361d6f642ba7dcd070eff534480` |
| office-independent-muse.json | `b099e2953c94d8c6a51be9462034ecbe7117fede346fe0ea371b6a7833484c2e` |
| office-native-cascade2/native-office-excel.json | `2b8be6a8bf082b425d10f495e61d8741950084ebfb854861c2a9cf6c846a8843` |
| office-native-cascade2/native-office-powerpoint-control.json | `4e71e4a2cc1a246719fb93bc829ec76ac88ecc8acf0e6e5a130c0b30f5d623f1` |
| office-native-cascade2/native-office-powerpoint.json | `f5b668f7f744d4d7cafe1dbc1135d6b09c14980482eed2bb3a1258bce2a7c183` |
| office-native-cascade2/native-office-word-control.json | `a1fe45c0890289e6e8dd983ab2ccb1a615ceb809072805253ddeaa955f3e25a3` |
| office-native-cascade2/native-office-word.json | `8b1918a717981613567662dd3b16b414ed240100f8a2f4bdc0bb820fe7f660c6` |
| office-native-cascade2-process.json | `fe239bcacd87897c08fa06cfe8b4333ea0f62c2814af1afdbbbac3c4a310c2b5` |
| office-native-cascade2-rerun/native-office-powerpoint-control.json | `ef981ba1685c1bf966bdfdc88bfc1c62607f54587d361ecf56d748fe2a6517a0` |
| office-native-cascade2-rerun/native-office-powerpoint.json | `9d87c4ad55671d55b63f64b2cb27ac84c688cf2047514969f8ec43e2eeeb1cae` |
| office-native-gptoss/native-office-excel.json | `2b8be6a8bf082b425d10f495e61d8741950084ebfb854861c2a9cf6c846a8843` |
| office-native-gptoss/native-office-powerpoint.json | `3c79e287923f38d4d14cd064906cd9e64db26dd66c38c2aa314182726812d472` |
| office-native-gptoss/native-office-word.json | `8b1918a717981613567662dd3b16b414ed240100f8a2f4bdc0bb820fe7f660c6` |
| office-native-gptoss-process.json | `b13813660483e1b8bcabe33ae74c0af19865455d968d2a6ca051279d6af25997` |
| office-native-independent-word-control/native-office-word.json | `8b1918a717981613567662dd3b16b414ed240100f8a2f4bdc0bb820fe7f660c6` |
| office-native-lightning/native-office-excel.json | `2b8be6a8bf082b425d10f495e61d8741950084ebfb854861c2a9cf6c846a8843` |
| office-native-lightning/native-office-powerpoint.json | `3c79e287923f38d4d14cd064906cd9e64db26dd66c38c2aa314182726812d472` |
| office-native-lightning/native-office-word.json | `8b1918a717981613567662dd3b16b414ed240100f8a2f4bdc0bb820fe7f660c6` |
| office-native-lightning-process.json | `bf4da18645d476bb3e4713d1b1cade60a7606857372c22eb8df36c0b02d4d87c` |
| office-native-muse/native-office-excel.json | `2b8be6a8bf082b425d10f495e61d8741950084ebfb854861c2a9cf6c846a8843` |
| office-native-muse/native-office-powerpoint.json | `3c79e287923f38d4d14cd064906cd9e64db26dd66c38c2aa314182726812d472` |
| office-native-muse/native-office-word.json | `8b1918a717981613567662dd3b16b414ed240100f8a2f4bdc0bb820fe7f660c6` |
| office-native-muse-process.json | `d48d557afc0f3979c31a8f33d0addf21edb4706ee16ab0866c99ec243968ca42` |
| office-render-inventory.json | `fec8ed4e132be9bc8e475bce3deaa7c98a499cf49a51682e96baf688403d9898` |
| office-visual-review.json | `2fc00c11ee128681fc96a180dbec51a7e062ac719c94e39cfd50e7a1f7cac384` |
| office-wait-revalidation.json | `e4a42398583e565893fb4949d2a924795c4dd9511f5f38c419cef01db1525dca` |
| online-install.json | `986affebfb595deefedeaac16cfaf2c8ae3f4e6ebaa7bed2f021666c1399a6ee` |
| public-bootstrap-policy.json | `6651e6560a13454151fcf2c0eb36230f96a9756e6e04165fcbae728ce7f73a66` |
| qt-cascade2/desktop/interface-results.json | `aa824a6e5767e9d761b4fcb984bbca95cc318ab8f9bc42cc8a40d8ed894596e8` |
| qt-cascade2-process.json | `8fa764b1c3591dcb12f99ba66087896a0c55e194b2c8ee94e05837980cab6fd1` |
| qt-final-cascade2/desktop/interface-results.json | `6478fba6225c691105a33b57bd33e433969e1b59635318635eca17889bc97c4b` |
| qt-final-cascade2-process.json | `25baa95ed41e6c9e75bce403a35f488a65010e1fe93c85fa68da7961b01456ad` |
| qt-final-gptoss/desktop/interface-results.json | `be84fa6038ed5630889bc5766683ef63519614d5f85747fb3b81d00394516460` |
| qt-final-gptoss-process.json | `0b192b4de63a762aabf5209eb71ace465e3b5c761dcdf6885edf255a19c6fb88` |
| qt-final-lightning/desktop/interface-results.json | `eb22d72524eb99f8bfb92cb76788652190a3fa36a1ee67e800389db1ba083b71` |
| qt-final-lightning-process.json | `c4c071b1d1328f9623dc15af19f14688838717e39f61be91bde9939eae188787` |
| qt-final-muse/desktop/interface-results.json | `71f5cb4e3b77ea7bb5f6172afec48ec8f85c04d3bc8c65ce3f9f39d2a722702c` |
| qt-final-muse-process.json | `95f9f493889b411b4bdfb7d0be01452b9b6afad400208e03b7cd2dfbdc9681f2` |
| qt-gptoss-process.json | `f035738cd59358043afff223c719496dd007ae5fcc75965c4f1d3cea44d4ab84` |
| qt-lightning/desktop/interface-results.json | `0ed9c2980c2e49ceb8968c76bf5c557c661b0032c72a2a6288c7eb55deb26935` |
| qt-lightning-process.json | `a21f6f08e112b7d11bb4a9ecda4029c9e56f99b9899349adb65eabc9bd91ad80` |
| qt-muse/desktop/interface-results.json | `f74ca5e11d8a211e1265488b314c4ac97eef6b7bb365d55c97932c05887d54c0` |
| qt-muse-process.json | `9cae57ade2b0df2401844d5b7d622c12cb7fb3cf66c8824cd76798bec232402e` |
| qt-timeout-fault.json | `91c65fd7c6623e7734f761f06e356cf14bd45f559caf6b9192eb937105b2745f` |
| qt-timeout-final-negative/desktop/interface-results.json | `85093df7011704b1f37339f22fc1e8026e4943300f04dd60c84c1cfe375dbf87` |
| qt-wrong-profile-negative/desktop/interface-results.json | `92e3500b0bc456d702dd2605f056cd92423c31a74ca5247ad73463af5a6dfa3f` |
| qt-wrong-profile-negative-process.json | `3045bb7d634fa209c4263981d8570204f4cdfb5cdee9f5e003fb1d820873b2fe` |
| restore-nano-process.json | `bd6ac145b2e0278d4a8f73ed7d181716342fa9fb3b004c5ff1331a90bfe6f6d6` |
| select-cascade2-process.json | `72f214ac590fc5e3ff3b862ca639dc081384d4c9d4b7340573de5b134d9bbb56` |
| select-gemma26-process.json | `bea10b109e46c0731525d94907680dcff917f0ed43d95b7a69ce82eda1d96296` |
| select-gptoss-process.json | `4ab97a65c3a4bc8c21a788b4f8d6649bd420e8a0b266f20791580ab1f9f3dda6` |
| select-lightning-process.json | `2ffcb892e48d058f266bc7b5f1e054750bb7149838e241c34f88d56c954a47c2` |
| select-muse-process.json | `eae69b5ac5a2dcaf3acb16159b0c659cb2349af7cd5717b67c7bb312dfe1ee24` |
| select-nano-final-process.json | `84dc97bdd12d6c8a86ff4cf814b361578b75e275d74156947c3d188397a2b89e` |
| source-baseline.json | `eb7382de181db15d5d19d82d125385a8e549567f7c4a497a939ad4b5f95b940b` |
| source-final-3841b23.json | `aa334fb8c0c1d7ff756a9aad7dc057def4bc3d92325b7b6949ba93b45df1c7ab` |
| source-final-complete.json | `deb75338794bda20e767d8b410bfd37f8789fd9981fb36e3934ecdf29e438802` |
| source-final-connectivity.json | `5cabeda443ec89f66634298145f52bdbc07163011aca677692a45ed2ba027440` |
| source-final-office-wait.json | `bc096e0b125154f5bb57f46f5fb2a1926e4f9cea2d2baba4565e188c52e83653` |
| terminal-cascade2-process.json | `123b37ce670a2e3fdb63cfa1930662e744dda924b51fa502f6197a92b4eb7ccb` |
| terminal-cascade2.json | `dd2a18f0fba5969948d4d4a11ca2794f2c0a22877c41a3f5cfee02be43313757` |
| terminal-gptoss-attempt-accounting.json | `4fa684987f326d20cca4a826f40fe31f47dbf970965dd8243535b1a4d3e225d2` |
| terminal-gptoss-process.json | `e48fd80b0e11bcb225f59ef73bc9fc23c8bd0c5b0b9b16fee7a08dca053f005e` |
| terminal-gptoss.json | `0e06338910b1b5834b7f5b8df1d55d8a93eb3ee5757ac755a9d4c0f7218fb6e2` |
| terminal-lightning-process.json | `a18514ffe4dce332734f6884d949359c2e75a977986a1bf12c9544523e514b05` |
| terminal-lightning.json | `b07705e551c6187b12ee7c23c7853feaf8c0dc303b924c7528c4cf7497189eb2` |
| terminal-muse-process.json | `f8afb5da63ddbf99d962620ad9fa21cebcff0cbcc6704341eff4513a9873c99a` |
| terminal-muse.json | `435af70e633bbce13607fe8c2bcbd647c7b8afa5ac8e00d27dd00ca0ba53e102` |

The original application baseline contains 2,836 eligible files (up to 8 MiB, excluding `.git`, virtual environments and bytecode caches). Final cleanup must verify those hashes, no new eligible files, persistent native/modern PowerShell policy equality, and absence of owned workers/Office profiles/VHD/drive. This is a bounded restoration check, not a claim of secure erase or bit-for-bit Windows state restoration.

---

<!-- Historical report preserved below verbatim. -->
# Release-3 Windows follow-through validation — 11 October 2026

This third run follows the current GitHub `test_plan.md` after PR #19 and the release-3 documentation update. The user authorized an isolated installation, available synthetic tests, fixes/PR, and deletion of all run-created files. The original application has not been used as a test installation or edited. Raw receipts and synthetic state remain private; cleanup confirmation belongs to the final task handoff.

## Tested identities and changes

The fetched main baseline was `9f4435e7de88c966973d4c5023fe48a63559c28f`. Its executable source matches published release 3, `e3da3c10b96120744c130236f9e62bba83d033d3`; the differences are documentation. The fix branch starts from that exact released source. Executable workflow test commit: `3664d7f807d64c2676c0d3a2b31d6b0c7a7fbdd4` (native workflows); final test-only import/discovery commit `17e84d3d99b14502d3ae686b342b1a1d8b3b5cf2`. The fixed source was reinstalled instead of patching an immutable installation.

Two changes are included. First, an existing Windows session's byte-range lock can reject the constructor's initialization read before `msvcrt.locking` runs. Previously this escaped as `PermissionError` with the failed constructor's file handle unclosed. The entire initialization now shares the existing cleanup/refusal handler. A real native lock test confirms peer refusal, handle closure, preservation of the owner, and recovery after it closes; the installed negative retest also passed.

Second, the native model validator now checks the actual fact/units and exact line, PDF page and DOCX paragraph; a unique, correctly named, unsaved proposal with the real source path/hash; independent cleared chats; heading-search support; and ordinary/quoted-instruction scope. Missing genuine proposals leave review/save/replay cases explicitly not run. Private receipts record request/call/proposal metadata and the assertion-helper digest. Negative assertion tests reject missing/broad/wrong citations, wrong facts/units, unsourced/wrong/duplicate/saved proposals. The documented `-I` CLI explicitly resolves its new helper. The initial seven enhanced-driver attempts failed on that helper import before inference and do not count as model trials. Final review also caught and corrected an unintended UTF-8 decoding change in four startup messages before these trials.

No model/runtime pins, tool budgets, organization policies or code-acceptance gates were relaxed. Ordinary x64 Windows 11 Pro build 26200; i9-14900KF, approximately 64 GiB RAM, RTX 4090 with 24,564 MiB, driver 591.86, local fixed NTFS, application-local pinned CPython 3.14.8. Installation used process-only RemoteSigned under the user's existing authorization; persistent execution policies and global machine settings were preserved.

## Case ledger

| Stage/case | Status | Expected and observed outcome |
| --- | --- | --- |
| Original application | passed | All 2,836 eligible baseline files rechecked unchanged during the run; no original application writes. Final cleanup check is reported in the task handoff. |
| Released-code baseline source suite | passed | 558 executions, 312 successful methods, no failures/errors, 249 skip records covering 245 skipped methods. Counts include parameterized skip records. |
| Final corrected source suite | passed | 563 executions, 317 successful methods, zero failures/errors; 249 skip records. Windows-inapplicable and opt-in cases remain skips, not native acceptance. |
| Native installed-worker fixtures | passed / skipped | 52 executions: 50 successes, two skips, no failures/errors. Native symlink privilege was unavailable (1314); a POSIX review fixture was inapplicable. |
| Interrupted owned download / resume | passed | Transfer stopped at 2,113,929,216 bytes with no activation. Resume produced the exact 18,168,955,680-byte default-model pin; all ten install preflight checks passed. HTTP Range behavior was not independently captured. |
| Concurrent installer | passed | Same-root competing installer refused without activation. |
| Offline negatives / bad location | passed | Missing cache, corrupt pinned Python archive and overlong private socket root refused without activation. A real temporary NTFS junction was refused (exit 1); its owned target stayed empty and the verified alias was removed. |
| Public Zone-marked bootstrap | blocked | Verified anonymous release assets; native PowerShell 5.1 process-only RemoteSigned refused unsigned Zone-3 script. No zone removal or weaker policy; reviewed-source installation was used. |
| Final fixed-source repair | passed | Exit 0 and 10/10 native fresh-install preflight checks; final installation identity below. Earlier repair and its receipt were retained separately. |
| Installed launch / import negatives | passed | Desktop and terminal launcher rejected undeclared payload file; duplicate session refused; missing required policy anchor refused; unknown/missing/directory/small model imports refused; active record unchanged. |
| Shipped Nemotron model validator | passed | 15/15 original driver checks, real GPU/document/draft/cancel/restart/cleanup. This is the released-code baseline driver, not the stronger 18-case validator. |
| First actual Qt/Nemotron run | failed | 35 true checks, one false text-draft-review check, one error: request exceeded tool/context limits after saved-project reopening. Preserved as a first model-workflow failure. |
| Native same-prompt Nemotron reproduction | passed | Fresh real reopened synthetic project produced the genuine sourced draft without a source or budget change. Does not erase the Qt failure. |
| Model-authored Office review/save/read | passed | Actual Qt-authored DOCX/XLSX/PPTX reviewed, exact-byte saved, and contained-parsed; independent readers confirmed 48/60/108 kg and provenance. Excel values are literal strings; numerical-cell/formula compatibility was not established. |
| Native Excel / PowerPoint | passed | Excel content/no-formulas/no-external-links/PDF export and PPT content/geometry passed. Both Excel PDF pages and PPT slides inspected visually: readable values and source provenance, no clipping. |
| Native Word | blocked | New-document control passed; actual DOCX open exceeded 120 seconds. Independently authored control DOCX also timed out. Only owned Word processes were cleaned; output-format blame is not established. |
| Actual console Ctrl+U | passed (partial route) | On published release 2: startup update notice; unsent text, active inference, model menu and real pending draft each blocked update and preserved work. Ctrl+C canceled staging; the same console then returned 37 crates with exact line-2 citation. Idle Ctrl+U produced a real ticket and closed owned workers/vault. Launch hook captured the ticket instead of opening an updater window. |
| Published pair, selected Nemotron | passed installation / failed harness restart | Real release-2→3 staging, native selected-model preflight 10/10, activation, state/model byte preservation, previous record, selection and single-use ticket passed. Captured full-screen launch flags were passed to redirected streams; it exited 1 (`No Windows console found`). This route mismatch does not qualify default interactive restart and is not a redirected-code regression. |
| Published pair, no selected model | passed | Corrected private staging harness used the production selection key. Eight applicable preflight checks passed; GPU/cited inference explicitly not applicable. Real scrolling/plain redirected model-menu/quit restart exited 0; empty managed weights, selection/vault, previous record and ticket replay checks passed. The first wrong-key harness attempt was preserved separately. |
| Initial final-Qt driver attempts | blocked | All three stopped at the explicit active-saved-project prerequisite before opening a window. These are driver setup failures. The owned synthetic project was closed via the production terminal, and fresh actual-window retests followed. |
| Published pair, selected smaller model / removal | passed | Gemma 26B selected; actual terminal/model-menu No confirmation preserved GPT-OSS bytes, Yes removed the different 12,109,566,624-byte pinned model. Release-2 strict cp1252 redirected terminal returned the exact capacity citation. Native release-2→3 preflight, activation and real scrolling/plain resumed-citation restart passed; selected Gemma bytes/selection and vault bytes preserved before restart, removed GPT-OSS remained absent, ticket replay denied. |
| Selected and no-model native rollback | passed | Corrupt previous manifest refused and active record preserved; valid PS5.1 rollback restored verified release 2 and retained former-active/model/vault bytes. |
| Before/after-update connection observations | passed observations / not full isolation | Host GitHub/PyPI controls reachable; worker literal IPv4 TCP refused with WinError 10013; child creation refused with 367; ungranted reads/runtime writes refused; zero-capability AppContainer, no loopback exemption, cleanup passed. Owned loopback TCP timed out and UDP send returned success with no responder delivery. These are not qualified denial results. |
| Native code candidate | blocked | Fixed developer probe stopped before execution at trusted DiskPart executable attributes check (`0x40020`, regular file, two links, no reparse tag). All 19 acceptance cases remain pending. Opt-in native code suite ran nine tests and failed nine prerequisites; it did not pass. Reconciliation verified no owned VHD/drive/process before removing failed-provisioning leases. No model-generated code executed. |
| External responders / transitions / full isolation | not run | Controlled external UDP/IPv6, LAN, proxy/COM relay, full inference/graph/parser/OCR matrix, reboot, sleep and VPN transitions unavailable or require further scope; full isolation remains false. |
| Organization policy / native coding milestone | blocked | No independently qualified organization policy or release-bound native code acceptance. Open-code-workspace update guard and actual model-authored coding milestone are not qualified. |
| Interactive updater window / manual display | not run | Full default-console update-window→restarted Ready and manual DPI/display qualification remain pending. Console guard/ticket evidence and redirected restart are distinct. |
| Native update fault matrix | partial | Real publication/digest checks, concurrent install/session refusal, corrupt rollback, ticket replay and rollback observed. Remaining low-disk, changed-publication, activation/launch failure and interrupted-update fault fixtures are source tests; native fault/reboot coverage is incomplete. |

The trusted-tool attribute interpretation remains unresolved: Microsoft documents extended attributes and recall-on-open sharing the same numeric bit in different contexts. This is a possible compatibility cause, not proof of a qualified provisioning route. The guard was preserved. [Microsoft file attribute constants](https://learn.microsoft.com/en-us/windows/win32/fileio/file-attribute-constants).

## Real model and UI outcomes

| Profile / native trial | Status / checks | Cold ready (s) | Observed peak machine GPU (MiB) |
| --- | --- | ---: | ---: |
| Gemma 26B / 01 | passed 18/18 | 39.29 | 15596 |
| Muse / 01 | passed 18/18 | 49.408 | 16844 |
| Muse / 02 | passed 18/18 | 54.502 | 16844 |
| Muse / 03 | failed host TLS control; model tasks not run | 45.586 | 16824 |
| Muse / 04 | passed 18/18 | 46.365 | 16862 |
| GPT-OSS / 01 | failed: pdf_docx_deadline_citations; 17/18 | 58.38 | 12494 |
| GPT-OSS / 02 | passed 18/18 | 38.737 | 12494 |
| GPT-OSS / 03 | failed: correct_capacity_citation; 17/18 | 40.179 | 12494 |

Muse completed three fully passing stronger trials (01, 02, 04); the intervening 03 host-control failure is retained. GPT-OSS passed one of three complete trials: 01 stopped on the combined exact PDF/DOCX task; 03 stopped on the direct exact capacity task. Both later heading-search cases and all actual named-draft review/save/replay cases passed. These mixed results do not qualify GPT-OSS consistency. Gemma 31B and Gemma 12B were not rerun in this focused update.

| Interface / selected profile | Outcome |
| --- | --- |
| Terminal / Muse | passed; 12/12 attempted checks; 0 recorded errors |
| Terminal / GPT-OSS | failed: capacity_exact; 11/12 attempted checks; 0 recorded errors |
| Qt / Nemotron final | failed: office_docx_model_proposal; 39/40 attempted checks; 0 recorded errors |
| Qt / Muse | passed; 43/43 attempted checks; 0 recorded errors |
| Qt / GPT-OSS | passed; 43/43 attempted checks; 0 recorded errors |

The final Nemotron Qt run passed its text-draft workflow but failed the DOCX proposal at the tool/context limit; its DOCX review/save/read follow-ups were not run. XLSX/PPTX and remaining workflow/lifecycle cases continued. Muse and GPT-OSS each passed the actual Qt driver’s 43 checks; their document receipts were additionally reviewed for exact page-2/paragraph-2 locators. Terminal capture observed actual native adapter replies through the installed production entry point, with unchanged handlers and redirected strict cp1252 streams. Muse passed all 12 terminal checks; GPT-OSS stopped on the direct exact capacity task, with 11/12 checks true. No terminal draft was auto-approved or saved. The GUI’s static assistant label is not used to infer model identity; the explicitly selected profiles and pinned startup routes are recorded separately.

Every independent stronger trial uses the exact requested pinned profile and a new native session, with chat cleared between requests. Reports bind source ID, manifest, model pin, driver/support hashes, UTC interval, cold start, call totals and whole-machine GPU samples. Peak GPU readings are not exclusive allocation. RAM and tokens/s were not measured. The actual corrective-turn reason is not instrumented; call totals do not identify a bounded correction. Source tests cover the correction/permission/budget contracts, but this run does not qualify a live correction trace or every off-topic/garbled-response case.

## Installation and published asset identities

| Installed source / role | Source ID | Installed manifest SHA-256 |
| --- | --- | --- |
| Released-code source install | `567828fae2d61509` | `b85f717fa99f3508f8bb3f293957afa4fd4ced211d6f6fb8c9858c11b6768ed6` |
| Native model/interface fixed source | `c0cc5e8dcf4cca94` | `d85b114db42364271290b9906171963a5129235737077b69a1b86c0657a41d05` |
| Final test-only source repair | `c0cc5e8dcf4cca94` | `d85b114db42364271290b9906171963a5129235737077b69a1b86c0657a41d05` |
| Published sequence 2 | `1b04a66b2b47f205` | `1a400f44df6e3ef8dfefc97dd34de242a17f6d7fc08fa32ab53ffab79fd3be50` |
| Published sequence 3 update | `900d9e55ba242a3c` | `63c9de2cd07b8ccaad16b753f8d2e024a2b35330a16a1430d1eb159bc260fecc` |

Native model and interface outcomes bind commit `3664d7f` and source `c0cc5e8dcf4cca94`. Commit `17e84d3` only resolves the new test helper under ordinary unittest discovery; production source, scripts, profiles and pins are byte-identical. The final source suite again passed 563 executions / 317 successful methods / 249 skip records with no failures or errors, and the final reinstall passed all ten native preflight checks. This distinction does not carry forward any deployment or code-acceptance qualification.

evaluation-2026.10.11-silo.2: bootstrap `bc810719bf82abf701e3c9cf4470f0530d9b3d2e3ef91fd1058870824ba40356`; source ZIP `4fbac7bcfe8dfb0f450c6d09b4778760d8fcb37bc55a760b4a165f86c8892e1d`; source manifest `afc68c34e5c5a4c7e453c43b0714e61f25737f09e866fede0eefa514994306b3`.

evaluation-2026.10.11-silo.3: bootstrap `4e43dab5186bbfe3a39336093358397aa1298163a6b18c4768a93d13c977b75e`; source ZIP `36c90656f3407f71c0461184420cd97ce55c4f3001879da642305edafa624c27`; source manifest `d85f1ee22f06addfef91c58edd781490478bb4eb5386cb9f831bb0bc0e2b92a3`.

Published sequence 2 is `evaluation-2026.10.11-silo.2`, source `f7995d48cdbfecc15145e2e91f2d1ddb6dd80e68`; sequence 3 is `evaluation-2026.10.11-silo.3`, source `e3da3c10b96120744c130236f9e62bba83d033d3`. All eight assets were anonymously fetched and checked against independent GitHub API size/SHA-256 values. Extracted source inventories (228 and 230 files) match their pinned source manifests. No release was published or mutated.

Private-receipt checksum witnesses (raw contents are intentionally excluded from GitHub and will be deleted on the requested cleanup):

| Local case receipt label | SHA-256 |
| --- | --- |
| `source-baseline.json` | `6c2c6ce72a51c1a642f7cd01282385f3071617546d65dd76efa6d6718009fad7` |
| `source-final-portable-test.json` | `6d2eda3f0d807bc2f51359eb7b8acc7afe4f9d76950401085fbf0c4ae1130fde` |
| `native-complete-fixtures.json` | `aecda171ea3598de0c04dc7baa3f9d28b6d215c094966c4489d71e5e215c7a35` |
| `native-negative-results-03.json` | `2d83224e7a9eb439794edaa7b285c578e86e8700f341645f849904627244b717` |
| `original-recheck-before-cleanup.json` | `461f09f0941fabf65709c3b47c4385731bc8f66dd0259ccc49dc17be14c97564` |
| `nemotron-shipped-validator.json` | `71b33b07f5344bee2a3f950d2f41bd786b20ccc22bb4391b0977cde0c4b50371` |
| `nemotron-draft-repro-02/result.json` | `3fb8f4c49b99b2004a556e57fbaaf761a4e517e1d1a9c81ccc8e17cad4f2c9ec` |
| `qt-nemotron/desktop/interface-results.json` | `1cd86772540fe80015e0f9da843875abf65e2c3909dab2244a1eb0514aeaa37f` |
| `qt-nemotron-final/desktop/interface-results.json` | `6d13c6b7a0b0b34db54d3fea91d6dd8a1de14b737c38ab41b2df7712241b2b7e` |
| `qt-muse/desktop/interface-results.json` | `47d3fc5079822ee834cf943520b398f3b5a23585fd3f457f5f8d58342f4c28e2` |
| `qt-gptoss/desktop/interface-results.json` | `7cb73edaa27edaeb63d4e102bac3e60f4832dd4c1bdc4073abee00decd07dd28` |
| `terminal-muse-final.json` | `c173cc4f90544555eb1fc2fe8a3059872908f7be638e6beb3509f6647df7fadd` |
| `terminal-gptoss-final.json` | `f4157efb590d0e2a92233b91a778fa5557d8ae196383a343f2b708c321933520` |
| `pair-selected-install.json` | `3cb86ed5b33505f847dfe7d947dd0892bf96c03a159a86b8ded99e64c8652831` |
| `pair-none-install-02.json` | `1cb0ccacde2ac22f80c5d9a6be30b6365c140befbab88375c4d4fcb0194b55ad` |
| `pair-rollback.json` | `cc11518393751d6a4de0645b5f79c1611d3c440aa2858784bb72d7859eb6e3d8` |
| `pair-none-rollback.json` | `2027efd9264d175d227a87edfe7a9e301fb49884d2d3e9581525d6d06dc02902` |
| `pair-smaller-stage.json` | `ff3e95ef56882a5abed48e3ba1f77c11b48493dea678fc5cee992e2a3eee92c2` |
| `pair-smaller-install.json` | `fb57f007c5cbbb188163a51199c47aebd7b8ab90e1aafbb0d3adcdf4d43ebec1` |
| `repair-final-test-import.json` | `69958b5f3a84436f54c8bcb32a07363de3bfa22564acad28d1c09adb1cfeaffc` |
| `network-observations.json` | `efc24e4c3ed5cbad8ee9a50eea9162c13ff8ce346b35353685664dd9fef8b6fd` |
| `network-release3-observations.json` | `062c7290d88d729321acaf40d6ebe6414719d73c9a783a3da342b80f921b8451` |
| `native-code-fixtures.json` | `afe7b16698012436008d8d3315ebb21f8f79f7bf730e47d006fb3a267f2b3d3b` |
| `native-code-candidate.json` | `0dd600a4b90f95cacede6ead370440c1ed16362447dae32a63df32fb6e9d20e3` |
| `native-code-candidate-02.json` | `0dd600a4b90f95cacede6ead370440c1ed16362447dae32a63df32fb6e9d20e3` |
| `negative-junction.json` | `0764eff7c1a55bbbe98ee7ba0be1896b4c2533ae9ca807f2a5c94d67fbd71dab` |
| `model-gemma26-native-01.json` | `fa57013ee3c6d61d6fa831451661acf9b6eaca3646c43cee3c8ec07c67770fe1` |
| `model-gptoss-native-01.json` | `8e67c78f61821d72edfce7b3f782766e8524ace6c6daf6348ab8a579b11ea264` |
| `model-gptoss-native-02.json` | `4c5ff3dd90cee9fec6703a79d1d5113dbf94b95a447e3909ec1344645e2685d6` |
| `model-gptoss-native-03.json` | `3e1327da7e9a71a775bb0c33e61737504635651b6885eda11187990c67e344da` |
| `model-muse-native-01.json` | `94f66600bfc708bbe754ec7958d3627726fc440a6bfd076bf1228f1f9df15668` |
| `model-muse-native-02.json` | `5f27d5fb061f1ed9ca86ccd19fed2b6e364df75f5bae3e06d843e531a6c5ab25` |
| `model-muse-native-03.json` | `03c6d02360d3bfb5f90b6003deb4c23d5f980943d6c9a3690e686d93e6e1a4ce` |
| `model-muse-native-04.json` | `83ac8b9cf08ed4b98ae45537655076b71d5ec8285424b3ee38d2df96140d203b` |

Installation/lifecycle validation passed within the documented source/manual routes. Desktop/terminal and model results retain their individual failures and coverage limits above. Full network/IPC acceptance, native generated-code milestone, distribution signing/licensing and organizational CUI authorization remain **unqualified**. Deployment-ready, full-isolation and code-acceptance values remain **false**.

---

The following report is historical evidence from the preceding runs.

# Repeat Windows validation - 11 October 2026

This run follows the updated test_plan.md after the model-menu and terminal-updater merges. The original application is separate from every test root; all 2,836 baseline files were rechecked unchanged during testing. Raw receipts, prompts, paths, keys, weights and caches are private and will be removed after the PR handoff at the user's request; final cleanup confirmation is in the task handoff. Persistent execution policy, PATH, firewall, adapters, WSL and drivers are unchanged.

Full deployment, full isolation and native generated-code acceptance remain **false**. Default desktop shortcut execution under persistent Restricted policy, manual console keys, display scaling, reboot/sleep/VPN transitions, controlled external UDP/IPv6/LAN/proxy responders, organization policy enrollment and the two-published-release updater matrix remain unqualified. No test release was published.

## Source and fixes

Baseline main: `c647296707ad6e26eb5ef122f5fb856fae2c80ce`; published updater release: `evaluation-2026.10.11-silo.1`, source `f018f0d62f2baefaebf71c947b1bf8678ca9369f`, sequence 1. Main differs from that release in documentation. Native fixture fix: `ee77258ad044532c5d5d03f8b52629786dc310b6`. Final executable source: `1dd147b87fb38630635064ca5dafd33f961bd061`. Redirected input was fixed in `80def3eb1619cf6f7c32473d696b9f2f0b4ea915`; console/validator follow-up in `6cfcc9b8945468ff02ac450c87b1ffb8836fed58`; legacy-stream Unicode rendering in `1dd147b87fb38630635064ca5dafd33f961bd061`.

A fresh native suite initially reported 28 errors: 27 Qt cases assumed a source-tree scratch directory existed; the instructions fixture bypassed the constructor and omitted `model_manager`. The fixes use an ordinary temporary synthetic tree, initialize the new field, and replace repository-ancestor overlap grants with the synthetic fixture parent. No interpreter/model pins or execution/acceptance boundaries were relaxed. The intermediate overlap failures and first 28 errors were preserved before correction.

Environment: ordinary user, x64 Windows 11 Pro build 26200, i9-14900KF, approximately 64 GiB RAM, RTX 4090 / 24,564 MiB, driver 591.86, fixed local NTFS. Application-local pinned CPython 3.14.8. Seven separately versioned and PyPI-digest-verified diagnostic Office reader wheels were used outside the application; no pip setup hooks or application lock changes.

## Completed evidence

| Case | Outcome |
| --- | --- |
| Source suite after fixture fixes | 537 executions, 291 successes, zero failures/errors; 249 skip records. Source/scripted contracts, not complete native acceptance. |
| Final source suite after all fixes | 540 executions, 298 successes, zero failures/errors; 245 skip records, including parameterized skip records. The preceding source at 6cfcc9b also passed (539 executions, 297 successes). Focused terminal/update suite: 25 executions, 20 successes/five skips; input/real-key-binding retest: 15/15; final presentation/input/key-binding retest: 19/19. |
| Extended suite with installed workers and independent readers | 537 executions, 311 successes, nine errors at native code prerequisites, 217 skip records. This extended run did **not** pass. |
| Focused installed-worker/storage/folder fixtures | 73 executions, 61 successes, zero failures/errors; 12 skip records. Includes AppContainer/IPC, malformed parser input, NTFS staging, DPAPI retention/backup/recovery. Native symlink privilege was unavailable (1314). Four optional independent-reader cases subsequently passed in the extended suite. |
| Interrupted default-model acquisition | Owned transfer stopped after 10,234,101,760 bytes, no activation; partial retained and resumed to the exact 18,168,955,680-byte pin. |
| Concurrent installer / live session | Second same-root installer refused; second real session refused while the Qt session owned its lock. |
| Online install | Exit 0; all 10/10 required preflight checks. Source ID/version `4fb8e093b50eaf33`; manifest `f6406ef54e858ac4b748dff18f7adbec40478f02b239e6d04e09c64d2d6523cf`. |
| Fresh offline install from verified populated cache | Final full retry exit 0, all 10/10 checks; manifest `cbed08b23945847dcbca106f65bbad092d6377871cd3142e32df77296ba8eaca`. Connected workstation with offline acquisition flags; disconnected clean-machine coverage is pending. |
| Offline first failure | Trusted GPU inventory executable rejected before GPU startup. The retained payload passed an identical direct preflight, then the complete installer retry passed. Root cause of the earlier inventory refusal remains unresolved. |
| Idempotent rerun | Exit 0; exact active record and version set unchanged. |
| Missing/corrupt offline cache and overlong root | Refused without activation. Initial corrupt-cache harness used the wrong filename field; the actual corrupt-file retest failed its expected size/hash check. |
| Published PowerShell bootstrap | Anonymous assets verified against GitHub size/digests. Zone-marked unsigned install.ps1 was blocked by native PowerShell 5.1 under process-only RemoteSigned; no bootstrap install root was created. No zone removal or weaker execution policy. |
| Real Qt + Nemotron | 43/43 checks, no errors; cold ready 45.564 s, peak observed GPU use 18,657 MiB. Offscreen rendering, not manual display qualification. |
| Separate Nemotron model workflow | 15/15 checks, no errors; cold start 44.094 s. |
| Actual model-authored Office files | Separate review/exact-byte save and contained parsing passed. Independent readers confirmed 48 kg, 60 kg and 108 kg total; both native Excel PDF pages and both PowerPoint slides visually inspected. |
| Native Excel / PowerPoint | Opened actual generated files; Excel values/no formulas/no external links/PDF export and PowerPoint values/geometry/two slides passed. |
| Native Word | New empty-document control passed. Opening both SILO's DOCX and an independently authored DOCX exceeded 120 seconds; only verified owned automation processes were stopped. File-opening compatibility is blocked, not a confirmed SILO format defect. |
| Partial worker network checks | Reachable host GitHub/PyPI TCP controls; worker literal IPv4 TCP denied with Windows 10013. IPv4/IPv6 loopback TCP timed out and UDP send returned successfully, while responders received no worker bytes. These loopback observations do **not** prove effective denial. |
| Native code candidate | Trusted disk-provisioning tool rejected before a VHD image/drive existed; lease retained. Eight later native-code cases refused the unreconciled lease. All 19 boundary gates and the coding milestone remain pending; no generated-code acceptance or model code execution. |

## Real models and native menu

All six pinned profiles loaded on CUDA0 without CPU spill. Exact-profile model workflows are separate from native menu/controller tests; their outcomes were not inferred from download success.

| Profile | Workflow outcome | Cold start (s) | Peak observed GPU use (MiB) |
| --- | --- | ---: | ---: |
| Nemotron 4090 CP314 | 15/15 checks passed | 44.094 | 18,655 |
| Gemma 4 26B A4B Q4 | 15/15 checks passed | 41.458 | 15,709 |
| Muse Glimmer 30B Q4 | 11/12 checks passed; real draft proposal missing | 45.503 | 16,957 |
| Gemma 4 31B Q4 | 15/15 checks passed | 47.857 | 20,167 |
| GPT-OSS 20B MXFP4 | Corrected native retest: 14/15 checks passed; capacity answer failed | 46.769 | 12,589 |
| Gemma 4 12B Q4 | 15/15 checks passed | 31.477 | 8,701 |

Muse answered the document questions but returned proposed text without invoking a proposal tool. The host saved nothing; the three dependent review/approval/single-use cases were not run. GPT-OSS's first capacity reply cited the document as `[source:S1]`, without the requested exact line; nullable citation positions crashed both the public validator and the private menu checker. The diagnostic correction keeps the exact-line requirement and continues the remaining checks. Its final installed-payload retest completed all 15 checks without errors: 14 passed, but the capacity request read only the heading and did not produce the available 37-crate line-2 answer. The later PDF/page-2 and DOCX/paragraph-2 replies used actual exact locator tags, and a real sourced proposal passed review, exact-byte save and single-use approval. Cancellation/restart/cleanup passed. The earlier exception and later failed answer remain separate failures. Peak GPU numbers are whole-device observations, not process-exclusive measurements. RAM usage and token throughput were not measured.

The actual host menu/controller passed 11/11 lifecycle checks: invalid input and cancellation stay in the host menu, canceled download does not publish weights, an unknown switch preserves the ready session, confirmed deletion removes all managed weights, last-model removal unloads inference while keeping parsers/project/instructions, no-model restart retains the menu, exact offline import restores Nemotron, and owned cleanup completes. All five alternative switches retained the saved synthetic project/task instructions and fresh verified folder identities, and cleared old chat/pending reviews. GPT-OSS's exact cited-answer menu check remains failed/unqualified; the other four alternatives passed it. This used production controllers with captured output, not manual console keys.

Private harness failures were kept separate: the first menu attempt used a nonexistent folder path field and inadvertently ran the default profile's checker. That receipt does not qualify Gemma 26B; the later explicitly bound Gemma workflow passed. The initial rollback harness inherited the PowerShell 7 module path and assumed a vault context manager; the corrected harness removed the module path case-insensitively and explicitly closed the vault.

## Native updates, negative cases and repair

The published sequence-1 release was actually staged, prepared, preflighted and activated from a Git-source installation with no release origin. This is **not** the two-published-release/increasing-sequence matrix. Selected Nemotron passed 10/10 native checks; no-model mode passed all eight applicable checks with GPU/inference explicitly not applicable. Selected model bytes and encrypted vault records matched before restart; absent weights stayed absent in the no-model run. Both retained the previous active record, denied claimed-ticket replay and reported no newer compatible release afterward.

Both actual restarted production terminals used `--scrollback --plain` with redirected streams for controlled process ownership. The published source exited 1 with `No Windows console found`, so restarted Ready and the resumed cited request did **not** pass. The PR now uses ordinary input when either stream is redirected and preserves the interactive Ctrl+U prompt binding. A first broader retest timed out because the old console fixture did not declare its streams interactive; its corrected real-key-binding test and the final full suite passed. Default new-console presentation, human key presses and reboot remain unqualified.

A separate corrupted staged-ZIP native test refused preparation, kept the active record unchanged and denied replay. Its failure-restart spawn was stubbed; it does not establish actual automatic recovery. A concurrent staging attempt during model operations detected changing file metadata and stopped; staging while idle later passed. The earlier staging parent PID had been reused by Windows, so a fresh exited staging process supplied the actual positive handoff.

Native desktop and terminal launchers refused an undeclared payload file before inference; the fixture was removed and the active record stayed unchanged. A missing required policy trust anchor refused terminal startup. Missing/small/directory/unknown-model imports were rejected without changing the selection or published weights. These are fail-closed observations, not qualification of an enrolled organization policy.

Both selected-model and no-model installations refused a corrupted previous manifest without changing the active record. Subsequent native PowerShell 5.1 rollback exited 0 and restored the verified previous version, retaining the formerly active record, exact managed-model bytes, encrypted project bytes and selection.

The first repaired source (6cfcc9b, source ID `e6a0eb4d1da85683`, manifest `e539f5c4c721caf94c72c3be8ee76b3b45bd2644b36a90c1fddcb23c1b20ed35`) passed 10/10 native preflight checks. Both redirected terminals exited 0 and saved project/selection remained intact, but the cited reply hit a cp1252 UnicodeEncodeError on a narrow space. That first request remains failed. TerminalView now escapes only unsupported code points before wrapping, preserves Unicode on UTF-8 streams, and retains terminal-control/bidi sanitization. Strict ASCII/cp1252/UTF-8 tests preserved exact citation text and width.

Final clean-source repair (1dd147b, source ID/version `87a2ae3c03c16ce5`, manifest `c316240bcfeef138b53b2db581e7f0ef62716ecfa780321d5693fe4fad5b0e61`) exited 0 and passed 10/10 native preflight checks. The actual production scrolling/plain terminal passed 4/4 checks: no-model menu/quit, selected-model startup/quit, resumed synthetic folder grants and correct 37-crate line-2 citation, and retained saved project/selection. Both terminal processes exited 0. The real answer included narrow spaces, rendered as visible code-point escapes on the legacy output stream.

Earlier Qt/menu/model receipts bind the baseline executable source ID `4fb8e093b50eaf33`; the repaired preflight/terminal receipts and corrected GPT-OSS workflow bind `87a2ae3c03c16ce5`. Native fixes were reinstalled and tested rather than inferred from source fixtures. These partial routes do not qualify the published release's default interactive restart or the complete update matrix. Publication/signing/licensing/CUI review, the complete network/IPC transition matrix and all 19 native code gates remain pending.

---

## Historical report from the previous run

The following report records the earlier validation already merged in PR #13. Its raw local evidence was deleted after that handoff at the user's request; it must not be treated as evidence for the newer executable source.

# Windows validation report

Synthetic Windows evaluation on 10-11 October 2026. The old project was left intact (101 baseline source/configuration/document/test files rechecked byte-for-byte); work used a separate checkout and disposable installations. Raw logs, prompts, inventory, keys, caches and weights remain local.

Full deployment, full isolation and native generated-code acceptance remain **false**. Passing source fixtures or document smoke tests do not close those gates.

## Source and environment

- GitHub main baseline: `ceaeb04db43eb97d5edec9d9c81b6231b430abbe`; six-model merge `61d2ccb1047f9f6c48d51afe54a4b56cc77aa549` is an ancestor.
- Windows-tested executable source revision: `703f6e78969da2ee83fc2066114f2e0378c6d9df`. The review follow-up below changes the executable source; these Windows receipts do not qualify that later revision. Installer inventory excludes this report.
- Ordinary user, native x64 Windows 11 Pro build 26200, Core i9-14900KF, approximately 64 GiB RAM, RTX 4090 / 24,564 MiB, driver 591.86, fixed local NTFS.
- Pinned application-local CPython 3.14.8; separate verified host, document-worker and code runtimes. No application dependency was installed from pip. Optional independent Office readers were added only to the separate diagnostic interpreter.
- Windows PowerShell 5.1 used process-only RemoteSigned with user authorization. Persistent policy, global PATH, firewall, adapters, WSL and drivers were unchanged.
- Merged-source installation route: the initially published installer targeted older `899284b...` source. A matching public bootstrap was not tested or published.

## Confirmed fixes

| Defect | Change and verification |
| --- | --- |
| Fresh PowerShell 5.1 could not resolve ZipArchive | Load System.IO.Compression explicitly before FileSystem; pinned interpreter extraction and native installs retested. |
| CPython 3.14 Windows lstat/fstat time mismatch rejected valid assets | Distinguish birth/metadata timestamps while retaining descriptor mutation and single-link checks; same-size tampering with restored mtime still rejected. |
| Git CRLF conversion changed pinned JSON/fixture bytes | Exact LF attributes restore the reviewed bytes; hashes and model pins were not replaced. |
| GPU inventory rejected a system servicing hardlink / failed NVML in a minimal environment | Permit the fixed OS GPU tool, and supply machine ProgramFiles from Windows API. Payload link restrictions remain strict; native hardware fit now gates preflight. |
| Repeated launcher publication failed in PowerShell 5.1 | Use Language.NullString.Value for File.Replace; publish-twice fixture and repair retested. |
| Native PowerPoint rejected generated PPTX | Add fixed internal master/layout/theme/properties parts and relationships. Independent reader and real PowerPoint opens/rendering retested. See [Microsoft structure reference](https://learn.microsoft.com/en-us/office/open-xml/presentation/structure-of-a-presentationml-document). |
| Native shortcut creation failed after successful activation | Avoid empty IconLocation; native present/missing-icon fixture and final installer integration retested. |
| Native tests assumed development worker paths; UI validator granted a repository ancestor | Use explicit verified installed workers, retain only synthetic child grants, and add repeatable model/UI/Office/regression drivers. |

First failed runs were retained. A separate final harness failure came from inherited pwsh module paths in a PowerShell 5.1 child; native child defaults resolved it without persistent environment changes.

## Installation and regression results

| Case | Result |
| --- | --- |
| source-repair | Passed; exit 0 |
| idempotent-rerun | Passed; exit 0 |
| offline-new-root | Passed; exit 0 |
| corrupt-rollback | Passed; exit 1 |
| valid-rollback | Passed; exit 0 |
| restore-current | Passed; exit 0 |

Final active source ID/version: `166ef18045bd6e69` / `166ef18045bd6e69`; manifest SHA-256 `0de52cde5bd3867b5000da247ad585c2ba7db2eba4ad7ea57ee044437b4ec3fd`.

Broad suite: **489 test executions**, 264 successes (255 distinct passing IDs), 225 skipped method executions (224 distinct IDs; 228 skip records), zero failures/errors. Imported unittest classes cause repeated discovery. These counts are source/scripted contracts, not complete native acceptance.

Native storage lifecycle: six passing DPAPI/NTFS encryption, tamper, concurrency, backup/recovery and retention cases. Native staging: six passing cases. Strict native folders: 13 passed, one symlink-privilege case skipped (WinError 1314); strict folder gate is incomplete.

Interrupted 18,168,955,680-byte default-model acquisition retained its partial, refused a concurrent same-root installer, and resumed to the exact pinned digest. Disposable missing/corrupt caches and overlong root were refused without activation. No original valid cache was corrupted.


Final online and fresh offline preflight each passed all **10/10** required checks. Both installations use source ID `166ef18045bd6e69`; offline manifest SHA-256 is `cdd7e3c36831628848dc4b54016772429f6f633792ce6149079e493a4b7a617e`. The offline run used a verified populated cache on a connected workstation; a disconnected clean machine remains untested.

Repair preserved all three existing encrypted synthetic project records and preferences by hash. Idempotent rerun kept the same active record and version set. Both desktop and terminal rejected an undeclared inert payload file for the expected integrity reason; the exact fixture was removed and active/manifest bytes stayed unchanged. Desktop and Programs shortcuts have the expected target and an existing icon.

**Ordinary desktop launch remains blocked** by effective Windows PowerShell 5.1 `Restricted` policy. All persistent native policy scopes remained Undefined. Installation/launcher tests used the separately authorized temporary process-only RemoteSigned scope; no persistent policy was changed.

Final verified installed parser/IPC/Office fixture run: 37 executions, **31 passed**, six portable-only skips, zero failures/errors. This includes actual AppContainer hostile-document handling, malformed/replayed/bounded IPC, denied child creation and recovery.

## Model and workflow results


Final executable source was also exercised through the committed desktop driver with real GPU models and Qt offscreen rendering:

| Model / installation | Result | Cold ready (s) | Peak whole-machine GPU used (MiB) |
| --- | --- | ---: | ---: |
| Nemotron / fresh offline root | 43/43 workflow checks passed | 66.304 | 18655 |
| Gemma 4 31B / online root | 43/43 workflow checks passed | 72.163 | 20167 |

These runs include actual cited text/PDF/DOCX questions, saved-project context/grants, unsaved proposals and separate exact-byte approval, stale approval/source drift/collision/replay refusals, model-generated DOCX/XLSX/PPTX proposals with contained roundtrip, a real scheduled model request with exports left pending for review, uncertain-slot reconciliation, revocation, cancellation/restart and cleanup. Native display scaling and manual console interaction remain unqualified.

The Nemotron-approved model artifacts also passed native Excel and PowerPoint compatibility: correct 48/60/108 kg values, no spreadsheet formulas or external links, two rendered slides. All two Excel pages and two slides were visually inspected and were legible without observed clipping/overlap. Native Word compatibility remains blocked as described below.

Five additional pinned models were imported through the actual manager, selected individually and run with real GPU/AppContainer inference. The following baseline receipts bind source ID `98a8ade7914933c5`, manifest `d453e1d4989537cd0d4d261080a620068c422411643f8a02b23b1a108a042922` (code revision `005ae94...`). Later installer/Office fixes do not retroactively turn these into final-release acceptance.

| Model | Basic document/draft result | Cold ready (s) | Restart (s) | Peak whole-machine GPU used (MiB) |
| --- | --- | ---: | ---: | ---: |
| Gemma 4 26B-A4B | Passed basic checks | 74.006 | 94.168 | 15745 |
| Muse Glimmer 30B | Failed: claimed pending draft with no proposal | 62.781 | 62.081 | 16957 |
| Gemma 4 31B | Passed basic checks | 74.937 | 63.061 | 20167 |
| gpt-oss-20b | Failed: first cited answer rejected | 66.552 | 85.586 | 12667 |
| Gemma 4 12B | Passed basic checks | 56.892 | 46.706 | 8701 |

Basic checks cover the 37-crate fact, PDF page/DOCX paragraph deadline citations, actual unsaved proposal, separate review/exact-byte save/single-use approval, source preservation, revocation, real cancellation, restart, cleanup and host connectivity. They do not establish general factual reliability. RAM and tokens/s were not measured.

Earlier Nemotron receipts are retained as failures: it passed native preflight and 23 first desktop checks, including text review/save invalidation and saved-project reopen. Subsequent requests failed: a DOCX proposal hit tool/context limits, and another text-draft response claimed a pending proposal without creating one. Cleanup completed. That earlier run's offscreen cold ready time was 90.633 s and peak GPU used 18,655 MiB.

The Gemma 26B terminal mechanics passed, including actual installed scrollback launch, project/backup controls and refusal of unaccepted code. **Capacity accuracy failed**: the answer led with 124 kg despite deriving 48 + 60 = 108 kg. A first checker merely searched for 108 and was too weak; independent saved-history review supersedes that factual pass. Terminal keys/fullscreen interaction were not qualified by piped input.

Saved text drafts for several models retained literal internal source markers; exact-byte publication passed, but polished standalone citation presentation is not established. Missing/corrupt/unknown imports and unavailable selections failed closed, including an exact-size sparse wrong-digest model. Default Nemotron selection was restored.

## Isolation, Office and remaining gates

Owned IPv4/IPv6 TCP/UDP loopback host controls were reachable. Workers timed out or sent without an attributable OS error, while responders received no worker marker. Those cases are **blocked/inconclusive**, not denial passes. An external IPv4 TCP connection produced WSA 10013 with a reachable host control; host HTTPS before/during/after was preserved. These are partial observations, not N01-N09 acceptance.

Full external UDP/IPv6, LAN, proxy, DNS-route, resource/descendant/interoperation and sleep/reboot/network-change coverage remains not run. The user authorized available checks and explicit coverage gaps. Native malformed/replayed/bounded IPC and hostile contained document-parser fixtures provide partial I01/I02 evidence.

Host-authored synthetic Office fixtures were reviewed and approved through the actual broker and parsed in an AppContainer; this establishes format/authority behavior, not model authorship. Excel opens expected values without formulas/external links and exports a legible PDF. Fixed PPTX opens/rendering succeeds in PowerPoint. One conservative batch retry was blocked while the preceding test-owned blank PowerPoint control was still closing; the separate native retry passed. That blocked batch receipt remains intact. Native Word open remains blocked: SILO and independently generated DOCX both time out even with OpenNoRepairDialog and native module defaults; blank-document creation succeeds. Only verified test-owned Office processes were retired.

Native code provisioning is blocked before DiskPart execution by trusted-system-tool metadata validation (attributes 0x40020). An owned inert unreconciled lease is retained, with no VHD created. The 19-check acceptance and generated-code milestone were not completed; code stays disabled. No gate, token capability, profile limit or acceptance record was lowered/manufactured.

Native display scaling, manual terminal keys, sleep/resume/reboot, clean-machine no-Python validation, missing non-NTFS/UNC/reparse locations, complete native code containment, full gpt-oss private-reasoning lifecycle, organizational signing/licensing and CUI authorization remain unqualified.

## Repeatable test entry points

Use the same pinned diagnostic interpreter for source regressions and optional development-only independent Office readers. Keep reports outside the source and immutable payload. Use the installed host interpreter for model/UI/Office drivers. Close clients and select the intended model before GPU tests.

```text
scripts/run_windows_regressions.py --source <checkout> --output <new-private-report.json>
SILO_NATIVE_TEST_ROOT=<active-payload/app>  (process environment for native fixture runs)
scripts/validate_windows_model.py --root <active-payload/app> --output <new-private-report.json> --model-id <selected-id>
scripts/validate_windows_ui.py --root <disposable-payload/app> --evidence <new-private-directory>
scripts/validate_windows_office.py --fixtures <approved-synthetic-office-directory> --evidence <new-private-directory>
scripts/test_evaluation_bootstrap.ps1 -PythonArchive <exact-pinned-cache-archive>
```

Use only synthetic fixtures. The UI driver refuses an active saved project, and these drivers do not enable code or accept full isolation. Raw evidence is retained privately with per-case hashes and source/profile bindings in the final ledger. The final process audit found no remaining Python or Office test processes. The blocked code lease is intentionally retained. No release was published and no PR was pushed or opened during testing.

## Review follow-up

Reviewed executable source: `ecde357d0596171473947b7552fbf9d77980230a`.
Two issues reproduced during review were corrected before merge:

- The new hardware prerequisite made four mocked preflight tests probe the review computer's actual GPU. Those tests now use an explicit synthetic hardware fixture, with additional insufficient/unknown-hardware and sanitized inventory-error cases. Production hardware admission is unchanged.
- The Windows timestamp compatibility fix dropped the final path metadata-change comparison. The verifier now compares path ctime only against its earlier path snapshot, separately from descriptor ctime. This preserves the legitimate path/descriptor timestamp difference while rejecting a same-size final mutation with restored mtime. Focused simulated Windows-stat regression cases cover both outcomes.

The local macOS/Python 3.14.3 review run completed **493 executions: 327 passed,
166 skipped, zero failures/errors** (317 distinct passing IDs). All 17 focused
asset/preflight checks passed. The portable PowerShell check parsed 11 scripts,
exercised repeated launcher publication, rejected 11 unsafe paths/four archive
cases, and verified/extracted the pinned official interpreter archive. Python
sources parsed and `git diff --check` passed. These are local development checks;
Windows installation/model/Office evidence above remains tied to `703f6e7...`,
not this later revision. Full isolation, native code, signing and CUI gates
remain unqualified. Raw review evidence stays outside the repository.
