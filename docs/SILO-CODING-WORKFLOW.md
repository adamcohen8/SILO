# Coding workflow implementation and acceptance

11 October 2026. This describes source candidates, portable regressions and
data-only preparation. Native Windows execution, repository mutation, Git and
language servers require separate independent acceptance. Nothing here updates
the published installer, enrolls a machine or authorizes CUI processing.

## What is implemented

| Capability | Source behavior | Remaining acceptance |
| --- | --- | --- |
| Offline Python/NumPy | Exact runtime/wheel pins, actual wheel metadata dependency closure, new-directory assembly, immutable inventory | Licensing, protected deployment, native imports/DLL closure, process-tree boundary |
| Build execution | Separate LPAC/job runner, bounded child processes, aggregate job memory, offline fixed commands, structured test feedback | Every `BUILD_CHECKS` item for each exact environment |
| Repository application | Host review digest, held-handle Windows preimages, encrypted intent and recovery journal, per-file publication | Native sharing/namespace/crash/recovery matrix |
| Git | Host-only status/diff and exact reviewed commits; Windows Git parses a private bounded copy; verified objects, index and branch published through the broker | Pinned managed Git distribution, native LPAC/metadata/publication qualification |
| Navigation | Incremental Python AST and lexical JS/TS/Rust/C/C++ index, symbol/name-reference and syntax-diagnostic pages | Portable implementation; lexical references do not resolve bindings |
| Language servers | Bounded stdio LSP client and separate read-only LPAC operation; no host commands or external locations | Prepared server dependencies and exact native server/environment acceptance |
| Other SDKs | Fixed Node/TypeScript/Cargo/Clang command adapters and data-only SDK inventory/import | Actual reviewed SDK assets, closure/licenses and independent native acceptance for each |

There is no interactive lifetime model-call, tool-call or execution-attempt quota.
Context/frame limits and individual process limits remain. `WorkPolicy.benchmark()`
continues to provide explicit reproducible benchmark caps.

## Offline environments

`silo-environment.json` binds every payload file to a size and SHA-256, the target
platform, package versions/provenance/licenses/exact dependencies, fixed operations
and search paths. A separately obtained digest is required. Extra, changed, linked,
aliased and missing files are rejected. Preparation never runs pip, setup.py,
package lifecycle hooks, an interpreter or a compiler. It never enables execution.

The Windows Python 3.14.8 / NumPy 2.4.3 preparation profile is
`profiles/windows-python-numpy-build.json`. Run with a separately reviewed profile
hash, an existing ordinary cache and a **new** destination. `--online` explicitly
permits pinned host acquisition; omit it to require the offline cache:

```powershell
$PreparationProfile = Join-Path $SourceRoot 'profiles\windows-python-numpy-build.json'
$PreparationHash = (Get-FileHash -LiteralPath $PreparationProfile -Algorithm SHA256).Hash.ToLowerInvariant()
# Compare PreparationHash with the independently reviewed source/profile first.
& $HostPython "$SourceRoot\scripts\prepare_numpy_environment.py" --profile $PreparationProfile --profile-sha256 $PreparationHash --cache $AssetCache --destination $NewEnvironment --online
```

The wheel resolver reads actual `METADATA`, Windows/Python/ABI tags, Python-version
requirements and dependency markers. It rejects missing/conflicting pins, extras,
direct URLs and unsupported wheels. It verifies an exact supplied closure; it
does not select arbitrary versions from a package index. NumPy's bundled notices
and DLLs are inventoried. Independent licensing review must cover every component,
including the interpreter and libraries. Changing `license_review` to `reviewed`
changes the manifest digest and requires a new independent review.

For other pre-acquired SDKs, put the complete runtime/compiler/vendor assets in
`SDK_ROOT/payload`. Supply a reviewed JSON array of packages with fields `name`,
`version`, `license`, `source`, `requires` (exact name-to-version dependencies):

```powershell
& $HostPython "$SourceRoot\scripts\inventory_build_environment.py" --source $SdkRoot --output $NewDescriptor --id javascript-reviewed --language javascript --executable node.exe --packages $Packages --packages-sha256 $PackagesHash
& $HostPython "$SourceRoot\scripts\assemble_build_environment.py" --source "$SdkRoot\payload" --descriptor $NewDescriptor --descriptor-sha256 $DescriptorHash --destination $NewEnvironment
& $HostPython "$SourceRoot\scripts\prepare_offline_environment.py" --source $NewEnvironment --manifest-sha256 $EnvironmentHash --operation check --entrypoint sample.js
```

Inspect/independently approve the descriptor and its hash before assembly. Package
declarations are review inputs, not proof that npm/Cargo dependency resolution has
been performed. For TypeScript use `--compiler node_modules/typescript/lib/tsc.js`;
for Rust use a fully pre-acquired toolchain, `--executable bin/cargo.exe --path bin`,
and `--vendored` only with a complete pinned vendor tree. Cargo uses `--frozen
--offline`; compiler/build-script children stay inside the separate job. C++ uses
the pinned compiler for `check/build`; add an independently inventoried Python
`--driver` for compile-then-run/test. Node disables native addons. No npm install,
remote Git operation, shell or model-selected command options are exposed.

Python supplies run/unittest/syntax check; Node supplies run/test/syntax check;
TypeScript supplies check/build; Cargo supplies run/test/check/build; C++ supplies
syntax check/build and optional compile/run. These are initial fixed profiles,
not arbitrary project build automation. Additional package managers, project
configuration and SDK compatibility need explicit review and validation.

## Machine enrollment and contained operations

The existing managed deployment and code policy are prerequisites. The offline
registry is a separately signed, expiring `offline-environments` review, stored
under protected machine authority. Every SDK byte must have administrator-protected
ownership. `enroll_coding.py` accepts independently signed records using the
already enrolled reviewer anchor; it does not create keys or passed acceptance.

The separate build receipt binds the exact release, OS build, environment ID/hash,
bootstrap/plot hashes, volume identity and `BuildPolicy`. Its default limits are
180 s, 2,048 MiB aggregate job memory, 256 KiB combined output, eight processes
and 64 MiB workspace. The administrator-provisioned fixed NTFS pool must fit the
accepted profile. Ordinary sessions never provision/mount/detach storage. The
original Python runner retains one process and its separate receipt.

Run `enroll_coding.py --kind environment|build|repository-apply|git-runtime|git-host|language-service --signed-record ACTUAL_REVIEWED_RECORD`
as the explicit administrator enrollment step, once prerequisites and evidence
exist. Names are choices, not a literal combined argument. Receipt schemas and
required checks are in `host_capabilities.py` and `windows_build_runner.py`.
Candidate observations, unsigned JSON, stale receipts or caller approval cannot
activate public operations.

```text
/environments
/code-build python314-numpy243-windows-x64
/build test test_analysis.py
/build run analysis.py
/build check analysis.py
/code-save
/code-restore build python314-numpy243-windows-x64
/code-restore edit-build
```

The agent receives fixed `run_build` and bounded source-navigation tools. Test
feedback records exit status, bounded failures and compiler diagnostics; model or
program text claiming success cannot override a failing exit. Build caches and
compiled binaries are destroyed with the disposable volume. Supported source,
text and small PNG artifacts can be reviewed/exported. Interrupted cleanup retains
the volume lease/marker and blocks reuse until independent inspection.

`edit-build` restores within the default build workspace size with execution
disabled and no environment acceptance. Source/grant validation still applies;
it cannot restore process or approval authority.

## Repository publication and recovery

Import from a Reference grant into `/code-edit` or a qualified code workspace.
Grant the intended target as writable explicitly. Reference grants never acquire
write authority. Model edits remain in the disposable snapshot. The host can:

```text
/repository prepare WRITABLE_ID
/repository review TRANSACTION_ID
/repository apply TRANSACTION_ID EXACT_REVIEW_SHA256
/repository inspect TRANSACTION_ID
/repository transactions
/repository reconcile TRANSACTION_ID keep
/repository reconcile TRANSACTION_ID rollback
```

Review includes original/new blob hashes and a bounded diff marked partial when
necessary; inspect the complete changes in the snapshot/patch before approving a
partial preview. Every target preimage and imported source is rechecked. Changes
are atomic **per file**; a multi-file set is not an atomic filesystem transaction.
Encrypted intent precedes effects. Windows receipts retain the native identities
of owned temporary/backup files. An interruption is unknown until explicit host
reconciliation. Rollback changes only bytes still equal to reviewed before/after
images; foreign edits are preserved. New empty parent directories may remain.
Saved projects/backups retain journals and recovery blobs, but no approval or
process authority. Use `transactions [OFFSET]` after reopening the saved project
and an editing workspace to find interrupted transactions after restart.

## Git and language navigation

Git is available only as a host command on an explicit writable working copy.
The entire pinned Git distribution must be in the signed managed release's
`payload/git`; the executable pin and separate exact-release capability must be
enrolled. The capability also binds the provisioned volume-record digest and
fixed time/memory/output/process/disk/snapshot policy in `git_workflow.py`.
A normal existing local branch is required; unborn/detached HEAD,
submodules, shared/linked storage, filters and config includes are unsupported.
The snapshot is limited to 64 MiB and 768 files/directories, with broker per-file
limits. Windows Git has no original repository mount/ACL, network authority,
hooks, signing helpers or child processes. It runs in a one-process LPAC job.

```text
/git open WRITABLE_ID
/git status
/git diff
/git prepare {"paths":["analysis.py"],"message":"Fix analysis","author_name":"Explicit user name","author_email":"explicit@example.test"}
/git commit EXACT_REVIEW_SHA256
/git discard
```

Preexisting original staging is refused. Review binds exact tree, parent, branch,
paths, patch and explicit identity. Native preparation stages only the private
copy and binds its exact index digest. Strict inventories reject forbidden
entries; output objects/index are read through held-folder brokers, never host
pathname reads. Source/index/ref drift rejects publication. Verified immutable loose objects
are copied first, the reviewed index next and the branch last using exact preimages;
HEAD/config/packed-ref read leases remain held. An interruption can leave approved
objects/staging with the old branch: inspect status/HEAD before preparing again.
There is no automatic retry, push or merge. A consumed review cannot replay.
`discard` or any non-Git terminal command removes the private copy/review and
releases the bounded pool; discarded native preparation preserves original staging.

```text
/navigate symbols
/navigate definitions calculate
/navigate references calculate
/navigate diagnostics
/navigate symbols {"file_offset":128,"offset":0,"query":""}
/language definitions analysis.py 12 8
```

The built-in index reads up to 128 source files per page; results return continuation
offsets and explicit partial-file indicators. Python AST definitions and token
references are source-based; other languages are lexical. Semantic navigation
requires an independently pinned server `lsp` command added to the environment
descriptor and separate `language-service` receipt. Each query starts a server
over a read-only disposable snapshot with private inherited pipes. UTF-16 positions,
bounded Content-Length frames and output/deadline limits are enforced. Servers
must support the requested document-symbol/definition/reference/pull-diagnostic
operation. Server requests are refused; commands/edits are stripped; external
locations are rejected. No server inherits host folder grants or can apply edits.

The full native matrix and actual-model work are in [test_plan.md](../test_plan.md).
Portable validation and preparing Windows payload bytes do not establish native
containment, useful model coding performance, installer delivery or CUI authorization.
