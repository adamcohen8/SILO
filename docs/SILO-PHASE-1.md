# SILO Phase 1: shared agent foundation

> These are implementation/validation notes for the original phase and its recorded updates.
> For the 12 October source, shipped-release distinction and qualification status,
> use [current status](SILO-STATUS.md), [long work](SILO-LONG-WORK-AND-CODING.md)
> and [expanded coding workflow](SILO-CODING-WORKFLOW.md). Dated tool counts and
> deferred-feature statements describe that phase snapshot; current interactive
> work has no lifetime call/run quota, while per-operation resource limits remain.

10 October 2026

Phase 1 establishes the shared session API, permission vocabulary, development configuration policy, harness choice, frozen milestone inputs, and generated-code containment design. The production harness remains LangGraph. The POSIX development terminal now uses the shared session API and remembers follow-ups in bounded memory.

This work was validated on macOS with scripted model replies. No Windows machine or actual inference was used for this change. Native launch, installer acceptance, and execution isolation remain pending. Code grants and execution are denied. The first complete coding milestone belongs to Phase 2.

## Implemented interfaces

| Contract | Implementation and responsibility |
| --- | --- |
| Project | `contracts.Project`: explicit ID, display name, public/synthetic evaluation scope; no persisted project database |
| Session | `SessionBackend`: start, ask, grant, revoke, review, approve, discard, clear chat, cancel, close |
| Portable backend | `backend.PortableSession`: existing broker, graph, and bounded in-memory `Conversation`; cooperative cancellation; development use only |
| Windows backend | `backend.WindowsSessionAdapter`: wraps existing `WindowsSession` host service; preserves its contained launch and hard cancellation; tested with a fake service on macOS |
| Model adapter | Existing `model.ChatModel` and `LocalChatModel`: reasoning and tool requests; no authority or model downloads |
| Harness | `contracts.Harness` / `agent.DocumentAgent`: bounded orchestration and six registered document tools; progress and cancellation checkpoints |
| Permissions | `WorkspaceKind.REFERENCE` maps to read-only; `DRAFT` maps to reviewed new-file creation; `CODE` is defined and refused |
| Progress | `contracts.Progress`: fixed stage and counters, without prompts, filenames, document text, or command output |
| Execution policy | Validated limits in `execution_policy.ExecutionPolicy`; `DisabledExecutionService` always refuses execution |

The host session methods are absent from the model's tool registry. Only `list_folders`, `list_files`, `read_text`, `read_document`, `search_document`, and `propose_text` are registered. Documents and filenames remain untrusted data. None can grant access, approve a save, invoke a shell, or select an executable.

These Python interfaces organize trusted host code; they do not sandbox Python objects. The Windows service remains responsible for the native process boundary. New interfaces must call host authority services and must not expose these objects to generated code.

The new terminal path uses `PortableSession`. The existing Qt interface continues to use its existing Windows service directly; this change supplies its adapter without rewriting Qt or creating a contained Windows terminal client. Phase 2 will route that terminal through the native adapter.

## Session and review behavior

Sessions begin without grants. A host Reference or Draft grant changes permission revision and clears retained context. Code grants fail without changing permissions. The host must review the current immutable proposal before approval; approval rechecks source bytes, destination, permissions, and collision/replay protection in the existing broker. Model-generated IDs cannot manufacture approval.

Starting a new request discards previous unsaved proposals and reviews. Follow-ups retain up to the existing conversation limits of 16 turns / 48 KiB, with source revalidation and graph context budgeting. Every read source, including an uncited read, is rechecked before retaining the result. Changed sources or permissions clear affected chat. `/clear` clears chat and pending drafts. Closing retains no project history.

Portable cancellation is cooperative: it prevents later tool dispatch and acceptance of late responses, invalidates pending drafts/reviews, and clears chat. It cannot interrupt an already blocked HTTP request. Closing a busy backend is refused until its cancelled operation returns. Native hard termination remains the Windows host service's responsibility. UI progress callbacks are trusted host code.

## Harness decision and reproducible comparison

**Decision:** retain `silo-langgraph-1`, the existing bounded `DocumentAgent`, as the Phase 1 default. This preserves the already pinned application dependencies and Windows integration while exposing a common host API for future clients.

The optional developer spike evaluates Deep Agents 0.7.23 through the same six host dispatchers and scripted model replies. It uses an in-memory StateBackend, no filesystem/shell backend, no persistent checkpointer/store/cache, and no remote model. The restricted candidate uses its documented harness profile to hide filesystem tools and disable its general-purpose subagent.

| Candidate | Identical scripted workflows | Model-visible tool set | Decision |
| --- | --- | --- | --- |
| Existing LangGraph 1.2.13 / LangSmith 0.14.4 | 7 / 7 passed | Exactly six SILO tools | Keep as default |
| Deep Agents 0.7.23 defaults | 7 / 7 passed | Six SILO tools plus eight filesystem/delegation tools | Default configuration is too broad for the desired interface |
| Deep Agents 0.7.23 restricted profile | 7 / 7 passed | Exactly six SILO tools | Feasible candidate; defer migration and Windows qualification |

Cases cover no grants, a cited source read, an unsaved draft followed by a host save of exact bytes, attempts to self-approve/run commands, forged citations, a stale source at approval, and hostile source instructions attempting grants/commands. A scripted model intentionally requests denied operations. This measures orchestration and host authority, not whether a real model resists injection or reliably completes tasks.

The eight default extra names observed were `delete`, `edit_file`, `glob`, `grep`, `ls`, `read_file`, `task`, and `write_file`. Their in-memory backend did not grant host filesystem access. Deep Agents explicitly describes profile tool exclusions as model-facing calibration rather than a security boundary. Future adoption still requires host-side rejection, dependency review, and native containment qualification.

The Deep Agents spike resolved LangGraph 1.2.14, LangSmith 0.14.7, LangChain 1.4.4, and additional provider SDKs. They were installed only in a separate temporary development environment. No application dependency, pinned Windows wheel profile, model, or runtime was replaced. `requirements/deepagents-evaluation.txt` records that environment's full version snapshot; it has no wheel hashes and is not an offline Windows installation lock. Production uses the existing pins and target wheel manifests. Deep Agents' package declares MIT licensing; adopting its resolved dependency tree still needs full licensing/provenance review.

For each candidate, graph construction and invocation run with LangSmith tracing disabled while common tracing environment switches are enabled. Python `socket.connect` and `socket.create_connection` are replaced with denial sentinels. No observed connection attempt occurred. This is a regression check for these paths, not OS network isolation; it does not cover every transport or prove behavior of future dependency versions.

Run from the repository root using separate environments:

```sh
python3 -m venv /tmp/silo-phase1-current
/tmp/silo-phase1-current/bin/python -m pip install -r requirements/agent-dev.txt
/tmp/silo-phase1-current/bin/python scripts/evaluate_phase1_harness.py \
  --candidate langgraph --output artifacts/phase1/current.json

python3 -m venv /tmp/silo-phase1-deepagents
/tmp/silo-phase1-deepagents/bin/python -m pip install -r requirements/deepagents-evaluation.txt
/tmp/silo-phase1-deepagents/bin/python scripts/evaluate_phase1_harness.py \
  --candidate deepagents --output artifacts/phase1/deepagents.json
/tmp/silo-phase1-deepagents/bin/python scripts/evaluate_phase1_harness.py \
  --candidate deepagents-restricted --output artifacts/phase1/deepagents-restricted.json
```

Environment setup downloads developer packages; the scripted evaluations themselves need no model or network. Use new output paths on reruns. Reports contain only synthetic case results, dependency versions, offered tool names, and fixture hashes. The checked-in [comparison record](SILO-PHASE-1-HARNESS-EVALUATION.json) preserves the observed results. See the official [customization](https://docs.langchain.com/oss/python/deepagents/customization), [backends](https://docs.langchain.com/oss/python/deepagents/backends), and [package metadata](https://github.com/langchain-ai/deepagents/blob/main/libs/deepagents/pyproject.toml).

## Minimal configuration policy

`profiles/configuration-catalog.json` permits two exact public/synthetic **document evaluation** configurations: the historical CPython 3.12 profile and the standalone CPython 3.14 installer candidate. Each records the harness, interpreter, publishers, jurisdiction status, scope, qualification status, and hashes of the existing model/runtime/wheel profiles. Those profiles retain the individual payload pins and known provenance. Unknown jurisdiction is stated explicitly; no nationality or government approval is inferred from names.

The trusted host pins the catalog's bytes in `configuration_catalog.CATALOG_SHA256`. Unknown IDs, revoked entries, excluded publishers/jurisdictions, broadened scope, malformed policy, or changed profile bytes are refused. Empty blocked lists do not permit arbitrary models: only the exact enumerated configurations are allowed. An organization that prohibits unresolved jurisdiction can block `unknown`; a reviewed source update is currently required to change policy. Model text and `AGENTS.md` cannot update it.

Evaluation preparation checks the catalog before model/dependency acquisition. The PowerShell bootstrap can provision its already pinned host interpreter before Python preparation reaches this check. Windows session verification checks policy before inference launch. Existing payload/source manifest checks still run. An installed older snapshot retains its older implementation; this change does not remotely revoke previously published releases.

This is a development allowlist and trust starts with reviewed source. It is not a signed administrator policy system, automatic jurisdiction classifier, recommendation engine, runtime attestation service, or CUI approval. The POSIX developer CLI accepts the alias of a separately operated loopback server; it cannot attest that server's loaded model and is explicitly outside the catalog-governed Windows deployment path.

## Selected native target and remaining gates

The first new native milestone will target the standalone **CPython 3.14.8** configuration in `windows-evaluation-installer.json`, the existing pinned Nemotron 3 Nano 30B-A3B IQ4_XS / llama.cpp b11433 runtime, and `silo-langgraph-1` on the Windows RTX 4090 target. The CPython 3.12.14 result remains historical, partial evidence. macOS/Python 3.14.3 tests do not qualify either Windows interpreter. The generated-code toolchain must gain separately pinned offline plotting dependencies and runner qualification in Phase 2.

The [execution-boundary design](SILO-EXECUTION-BOUNDARY.md) specifies the OS controls, data transfer, ownership, cleanup, and denial tests required before execution can become available. Limits in a Python dataclass do not implement those controls.

Frozen inputs are in `tests/fixtures/silo-milestone`: policy, inventory, injection text, missing-capacity/negative-quantity/malformed CSVs, independent expected result of **108 kg**, and an exact-byte manifest. Only those four reviewed synthetic CSV paths are permitted by source release packaging; general CSV data remains excluded. No analysis program, generated tests, chart, or report was executed or accepted as the future coding milestone.

## Portable verification

The full regression suite on macOS/Python 3.14.3 completed with **231 passed, 116 native Windows skips** (347 discovered). Agent, UI, parser, installer, configuration policy, session cancellation/review/source checks, frozen fixtures, and source/target-kit packaging tests ran with their required development dependencies. The tests use synthetic model replies and local HTTP responders. No skipped native test is counted as a pass. `git diff --check` passed.

```sh
PYTHONPATH=src QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
```

Install the agent, UI, and document development dependencies described in the repository before using that command; missing extras produce additional skips. The recorded local run used the existing development environment and required permission for synthetic loopback servers. Its log is `artifacts/phase1/portable-tests-final.txt`, an ignored local artifact rather than deployment evidence.

Phase 1 implementation can be developed without Windows. Native integration/acceptance remains pending, and Phase 2 must demonstrate actual local inference plus generated Python execution, result inspection, reviewed publication, network/filesystem denial, cancellation, and cleanup. Do not label skipped native checks as passes or enable execution based on portable results.
