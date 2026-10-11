# SILO phases 3–5: implementation and acceptance

The source now implements the remaining application features around the full-window terminal from the **TUI** chat. The 11 October 2026 evaluation installer includes these changes. Historical Windows observations are in [the validation report](../windows_test_report.md); exact-release qualification, including the new model menu and updater, remains pending. Public and synthetic evaluation remain the only allowed data scopes; no code or document change authorizes CUI.

## Phase 3: retained projects and office work

- Explicit local projects, resumable bounded conversations, per-project task instructions, and retention/deletion controls use `ProjectSession`, a decorator around the shared backend. Both native interfaces use it.
- Projects retain up to 16 turns and 48 KiB of model context, 64 grants, 32 workflow prompts, and 8 KiB of combined application/project instructions. Default retention is 30 days, configurable from 1 to 365 days.
- Saved grants include native directory identity. Reopening issues fresh opaque IDs, checks identities, remaps source references, and checks original file hashes. A missing/replaced folder or changed source invalidates the retained context. Pending approvals, Code workspaces and running processes never resume.
- AES-GCM authenticates each bounded record with its record identity. Windows protects the key with current-account DPAPI and requires a protected private NTFS directory. The POSIX development fixture uses a private directory and a mode-0600 key; it does not qualify Windows storage or CUI handling.
- The private project directory is excluded from folder grants, including native aliases and ancestors. Sample folders remain separate. Project data stays outside signed application payloads and model/code read grants.
- The desktop has a **Projects** dialog for create/open/close, instructions, retention and deletion, plus immutable office-artifact review. The terminal exposes the same operations through host commands.
- Bounded CSV/XLSX parsing and decimal column summaries count numeric, missing and rejected values separately. XLSX formulas, error/date cell types, macros and external relationships are rejected rather than trusting cached formula results. Ordinary literal strings beginning `=` remain strings; CSV output escapes spreadsheet formula prefixes.
- Structured DOCX, XLSX, CSV and PPTX proposals are built by fixed host writers. DOCX has heading styles and tables; XLSX has typed cells and a frozen header; PPTX uses a bounded slide layout. Word, Excel and presentation citations become readable file/locator references. Supporting-file digests are embedded in office formats and shown during review. CSV provenance is shown in the host review and retained project context.
- A reviewed approval writes exactly one new file and rechecks all supporting source hashes. Destination collisions preserve the existing file.
- `search_folder` searches explicitly selected granted folders through the broker, with limits of 16 readable documents, 32 directories and depth 6. Partial search results cannot establish absence. No stale disk index or ungranted crawl is introduced.
- Optional image OCR has a separate signed runtime inventory and an owned native LPAC process with bounded memory, deadline and output. It supports an explicitly selected PNG/JPEG/TIFF image, labels transcription uncertainty, and has no automatic downloads. An administrator stages the exact signed OCR runtime in `state_root/ocr`; the repository ships no approved OCR binaries/language data. OCR accuracy, native execution and scanned-PDF conversion remain unqualified; scanned-PDF conversion is not implemented.

The development office samples were opened by independent Word/Excel/PowerPoint readers, converted to PDFs with bundled LibreOffice, and visually inspected. This establishes basic portable content/layout behavior for those samples, not Microsoft Office or native Windows compatibility for arbitrary documents.

## Phase 4: models and repeatable tasks

`ModelManager` reads either the existing pinned evaluation catalog or an explicitly enrolled, administrator-signed policy. Enrollment requires a separately supplied public-key hash. Updates require administrator rights on Windows, a valid Ed25519 signature, a strictly increasing sequence and an unexpired policy. Once a key is enrolled, a missing active policy is an error; it cannot silently revert to the embedded catalog. An organization launcher can additionally require an independent key digest.

Signed profiles bind exact GGUF bytes, publishers/jurisdictions, license-review metadata, the pinned llama.cpp runtime, CPython 3.14.8, the existing SILO harness, GPU layer count, minimum RAM/VRAM and permitted data/workload scopes. Unknown, revoked, prohibited, expired or changed models are denied before import/launch. Restrictions are explicit administrator judgments, not guessed national policy. Unknown provenance can be prohibited explicitly.

Hardware inspection reports CPU/RAM and available NVIDIA VRAM. Recommendations compare declared minimums and never claim task qualification. Offline imports copy and rehash the bytes actually copied, then publish a new model file atomically. New installations keep all model files in private mutable `state_root/models`, outside the immutable application payload. The terminal `/model` menu supports live switching, explicitly selected host downloads of pinned supported models, and confirmed removal. The inference worker has no download authority. Switching clears chat/reviews/code and restores identity-verified grants; the menu pauses automatic schedule checks. Each request rechecks current revocation/scope policy. A custom document model cannot inherit the existing coding acceptance receipt. See [model menu details](SILO-MODEL-SUPPORT.md#model-menu-and-offline-import) for legacy bundled-model handling.

The implementation supports multiple approved GGUF models behind the fixed local protocol and harness. It does not install arbitrary model-specific executables or external harnesses. Those integrations were optional in the plan and remain separate security/compatibility work. Only the existing model is provided by the repository; additional organization-signed profiles still need measured task quality, latency, memory, tool compatibility and failure evidence.

Reusable workflows retain a bounded prompt and permission/instruction/model scope. Schedules additionally bind the exact workflow prompt. Changed scope or workflow content disables them. Scheduling is opt-in and local: the full-screen terminal checks due tasks while the matching saved project is open. Scrollback mode provides explicit `/schedule tick`; the desktop does not run unattended schedules. No background OS service or hosted scheduling is installed.

Each due slot has a durable idempotency key. Missed slots coalesce into one attempt, completed/failed slots advance, and interrupted running slots become unknown and require explicit reconciliation. Reconciliation skips the interrupted slot. Cancellation reaches the owned session. Results remain encrypted project context and pending reviews; schedules never approve a save or publish an artifact. Restored schedules are disabled until reconciliation.

Private record transactions serialize policy and scheduler state changes across clients. A separate exclusive schedule-runner lock prevents another client from launching or reconciling an active attempt. A crash can leave this lock behind: an operator must confirm that the owner has exited before retiring the marker, then reconcile the unknown slot. SILO never steals the lock or automatically replays an uncertain attempt.

## Phase 5: release and operational tooling

- `scripts/manage_silo.py` supports key enrollment, signed policy updates, detached versioned bundle signing/verification, license inventory generation, and creation/checking of the complete release evidence matrix.
- A signed bundle covers the complete payload inventory. Verification rejects missing, extra, aliased, linked or changed files and requires an independently supplied public-key hash. Synthetic test keys are test fixtures, never organization trust anchors.
- `installer/Sign-SILORelease.ps1` signs PowerShell bootstrap scripts with an explicitly selected existing certificate. `Verify-SILORelease.ps1` checks the independently configured signer. Neither obtains credentials, enrolls a certificate, changes execution policy or publishes a release.
- Bootstrap signing must precede the final payload inventory/signature. The organization's already trusted deployment mechanism must verify first-stage trust before executing downloaded PowerShell/Python. Python cannot establish initial trust by checking itself after execution.
- The readiness matrix includes 38 required native/operational/organization checks. Every entry starts pending. A pass needs an unchanged signed receipt tied to the exact configuration/release and an independently trusted reviewer key. Operational checks additionally require native execution; bundle/license/organization decisions have their own approval evidence. Pending, skipped and failed checks prevent readiness. Reviewer key enrollment and approval custody belong to the organization’s deployment process; unsigned JSON `reviewed` flags are rejected.
- License inventory binds component versions and file hashes. All redistribution review statuses start pending, including model weights, Python packages, runtime and CUDA redistribution. Hash verification does not establish legal permission.
- [Operational procedures](SILO-OPERATIONS.md) cover data storage, backup/restore, retention, updates, incident response and qualification. These procedures require organization review before deployment.

## Terminal commands

The full terminal window is now the default Windows terminal. Enter sends, Alt+Enter inserts a newline, PageUp/PageDown scroll, Ctrl+C cancels active work, and Ctrl+D waits for cancellation/cleanup before exit. `--scrollback` selects the previous scrolling presentation. `--plain` removes color. The portable `scripts/preview_terminal.py` remains a clearly labeled scripted design preview.

```text
/reference C:\Users\Example\Documents\Reference
/draft C:\Users\Example\Documents\Drafts
/project new Capacity study
/project list
/project context
/project open PROJECT_ID
/project retention 30
/project renew EXPIRED_PROJECT_ID 30
/instructions set Keep reports concise and include units.
/workflow save capacity Summarize capacity.csv with supporting citations.
/workflow run capacity
/schedule create capacity 3600
/schedule list
/schedule cancel SCHEDULE_ID
/schedule reconcile SCHEDULE_ID
/models
/hardware
/model import APPROVED_ID C:\OfflineMedia\approved-model.gguf
/model select APPROVED_ID
/review PROPOSAL_ID
/approve PROPOSAL_ID
/backup C:\Backups\capacity-projects.silo
/project close
/project delete PROJECT_ID
/project prune
```

Paths are literal text after the command; no shell quoting/expansion is used. Administrative policy/signing tools are separate from model tools. `/code` still requires complete independently reviewed Windows boundary evidence.

## Remaining acceptance

Windows key/ACL behavior, live contained OCR, Office compatibility, local-model quality for the expanded tool set, alternate-model startup, hardware probing, native scheduling/cancellation and the complete fresh/offline-install/lifecycle/isolation matrix remain pending. Actual organization signing keys, certificates, redistribution decisions and CUI authorization are external prerequisites. The first real-model coding milestone remains a required native acceptance test. No skip, mock model, portable renderer or synthetic signing key completes those gates.

## Portable validation

The development regression run discovered 452 tests: 325 passed and 127 were skipped. Compilation and `git diff --check` passed. New fixtures cover encrypted recovery, retained-source invalidation, independent Office readers, exact artifact review, signed-policy rejection, concurrent vault operations, schedule scope/idempotence and crash recovery, and desktop/terminal integration. OCR fixtures check only the bounded pipe contract; they do not execute OCR. Native storage tests are labeled separately.

For a development environment, install `requirements/agent-dev.txt` and `requirements/office-verification.txt`, then run:

```text
PYTHONPATH=src QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
python -m compileall -q src scripts tests
git diff --check
```

This POSIX command is a development check, not a Windows installation procedure. Local generated evidence is retained under `artifacts/phases3-5/validation.json` and `portable-tests-final.txt`; office source files and rendered PDFs are under `artifacts/phases3-5/office`. These ignored development artifacts are not signed acceptance receipts or installer assets.
