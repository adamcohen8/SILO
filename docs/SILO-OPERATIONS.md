# SILO operating procedures (evaluation draft)

These procedures describe the implemented local mechanisms. An organization must review them and complete authorization before CUI use. The current application permits public/synthetic evaluation only.

## Storage and retention

Application payloads, model assets and private project data have separate purposes. Installed projects live in `state_root/projects`, a protected NTFS directory owned by the current account with access limited to that user, SYSTEM and Administrators. Windows protects its random encryption key with account-scoped DPAPI. The model receives neither this directory nor the key. Avoid roaming/cloud-synchronized state roots.

Saving a project is explicit. Retention defaults to 30 days since activity and can be set to 1–365 days. Expired projects cannot resume or run tasks until explicitly extended; `/project prune` removes expired stored projects. Inspection/closing does not renew retention. `/clear` clears retained conversation and reviews in the active project; project deletion removes its retained records and grants. User documents and approved exports remain in their selected folders. Deletion is logical filesystem deletion, not a secure-erasure claim; backups have their own retention policy.

Revoked/replaced folders and changed source hashes invalidate retained context. Opening a project can restore only the same directory identities. A user must explicitly select changed folders again. Pending saves and Code workspaces are never restored.

## Backup and recovery

`/backup ABSOLUTE_PATH` creates a new encrypted project backup, excludes `vault.key`, policy/trust records and model selection, and refuses overwrite. It is at most 64 MiB. Keep the backup under the organization's handling rules. Restore authenticates every record before writing anything, refuses replacement of existing project records, disables restored schedules, and rechecks folder/source identities when the project opens.

The ordinary backup is account-key-bound. Retain the original protected `vault.key` with the protected application state under the approved account recovery process. A newly generated key cannot decrypt an old ordinary backup. Do not copy a development plaintext key into a native installation or send keys in logs, chat, email or support tickets. Use the separate recovery-export command for a password-protected portable backup when authorized. Store the recovery password separately from the backup. The organization must approve recovery-key/password custody and test restoration on its target environment.

For portable recovery, use the trusted host interpreter from a separate terminal (password entry is hidden):

```text
python scripts/manage_silo.py export-recovery --state C:\SILO-State\projects --output C:\Backups\projects-recovery.silo
python scripts/manage_silo.py restore-recovery --state C:\New-SILO-State\projects --archive C:\Backups\projects-recovery.silo
```

Select an empty, approved private target vault created by SILO. The recovery archive authenticates the original record key inside password-protected ciphertext, and restoration reseals records with the new local account key. It uses a random salt/nonce and a fixed bounded Scrypt derivation; native performance and organizational cryptographic requirements still need qualification. Administrative trust/policy records are excluded from both backup forms.

After restoring, open the desired project, inspect grants/context, check source freshness, and reconcile any schedules explicitly. A schedule interrupted by a crash or restored from backup must not replay its uncertain slot. Reconciliation advances to a future deadline. Publication still requires normal reviewed approval.

A private `.schedule-runner-lock` excludes concurrent schedule runners and reconciliation during an active attempt. It is removed after clean completion. If a crash leaves the marker, first confirm that all SILO processes using that vault have exited and preserve the attempt record. An operator may then retire that exact marker under the incident/recovery procedure, reopen the project, and reconcile the interrupted schedule. Never remove the marker while its owner is active. The private `.installer-lock` similarly protects atomic record transactions and requires inspection after an interrupted write.

## Model policy

Administrative `--state` arguments refer to `state_root/projects`, the vault directory. Before deploying an organization policy, acquire the public key and its SHA-256 fingerprint through an independent approved channel. Use `manage_silo.py enroll-key` and `update-policy` explicitly as administrator on Windows. A signature/key delivered only inside the bundle being verified is not an independent trust anchor.

The deployment launcher should require the organization's key fingerprint (`--required-policy-key-sha256` for the terminal), be protected against ordinary-user changes, and maintain policy sequence/expiry through the organization's configuration-management process. The local account store guards model-worker access; it is not a TPM-backed monotonic counter or a machine-wide policy service. Do not treat an old valid backup or manually removed policy store as an approved policy rollback. Ordinary project backups do not restore administrative policy records.

Import only catalog-pinned GGUF files from approved offline media. No model session downloads dependencies. Inspect hardware recommendations as capacity estimates, then measure each model's documents, code (if separately qualified), structured tools, accuracy, latency, peak memory and failure behavior. Record publisher/jurisdiction uncertainty explicitly; signed administrative policy can reject it. Model selection requires restart and never changes folder grants or grants execution authority.

## Updates, rollback and deployment

1. Prepare a versioned offline bundle with pinned source/runtime/model/dependency inventories and reviewed license/redistribution records.
2. Sign bootstrap scripts using the organization's existing certificate. Build the final inventory after signing, then sign the detached manifest with the organization's protected signing key.
3. Verify first-stage trust through an already trusted organizational deployment mechanism. Verify the detached manifest and the complete payload before installation. Do not rely on a self-verifying downloaded interpreter as initial trust.
4. Back up projects under the approved recovery procedure. Keep state outside application payloads; an application update must not silently grant folders, resurrect approvals or restore uncertain scheduled actions.
5. Exercise the existing installer’s fresh/offline/retry/repair/rollback paths against the exact signed bundle. These paths are implemented but their new native acceptance is pending. Keep the prior verified application version and its receipts until rollback testing passes.
6. Collect the complete native acceptance matrix for that release/configuration. Independently review and sign evidence receipts, supply the reviewer public key and its independently verified digest to `manage_silo.py readiness`, and check measured model behavior, office rendering, storage recovery, resource limits and all network/filesystem paths. Do not count skips as passes.
7. Obtain the organization's deployment/CUI authorization separately. Publication and production deployment need their own release-owner approvals.

Signing tools create artifacts only when explicitly invoked; this implementation run did not sign or publish an organization release. Signing-key rotation and migration require a separately reviewed procedure. A future hosted inference mode would need separately approved endpoints, credentials, data-transfer controls and handling rules; this local implementation has no hosted inference fallback.

## Incident response

Cancel active work and close SILO; cancellation owns the inference/worker/code jobs and waits for cleanup. If cleanup is incomplete, keep the application closed and preserve the exact owned leases/metadata for review. Do not remove unknown VHDs, steal locks, loosen ACLs, disable firewalls or change script execution policies to force progress.

Preserve nonsensitive configuration IDs, release/policy hashes, evidence receipts and error categories. Avoid collecting prompts, documents, model stderr or secrets in support bundles. Inspect source/runtime/model drift and current policy before restarting. Reconcile unknown scheduled attempts without replaying the same slot. Use the organization's incident/handling process for suspected data exposure, credentials, retained state and authorization decisions.
