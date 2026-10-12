# SILO architecture and decisions

Current source review: 12 October 2026. SILO is a local document, analysis, coding,
and project-work assistant. LangGraph remains the selected harness following the
[Phase 1 comparison](SILO-PHASE-1.md). The shared `SessionBackend` connects terminal
and desktop behavior to host-owned grants, reviews, cancellation and persistence.
[Current status](SILO-STATUS.md) separates source implementation from native
acceptance and the older published installer.

## Authority and data flow

The host selects folders, grants Reference/Draft access, and approves exact
outputs. The model receives opaque IDs and relative names. Documents, filenames,
retrieved passages, program output and model replies cannot grant access or
approve a save. Model selection and editable assistant preferences do not change
permissions. Overlapping/whole-drive grants, traversal, reparse links, alternate
streams and unsupported path forms are rejected.

The document registry exposes bounded reads/search/table analysis and text/office
proposals. The model cannot directly save a proposal; host review binds approval
to stored bytes, current sources, grants and a new destination. Existing document
files remain unchanged. The separate repository-apply controller can replace
explicit writable targets only after exact review and independent native acceptance.
It does not turn a Reference grant into write authority.

Permissions and source changes invalidate retained context. Ordinary chat is
in-memory; explicit saved projects persist encrypted conversation/task/code data
with retention and source checks. Revocation cannot erase content already seen
by a model, so access changes clear the active context. Recovery restores data,
never old process handles, permissions beyond current grants, or approval.

## Agent and interfaces

`agent.py` validates a fixed tool registry and structured arguments before host
dispatch. It supports document tools, exact returned citation tokens, progress,
cancellation checkpoints and context rollover. `code_agent.py` adds disposable
workspace edits/navigation and separately qualified fixed execution/LSP operations.
Neither registry exposes host approval, machine policy, arbitrary shell, Git push
or merge. Citation checks establish provenance, not factual correctness.

Interactive `WorkPolicy` has no lifetime model/tool/run quota. The graph advances
one scheduling step at a time. Each message/read/frame and active model context
remains bounded; old complete exchanges may be removed, and missing evidence
must be reread. Explicit benchmark policy retains 16 model calls, 48 tools and
eight execution attempts. No lifetime quota changes per-process limits.

`cli.py`/`PortableSession` provide a POSIX developer connection to an independently
operated loopback model server. Loopback checks and disabled tracing are not OS
containment. `terminal_client.py`/`terminal_fullscreen.py` provide the shared native
terminal, project/model/task/workflow commands and host review controls. The
scripted Mac preview remains separate. `windows_desktop.py` provides the native
project/document interface; `desktop.py` is the earlier manual preview.

## Native Windows boundary

`windows_session.py` owns inference and graph/parser workers. The current source
uses verified LPAC tokens, Windows jobs, private transports and independently
protected machine policy/release trust. Installed sessions refuse missing managed
enrollment; per-user source hashes cannot establish administrative trust.

`windows_folders.py`/`windows_native.py` hold ancestor handles and check NTFS
object identity before data access. Content reads use a checked file-ID handle
with no-recall/no-follow flags. Reviewed existing-file mutation pairs that read
with a named metadata/DELETE lease: the named lease performs rename/delete while
combined sharing denies foreign readers/writers/renames. New publication refuses
replacement. Native fixtures pass for specified cases; broader hostile-filesystem
and complete release acceptance remain pending. There is no pathname fallback.

Generated programs receive copied inputs in disposable bounded volumes, not
original granted folders or host broker handles. The original Python runner
retains one-process policy. A separate build runner supports an independently
accepted process tree and offline environment. Git runs over a private copy;
language services receive a read-only snapshot. Each capability requires its own
exact-release/configuration receipt and cannot inherit another runner's acceptance.
See [execution boundary](SILO-EXECUTION-BOUNDARY.md) and
[coding workflow](SILO-CODING-WORKFLOW.md).

Network denial must cover inference, parsers, generated code and allowed children,
including IPv4/IPv6, TCP/UDP, DNS, loopback, LAN, VPN and host relays, while permitted
host connectivity remains available. No disconnected network adapter, model
instruction, working directory or loopback-only client substitutes for OS
containment. WSL2 is an alternative requiring separate evaluation; the current
candidate path is native Windows LPAC/jobs and fixed NTFS volumes.

## Persistence, artifacts, and installation

`ProjectStore` and task/code stores retain encrypted project records, workflows,
schedules, task intent/results and snapshots. Native Windows keys use DPAPI/CNG;
portable development storage is separate. Schedules are local host services
while the project is open, not unattended background agents. Unknown interrupted
actions are reconciled explicitly without automatic replay. Approved exports live
in the selected destination and have their own retention.

Bounded deterministic office writers produce reviewed DOCX/XLSX/CSV/PPTX proposals;
optional signed image OCR has separate runtime/acceptance requirements. Source
locators and original-byte digests accompany document excerpts. Macro/formula
execution, complete Office fidelity and scanned-PDF conversion are unsupported.

`Install-Evaluation.ps1 -PrepareOnly` verifies pinned public assets and prepares an
inactive exact-source candidate. It creates no active record or model session.
Protected deployment, signatures, policy/environments, bounded pools and independently
reviewed acceptance are separate administrative steps. The older published
installer retains its own immutable behavior. `Install-LocalAI.ps1` and `bundle.py`
remain staging/checker components; they do not replace managed activation.

Complete native containment, current actual-model quality, signed deployment,
licensing/redistribution and organizational CUI authorization remain open. See
[latest evidence](../windows_test_report.md), [managed security](SILO-SECURITY-HARDENING.md),
and [operations](SILO-OPERATIONS.md).
