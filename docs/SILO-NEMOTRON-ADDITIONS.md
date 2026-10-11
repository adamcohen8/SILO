# Additional Nemotron profiles and Windows retest handoff

Prepared 11 October 2026. This local change adds Cascade 2 and Lightning to the
existing offline model import, explicit selection, hardware recommendations,
document tools, and gated coding flow. Nano remains the initial default.

## Local change and reconciliation

The isolated checkout is based on `61d2ccb` (the six-model integration), with
the branch `codex/nemotron-cascade-lightning`. Concurrent Windows fixes are not
copied into this change. Apply the task commit or patch to the reconciled source
after those fixes are available. Preserve existing Windows evidence as evidence
for its original source and configuration; retest the resulting source.

Reconcile the model and configuration catalogs by profile ID. Recompute every
configuration pin referencing `profiles/model-catalog.json`, the
`MODEL_CATALOG_SHA256` constant in `model_management.py`, and `CATALOG_SHA256`
in `configuration_catalog.py` against the final exact bytes. Do not copy an old
catalog wholesale over concurrent additions. The shared model tests now cover
eight profiles; retain newer Windows task-completion and terminal menu tests.

## Exact evaluation candidates

| Profile | Quantization publisher | Weight bytes | SHA-256 |
| --- | --- | ---: | --- |
| `nemotron-cascade2-30b-iq4-xs-evaluation-1` | bartowski | 18,166,698,432 | `871a80bfd682289f2efa1b4fdee899576b5a768681f2b2ad74a15b59af6a510e` |
| `nemotron35-lightning-30b-q4-evaluation-1` | ggml-org | 18,898,091,584 | `61f87e75974e4b535dcdf9aad056541a9514f1dfa4538b463b081d19b7a00e3c` |

The exact filenames, immutable download URLs, repository revisions, upstream
reference revisions, and license sources are in `profiles/model-catalog.json`.
Hashes were read from public LFS metadata. Upstream reference revisions do not
establish the precise conversion lineage. Imports and launch verify complete
payload bytes against the pinned size and hash. No weights were fully downloaded
or run during this local implementation.

Both are text-input evaluation profiles under the existing `silo-langgraph-1`,
CPython 3.14.8 and pinned llama.cpp b11433 CUDA runtime. Their capacity floors are
32 GiB RAM and nominal 24 GiB VRAM on CUDA0, with the existing 128 MiB reservation
tolerance. These are evaluation candidates, not measured memory guarantees.
The new catalog entries authorize public/synthetic documents and synthetic code
evaluation only; generated-code execution still requires the existing native
boundary acceptance for the exact application/toolchain.

Cascade 2 uses NVIDIA's Open Model License and a separately identified
bartowski quantizer. Lightning uses NVIDIA's OpenMDW-1.1 release and ggml-org's
conversion. Both keep `unknown` conversion jurisdiction and pending
redistribution review; blocking either NVIDIA or the quantizer blocks the
profile. Changing the adapter/weights under a known coding ID does not inherit
that ID's reviewed binding.

## Adapter and template checks

Both use NVIDIA's temperature 1.0 / top-p 0.95 guidance, with top-k and min-p
filters disabled. They retain the existing 8,192-token context, 2,048-token
generation maximum, one inference slot, and 1,024-token reasoning budget.
Both explicitly enable thinking; Cascade also passes its template's reasoning
budget. Template settings are identical in launch defaults, chat requests, and
prompt counting. Returned reasoning is discarded by these adapters.

Only a bounded 8 MiB prefix of each pinned GGUF was inspected. Both headers
declare `nemotron_h_moe` and 52 model blocks; including the output layer gives
the expected `53/53` full-GPU marker. The pinned llama.cpp source includes this
architecture and recognizes their `<tool_call>`, `<function=`, `<parameter=`
syntax via its Qwen3-Coder parser. This structural inspection is not an actual
model-load, native tool-call, performance, or containment test.

| Embedded template | SHA-256 |
| --- | --- |
| Cascade 2 | `174391c306dcfb075b593e0d17e7410c48b92360543f70664a116c505984f129` |
| Lightning | `58933db77d3099b4f78c55a38347a72e1ea05b97d6bd8f38775303dc0194e0a9` |

NVIDIA's Lightning example mentions `force_nonempty_content`; the pinned GGUF
template does not reference that setting, so this adapter does not advertise it
as enforcement. Use the reconciled host task-completion checks and actual-model
retests to establish follow-through. Lightning's separate MTP head, NVFP4 and
speculative decoding are outside these Q4_0 settings.

## Windows retest after reconciliation

1. Record the reconciled source revision, interpreter, runtime digest, driver,
   GPU inventory, profile ID, and model size/hash. Use only synthetic fixtures.
2. Prepare the exact GGUF through an approved transfer, then import and select
   one candidate using the commands below. Test each in a separate restarted
   session. A missing/drifting model must fail without substituting Nano.
3. Confirm `/models`, the model menu when present, and `/hardware` include the
   new profiles. Confirm the selected model starts with `53/53` GPU offload on
   CUDA0. Record startup time, peak VRAM and generation latency, including the
   bounded thinking settings. Unknown/insufficient hardware remains denied.
4. Run multi-step text/PDF/DOCX reads with independently checked exact citations;
   request a named draft and confirm an actual proposal is available for review.
   Verify no save occurs before host review/approval. Exercise malformed or
   incomplete responses, refusal, cancellation, and restart.
5. Repeat the existing worker/model/parser filesystem, network, IPC and child
   process matrix while retaining host connectivity. Record native observations
   separately from scripted source tests.
6. After native code-boundary acceptance, run the synthetic 108 kg milestone
   with each actual model. Inspect Python, tests, chart, report and source
   citations; exported manifests must identify the selected model ID/hash.
   Check cancellation and cleanup. If code acceptance is unavailable, report
   this gate pending and finish independent document/model checks.
7. Test exact-byte import rejection, policy revocation/omission and blocked
   quantizer/publisher restrictions. Restore Nano only through explicit
   selection if desired. Neither a passing local suite nor a model loading
   establishes organizational CUI authorization.

```text
/model import nemotron-cascade2-30b-iq4-xs-evaluation-1 D:\Models\nvidia_Nemotron-Cascade-2-30B-A3B-IQ4_XS.gguf
/model select nemotron-cascade2-30b-iq4-xs-evaluation-1

/model import nemotron35-lightning-30b-q4-evaluation-1 D:\Models\NVIDIA-Nemotron-3.5-Lightning-30B-A3B-Q4_0.gguf
/model select nemotron35-lightning-30b-q4-evaluation-1
```

Use the standalone installation's management CLI for selection before startup
if the currently selected model is unavailable. An enrolled organization policy
must explicitly include the new profiles; there is no embedded fallback around
an enrolled policy. Report actual model quality and native acceptance per
profile, independently of portable tests.

## Portable validation

The [local validation receipt](SILO-NEMOTRON-VALIDATION.json) binds the tested
source snapshot and records 471 tests on macOS / Python 3.14.3: **320 passed,
151 skipped, zero failures and zero errors**. Skips cover native Windows and
optional dependencies. The focused model-management, adapter, and configuration
suite passed all 35 tests. The all-profile flow uses inert weights, synthetic
HTTP responses, and a simulated runner; it establishes application plumbing,
not actual model quality or native execution acceptance.

## Sources

- [NVIDIA Cascade 2 model card](https://huggingface.co/nvidia/Nemotron-Cascade-2-30B-A3B)
- [Cascade 2 quantization](https://huggingface.co/bartowski/nvidia_Nemotron-Cascade-2-30B-A3B-GGUF/tree/931b595fc71b7ca14fb9d935af011f69f7c0434c)
- [NVIDIA Lightning model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16)
- [Lightning conversion](https://huggingface.co/ggml-org/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-GGUF/tree/8a08a1c81dadcc75d35dbb96016cfd344b632e67)
- [Pinned native tool parser selection](https://github.com/ggml-org/llama.cpp/blob/50569eb87df530daff11afda229ceb9ab8e6cae8/common/chat.cpp)
