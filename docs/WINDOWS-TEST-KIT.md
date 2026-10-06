# Start here: Windows validation kit for 6 October 2026

**Downloaded Code → Download ZIP from GitHub? Start with [source-ZIP instructions](WINDOWS-SOURCE-ZIP.md).** This page applies to the separately generated kit containing `TEST-KIT-MANIFEST.json` and `wheelhouse`. GitHub's source ZIP does not include those generated files. You can still run inventory and native synthetic tests directly from source without the kit launcher.

This archive contains reviewed source, synthetic fixtures, a candidate inference profile, an isolation plan, a staging framework, and two small optional parser wheels. It contains no real model weights, CUDA runtime, complete agent/UI environment, Python distribution, CUI, credentials, or deployment authorization. It makes no GitHub/network request and requires no GitHub login on the unit computer.

## First session

1. Transfer/extract through the unit's permitted process into ordinary approved local storage. Keep the separate archive/manifest hashes from the trusted development channel. Review the PowerShell scripts; obey the existing execution policy. Do not unblock/bypass policy or change developer mode to make tests pass.
2. Use an approved native **64-bit Windows Python 3.11+** executable. The first folder/installer tests require only its standard library. If Python is unavailable, run the read-only inventory script alone and report that prerequisite as unavailable. Python provisioning is not hidden in this kit.
3. From the extracted kit root, run the command below with the actual executable path and the **manifest hash from the separate hashes JSON**. It verifies kit integrity, checks Python, prints metadata-only inventory, and runs 11 native synthetic folder fixtures. It does not grant model access to the included fixtures or start inference.

```powershell
.\installer\Start-TargetValidation.ps1 -PythonExe 'C:\Approved\Python\python.exe' -ExpectedManifestSha256 'INDEPENDENT_TEST_KIT_MANIFEST_SHA256'
```

No skipped/failed folder fixture is accepted as success. Symbolic-link creation may require already-approved elevation/developer-mode permissions. Missing privileges remain a failed acceptance gate; do not change unit policy for this test. The runner returns nonzero on failure/skip and always reports `deployment_ready: false`.

4. If permitted, run the six additional synthetic ACL/staging tests. They create private ACLs only on owned temporary folders and stage inert text, not an AI model:

```powershell
.\installer\Start-TargetValidation.ps1 -Scope Installer -PythonExe 'C:\Approved\Python\python.exe' -ExpectedManifestSha256 'INDEPENDENT_TEST_KIT_MANIFEST_SHA256'
```

5. Record permitted inventory and fixture counts/failures. The [results checklist](TARGET-SESSION-CHECKLIST.md) distinguishes passed, failed, and not-run work. Share only permitted metadata; keep prompts, documents, addresses, sensitive errors/logs and operational data out of GitHub/chat.

## Optional document parser session

Only if approved, create a separate test environment **outside the extracted kit**. Adding a venv/results file inside the kit will intentionally fail its exact-inventory check. No system Python changes or Internet installation are needed:

```powershell
& 'C:\Approved\Python\python.exe' -m venv 'C:\Approved\LocalAI-TestEnv'
& 'C:\Approved\LocalAI-TestEnv\Scripts\python.exe' -m pip install --no-index --no-deps --require-hashes --find-links .\wheelhouse -r .\requirements\documents-offline.txt
& 'C:\Approved\LocalAI-TestEnv\Scripts\python.exe' .\scripts\validate_document_parsers.py
```

The optional parser run tests only synthetic bytes and explicitly opts into the unqualified Windows parser candidate. It does not establish OS containment, full document fidelity, OCR, model quality, or inference. Wheels are pypdf 6.19.0 (BSD-3-Clause) and defusedxml 0.7.1 (PSF); their distributions contain their license texts. The kit checksum is an integrity aid, not a production signing authority.

## Later tests

Follow [inference profile](INFERENCE-PROFILE.md), [network isolation plan](ISOLATION-VALIDATION.md), and [installer framework](INSTALLER-FRAMEWORK.md). GPU binaries/weights, their full hashes/licenses, and an implemented containment boundary are still needed before those acceptance tests can run. Inventory and synthetic native tests can make tomorrow useful without them.

The verifier catches accidental/known-byte changes in the trusted kit. It is not an authenticated production installer or a guarantee against concurrent hostile changes between verification and execution. Use reviewed source from a trusted transfer process; signed protected staging is a separate gate.
