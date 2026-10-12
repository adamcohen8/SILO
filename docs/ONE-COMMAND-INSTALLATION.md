# One-command installation and managed activation

v0.1.0, 12 October 2026, packages the reviewed source as an **unsigned evaluation
release**. Its [pinned command](https://github.com/adamcohen8/SILO/releases/download/v0.1.0/INSTALL.md) defaults to inactive preparation.
Windows preparation and refusal fixtures passed on the recorded checkout;
exact-release native activation, ordinary-user first launch, and signing remain
pending. Publication does not supply the required activation inputs.

The local bootstrap now defaults to inactive preparation and forwards
`-PrepareOnly`, `-Offline`, `-ModelId` and reviewed activation parameters. It no
longer calls the current installer without its required mode. Offline bootstrap
requires both the pinned source archive and the complete asset cache; it refuses
missing source rather than using the network.

An administrator can supply one reviewed exact-host activation plan. The
installer prepares the selected payload, copies only approved bytes to a new
named Program Files release, protects it, verifies its independent signatures
and native receipt, registers the SILO audit source if needed, and enrolls all
security/deployment records with one atomic replacement. It can create a desktop
shortcut for the same target account. It does **not** launch an elevated model.
The user opens that shortcut from an ordinary, non-elevated session.

This first activation path supports documents/analysis. Code, code export, OCR
and schedules must be disabled in its plan; their separate provisioning and
acceptance gates remain intact. Neither installation nor a signed technical
receipt supplies organizational CUI authorization.

## Target-host command

After separately reviewing/delivering the plan and its SHA-256 through the
approved process, use an approved elevated native 64-bit Windows PowerShell
session **for the same target user account**, from the reviewed source folder:

```powershell
.\installer\Install-Evaluation.ps1 -Activate -InstallRoot 'C:\SILO-Preparation' -ActivationPlan 'C:\Approved\activation-plan.json' -ActivationPlanSha256 'INDEPENDENT_PLAN_SHA256' -Interface Terminal
```

The hash above is a placeholder, not a valid command pin. Add `-Offline
-CachePath 'D:\Approved\EvaluationCache'` for a complete preverified cache, or
`-NoShortcut` to suppress desktop integration. No automatic elevation, script
unblocking, execution-policy bypass or native acceptance bypass is offered.

The plan names the exact source identity, user SID, model, private-state path,
release name, all three public trust anchors, signed model policy, signed
advisory snapshot, signed maintenance review, signed release inventory, signed
technical receipt and explicit storage settings. Private state must be outside
public software and explicitly excluded from folder grants. The receipt must
match the actual OS version, exact release and existing managed boundary, be
unexpired, and contain all 23 passing checks with evidence digests.

The caller-supplied plan digest is initial trust: deliver it through an
independently reviewed channel. A hash downloaded beside an untrusted plan
does not provide that trust. Existing machine anchors cannot be rotated by
installation. Policy/review sequence rollback and conflicting replay are
refused; exact same-byte retries are idempotent and preserve unrelated records.

An incomplete or different protected release is never overwritten or deleted.
It is retained for inspection. If an audit or shortcut operation fails after
enrollment, the command can report failure after the records were published;
inspect protected state and retry the **same** reviewed plan. Do not invent a
new receipt, erase machine state, or weaken policy to recover. Shortcuts already
at `SILO Managed.lnk` are preserved and produce a warning instead of replacement.

## Preparing approval material

Review and Authenticode-sign the PowerShell sources, including the first-stage
managed launcher, **before** preparing/signing the payload. Changes after signing
invalidate its independent release and technical review. The local installer
requires a valid trusted Authenticode signature on the managed launcher before
enrollment, and preserves Internet-zone provenance on copied PowerShell files.

On the target preparation host, prepare an inactive candidate with the intended
private-state path and explicit model. Its `evaluation-installation.json` is part
of the signed inventory; do not rewrite its state location after signing.
Use the existing independent signing/review procedures in
[managed security](SILO-SECURITY-HARDENING.md). Keys must be supplied independently;
the installer never creates signing keys, signs its own policy, or marks tests
passed. The candidate evaluation route remains separate for collecting evidence
before ordinary activation; it is not a switch on this installer.

When the actual signed documents are available, assemble them locally:

```powershell
python .\scripts\build_activation_plan.py --prepared-root 'C:\SILO-Preparation\versions\EXACT_CANDIDATE' --source-id EXACT_16_HEX_SOURCE_ID --release-name REVIEWED_RELEASE_NAME --user-sid EXACT_TARGET_ACCOUNT_SID --native-version EXACT_PLATFORM_VERSION --settings 'C:\Approved\settings.json' --trust-key 'C:\Approved\trust.pub' --trust-key-sha256 INDEPENDENT_TRUST_DIGEST --release-key 'C:\Approved\release.pub' --release-key-sha256 INDEPENDENT_RELEASE_DIGEST --reviewer-key 'C:\Approved\reviewer.pub' --reviewer-key-sha256 INDEPENDENT_REVIEWER_DIGEST --model-policy 'C:\Approved\model-policy.signed.json' --advisories 'C:\Approved\advisories.signed.json' --maintenance 'C:\Approved\maintenance.signed.json' --release-envelope 'C:\Approved\release.signed.json' --technical-receipt 'C:\Approved\technical.signed.json' --output 'C:\Approved\activation-plan.json'
```

This preparation tool needs a reviewed Python environment (or the prepared host
interpreter with `-I -B`); the end-user installer does not need an existing Python
installation. It validates supplied signatures/expiry/storage and refuses an
existing output. It does not enroll or execute a model. Its validation cannot
substitute for the independently collected native observations in the receipt.
Both source preparation and exact-source release packaging must include the
pending installer changes before a real plan/command can refer to them.

Example storage settings, with optional features disabled:

```json
{
  "reference_roots": ["C:\\SILO-Synthetic\\References"],
  "draft_roots": ["C:\\SILO-Synthetic\\Drafts"],
  "excluded_roots": ["C:\\SILO-Preparation\\state", "C:\\Users\\Example\\OneDrive"],
  "allow_code": false,
  "allow_code_exports": false,
  "allow_ocr": false,
  "allow_schedules": false,
  "maximum_retention_days": 30
}
```

These are illustrative paths, not approved settings. Every root must exist,
and sync/storage exclusions and user permissions need real review.

## Distribution command and signing order

1. Review/Authenticode-sign the PowerShell source bytes through the approved
   process before committing the future release source.
2. After source is reviewed/committed for a future release, use the existing
   exact-commit `build_evaluation_release.py`. It never packages private
   `context.md`, dirty/untracked files, signing keys or installed model weights.
   Extract that exact source archive on the target and prepare the inactive
   payload from its `payload` directory. Build the reviewed plan against this
   payload, including any generated `release-origin.json`; a plan made from the
   original checkout may have a different source identity. Native receipt,
   policy, license, advisory and maintenance review remain independent inputs.
3. Authenticode-sign the generated `install.ps1` through the approved signing
   process. Keep the original generated asset set and use a separate signed copy.
4. Run `scripts/repin_signed_bootstrap.py --release ORIGINAL_ASSETS
   --signed-bootstrap SIGNED_INSTALL_PS1 --output NEW_ASSETS`. This checks the
   reviewed bootstrap body stayed byte-identical, regenerates its size/SHA-256
   and installation command, and preserves the source archive. It accepts only
   an appended signature comment block. If signing changes the script body or
   encoding, stop and rebuild/review rather than accepting different code.
5. On Windows, independently verify the actual signer, timestamp, trust/revocation
   status, and permitted script policy on the exact repinned bytes. The portable
   repinning tool deliberately leaves `authenticode_signed: false` and
   `authenticode_status: supplied_pending_native_verification`; comment-block
   detection alone is not signature verification.
6. Prepare the pinned end-user activation command:

```shell
python scripts/build_install_command.py --release NEW_ASSETS --plan activation-plan.json --plan-sha256 INDEPENDENT_PLAN_SHA256 --install-root 'C:\SILO-Preparation' --target-plan-path 'C:\Approved\activation-plan.json' --output ACTIVATION-INSTALL.md
```

This tool accepts only a bootstrap marked as supporting reviewed activation,
checks the local archive/bootstrap pins and matches the archived source identity
to the plan, quotes arguments as PowerShell literals,
and writes a new file. It can read a Windows plan on macOS. It downloads/publishes
nothing. The generated download command becomes usable only after a separately
authorized matching release publication. **No publication is authorized by this
local implementation request.**

## Remaining Windows and signing gates

| Gate | Required evidence |
| --- | --- |
| Authenticode | Valid reviewed signer/timestamp/trust on bootstrap and relevant source/managed launch scripts under the permitted Windows policy; correct pins after signing |
| Independent approval | Exact payload signature, protected public-key enrollment, signed model policy, complete advisory coverage/maintenance review and release/OS-bound technical receipt |
| Fresh installation | Clean Windows host without existing Python/Git; online and complete-cache offline routes; hardware/model selection; space/path failures |
| Native provisioning | Program Files and ProgramData ACL/ownership, LPAC RX, held-handle/link/reparse denial, same-user elevated preparation and ordinary-user launch |
| Failure/retry | Interrupted download/copy; partial managed release refusal; signature/expiry/revocation denial; competing installers; atomic state replace; audit failure before/after commit; exact retry and preserved unrelated records/state |
| First use | Real terminal/desktop shortcut launch, actual pinned model placement, document answers and reviewed artifacts, cancel/restart/cleanup; no elevated ordinary session |
| Upgrade/recovery | Exact newer signed plan, increasing policy/review sequences, retained projects/models, old-release preservation, explicitly reviewed rollback; persistent/reboot/sleep/VPN matrix |
| Expanded coding | Separately provisioned execution pools, SDKs/servers/licenses and independent execution/build/Git/LSP acceptance, followed by the actual-model 108 kg coding milestone |

Portable tests cover data/signature/sequence/atomicity and inert bootstrap
dispatch. PowerShell parsing and portable file-copy/hash fixtures do not qualify
NTFS ACLs, Authenticode, UAC/account behavior, actual inference or containment.
Organization deployment and CUI authorization remain separate decisions.

Local focused verification recorded **93 executions: 88 passes, five native
Windows skips, zero failures/errors**, plus a passing final command-builder
follow-up. Installer/activation/rendered-bootstrap PowerShell syntax parsed and
Python compilation passed. The [validation record](ONE-COMMAND-INSTALLATION-VALIDATION.json)
contains post-test file digests and the evidence limits. Combined PR regression
validation recorded 854 executions: 666 passes, 188 skips, zero failures/errors.
The first full-suite attempt was blocked by loopback sandbox restrictions and
missing terminal dependencies; the complete rerun used the existing full test
environment with loopback permission. No native activation,
Authenticode trust check or real model inference was performed here.

The subsequent PR #29 review fixed archived-source/plan matching and complete
sharded-model preparation. Its full-suite rerun recorded **856 executions:
668 passes, 188 skips, zero failures/errors**, with successful test IDs counted
directly. These results remain portable evidence; the Windows gates above stay open.
