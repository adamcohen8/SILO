# Long-running work and repository editing

11 October 2026. Source implementation and portable regression coverage; native
Windows and actual-model qualification remain pending. No installer release or
execution acceptance is produced by this change.

## Interactive work

Interactive requests have no lifetime model-call, tool-call, or execution-attempt
quota. The contained agent advances one model/tool scheduling step at a time,
so LangGraph recursion depth does not end a long task. The operational pipe
exchange has no total request deadline or frame-count ceiling. Every individual
frame, source read, tool argument and displayed answer still has a size limit.
The inference transport streams internally, including when live display is off,
and uses an idle timeout rather than a whole-request deadline. Repeated identical
tool requests/results pause work for a new direction. User cancellation still
terminates owned Windows jobs; native cancellation needs retesting.

Adapters omit `max_tokens` in interactive requests and use `--predict -1` and
`--reasoning-budget -1`. Cascade's template receives the same disabled reasoning
quota. The supported active context is still 8,192 tokens. A deterministic
context manager removes complete old history pairs/tool rounds, preserves the
current objective and latest exchange, and marks oversized tool excerpts partial
with their original digest. Missing details must be re-read. It does not invent
summaries or turn previous permissions into new authority. Plain text explicitly
finished with `length` can continue; incomplete tool requests never execute.
Raw private reasoning is not retained in task journals or project snapshots.

`WorkPolicy.benchmark()` retains 16 model calls, 48 tool calls and eight execution
attempts when explicitly requested. Benchmarks must record their chosen policy.
The separate per-process time/memory/output/disk/process limits remain enforced;
removing a lifetime quota does not authorize an unlimited program or new child
processes. Generation, context management and usefulness on hard topics still
need measurements on the actual local model.

## Saved tasks and code

Only an explicitly saved/opened project enables persistence. Host-owned encrypted
task heads and immutable events retain the objective, directives, tool intent,
tool results, partial text and accepted answers. A digest chain detects missing
or changed events. Tool intent is durable before dispatch; an interruption before
its result leaves an unknown outcome. Resume rechecks project, permissions, model,
instructions and previously read source bytes. A stopped/uncertain action never
replays automatically. Reconciliation requires host inspection and owned process
cleanup, skips the uncertain action and restores no approval. Orphan checkpoints are
quarantined as encrypted evidence rather than silently erased.

Terminal commands are `/task new OBJECTIVE`, `list`, `show ID`, `resume ID`,
`continue`, `pause`, `stop`, and `reconcile ID`. Show displays the latest 20 events;
the storage API supports explicit pages. Continuation uses bounded historical
excerpts, retains the complete objective in the journal and re-reads evidence.
A maximum-size objective may need a shorter continuation direction or file
reference to fit one request. This is a request/context resource limit, not a
lifetime work budget.

`/code-save` stores file blobs, immutable inputs and repository preimages in the
private vault. Model switching/project transitions save code before destroying
its old execution authority. `/code-restore edit` restores into a fresh
editing-only workspace; `/code-restore` needs fresh native runner qualification.
Grant identities, source hashes, inventory and policy are rechecked. Process
handles, completed-run authority, reviews and pending exports are never restored.
`/code-restore files` can recover edits after source/grant drift into an
editing-only workspace, dropping inputs, repository binding and all source/run
authority. Create a new task and re-read current sources. Project deletion/expiry
removes its tasks, snapshots and blobs. Account-bound and
password-protected backups include these records, exclude machine policy/trust
and still require source validation/reconciliation. Archives have physical
limits of 10,000 records and 64 MiB, checked while assembling the archive.

## Repository workflow

1. Open a saved synthetic project, explicitly grant a synthetic repository as
   Reference and an empty Draft destination, then use `/code-edit`.
2. `/repository import REFERENCE_ID` copies supported UTF-8 files through the
   broker. It excludes Git metadata, credential/environment files, dependency
   trees and generated build directories, reports exclusions and refuses a
   truncated directory listing. It has depth eight, 4,096-file, individual
   1 MiB-file and configured workspace-byte bounds. A root named `inputs` or
   `silo_plot` is reserved. This is a supported text snapshot, not an assertion
   that every repository asset was imported.
3. The model can page files/lines, search literal text, and write, patch, delete or
   rename supported Python/JS/TS/Rust/C/C++ and other text files. Revisions require
   exact hashes; a patch requires one unique exact text preimage. These operations
   modify the disposable copy. Model tools expose no shell, Git hooks, remotes,
   package installation or host approval.
4. `/repository status`, `diff`, and `patch` show changes and original hashes.
   `/repository export DRAFT_ID changes.patch` creates an unsaved new text patch.
   Changed original preimages prevent export. Existing-file dependencies are
   checked again during host review/approval. `/review ID` and `/approve ID` save
   the exact reviewed patch as a new copy; originals remain unchanged. Patch
   export is currently bounded to a 32 KiB text frame and rejects binary changes.
5. Test an exported patch with `git apply --check` in a disposable host branch.
   The new [coding workflow](SILO-CODING-WORKFLOW.md) also supplies separately gated
   host-reviewed application to an explicit writable grant, interruption recovery,
   private-copy Git commits and contained LSP candidates. Publication is atomic
   per file, not across a multi-file set. A Reference never gains write authority.
   Model tools cannot approve, apply, commit, push or merge.

Editing-only workspaces have a disabled execution service. The host labels their
answers as unexecuted; even a model-authored passed claim cannot enable a runner.
`/code` retains the separately qualified offline Python boundary. It still has
one process, 60 s/run, 512 MiB RAM, 16 MiB workspace and 64 KiB output by default.
The controller keeps only 16 recent run receipts in memory and reports omitted
older receipts in exports; saved-task journals retain the tool results.

## Offline environments and benchmarks

`ToolchainBundle` verifies an independent manifest digest and the exact payload
inventory, rejecting changed/extra/linked files. Its fixed command profiles can
produce data-only command previews with workspace-relative entrypoints.
`scripts/prepare_toolchain_bundle.py` verifies or imports an already prepared
bundle into a new directory and rehashes copied bytes. It never downloads,
installs packages, executes code, or treats license-review metadata as native
acceptance. Its legacy activation deliberately refuses. The separate
`OfflineEnvironment` implementation now prepares the pinned Windows Python/NumPy
profile and supplies fixed JS/TS/Cargo/C++ adapters. Its native build runner has
separate process-tree, SDK, memory and offline gates. No prepared manifest is
execution acceptance; SDK licenses, protected deployment, native package closure
and independent receipts remain necessary. See [commands and limitations](SILO-CODING-WORKFLOW.md).

`tests/fixtures/coding-repository` supplies a known first-row bug and unchanged
four-test oracle. `coding-benchmark-cases.json` defines repair, artifact, long
context, interruption, switching, conflict and repeated execution cases plus
correctness, latency, memory and intervention metrics. These are fixtures and
criteria, not measured model scores. The native handoff in `test_plan.md` asks for
actual local-model runs and distinguishes editing from execution.

The existing inference/parser/agent boundary remains strict. Compilers/test
runners with children need a separate runner profile or VM boundary, verified
build assets and process-tree/network/filesystem/resource/cleanup qualification.
They cannot inherit the Python receipt or relax the one-process worker. Source
candidates for that separate boundary, repository application/Git UI and language
navigation are now implemented; native integration/acceptance and measured actual
model coding quality remain open work in `test_plan.md`.
