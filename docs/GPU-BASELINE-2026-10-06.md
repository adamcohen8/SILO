# Windows CUDA baseline — 6 October 2026

## Outcome

The pinned Nemotron IQ4_XS model and Windows CUDA runtime were acquired, verified,
and evaluated on this workstation using synthetic prompts. All 53 model layers
were placed on the RTX 4090 with an 8,192-token context and one request at a time.
Arithmetic, structured tool calls, and a longer context answer succeeded. One
tool-based answer omitted the requested line locator, so the harness correctly
returned **exit 1 / `baseline_passed: false`**. Deployment readiness remains false.

This establishes a first GPU and protocol baseline. Full LangGraph/document
integration, isolation, broader model quality and installation acceptance remain
required. The temporary server was stopped and its temporary API token removed.
The final process inventory found no `llama-server.exe`; total GPU memory use
returned to 682 MiB.

## Verified assets

The [candidate profile](../profiles/nemotron-30b-4090-candidate.json) and
[asset inventory](../profiles/nemotron-30b-4090-assets.json) record identities,
sizes, SHA-256 hashes, license sources, and every extracted runtime file.

| Asset | Identity | Verified size / SHA-256 |
|---|---|---|
| Model | Unsloth Nemotron-3-Nano-30B-A3B-IQ4_XS.gguf; quantizer revision `9ad8b366c308f931b2a96b9306f0b41aef9cd405` | 18,168,955,680 bytes; `0f2cbdc4f578b5a53f521bcb1a5f5297cd54ea72ebf6c8ce80b570cc5645bac1` |
| Windows runtime archive | llama.cpp `b11433`, CUDA 12.4 x64 | 264,475,988 bytes; `ca560fd770cd849195c7aed269d65c23107486dbf4655b1d64df894c6549e09a` |
| CUDA dependency archive | CUDA 12.4 DLL package from the same release | 391,443,627 bytes; `8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6` |

GitHub's release and tag both resolve to pinned source commit
`50569eb87df530daff11afda229ceb9ab8e6cae8`. The executable reports build 11433,
commit `50569eb87`, Clang 20.1.8, Windows x86_64. Publisher hashes were compared
with complete local payloads before extraction. All 55 extracted runtime files
and the complete model were hashed again before each evaluation launch.
Hashes/TLS provenance do not provide signed installer trust. System Windows
libraries, the NVIDIA driver, a redistributable Python payload and the complete
Windows agent dependency set remain outside this development asset inventory.

Assets and detailed synthetic evidence are under ignored `artifacts/inference/`.
No weights or binaries belong in source control. The source archive still lacks
an independently authenticated source/test-kit identity.

## Configuration and measurements

Target: Windows 11 Pro 25H2 build 26200, Core i9-14900KF, approximately 64 GiB RAM,
RTX 4090 reporting 24,564 MiB VRAM, driver 591.86. See the
[filesystem session inventory](TARGET-SESSION-2026-10-06.md).

The runtime used `CUDA0`, `--n-gpu-layers 999`, `--fit off`, flash attention,
8,192 context tokens, one slot, and a 1,024-token generation ceiling. Thinking
was disabled using the runtime's supported `--reasoning off` switch. The
embedded Jinja template and native PEG chat parser were used; its exact template
hash and capability report are recorded in the local JSON evidence. Sampling
used temperature 0.6, top-p 0.95, seed 42; complete defaults are in the saved
server properties. Prompt reuse was disabled for measured requests.

The server bound only literal loopback, required an ephemeral API token, used a
specific local CORS origin, and disabled the web UI, built-in agent and MCP proxy.
It loaded a local model in offline mode. These application settings do not
establish OS network or filesystem containment; it ran as the current user.
No document folder grants or operational documents were supplied.

| Observation | Final recorded run |
|---|---:|
| Process launch to ready, including model warmup | 6.563 seconds |
| GPU layer placement | 53/53 |
| CUDA model buffer | 17,088.77 MiB |
| CPU-mapped model buffer | 231.00 MiB |
| GPU KV / recurrent-state buffers | 48.00 / 47.62 MiB |
| GPU compute buffer | 119.01 MiB |
| Peak sampled total GPU memory, including host/display use | 18,460 MiB (18.03 GiB) |
| Remaining reported VRAM at that sample | 6,104 MiB |
| 256-token generation decode rate | 246.14 tokens/second |
| 256-token request wall time | 1.125 seconds |
| Tool selection / answer wall time | 0.281 / 0.188 seconds |
| Longer context prompt / completion | 4,840 / 64 tokens |
| Longer context prompt processing / total wall time | 0.520 / 0.843 seconds |

These are short synthetic measurements with cached model files, rather than
cold-boot, long-running, concurrent or maximum-context benchmarks. One-second
GPU polling can miss brief peaks. The runtime retains CPU-mapped model data and
host buffers even with full GPU layer placement. No reduced-layer, smaller-context,
CPU or cloud fallback was used. Simultaneous host-workload responsiveness and
connectivity acceptance were not tested.

## Functional observations

| Check | Result |
|---|---|
| `17 + 25` | Passed: `42`, complete response |
| One bounded tool call | Passed: the sole registered `read_synthetic_excerpt` with exactly `{"document_id":"fixture-alpha"}` |
| Strict application completion/tool parser | Passed on functional responses; incomplete results remain rejected |
| Tool result answer | Correct `37 crates` and exact `[source:S1]`; **failed requested line-2 locator** |
| Longer synthetic ledger answer | Passed: `73 crates`, exact `[source:S2]`, line L118 |
| Disabled reasoning | Passed on all measured responses |
| Performance-only generation | Intentionally stopped at 256 tokens with `finish_reason: length`; excluded from functional acceptance |

The tool round trip used a fixed, in-memory synthetic response. Model output was
validated against the sole allowed function and arguments before supplying that
response. It dispatched no shell command, document read or filesystem write and
did not run the full LangGraph agent. Citation checks validate fixed expected
values/tokens/locators; they are not a general semantic accuracy evaluation.

An initial run stopped before inference because default log verbosity omitted
layer-placement evidence. A subsequent free-form citation run returned the right
facts but omitted a source name in one answer and substituted a Unicode hyphen
in another. Those attempts are retained locally. The final run follows the
application's existing exact `[source:S1]` token convention and preserves the
remaining missing-line failure. The harness has not been weakened to accept it.

## License provenance and next work

The pinned upstream card links the
[NVIDIA Nemotron Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-nemotron-open-model-license/),
while the quantizer card links the separate
[NVIDIA Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/).
Both texts, the [Trustworthy AI terms](https://www.nvidia.com/en-us/agreements/trustworthy-ai/terms/),
the pinned llama.cpp MIT license and [CUDA 12.4 EULA](https://docs.nvidia.com/cuda/archive/12.4.0/eula/index.html)
were preserved and hashed locally. LLVM OpenMP's license is also present in the
runtime file inventory. This acquisition supports local synthetic evaluation;
resolving distribution notices/terms and complete dependency licensing remains
a separate bundle requirement.

Next, validate the real model through the bounded document agent with trusted
source/line/page handling and reviewed saves. Implement and test the complete
[isolation matrix](ISOLATION-VALIDATION.md), preserve host connectivity, complete
the privilege-dependent native folder fixture, and qualify signed offline
installation/reboot behavior before promotion.

For an explicitly authorized rerun, invoke `scripts/validate_gpu_baseline.py`
with a native 64-bit Python 3.11+ interpreter. It verifies local assets, launches
only the pinned temporary CUDA server, evaluates synthetic data, stops its own
process, removes its token and records accurate readiness. Its nonzero result
for the missing line locator is expected until that behavior is resolved.
