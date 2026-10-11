# Local security hardening

11 October 2026. Local source implementation; native Windows acceptance pending.

These procedures govern the current source's activation paths. Historical
Windows reports and the published unsigned evaluation installer cannot qualify
this release, LPAC workers, managed code volume, OCR or new crypto. This work
does not publish a release, enroll organizational keys, change this Mac's host
policy or authorize operational data.

## Implemented controls

| Review finding | Local implementation |
| --- | --- |
| User vault could rewrite trust, replay policy or reset its counter | Fixed OS-resolved ProgramData machine store, administrator/SYSTEM ownership, ordinary-user read-only ACLs, monotonic signed updates; project backups cannot restore machine policy |
| Adjacent release hashes authenticated themselves | Independent release anchor, exact signed inventory, protected deployment digest, first-stage file verification before Python, held read handles, revocation, rejection of extras/links/unsafe ACLs |
| Caller-authored passed JSON could enable Code | Caller approval flags removed; independently signed, expiring exact-configuration acceptance in protected machine state |
| Broader worker access and broken OCR container | Model/graph/parser/code/OCR use zero-capability LPAC; private profile/registry writes denied; public installed software uses administrator-provisioned RX without runtime ACL changes |
| Operational Code needed administrator disk operations | Separate explicit administrator VHD preparation; ordinary runner checks volume GUID/serial/pool identity/account/capacity, takes an exclusive durable lease and cleans through held relative handles |
| No protected security audit | Metadata-only Windows Application/SILO events with actor SID, session/operation identity, sequence and failure-closed writes; admin changes, reads/grants/reviews/saves, execution, archives, retention and schedules covered |
| Host state could change after startup | Interface/route notifications, suspend-time detection, active policy/approval/advisory snapshots, expiry/revocation checks and owned-job cancellation on monitor failure |
| Storage/retention relied on user convention | Explicit administrator reference/draft/exclusion roots, host-only native archive broker, retention ceiling, account-bound backup and authenticated recovery |
| Project encryption used wheel crypto | Native Windows CNG AES-256-GCM and PBKDF2-HMAC-SHA-256 recovery derivation; DPAPI account-bound key protection retained; explicit legacy archive migration |
| Drafts could publish active files | Document type allowlist, ambiguous/bidi/alternate-stream rejection, separate code ZIP export policy |
| No enforceable maintenance gate | Authenticated offline SBOM, signed expiring advisory snapshot, explicit package coverage, exact-version findings across multiple installed versions, independent release/SBOM/snapshot review |

Normal managed sessions refuse missing or changed enrollment, signatures, model
policy, maintenance review, advisory coverage, native receipt, event source or
monitor. They run without administrator privileges. A provisioned machine
cannot fall back to a source evaluation directory. Code, code export, OCR and
schedules are explicit administrator feature decisions. OCR additionally needs
its own exact-runtime/release/OS independent receipt and must be inside the
authenticated `payload/ocr` tree; an inventory marked `native_acceptance:
pending` grants no execution approval.

Public software and approved public model assets belong in the immutable
release. Its read/execute ACL includes `S-1-15-2-2` (All Restricted Application
Packages), so LPAC startup does not need ordinary-user WRITE_DAC. Machine policy,
project secrets and operational documents never receive that grant. Imported
models retain exact-hash verification and a native held data handle through
shutdown. When integrating sharded models, pin **every** signed shard through
shutdown and provision public runtime trees with this same RX rule.

Drafts allow TXT, Markdown, JSON, CSV, DOCX, XLSX and PPTX. Scripts, binaries,
HTML, SVG and unknown types are refused. Office writers retain their existing
no-macro/no-formula/no-external-link rules. Text/link interpretation by viewers
still needs review. Code ZIPs can include active artifacts and need their
separate administrator decision and human review.

Events contain no raw prompts, documents, filenames, outputs or exception text.
Digests are metadata, not anonymization guarantees. Windows owns log deletion
and retention; privileged admins and authorized event writers remain trusted.
This is not a nonrepudiation system. Deletion is logical, without promises of
forensic erasure from SSDs, RAM/VRAM, pagefiles, dumps or VHD free sectors.

## Preparation and managed enrollment

These are future Windows deployment actions, not actions performed on this Mac.
Use organization-reviewed tools and independently supplied public-key
fingerprints. Key rotation or machine-state recovery requires a reviewed
migration; do not reset a sequence or restore an old machine store. Enrolled
anchor overwrites are deliberately refused.

1. `Install-Evaluation.ps1 -PrepareOnly` prepares an **inactive** candidate. It
   does not launch a model, create shortcuts, assert a preflight pass or activate
   an unsigned rollback. Existing versions/state are retained.
2. Put one named release directly under OS-resolved
   `Program Files/SILO/Releases`. Keep private state outside its payload. Correct
   `installed.json`'s state location **before** signing; editing afterward
   invalidates the release. The release must contain public software only.
3. Review the full payload and produce a detached signed inventory using existing
   `sign-bundle` tooling. Use `Protect-SILORelease.ps1` on this new release. It
   rejects linked/recalled/hard-linked files before ACL changes. Deliver the
   first-stage launcher through the organization's trusted mechanism.
4. `Register-SILOAudit.ps1` registers Application/SILO. The operator configures
   and tests log ACLs, retention, capacity and forwarding; the helper relaxes none
   and configures no remote destination.
5. `manage_security.py init-machine`, then `enroll-key` for `trust-anchor`,
   `release-anchor` and `reviewer-anchor`, with independently checked fingerprints.
   Administrative mutations require the audit source. Enroll signed model policy
   with `update-model-policy`.
6. Use `manage_security.py sbom` on the authenticated payload. Independently
   prepare/sign an offline advisory snapshot; run `scan`, then
   `update-advisory-snapshot` and `update-maintenance-review`. Missing package
   coverage, declared vulnerable versions, stale snapshots or mismatched reviews
   prevent launch. Native binaries, drivers, archives and model artifacts require
   separate native review.
7. For Code evaluation, separately run `provision_code_volume.py --user-sid
   EXACT_HOST_ACCOUNT_SID --size-mib 16` as administrator. This creates one new
   owned VHD, chooses an unused evaluation drive, protects its backing image for
   SYSTEM/Administrators, protects its mounted pool for the named host account,
   and enrolls native identities. It accepts no physical-disk selector and never
   replaces an existing pool/preparation. Leave it mounted. Operational sessions
   do not invoke DiskPart, mount or detach disks.
8. Enroll the deployment, collect/review native evidence, then activate with
   `Start-SILOManaged.ps1 -Interface Terminal` or `Desktop` as an ordinary user.

The deployment record contains exactly `format: 1`, absolute `release_root`,
`release_envelope` (base64 signed inventory), `release_sha256` (SHA-256 of those
**exact signed envelope bytes**), `technical_receipt` (base64 independent native
receipt), and `settings`. Settings contain exactly:

```json
{
  "reference_roots": ["C:\\SILO-Synthetic\\References"],
  "draft_roots": ["C:\\SILO-Synthetic\\Drafts"],
  "excluded_roots": ["C:\\SILO-State", "C:\\Users\\Example\\OneDrive"],
  "allow_code": false,
  "allow_code_exports": false,
  "allow_ocr": false,
  "allow_schedules": false,
  "maximum_retention_days": 30
}
```

These are example paths, not a qualification. All roots must exist and exclusions
must cover actual private/sync storage. A signed list alone cannot establish
that sync clients/filesystem filters cannot upload data. Native validation must
establish that, encryption of every backing volume, appropriate CUI/user ACLs,
dump/pagefile policy, audit retention and recovery custody. `.silo` archive I/O
uses a separate held-handle host broker never exposed to model tools.

SBOM, advisory snapshot, code-volume and OCR policy digests use
`signed_policy.canonical`: sorted keys, compact separators, ASCII escaping and
finite numbers. They are not hashes of arbitrarily formatted JSON. Code receipts
also bind the release envelope, bootstrap/plot/interpreter, OS, resource limits
and protected volume configuration.

## Native evidence and controlled candidate evaluation

`new_security_evidence.py` produces the 23-check technical matrix with every
check pending and an expired default. It cannot sign or qualify a release.
Evidence must cover every applicable worker role, actual supported transports,
filesystem/IPC boundaries, resources, cancellation, crash/reboot, suspend/resume,
runtime drift, storage, crypto and audit configuration. Negative tests need
positive host controls; unreachable endpoints and missing services are not
denial evidence. All checks need `status: pass` and a corresponding evidence
digest. Skips cannot enable managed launch.

The administrator may enroll a separate `evaluation-deployment` using
`enroll-deployment --candidate`. It still requires protected software, independent
anchors, active signed model policy, maintenance review, signed advisory coverage
and audit. Only the technical receipt gate is withheld while collecting evidence.
Explicit `--evaluation` / `-Candidate` requires administrator access and selects
only that record. It never enables model-generated Code tools or qualifies an
ordinary-user operational session.

`check_evaluation_install.py` requires the preparation manifest hash, an existing
dedicated approved `--fixture-root`, and exact signed `--model-id`. It tests
actual document/graph/parser behavior, placement, token evidence and cleanup.
Fixtures are not silently created under excluded private state. CPU placement
does not require a false GPU pass. `validate_code_boundary.py` runs a fixed
developer-authored script and positive outside-file host canary, leaves all
untested checks pending, and cannot manufacture acceptance. Independent Code
acceptance must test the ordinary target account too; privileged preparation
observations cannot qualify it.

Manual managed GUI evaluation uses `Start-SILOManaged.ps1 -Candidate -Interface
Desktop`. A controlled validator can use
`WindowsAssistantWindow(..., evaluation=True, autostart=False,
folder_settings=False)`, prepare/select its exact model, then start. Normal
restart retains its ordinary/candidate mode and corresponding gate.

Historical `validate_windows_ui.py` assumes a writable source directory,
temporary references in private state, GPU-only checks and permission to read
the outer software tree. These assumptions intentionally fail managed policy.
Its integration replacement must resolve state from authenticated installation,
use dedicated approved reference/draft roots, avoid remembered projects/grants,
select the exact signed model, check actual CPU/GPU placement, and store synthetic
reports/screenshots in approved storage. Replace the outer README case with a
nested synthetic reference. Preserve historical reports. The concurrent PR #22
Office validator is not edited by this task.

After a Code crash/cleanup failure, the volume lease/private failure marker
blocks reuse. Confirm owner/jobs have exited, inspect the exact registered
image/GUID/pool and receipts, and reconcile explicitly under operator procedure.
Never infer identity from a drive letter or delete an unknown allocation.
Reboot/remount and actual lease retirement require native testing. A mounted
bounded pool and logical cleanup do not constitute secure erase.

## Recovery and remaining validation

Project ciphertext remains `SILO1`, with compatible AES-GCM layout and filename
associated data. Account-bound backups exclude policy, anchors and model
selection. Recovery exports use `SILOR2`, random salt/nonce, PBKDF2-HMAC-SHA-256
with 600,000 rounds, and AES-256-GCM. Native operations use CNG. Old `SILOR1`
scrypt archives are refused by operational recovery. The explicit portable
preparation command `manage_silo.py migrate-legacy-recovery --archive OLD
--output NEW` authenticates the archive/inner records, preserves the original,
and writes a new encrypted archive without overwrite. Password input is hidden.
Native recovery uses this installation's private project vault and approved
archive storage. Former administrative `manage_silo.py ... --state` enrollment
paths are removed; use fixed machine state through `manage_security.py`.

CNG does not establish FIPS compliance. OS/provider/module configuration, DPAPI,
key custody and signature verification still require review; Ed25519 signatures
still use the pinned cryptography package. Unknown advisory coverage cannot be
interpreted as safety. Organization signing, native Windows qualification and
host configuration are still necessary.

Portable contracts cover forgery/replay, changed payloads, missing/expired/skipped
receipts, audit failure, unsafe outputs, storage roots, retention/recovery,
advisory coverage and volume identity/lease/cleanup decisions. Native CNG, machine
ACL and lifecycle tests are labeled and skipped on this Mac. PowerShell, actual
VHD provisioning, Windows isolation, real model inference and CUI deployment
were not executed here.

Platform references: [Windows LPAC](https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer),
[restricted package SID](https://devblogs.microsoft.com/oldnewthing/20220502-00/),
[Windows crypto guidance](https://learn.microsoft.com/en-us/security/engineering/cryptographic-recommendations),
[BCrypt provider API](https://learn.microsoft.com/en-us/windows/win32/api/bcrypt/nf-bcrypt-bcryptopenalgorithmprovider).
