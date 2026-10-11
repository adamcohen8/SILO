# Windows validation report

Synthetic Windows evaluation on 10-11 October 2026. The old project was left intact (101 baseline source/configuration/document/test files rechecked byte-for-byte); work used a separate checkout and disposable installations. Raw logs, prompts, inventory, keys, caches and weights remain local.

Full deployment, full isolation and native generated-code acceptance remain **false**. Passing source fixtures or document smoke tests do not close those gates.

## Source and environment

- GitHub main baseline: `ceaeb04db43eb97d5edec9d9c81b6231b430abbe`; six-model merge `61d2ccb1047f9f6c48d51afe54a4b56cc77aa549` is an ancestor.
- Final executable source revision: `703f6e78969da2ee83fc2066114f2e0378c6d9df`. This report is a documentation-only follow-up; installer inventory excludes it.
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
