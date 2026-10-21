# Windows development-lab results — 21 October 2026

These are synthetic-only development observations, not production/CUI approval
or complete native containment acceptance. Published v0.1.0 assets were not
replaced. The original application and separately staged public release were
preserved.

## Confirmed fixes

- Elevated model preparation produced Administrators-owned temporary files whose
  protected OWNER RIGHTS DACL prevented the intended ordinary account from
  reading the published model. Fresh model/shard staging now uses the existing
  explicit TokenUser/SYSTEM/Administrators private-directory policy. Old ACLs are
  not broadened. Native ACE checks passed in ordinary and elevated processes;
  the real elevated-prepared model was subsequently read and hashed by the
  ordinary account.
- Python basic/stat metadata reported the system GPU tool's internal 0x40000 EA
  bit, which the inventory guard interpreted as directory-enumeration
  RECALL_ON_OPEN. The fixed-system-tool check now obtains directory-enumeration
  metadata to interpret recall correctly. Real recall, reparse, offline and
  directory entries remain denied; general application-file and hardlink guards
  are unchanged.
- The launcher could not translate the displayed ALL RESTRICTED APPLICATION
  PACKAGES account back to its SID, even outside the tool sandbox. It now reads
  native SecurityIdentifier rules directly. Ownership, allowed trustees,
  private/public distinction and read-only rights checks are unchanged.
- The selected CPython 3.14 installer profile upgrades cryptography 46.0.5 to
  50.0.2. The installed advisory follow-up also upgrades pypdf 6.19.0 to 6.20.1
  and certifi 2026.7.22 to 2026.10.19, including exact wheel hashes, metadata and
  dependent catalog pins. A fresh 47-package installed scan had complete
  coverage and no findings. This does not cover native libraries, drivers,
  models or later advisories. Historical/unselected CPython 3.12/developer
  cryptography locks remain outside this tested profile.
- Signed-helper regression fixtures now avoid adding a second synthetic
  Authenticode trailer. Native private-folder fixtures use the actual TokenUser
  instead of an elevated temporary directory's initial Administrators owner.

## Frozen lab identities and actual regression records

The unsigned public baseline was commit
b288baf6f6e449f57d83d9b2eef04b800390b71b. The lab derivative, signed archive,
installed payload and this unsigned PR source are distinct identities.

| Lab installation | Source ID | Prepared manifest SHA-256 |
| --- | --- | --- |
| Reviewed/enrolled offline candidate | 102037111b4da7ec | 7804da262c8f8d3ecb827cc34ae9f28ecb4cb3cff5f2a3373947caa03de6c862 |
| Separate elevated online preparation | 102037111b4da7ec | acabb979ab928ad83526aa9e4abf6966644c973c1d7843641e69b88d6e9fd826 |
| Later inactive launcher-fix derivative | dc2649967442cc84 | 68213728f38cbd6adc053da2989c4010a11616dc9e4e3cf3fdd896a71f6fe511 |

The enrolled release-envelope SHA-256 was
4ed37ee568fc03033b8ae1ac7efb41637dd2442c959413a97fd3c6f122e702a8.
Offline preparation used verified owned caches; the online control reused model
weights and actually downloaded the two new pypdf/certifi wheels. No model
download was repeated. Separate state identities did not share approvals.

| Frozen run | Executions | Successful records | Skip records | Failures | Errors |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full ordinary, source 102037111b4da7ec | 868 | 489 | 382 | 0 | 0 |
| Focused ordinary, same source | 105 | 57 | 48 | 0 | 0 |
| Focused elevated, same source | 105 | 53 | 52 | 0 | 0 |
| Focused ordinary, launcher derivative | 105 | 57 | 48 | 0 | 0 |
| Ordinary authority checks after enrollment | 2 | 2 | 0 | 0 | 0 |

Successful records and skipped subtest records are not mutually exclusive
execution partitions. The new launcher derivative did not inherit the earlier
full-suite result. All frozen regression reports recorded no source change
during their run.

After rebuild, lab signing, 335-file archive verification, code/signature review
and fresh inactive installation, seven separate native ACL cases passed. The
real protected public ACL and in-memory controls exercised allowed RX, private
storage, write/unknown-trustee/deny-entry rejection. No existing ACL was changed.
Ordinary attempts to overwrite machine trust or substitute a private machine
store were refused; the original trust record remained unchanged.

Host: Windows 25H2 build 26200.9711, RTX 4090, driver 32.0.16.1088. Interpreter:
pinned CPython 3.14.8 AMD64, executable SHA-256
434b361fe0c5960d404974feed493db47f2603a1ace2574312104fbed0182c6f.
Actual installed cryptography/cffi/pypdf/certifi versions were
50.0.2 / 2.1.1 / 6.20.1 / 2026.10.19.

## Actual candidate preflight failure: LPAC verification remains blocked

Recovery catalog and a fresh existing Windows restore point were verified before
candidate enrollment. Actual component-specific review and advisory signatures
preceded enrollment; they authorized only narrow candidate evidence collection.
A protected evaluation-deployment was enrolled, with no ordinary deployment or
signed technical receipt.

The protected interpreter ran check_evaluation_install.py against the exact
offline manifest, candidate flag, dedicated synthetic Reference folder and
nemotron35-lightning-30b-q4-evaluation-1. First attempt and unchanged diagnostic
rerun both exited 1 at model_startup. Installed-file verification and Qt imports
passed; cleanup passed. Placement, cited TXT answers, PDF/DOCX parsing, completed
grants/revocation and token evidence did not pass because startup stopped first.

The first exception was OSError("Contained token metadata unavailable"), with
errno and winerror both absent. An inert suspended-worker probe using the same
boundary established:

- AppContainer=true, zero capabilities, low integrity and no profile loopback
  exemption were verified before the LPAC-specific query.
- GetTokenInformation class 46 returned required length 0 and captured Windows
  GetLastError 87. Ordinary own-token size/buffer probes independently failed
  with the same numeric error for class 46.
- ResumeThread was never reached; the inert worker launch failed and owned
  container cleanup completed. The probe did not load a model or enable Code.

A diagnostic collector's zero exit means its report was saved, not successful
worker launch. AppContainer membership alone does not prove LPAC identity.
The stronger pre-resume guard remains unchanged.

The [Win32 token enumeration](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ne-winnt-token_information_class)
describes LPAC, but the public
[GetTokenInformation contract](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-gettokeninformation)
does not supply a class-specific output/version contract that resolves this
observed failure. A supported, independently reviewed LPAC-verification method
on the target build is still required. This PR does not substitute plain
AppContainer, undocumented token attributes or fabricated acceptance.

## Remaining Windows and distribution gates

All 23 technical checks remain pending. Actual inference/placement, document
citations and parsers, terminal/desktop sessions, reviewed saves and cancellation
remain blocked by startup. External UDP/IPv6/LAN/proxy/VPN responder coverage,
child denial, filesystem/profile/registry boundaries, exhaustion, drift,
reboot/sleep, storage encryption, dump/pagefile policy, sync exclusion, crypto
configuration and audit retention need exact-role native evidence and
independent review. Fixture results cannot substitute for that receipt.

The new launcher derivative remains inactive and unenrolled. Updating the
protected candidate requires a reviewed update procedure preserving existing
anchors and monotonic records; machine policy was not deleted/reset, and
protected bytes were not patched in place. Lab enrollment/current-user trust
remain present; no physical restore or reboot was performed. Final observation
found no remaining process under the protected candidate runtime.

Initial approval cancellation, archive/working-tree line-ending disagreement,
task-harness errors and actual preflight failures were preserved locally before
correction/retest. Their raw logs, lab signing material, private context and
generated assets are excluded from this PR.

Public distribution still requires reviewed release remediation, publisher
signing, timestamp/revocation qualification, native binary/model conversion
lineage and redistribution review. No production or CUI claim is made.
