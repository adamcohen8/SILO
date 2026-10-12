# Local document agent development

The ordinary command is a POSIX development harness for public/synthetic UTF-8, PDF, DOCX, CSV, XLSX and PPTX documents, connecting to an already-running local model server. Separate explicit [Windows evaluation runners](WINDOWS-AGENT-ISOLATION-2026-10-06.md) now exercise the same graph with a real GPU model, native broker and contained workers. Neither path is the Windows installer or a qualified environment for CUI. The earlier manual desktop preview remains separate from the native Windows desktop/terminal and saved-project backend. See [current source and evidence](SILO-STATUS.md).

## What is implemented

The execution path is `local chat model -> LangGraph -> fixed document tools -> folder broker`. A final answer returns source metadata and pending proposals to the trusted host. The model contract is independent of a model family; this implementation uses an OpenAI-compatible chat-completions protocol. Actual tool-call behavior, chat templates, context settings, quantization, and hardware fit must be tested for every supported profile. The pinned Nemotron 3 Nano 30B-A3B Windows candidate has passed the small synthetic contained workflow; broader quality and deployment qualification remain pending.

The model receives only these tools:

| Tool | Capability |
|---|---|
| `list_folders` | Names, opaque IDs, and permissions of explicit grants |
| `list_files` | Bounded listing inside a granted folder |
| `read_text` | Up to 200 lines / 32 KiB, source token, line range, and SHA-256 |
| `read_document` | Up to five PDF pages or 200 DOCX paragraphs / 32 KiB, source locators and original SHA-256 |
| `search_document` | Literal keyword/phrase search in a granted PDF, DOCX or UTF-8 file; a bounded excerpt with a verified page, paragraph or line citation and continuation locator |
| `analyze_table` | Deterministic decimal statistics for one named CSV/XLSX column, with missing/nonnumeric counts |
| `search_folder` | Bounded literal search in one explicitly referenced grant; reports incomplete coverage |
| `read_image_ocr` | Optional signed, contained image transcription; disabled without a separate OCR runtime |
| `propose_artifact` | Structured DOCX/XLSX/CSV/PPTX proposal with host-built bytes; cannot save |
| `propose_text` | Pending new-file draft in an editable grant; optional checked revision source |

The document tool set has no permission changes, approval, shell, arbitrary Python, direct write, or network tool. The separate Code registry supports execution-disabled repository editing/navigation; run/build/semantic operations require their own native qualification. See [coding workflow](SILO-CODING-WORKFLOW.md). Existing documents are preserved. Only host approval saves the proposal's exact stored bytes.

## Development setup

Use Python 3.11 or later. The dependency snapshot was resolved and tested on macOS/Python 3.14. The commands below install development dependencies online; they are not the [Windows source-preparation command](EVALUATION-INSTALLER.md). Put the environment outside cloud-synced folders to avoid placeholder-file issues.

From the repository root:

```sh
python3 -m venv /tmp/local-ai-dev
/tmp/local-ai-dev/bin/python -m pip install -r requirements/agent-dev.txt -r requirements/documents-offline.txt -r requirements/office-verification.txt
/tmp/local-ai-dev/bin/python -m pip install --no-deps -e .
/tmp/local-ai-dev/bin/python -m unittest discover -s tests -v
```

For document parsing, install the optional `documents` extra or use the test kit's hash-pinned offline wheels. The `agent` optional extra also installs the two direct pins. `requirements/agent-dev.txt` records all resolved dependency versions to reduce drift during development. It has no payload hashes and is not a Windows-qualified bundle lock. A production bundle still needs target-specific wheels, reviewed licenses/provenance, asset hashes, and signatures.

## Connecting a model

Start a locally provisioned, trusted inference server yourself. It must bind only to a literal loopback interface and support tool calls at `/v1/chat/completions`. Do not expose it to the LAN. Supply the alias of the model already loaded by that server:

```sh
/tmp/local-ai-dev/bin/local-ai-agent \
  --endpoint http://127.0.0.1:8080/v1 \
  --model local-document-model
```

The alias above is illustrative, not a download identifier or a tested profile. The adapter never fetches a model. For llama.cpp, its [official function-calling documentation](https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md) describes the `--jinja` requirement and model-dependent templates. The [candidate profile](INFERENCE-PROFILE.md) pins source/quantization metadata; a Windows binary, template behavior, GPU fit, and isolation remain unqualified. Absence of a working local server causes a connection failure without a remote fallback.

Loopback client checks and disabled tracing are application controls. They do not prevent the inference server or compromised dependencies from using WiFi, Ethernet, DNS, VPNs, or host relays. The required OS enforcement is still pending; use synthetic data only.

## A synthetic session

The harness starts with no folder grants. Host commands consume everything after the first space as a literal argument; do not quote paths with spaces, and no shell expansion is performed.

```text
/ro /absolute/path/to/synthetic-reference
/editable /absolute/path/to/synthetic-drafts
/folders
Read guide.txt in the reference folder and propose a clearer revision as revised.txt in drafts.
/review PROPOSAL_ID
/approve PROPOSAL_ID
/quit
```

Use the proposal ID printed after generation. `/review` displays the destination and stored diff. `/approve` requires that review first and then rechecks permissions/source/destination through the controller. `/discard ID` removes a pending proposal. `/revoke FOLDER_ID` removes access and invalidates all pending proposals. Grants and proposals disappear when the session closes. The harness writes no conversation log or index; terminal scrollback and the separately operated server's logs are outside this in-memory controller and must be considered in deployment storage design.

The terminal entrypoint now uses the [shared Phase 1 session backend](SILO-PHASE-1.md). Follow-ups retain bounded context only in memory. `/clear` erases chat and pending drafts; new requests invalidate prior unsaved proposals and reviews. Grants/revocations clear chat, and retained source bytes are rechecked before reuse. Changed sources reset the history. This is a development session, not saved project continuity or a contained Windows terminal.

## Limits and evidence

- The default broker caps source files at 1 MiB. Optional PDF/DOCX ingestion has additional parser/excerpt bounds; see [document ingestion](DOCUMENT-INGESTION.md). Windows parsing remains explicitly gated until process containment is qualified.
- Excerpts use exact lines from the read version and carry its SHA-256. Each request includes fresh grant metadata; partial excerpts report total units and whether more remain. Located tokens such as `[source:S1:page:2]` must identify units actually read in that request. Document answers require supporting exact returned locators; named-file requests must produce an actual pending proposal. Bounded citation/task repair can request a correction, without accepting invented tokens or a prose-only save claim. This checks provenance, not answer truthfulness, complete citation coverage, or other reference formats.
- Revisions require a source read in the current request and reject a changed source at proposal/approval time. New drafts need no source.
- Interactive work has no lifetime model-call/tool-call/run quota. `WorkPolicy.benchmark()` explicitly caps benchmarks at 16 model calls, 48 tools and eight execution attempts. Individual tool batches, user input, messages and serialized context remain bounded; the graph rolls over complete old exchanges rather than ending a task at a call count.
- Managed native interactive transport uses streaming internally and an idle timeout. A plain-text `length` finish can continue; truncated tool requests never execute. HTTP errors, redirects and malformed data fail closed. The separate POSIX developer connection retains its configured transport deadline; neither path guarantees useful long work on an actual model.
- Graph tracing is disabled even when common tracing environment settings or an outer LangSmith context enable it. No remote callbacks or persistent checkpointer are configured.
- Network protocol integration is tested against a synthetic loopback service. Scripted model replies exercise the real LangGraph graph and broker. No real-model quality, GPU performance, Windows support, or OS isolation is established by those tests.

Next target work: complete the broader isolation/peer/drift and reboot/resume matrix, qualify remaining native folder/UI behavior and model quality, and assemble the signed offline installer from verified assets. Exact Nemotron provisioning, synthetic contained graph/parser/GPU integration and the Windows evaluation wheel lock are recorded in the linked target results.

## Implementation references

- [LangGraph graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [Explicit tracing context controls](https://docs.langchain.com/langsmith/trace-without-env-vars)
- [llama.cpp function calling](https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md)

Saved-project, policy, recovery and workflow development is described in [phases 3–5](SILO-REMAINING-PHASES.md). Complete Qt smoke checks additionally need the `ui` extra. The terminal extra and cryptography are host-only Windows wheel pins; independent Office reader libraries are development verification dependencies and are not shipped into model/parser/code workers.
