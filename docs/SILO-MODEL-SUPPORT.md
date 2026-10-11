# SILO model support

SILO has six pinned, text-input evaluation profiles. Gemma 4 26B-A4B and Muse
Glimmer were integrated first. They share the SILO harness and the existing
hash-pinned llama.cpp b11433 CUDA runtime. Model selection does not change
folder grants, network containment, save approval, or execution authority.

This is implementation support, not measured model quality or native Windows
acceptance. All six profiles remain pending for the current application.
The previous Nemotron Windows observations remain historical baseline evidence.

| Model | Profile ID | Exact weight file | Nominal GPU / minimum RAM |
| --- | --- | --- | --- |
| Gemma 4 26B-A4B | `gemma4-26b-a4b-q4-evaluation-1` | `gemma-4-26B_q4_0-it.gguf` | 24 GiB / 32 GiB |
| Muse Glimmer 30B | `muse-glimmer-30b-q4-evaluation-1` | `Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf` | 24 GiB / 32 GiB |
| Gemma 4 31B | `gemma4-31b-q4-evaluation-1` | `gemma-4-31B_q4_0-it.gguf` | 24 GiB / 32 GiB |
| gpt-oss-20b | `gpt-oss-20b-mxfp4-evaluation-1` | `gpt-oss-20b-MXFP4.gguf` | 16 GiB / 32 GiB |
| Gemma 4 12B Unified | `gemma4-12b-q4-evaluation-1` | `gemma-4-12b-it-qat-q4_0.gguf` | 12 GiB / 16 GiB |
| Nemotron 3 Nano 30B-A3B | `nemotron-4090-cp314-evaluation-1` | `Nemotron-3-Nano-30B-A3B-IQ4_XS.gguf` | 24 GiB / 32 GiB |

The capacity floors are conservative evaluation candidates, not measured fit
guarantees. The GPU check allows 128 MiB for driver reservations on nominal
capacities. It does not pool VRAM or select the largest GPU. Startup still
requires the expected full-GPU offload marker; actual CUDA device enumeration
and placement must be checked on Windows. Unknown hardware fails closed.
There is no CPU, Apple Silicon, remote-model, or partial-offload fallback.

## Pins and model behavior

[`profiles/model-catalog.json`](../profiles/model-catalog.json) records exact
weight sizes, SHA-256 hashes, immutable GGUF download URLs, publisher metadata,
upstream reference revisions, and pending license review. New hashes come from
publisher LFS metadata; complete payload verification happens during offline
import and launch. Upstream revisions are reference snapshots, not evidence
that the GGUF was converted from that exact upstream commit. Redistribution
and conversion provenance review remain pending.

Google's profiles use its official QAT GGUFs. Muse uses Meta's official 17 GB
quantization. gpt-oss uses the ggml-org MXFP4 conversion; its conversion publisher
is separately included in the allowlist. Nemotron retains the existing Unsloth
IQ4_XS pin. The model catalog and configuration catalog both have independent
host-side digest checks and are included in installer source snapshots.

All profiles use 8,192 context tokens, at most 2,048 generated tokens, and one
inference slot. These limits deliberately do not enable the models' advertised
maximum contexts. The four reviewed adapters use:

| Adapter | Temperature / top-p / top-k / min-p | Reasoning |
| --- | --- | --- |
| `gemma4` | 1.0 / 0.95 / 64 / 0.0 | Enabled; 1,024-token budget |
| `muse_glimmer` | 1.0 / 0.95 / 64 / 0.0 | High strength; 1,024-token budget |
| `gpt_oss` | 1.0 / 1.0 / 0 / 0.01 | Medium effort; 1,024-token budget |
| `nemotron3` | 0.6 / 0.95 / 40 / 0.05 | Existing 512-token budget |

The embedded GGUF template and pinned native parser handle each model's tool
syntax. The application consumes normalized structured calls and continues to
validate names, IDs, arguments, budgets, citations, and host permissions.
Muse reasoning cannot be disabled; its intermediate message terminator is not
added as a stop token. Template parameters also accompany prompt token counting.

gpt-oss private reasoning is retained only inside an unfinished tool sequence.
It is removed when the turn completes, excluded from user answers and saved
conversation history, and covered by the existing tracing prohibition. Other
adapters discard returned reasoning. Incomplete responses fail without executing
their partial tool calls or silently retrying inference.

Vision/audio inputs and speculative draft models are outside these profiles.
Document parsing and separately configured offline OCR still work. There is
no image encoder download or implicit multimodal activation.

## Model menu and offline import

On the standalone CPython 3.14 installation:

Run `/model` in either terminal mode. Choose a number or type the action:

- **switch** lists installed permitted models and loads the selected model immediately.
- **install** lists supported permitted models that are missing. Selection explicitly
  downloads that profile's pinned HTTPS URL through the host, verifies size,
  SHA-256 and GGUF format, then installs it. Installation does not select it.
- **remove** lists installed models, including revoked profiles still present in
  the current policy. Choose one and type `yes` to delete its managed weight file.
  Removing the active model unloads it; SILO stays open for model management.

Use `/back` to return or `/cancel` to close the menu. Ctrl+C closes an idle
full-screen menu or cancels an active operation. Downloads require host network
access, ignore ambient proxies/credentials, and can be cancelled; failed or
cancelled downloads leave no installed weight file. The model and generated code
have no download tool. Switch/install still enforce the administrator policy;
switching checks RAM and CUDA0 VRAM and verifies all weights/runtime bytes.

Switching clears chat, pending reviews and disposable code. Host folder grants
are restored only when their native identities still match, and project
instructions are retained. Failed loading attempts restore the previous model
when it remains available and permitted; cleanup or recovery failures stop the
operation. There is no automatic substitution with another model.

`/models` shows full policy profiles and `/hardware` shows capacity estimates.
For offline use, acquire the exact catalog file through an approved transfer
process, then import and switch:

```text
/model import gemma4-26b-a4b-q4-evaluation-1 D:\Models\gemma-4-26B_q4_0-it.gguf
/model switch gemma4-26b-a4b-q4-evaluation-1
```

For Muse, use `muse-glimmer-30b-q4-evaluation-1` and its exact filename from the
table. The other profiles use the same commands. Import copies ordinary files
to a content-addressed cache, verifies size/hash again, and never overwrites an
existing model. `/model select ID` remains an alias for live switching. A selected model that is missing or changed fails on restart;
the launcher does not substitute Nemotron. Nemotron remains the initial default.

New installer preparations put all weights, including Nemotron, in private
mutable `state_root/models`, outside the immutable application payload. Model
deletion preserves complete application/runtime verification and removes only
the current managed file. It does not delete offline media, installer caches or
older releases retained for rollback. Legacy bundled Nemotron files remain
protected as part of their verified payload; use an installer repair with this
source to get removable storage. Release/preflight verification remains strict;
fresh-install preflight still requires the default model.

Administrative commands also work before starting the model, for recovery or
selection when the previously selected weights are unavailable:

```powershell
python scripts/manage_silo.py models --root C:\SILO\app\source
python scripts/manage_silo.py import-model --root C:\SILO\app\source --state C:\SILO-State\projects --id gemma4-26b-a4b-q4-evaluation-1 --file D:\Models\gemma-4-26B_q4_0-it.gguf
python scripts/manage_silo.py select-model --root C:\SILO\app\source --state C:\SILO-State\projects --id gemma4-26b-a4b-q4-evaluation-1
```

Use the host interpreter shipped with the installation. Here `--state` is the
same private project vault used by the terminal, and the model cache is the
sibling `models` directory. Add `--required-policy-key-sha256` when that
independent organization trust anchor is required.

An enrolled signed organization policy is authoritative: it can omit/revoke
profiles and block publishers or jurisdictions. It never falls back to the
embedded catalog when missing or expired. Signed profiles can name a reviewed
adapter; legacy document profiles without `adapter` retain Nemotron settings.
Custom document profiles cannot gain coding authority by choosing an adapter.
Known coding IDs must also match the reviewed weights, runtime, layer count,
and adapter. Policy changes to active model bindings require restart.

US publisher metadata is not government authorization or a guarantee about all
training/conversion provenance. Profiles with unresolved provenance retain
`unknown`, which administrators can block. All embedded profiles authorize only
public/synthetic documents and synthetic code evaluation. Native generated-code
execution still requires the existing independently reviewed Windows boundary
acceptance record for the exact application/toolchain; no portable runner is
enabled by these additions.

## Validation and deferred Windows checks

`tests/test_model_support.py` exercises six profiles with inert import files and
synthetic HTTP responses: document reads, staging, code creation, simulated runs,
unsaved exports, host review, signed restrictions, drift, and reasoning handling.
Simulated execution is explicitly marked and is not acceptance evidence.
The [committed-source validation record](SILO-MODEL-VALIDATION.json) records 469
tests: 318 passed, 151 native/optional-dependency skips, and no failures or errors.

For each actual profile on Windows, record verified payloads, full placement,
startup time, peak VRAM, generation latency, real template/tool behavior,
multi-step document citations, failure behavior, and the existing network/IPC
acceptance matrix. After code-boundary acceptance, repeat the native synthetic
coding milestone and bind exported manifests to the selected model hash and ID.
Larger contexts, lower memory floors, vision, or different quantizations require
new profiles and measurements. Windows testing is deferred at the user's request.

Primary references:

- [Google Gemma 4 overview and QAT distributions](https://ai.google.dev/gemma/docs/core)
- [Google model card and sampling guidance](https://ai.google.dev/gemma/docs/core/model_card_4)
- [Meta Muse GGUFs, template controls, and memory guidance](https://huggingface.co/meta-models/Muse-Glimmer-30B-GGUF)
- [Official OpenAI documentation for gpt-oss reasoning history](https://developers.openai.com/cookbook/articles/gpt-oss/handle-raw-cot)
- [Pinned llama.cpp server options](https://github.com/ggml-org/llama.cpp/blob/50569eb87df530daff11afda229ceb9ab8e6cae8/tools/server/README.md)
