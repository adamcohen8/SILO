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
