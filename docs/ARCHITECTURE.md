# First-version architecture and decisions

## Accepted requirements, 2026-10-05

The user accepted a local PDF/Word document assistant for search, comparison, and drafting with citations. Folder access starts empty. Users explicitly grant folders read-only or editable access. Document writes are confined to editable folders. Administrator installation, Windows feature changes, and reboots are permitted. Initial development took place on macOS; the Windows target became available on 6 October 2026. Generated-code execution is deferred.

GenAI.mil integration is an aspiration, not an existing affiliation or interface requirement.

## Folder authority

Only the trusted host interface can select folders, assign access, change permissions, and revoke access. The native desktop preview implements folder selection and drag/drop; a web file-upload control is not equivalent to granting a directory.

The model receives opaque folder IDs, display names, access modes, and relative paths. It has no permission-management tool, absolute-path file tool, shell, executable launch, or HTTP tool. Files, retrieved passages, and generated answers are untrusted data and cannot change authority.

Overlapping grants are rejected rather than resolving conflicts between an editable ancestor and a read-only descendant. Whole-filesystem grants, traversal, symbolic links, alternate streams, and unsupported path forms are denied. Model-created files are bounded in size. Revisions are saved as reviewed new copies; existing files are preserved. The in-memory review controller displays a diff, binds approval to stored proposal bytes, detects stale sources at proposal/save time, and invalidates proposals after permission changes. In-place replacement remains future work.

Revocation prevents subsequent tool access and must invalidate the retrieval index and cached source passages for that grant. It cannot erase content already seen in the active conversation; the final UI must explain this and offer to clear that conversation. The development broker currently has no retrieval index or conversation cache. Grants are in memory and start empty after restart.

Application-owned configuration and indexes are separate from model document tools. Their approved storage location and retention must be explicit in the deployment design. No operational content belongs in the source checkout or diagnostics uploaded to GitHub.

## Implemented development component

`src/local_ai_appliance/folders.py` provides a POSIX development adapter with directory-descriptor-relative operations. Read operations validate file type, link count, device, and size before reading. New documents are published without replacing existing destinations. Directory listings use independent open-file descriptions, bounded enumeration, and file-type filtering.

`workspace.py` supplies in-memory draft review and the `DraftTools` agent facade: folder metadata, bounded listings, UTF-8 reads, and proposed writes. The facade exposes no approval action. The older low-level `DocumentTools` facade remains for broker testing and is not registered with the agent.

`agent.py` implements a LangGraph `StateGraph`: model request, validated tool dispatch, and another model request until a final answer or a limit stops the run. The fixed registry exposes only `list_folders`, `list_files`, `read_text`, `read_document`, and `propose_text`. Model replies cannot select a Python function dynamically. Tool arguments are checked for required fields, extra fields, and types before broker access. Call IDs cannot be replayed within a run. Defaults are eight model calls, 24 tool calls, four calls per batch, and a 256 KiB serialized context. Requests, replies, reads, and writes have additional size bounds.

Text reads return up to 200 lines and 32 KiB per excerpt, an opaque source ID, line numbers, and the complete file's SHA-256. Recognized `[source:ID]` citations in answers/drafts must refer to excerpts actually read in that request. This establishes reference provenance, not whether a claim follows from the excerpt. Plain-text references outside that syntax are not checked; factual correctness and citation coverage still require evaluation. A development subprocess parses bounded PDF pages and DOCX paragraphs, preserving original-byte digests and returning locators through `read_document`. Sources are revalidated before review/save. Parser OS containment, complete document fidelity, OCR, indexing/retrieval and long-document handling remain pending. See [document ingestion](DOCUMENT-INGESTION.md).

The controller requires a revision source to have been read during that request and checks its digest again before proposing. New drafts can be proposed without a source. Only the trusted host approves a stored proposal; the model can neither approve nor directly write it. Failed runs discard their own new proposals. Every request begins with fresh state, with no checkpointer or conversation cache. Permission changes detected before/after model or tool calls stop the request. They cannot retract bytes already delivered to inference.

`model.py` defines a replaceable `ChatModel` protocol. Its development adapter uses standard-library HTTP to a literal `127.0.0.1` or `::1` endpoint supplied by the trusted host. It uses no DNS lookup, environment proxy, credentials, redirects, retries, model download, remote fallback, or model-selected destination. Responses must contain a complete assistant chat/tool result. Malformed JSON, duplicate keys, truncated completions, excessive responses, and unsupported encodings are rejected. The adapter has socket timeouts, a body-read deadline, and a timer that interrupts slow header/body reception. This is a development transport, not the selected Windows host/worker IPC protocol.

LangSmith tracing is explicitly disabled around graph compilation and invocation, with no configured callbacks. The model adapter uses no vendor SDK. The dependency set nevertheless contains networking libraries and SDKs inherited from LangGraph. Their presence and the loopback restriction do not establish OS-level containment. A trusted inference server could itself access external networks unless separately restricted; a local relay could forward traffic. Operating-system enforcement and full-stack egress tests remain mandatory.

`cli.py` is a terminal development harness for existing local servers. Host folder grants, revocation, proposal review, and approval commands are parsed only from user input. Model output is displayed as literal text with terminal control characters escaped. It does not execute returned commands or load remote content. It is separate from the native preview and the future installation entry point.

`desktop.py` uses native Qt widgets for folder drop/selection, document preview, differences, and trusted approval. It renders source/proposed text literally, with escaped folder tooltips; it has no embedded web engine or network transport. This does not establish OS-level network isolation.

This adapter is not a process sandbox. It assumes the trusted broker is uncompromised and that the model can only invoke registered tool schemas, not inspect or execute Python. The local tests cover specified filesystem attacks, not every hostile same-user filesystem mutation or operating-system escape. It is not the production Windows access-control implementation.

The ordinary Windows adapter currently fails closed. `windows_folders.py` and `windows_native.py` add a separate handle-relative candidate requiring explicit synthetic validation mode. It retains ancestor handles, validates opened objects, refuses reparse traversal, rejects aliases/unsafe syntax, and publishes new files without replacement through a directory handle. Portable policy/ABI tests do not qualify it. A native runner rejects skipped/failing fixtures; Windows evidence and additional hostile-filesystem scenarios are required before promotion. See [Windows folder candidate](WINDOWS-FOLDERS.md). Pure path-prefix checks are insufficient.

## Candidate runtime architecture

The planned local interface and host-owned folder broker mediate all document access. Only allowed document bytes and structured requests are passed to the AI worker. The AI worker has no host drive mounts or document filesystem permissions. Inference, parsing/OCR, embeddings, and workflow tools run locally; all required assets are included in the bundle.

WSL2 is a GPU-runtime candidate, not a security sandbox. Two possible transports need on-target evaluation:

- Disconnected WSL networking and a narrowly defined host/worker IPC protocol.
- Filtered WSL networking with explicit local transport and enforced denial of all external traffic.

Neither design is selected or validated yet. Do not assume Windows localhost forwarding works when WSL networking is disabled. Preserve existing WSL workloads and configuration: `.wslconfig` and common WSL firewall settings can affect more than one distribution. Do not silently overwrite configuration or run a global shutdown.

The complete communication path, including DNS tunneling, Windows interoperation, host proxies, parsers, and rendered output, is in scope for isolation tests. The interface must not load generated remote URLs, images, fonts, scripts, or arbitrary HTML. A trusted Windows host is part of the system boundary. A stronger containment requirement for compromised software or code execution will require revisiting architecture.

## Offline installation

The intended entry point is a PowerShell installer operating on a complete offline bundle. A distributable bundle must contain a signed manifest, verified payloads, pinned model/runtime/dependency identities, licensing/provenance, and a target-supported configuration. No installer may fetch missing assets or declare success after a partial setup.

The installer must distinguish inventory, prerequisite changes, payload installation, reboot/resume, isolation verification, functional verification, and readiness. It must preserve unrelated settings, be idempotent, and support rollback of its own changes. Signing and trust anchors must be established before distributing installation software.

`installer/Install-LocalAI.ps1` now supplies a development framework for read-only planning and explicitly requested private staging/checkpoints/reboot gating/rollback. It executes no payload, applies no Windows feature/firewall/service change, and cannot activate an appliance. Native source/ACL/streaming implementations are candidates requiring target tests. `installer/Test-Target.ps1` remains inspection-only. See [installer framework](INSTALLER-FRAMEWORK.md).

`bundle.py` adds a strict manifest parser and POSIX development payload checker, with an independently supplied manifest hash and exact size/SHA-256 checks for every declared asset. Missing, altered, undeclared, linked, special, or cross-device content fails. It does not download, execute, install, verify a signature, or grant deployment readiness. Hash verification does not establish a signing authority or protect later source changes. The staging framework adds native Windows verification/private storage candidates; they are not qualified by portable tests. Signatures, power-loss/crash recovery, production activation, and a complete runtime/model payload remain pending. See [offline bundle prototype](OFFLINE-BUNDLE.md).

## Source references

- [Microsoft WSL configuration](https://learn.microsoft.com/en-us/windows/wsl/wsl-config): networking, Windows interoperation, mounts, and global configuration scope.
- [Microsoft WSL security model](https://github.com/microsoft/WSL/blob/master/doc/docs/technical-documentation/security.md): WSL is not a security sandbox.
- [Hyper-V Firewall](https://learn.microsoft.com/en-us/windows/security/operating-system-security/network-security/windows-firewall/hyper-v-firewall): WSL traffic filtering.
- [WSL commands](https://learn.microsoft.com/en-us/windows/wsl/basic-commands): runtime management and import/export.
