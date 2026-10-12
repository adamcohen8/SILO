# SILO model support

SILO has eleven pinned, text-input evaluation profiles. Nine use the existing
hash-pinned llama.cpp b11433 CUDA runtime. Gemma 4 E2B and E4B have explicit
Windows x64 CPU profiles with a separately pinned b11433 CPU build. They share
the SILO harness. Model selection does not change folder grants, network
containment, save approval, or execution authority.

This is implementation support, not qualification of the combined application.
See the [Windows report](../windows_test_report.md) for the tested configurations,
recorded results and remaining failures. CPU acceptance remains pending.

## Default on capable computers

Fresh preparation from the current source chooses **Nemotron 3.5 Lightning
30B-A3B** on native Windows x64 when the first NVIDIA GPU meets its **24 GiB
nominal VRAM** floor and system RAM is at least **32 GiB**. The existing 128 MiB
GPU driver-reservation allowance applies. GPU memory is not pooled across cards.
Preparation downloads/verifies Lightning's exact pinned weights and records
that first-launch choice in the installation payload, which must be signed
before managed activation. Smaller compatible machines choose from these tiers:

| Preferred fresh-install model | Minimum system RAM | Hardware requirement |
| --- | --- | --- |
| Nemotron 3.5 Lightning 30B-A3B | 32 GiB | First NVIDIA GPU: 24 GiB nominal VRAM |
| GPT-OSS 20B | 32 GiB | First NVIDIA GPU: 16 GiB nominal VRAM |
| Gemma 4 12B | 16 GiB | First NVIDIA GPU: 12 GiB nominal VRAM |
| Gemma 4 E4B, CPU | 16 GiB nominal | At least four logical CPU threads; no NVIDIA GPU needed |

All profiles require native Windows x64. Compatible GPU profiles take precedence
over CPU profiles. CPU RAM permits the existing 512 MiB firmware/iGPU reservation;
GPU VRAM permits the existing 128 MiB driver reservation. GPU RAM floors remain
strict. Unknown RAM, unsupported platforms, or no compatible model stop model
preparation before model/runtime asset downloads. The PowerShell wrapper first
obtains its pinned bootstrap interpreter to run those checks. A malformed GPU inventory is discarded in
full so a later, larger card cannot become the first card by accident. GPU
inventory failure can still yield a CPU choice if its requirements are known.

This order is a product preference using declared capacity floors, not measured
quality or speed on each hardware tier. If Lightning is not permitted, Nano is
the next compatible GPU preference, followed by GPT-OSS and Gemma 12B. CPU E4B
precedes E2B; other compatible GPU candidates remain available. Super remains an
explicit choice even on very large machines.

An explicit compatible pinned override is available during source preparation:

```powershell
.\installer\Install-Evaluation.ps1 -InstallRoot C:\SILO-Candidate -PrepareOnly -ModelId gemma4-e2b-q4-cpu-evaluation-1
```

The override must pass catalog authorization and hardware checks. It changes the
prepared first-launch hint and exact weights, and cannot override a saved choice.
Code/runtime-only updates reject model overrides.

Saved choices, including no selected model, take precedence. Old installations
without a recorded default retain Nano. The first permitted new-install choice
is persisted so a later repair cannot silently switch it. The installed hint
does not authorize a model: signed machine policy, scope, exact weight/runtime
verification, hardware placement and native activation gates still apply.
Code/runtime-only preparation downloads no weights and introduces no new
default. No published installer is changed by this source edit.

For offline Lightning preparation, the cache must additionally contain its
pinned model file. Use the existing explicit host preparation command before
disconnecting:

```powershell
python scripts/download_evaluation_assets.py --cache D:\Transfer --model-id nemotron35-lightning-30b-q4-evaluation-1
```

| Model | Profile ID | Exact weight file | Nominal GPU / minimum RAM |
| --- | --- | --- | --- |
| Gemma 4 26B-A4B | `gemma4-26b-a4b-q4-evaluation-1` | `gemma-4-26B_q4_0-it.gguf` | 24 GiB / 32 GiB |
| Muse Glimmer 30B | `muse-glimmer-30b-q4-evaluation-1` | `Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf` | 24 GiB / 32 GiB |
| Gemma 4 31B | `gemma4-31b-q4-evaluation-1` | `gemma-4-31B_q4_0-it.gguf` | 24 GiB / 32 GiB |
| gpt-oss-20b | `gpt-oss-20b-mxfp4-evaluation-1` | `gpt-oss-20b-MXFP4.gguf` | 16 GiB / 32 GiB |
| Gemma 4 12B Unified | `gemma4-12b-q4-evaluation-1` | `gemma-4-12b-it-qat-q4_0.gguf` | 12 GiB / 16 GiB |
| Nemotron 3 Nano 30B-A3B | `nemotron-4090-cp314-evaluation-1` | `Nemotron-3-Nano-30B-A3B-IQ4_XS.gguf` | 24 GiB / 32 GiB |
| Nemotron Cascade 2 30B-A3B | `nemotron-cascade2-30b-iq4-xs-evaluation-1` | `nvidia_Nemotron-Cascade-2-30B-A3B-IQ4_XS.gguf` | 24 GiB / 32 GiB |
| Nemotron 3.5 Lightning 30B-A3B | `nemotron35-lightning-30b-q4-evaluation-1` | `NVIDIA-Nemotron-3.5-Lightning-30B-A3B-Q4_0.gguf` | 24 GiB / 32 GiB |
| Nemotron 3 Super 120B-A12B | `nemotron3-super-120b-a12b-q4-evaluation-1` | `NVIDIA-Nemotron-3-Super-120B-A12B-UD-Q4_K_M-00001-of-00003.gguf` plus shards 2 and 3 | 96 GiB / 128 GiB |
| Gemma 4 E2B CPU | `gemma4-e2b-q4-cpu-evaluation-1` | `gemma-4-E2B_q4_0-it.gguf` | No GPU / 16 GiB |
| Gemma 4 E4B CPU | `gemma4-e4b-q4-cpu-evaluation-1` | `gemma-4-E4B_q4_0-it.gguf` | No GPU / 16 GiB |

The capacity floors are conservative evaluation candidates, not measured fit
guarantees. The GPU check allows 128 MiB for driver reservations on nominal
capacities. It does not pool VRAM or select the largest GPU. CUDA startup still
requires the expected full-GPU offload marker; actual CUDA device enumeration
and placement must be checked on Windows. Unknown hardware fails closed.
The CPU profiles require native Windows x64, at least four logical CPU threads,
and the stated RAM capacity (allowing up to 512 MiB of firmware/iGPU reservations).
They deliberately select CPU execution,
even on a machine with an NVIDIA GPU. ARM Windows and Apple Silicon are not
supported by these profiles. There is no automatic CPU, remote-model, or
partial-offload fallback for a CUDA profile.

## Nemotron 3 Super workstation profile

Super is an optional Windows x64 CUDA evaluation candidate. Its conservative
SILO floor is **128 GiB system RAM and 96 GiB nominal VRAM on CUDA0**, the first
enumerated NVIDIA GPU. VRAM is not pooled across cards, and a larger second card
does not satisfy the check. The ordinary 128 MiB driver-reservation allowance
applies to nominal VRAM. CPU fallback and partial offload are not enabled.
These are host-enforced evaluation floors, not measured fit or speed guarantees.
Super is an explicit choice; the fresh-install hardware default is described above.

The Unsloth UD-Q4_K_M conversion has three pinned GGUF shards totaling
**82,541,168,480 bytes (82.54 GB / 76.87 GiB)**. Prepare all three with their exact
filenames in the same transfer folder. Reserve space for both the transfer copy
and the imported copy; import temporarily stages one complete set before
publishing it. A missing, renamed, linked, or altered shard fails verification.
The catalog pins each shard's size and SHA-256 and an immutable source revision.
The upstream revision is a reference snapshot, not conversion-lineage proof.

On an approved connected preparation machine, explicitly prepare only Super's
weights (this command downloads approximately 82.54 GB):

```powershell
python scripts/download_evaluation_assets.py --cache D:\Transfer --model-id nemotron3-super-120b-a12b-q4-evaluation-1
```

Use the existing `import-model --file` command or terminal `/model import`
with the full path to shard `00001-of-00003`. Import verifies and atomically
publishes the complete set under a content-derived directory while preserving
the shard names required by llama.cpp. Select the profile and restart SILO.
No model weights are downloaded automatically during import or launch.

The pinned b11433 source implements Super's Nemotron-H LatentMoE architecture.
The inspected GGUF header records 88 blocks; full placement requires the runtime's
**89/89 layers** marker including the output layer. This profile uses the
embedded template and existing structured tool parser with a dedicated adapter:
temperature 1.0, top-p 0.95, top-k 0, min-p 0, and reasoning enabled without an interactive token quota.
The active context remains 8,192 tokens; the task can continue across windows. MTP
speculative decoding is not enabled. All three shards are hash-checked at launch,
pinned by managed-deployment handles, and individually granted to the contained
process. Existing CUDA process memory/time ceilings remain in force.

Public metadata and bounded header/source inspection establish plumbing inputs,
not actual model execution. Native Windows load, tool parsing, quality, latency,
peak memory, and containment acceptance remain pending. Public/synthetic scope
and pending license/redistribution review also remain unchanged.

Sources: [NVIDIA model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16),
[pinned quantization files](https://huggingface.co/unsloth/NVIDIA-Nemotron-3-Super-120B-A12B-GGUF/tree/036038fb30334a2d56a146c6f0d4871ab5edccbb/UD-Q4_K_M),
[pinned runtime architecture](https://github.com/ggml-org/llama.cpp/blob/b11433/src/models/nemotron-h.cpp).

## Laptop CPU profiles

E2B's exact text-model weights are **3,349,516,256 bytes (3.35 GB)**; E4B's are
**5,154,941,280 bytes (5.15 GB)**. The pins come from Google's official QAT GGUF
repositories, including the corrected-vocabulary checkpoints. These exact files
are larger than the approximate footprints in Google's overview. E2B/E4B denote
effective parameter sizes, not total resident weight sizes. Full payload hashes
are verified during offline import and launch; no model weights were downloaded
for this local implementation. Vision/audio projectors are not imported.

The separate [CPU runtime lock](../profiles/windows-cpu-inference-assets.json)
binds the official `llama-b11433-bin-win-cpu-x64.zip` (19,399,521 bytes), its
publisher SHA-256, and all 51 extracted file hashes. The archive was downloaded
and inspected without executing its binaries. The CPU launcher sets device
`none`, zero GPU layers, four inference/batch threads, disabled GPU KV offload,
and disabled flash attention. It retains the private AF_UNIX endpoint, offline
mode, zero-capability AppContainer, cancellation, one inference slot, and
host-owned filesystem grants. Model-process committed memory is capped at
8 GiB, with a five-minute startup deadline. Each model request has a five-minute
deadline; the contained document/coding workers have 15/20-minute total deadlines
to accommodate slower CPU generation. Host cancellation still terminates active
work. The CUDA limits remain unchanged.

CPU startup verifies the separate runtime inventory and waits for model health;
it records the CPU backend/runtime digest and never reports full GPU placement.
The 16 GiB RAM requirement is a conservative evaluation floor, not evidence of
fit, speed, model quality, or network containment on an actual laptop. Windows
reports usable physical RAM; the CPU capacity check allows a bounded 512 MiB
reservation, requiring at least 15.5 GiB detected RAM. A laptop with a larger
reservation can still fail. Inspect `/hardware`; lower capacity bounds require
new profiles and measurements.

New installer transactions include the verified CPU runtime alongside CUDA.
Existing installed releases remain immutable and must be rebuilt to gain these
profiles. For a development checkout with an approved offline archive, stage it
without execution:

```powershell
python scripts/prepare_cpu_runtime.py --archive D:\Transfer\llama-b11433-bin-win-cpu-x64.zip
```

To prepare only this small archive on an approved connected preparation host:

```powershell
python scripts/download_evaluation_assets.py --cache D:\Transfer --cpu-runtime-only
```

The application never downloads dependencies during a task. Import the exact
model file and select its explicit CPU profile, then restart SILO:

```text
/model import gemma4-e2b-q4-cpu-evaluation-1 D:\Models\gemma-4-E2B_q4_0-it.gguf
/model select gemma4-e2b-q4-cpu-evaluation-1
```

For E4B use `gemma4-e4b-q4-cpu-evaluation-1` and
`gemma-4-E4B_q4_0-it.gguf`. Fresh source preparation can select E4B automatically;
existing installations use explicit import/install and switching. E2B remains
an explicit alternative under the same CPU capacity floor.
Signed administrator policies remain authoritative and may omit/revoke either
profile. CPU/runtime/thread changes require restart and cannot inherit coding
authority from a different reviewed binding.

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
IQ4_XS pin. Cascade 2 uses bartowski's IQ4_XS; Lightning uses ggml-org's Q4_0
conversion of NVIDIA's BF16 release. Both retain an unknown conversion
jurisdiction in the policy. Cascade uses the NVIDIA Open Model License;
Lightning's upstream license is OpenMDW-1.1. Redistribution review is pending.
The model catalog and configuration catalog both have independent
host-side digest checks and are included in installer source snapshots.

All profiles use an 8,192-token active context and one inference slot.
Interactive generation and reasoning have no configured token quota, and
complete text truncated by a runtime context boundary can continue. Incomplete
tool calls remain rejected. This does not enable the models' advertised maximum
contexts, expand physical memory, or promise unlimited single-message output. The seven reviewed adapters use:

| Adapter | Temperature / top-p / top-k / min-p | Reasoning |
| --- | --- | --- |
| `gemma4` | 1.0 / 0.95 / 64 / 0.0 | Enabled; no interactive token quota |
| `muse_glimmer` | 1.0 / 0.95 / 64 / 0.0 | High strength; no interactive token quota |
| `gpt_oss` | 1.0 / 1.0 / 0 / 0.01 | Medium effort; no interactive token quota |
| `nemotron3` | 0.6 / 0.95 / 40 / 0.05 | Enabled; no interactive token quota |
| `nemotron_cascade2` | 1.0 / 0.95 / 0 / 0.0 | Enabled; runtime/template quota disabled |
| `nemotron35` | 1.0 / 0.95 / 0 / 0.0 | Enabled; runtime quota disabled |
| `nemotron3_super` | 1.0 / 0.95 / 0 / 0.0 | Enabled; no interactive token quota |

The embedded GGUF template and pinned native parser handle each model's tool
syntax. The application consumes normalized structured calls and continues to
validate names, IDs, arguments, citations, and host permissions. Explicit
benchmark budgets are separate from interactive work.
Muse reasoning cannot be disabled; its intermediate message terminator is not
added as a stop token. Template parameters also accompany prompt token counting.
For both new Nemotron adapters, thinking is explicitly enabled in the server
defaults, completion requests, and prompt-count requests. Cascade's embedded
template also receives `reasoning_budget: -1`; Lightning's template does
not consume that parameter. Top-k 0 disables that filter. Lightning MTP/draft
files and speculative decoding are not enabled. See the
[Nemotron addition and Windows retest handoff](SILO-NEMOTRON-ADDITIONS.md).

gpt-oss private reasoning is retained only inside an unfinished tool sequence.
It is removed when the turn completes, excluded from user answers and saved
conversation history, and covered by the existing tracing prohibition. Other
adapters discard returned reasoning. Incomplete tool responses fail without executing their partial calls.
Complete plain text marked `finish_reason: length` continues as partial work,
with no claim of completion until a final response passes host validation.

Vision/audio inputs and speculative draft models are outside these profiles.
Document parsing and separately configured offline OCR still work. There is
no image encoder download or implicit multimodal activation.

### Document-task follow-through

Development source checks conservative explicit English requests for named
proposals and exact line/page/paragraph/row/slide citations. For example,
`Propose summary.md in Drafts` requires a real proposal at that relative path,
and `Cite its exact supporting line` rejects whole-excerpt citations. Ordinary
prose requests still permit prose. Requirements come only from the current
user prompt; documents, quoted examples and retained history do not create them.
The native host independently checks actual pending proposals and read locators.

An incomplete response gets at most one shared completion/citation correction
within the existing model/tool/context budgets and grants. Requests with an
already-created proposal are not retried; failed requests discard their own
proposals. Corrections cannot approve saves or alter permissions. Text-property
searches now include at most two following lines within the 32 KiB excerpt cap,
with separate verified locator tokens, so a heading can expose its nearby value.
Continuation markers remain relative to the matched line; partial results do
not establish that the requested fact is absent.

These checks validate workflow completion and locator provenance, not whether
every answer or cited line is semantically correct. The preserved Muse/GPT-OSS
failures need fresh native retests. Published release
`evaluation-2026.10.11-silo.3` includes these host completion checks. Follow the focused instructions
in [`test_plan.md`](../test_plan.md). Model/runtime pins and save/execution
authority remain unchanged.

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

`/models` shows full policy profiles. `/hardware` shows the inventory and permitted
recommendations; `/model recommend` shows the recommendation and reasons a model
does not fit. Both respect the active project's data scope and signed model policy.
They do not read or change the selected-model record, download weights, or launch
a runtime. Install and switch remain explicit actions. The install/switch menus
mark the preferred compatible profile and explain insufficient or unknown capacity.
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
the launcher does not substitute another model.

New installer preparations put all weights, including Nemotron, in private
mutable `state_root/models`, outside the immutable application payload. Model
deletion preserves complete application/runtime verification and removes only
the current managed file. It does not delete offline media, installer caches or
older releases retained for rollback. Legacy bundled Nemotron files remain
protected as part of their verified payload; use an installer repair with this
source to get removable storage. Release/preflight verification remains strict;
managed candidate preflight requires an explicit profile and its exact pinned weights.

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

`tests/test_model_support.py` exercises all eleven combined profiles with inert import files and
synthetic HTTP responses: document reads, staging, code creation, simulated runs,
unsaved exports, host review, signed restrictions, drift, and reasoning handling.
Simulated execution is explicitly marked and is not acceptance evidence.
The prior six-model [validation record](SILO-MODEL-VALIDATION.json) records 469
tests: 318 passed, 151 native/optional-dependency skips, and no failures or errors.
The [two-model addition receipt](SILO-NEMOTRON-VALIDATION.json) records 471 tests:
320 passed, 151 native/optional-dependency skips, and no failures or errors.
That is the historical six-model record. The local CPU addition has a separate
[validation record](SILO-CPU-MODEL-VALIDATION.json), covering CPU policy, hardware
checks, pinned runtime staging, startup selection, and all eight simulated model
workflows. None of these fixtures establishes actual CPU inference quality.

The [Super integration validation record](SILO-SUPER-MODEL-VALIDATION.json)
records 101 focused model, installer, and security regression tests: 97 passed,
four native Windows skips, and no failures or errors. It used an isolated
content snapshot because an unrelated signing script's live fingerprint changed
during the installer inventory check. Super-specific fixtures verify the high
hardware floors, all-shard import/launch checks, changed policy bindings,
per-shard managed pins and read grants, and rejection of partial GPU placement.
No full Super weights were downloaded or executed.

For each actual profile on Windows, record verified payloads, full placement,
startup time, peak VRAM, generation latency, real template/tool behavior,
multi-step document citations, failure behavior, and the existing network/IPC
acceptance matrix. After code-boundary acceptance, repeat the native synthetic
coding milestone and bind exported manifests to the selected model hash and ID.
For each CPU profile, also measure startup time, peak committed/private/system
memory, prompt processing and generation latency, thread use, cancellation during
load/inference, and cleanup on a Windows x64 laptop with no NVIDIA driver. Repeat
the network/filesystem acceptance matrix and the 108 kg synthetic coding
milestone after independent code-boundary acceptance. CPU health in a fixture
is not native containment or model acceptance.
Larger contexts, lower memory floors, vision, or different quantizations require
new profiles and measurements. The [combined PR #21 portable receipt](SILO-PR21-RECONCILED-VALIDATION.json)
records the reconciled source. Cascade 2 and Lightning need native Windows retests
from a fresh installation of that source; they are absent from the published
release-3 installer.

Primary references:

- [Google Gemma 4 overview and QAT distributions](https://ai.google.dev/gemma/docs/core)
- [Google model card and sampling guidance](https://ai.google.dev/gemma/docs/core/model_card_4)
- [Meta Muse GGUFs, template controls, and memory guidance](https://huggingface.co/meta-models/Muse-Glimmer-30B-GGUF)
- [Official OpenAI documentation for gpt-oss reasoning history](https://developers.openai.com/cookbook/articles/gpt-oss/handle-raw-cot)
- [Pinned llama.cpp server options](https://github.com/ggml-org/llama.cpp/blob/50569eb87df530daff11afda229ceb9ab8e6cae8/tools/server/README.md)
- [NVIDIA Cascade 2 model card](https://huggingface.co/nvidia/Nemotron-Cascade-2-30B-A3B)
- [NVIDIA Lightning model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16)
