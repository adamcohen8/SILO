# Windows PR and concurrent-work reconciliation

11 October 2026. Local integration candidate; native qualification pending.

PR [#22](https://github.com/adamcohen8/SILO/pull/22) was reviewed against its
recorded source and native report. Its Office validator could exit successfully
when the helper produced no receipt: the newly added process-exit check was the
only true check. Commit `8810fff5ba9922aa60ed48f2ab2364d0d7372cfc` preserves
missing receipts and helper failures, requires the selected Office case's actual
compatibility checks, and treats process-query errors as failures. The fix is
published on the existing PR. Its native Office checks have not been rerun.

## Integrated inputs

| Input | Integration and provenance |
| --- | --- |
| Corrected Windows PR | Main `09f3447` plus PR head `8810fff`; stricter model assertions, Qt evidence finalization, Office teardown, native session-lock fixes and historical report retained |
| Model Selection | Committed TUI checkpoints through `7984c0a`; streaming/cancellation, autocomplete, model controls, project sidebar, and structured Reference/Drafts folder dialog |
| Prior laptop model dependency | Task-only Gemma CPU artifact from `artifacts/gemma-laptop-development`, checked against recorded preimages and all twenty final file hashes |
| Nemotron Super | Task-only thirteen-file handoff plus whole-set model-menu API follow-up; eleven profiles retain CPU, Cascade and Lightning inputs |
| Security Review | Forty-four task-only files checked against preimage/result hashes; protected machine policy, signed managed activation, LPAC, audit, storage/output rules, native project crypto, maintenance checks and provisioned code-volume leases |

The inputs started from different source revisions. Reconciliation used
per-file three-way comparisons with each task's preimages. It did not copy the
concurrent shared checkout wholesale. The original working tree, private
`context.md`, unrelated `SILO.md`, duplicate files and runtime data are excluded
from the combined source.

## Resolved overlaps

- Whole-set install/status/import/removal uses every pinned Super shard. Download
  publication refuses replacement, checks complete hashes and bounds, and
  preserves cancellation, policy rechecks and safe cleanup. Menu storage totals
  include all shards; removal confirmation recognizes managed shard directories.
- All shards receive protected pinning and contained read access. Signed release
  paths use provisioned access; mutable imported weights retain per-file leases.
- Model switches and cancellation recovery recreate the protected policy store
  and preserve explicit candidate mode. Active-model removal uses the replacement
  manager after unloading. Saved projects rebind their audit sink and retention
  ceiling before persistence after replacement or rollback.
- Management with no selected model retains LPAC, protected folder policy,
  audit and lifecycle checks. Folder dialogs call the structured host grant API;
  typed instructions do not grant folder authority.
- Source installers prepare inactive candidates. Installed startup requires
  managed enrollment. Native validation uses an explicit signed candidate path;
  synthetic candidate evaluation cannot enable model-generated code.
- The earlier unsigned terminal updater is blocked on provisioned Windows
  machines, including an updater created before provisioning. Managed updates
  require administrator-signed release enrollment. Preview and historical
  updater behavior does not establish a managed update workflow.

## Evidence and remaining native work

The local artifact's `validation.json` records the final combined portable
suite, source hashes and interpreter. Task-specific historical JSON receipts
remain in source for provenance; their counts and native observations apply
only to their recorded inputs. They do not qualify this combined candidate.

The next native campaign must enroll and test the exact combined signed
candidate, with approved synthetic fixture/evidence roots. It must cover:

1. Managed first-stage launch, protected policy/release/maintenance enrollment,
   revocation/expiry, candidate-to-ordinary activation, and refusal of unsigned
   update paths.
2. LPAC model/graph/parser/OCR boundaries, storage exclusions, audit failure,
   native CNG project/recovery formats and lifecycle cancellation.
3. Complete Super shard preparation, all pins/read grants, full placement on
   suitable hardware, menu switch/removal, and actual model quality; CPU runtime
   placement and both laptop profiles require separate native evidence.
4. Full TUI streaming, cancellation/recovery, folder dialog, saved projects and
   audit/retention across switches and recovery.
5. Corrected Office helper/receipt/teardown behavior, independent Word
   compatibility retest, managed code-volume provisioning/lease/crash recovery,
   and the remaining isolation/manual/reboot matrix.

The earlier Windows report's Word timeouts, GPT-OSS task failures, Cascade
variation and blocked code acceptance remain findings. Portable regressions
cannot resolve those native/model observations. No merge, hosted CI run,
release publication, administrator provisioning or operational authorization
is performed by this local reconciliation.
