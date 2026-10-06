# Offline installer framework candidate

`installer/Install-LocalAI.ps1` is the proposed one-command entry point, currently limited to an integrity plan and explicitly requested development staging. It does not install/run a model, download assets, enable Windows features, change firewall/services, reboot, schedule work, or grant deployment readiness. Production activation is deliberately unavailable.

From a reviewed test kit and an approved 64-bit Windows Python 3.11+ runtime:

```powershell
.\installer\Install-LocalAI.ps1 -Mode Plan -BundlePath 'C:\Approved\SyntheticBundle' -ManifestSha256 'INDEPENDENT_MANIFEST_SHA256' -PythonExe 'C:\Approved\Python\python.exe'
```

Replace the hash placeholder; a hash supplied with an untrusted bundle is not authentication. The kit contains a tiny synthetic bundle and its separately listed hash for exercising the framework, not real software or weights. The manifest format is described in [offline bundles](OFFLINE-BUNDLE.md).

Explicit `-DevelopmentCandidate -Mode Stage` copies verified bytes into private installation state storage. The wrapper creates only a new root with a protected ACL granting the current user, SYSTEM, and Administrators full control. It never changes an existing directory's ACL. Native code checks the held root's owner, protected DACL, exact principals, local NTFS/reparse/recall attributes, and ancestor handles. POSIX fixtures instead require current-user ownership and mode 0700. This protects staging from other ordinary users; it is not containment against compromised software under the same user or an administrator.

Streams are copied through held handles with exact size/digest checks, exclusive temporary files, and no-replace publication. The staged copy is verified again. Source links, undeclared assets, file/device/volume substitutions and recalled data fail closed. No code is imported from the payload. An exclusive lock rejects concurrent operations. A crash lock is never stolen automatically: inspect it before manual recovery. Native APIs, ACL creation, sharing, crash recovery, and storage-device behavior remain unqualified until Windows tests.

Append-only, hash-linked checkpoints bind the transaction to the manifest and record `planned`, `staging`, `staged`, `awaiting_reboot`, `pending_validation`, `failed`, or `rolled_back`. Checkpoint links detect corruption; they are not signed attestations. Repeat staging rechecks existing assets and is idempotent. `PauseForReboot` records the host boot timestamp without requesting a reboot. `Resume` requires a changed boot timestamp, rechecks staging, and leaves prerequisite/security verification pending. It cannot grant readiness or skip isolation checks.

`Rollback` stream-verifies present staged contents before removing declared payloads, preserves unrelated storage/settings, and retains the journal. Unowned or modified files stop rollback for inspection. An already rolled-back operation is idempotent, and the same bundle can then be staged again. Source bundle/manifest availability is required for operations. In-place repair/upgrade, power-loss durability, interrupted deletion, real reboot/feature changes, signed trust, and activation remain later gates.

Native synthetic framework tests:

```powershell
python .\scripts\validate_windows_installation.py
```

These six fixtures create private ACLs only on owned temporary synthetic folders, stage inert text payloads, exercise checkpoints/reboot gating/idempotence, reject public ACLs and changed content, and preserve unowned files. Passing them does not validate Windows PowerShell 5.1 wrapper execution or a complete installation.
