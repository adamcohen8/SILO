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
