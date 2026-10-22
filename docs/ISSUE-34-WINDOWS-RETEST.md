# Issue #34: local fixes and Windows retest

These source fixes were developed against merged PR #33, commit
`44a6873b8b2efcc6a580833f17fb8fc42600e752`. Publishing or merging the source
does not update the v0.1.0 installer or establish successful Windows retesting
or native acceptance.
Use only the existing authorized recoverable development host and synthetic
files. Preserve the original application, staged v0.1.0 release, backup, lab
keys, enrolled trust anchors, monotonic records and first-failure evidence.

## Changes to review

1. `asset_integrity.digest_file` now acquires a native Windows read handle with
   **FILE_SHARE_READ only**, OPEN_REPARSE_POINT and OPEN_NO_RECALL. Existing
   writers cause refusal. New normal write/delete/rename opens are excluded
   through the final path check. Native `FILE_BASIC_INFO.ChangeTime` and held
   identity/size/link/attribute observations supplement the existing Python
   path/descriptor checks. There is no permissive-open or Python-stat fallback
   if native acquisition/query fails. Cancellation closes the lease.
2. `RunnerContainer.prepare_process` replaces the rejected class-46 query with
   a controlled `AccessCheck` verification. The same suspended worker must
   already pass AppContainer/profile/zero-capability/low-integrity checks. On
   an impersonation duplicate, require Everyone-only read to be denied,
   Everyone + ALL_APPLICATION_PACKAGES read to be denied, and Everyone + the
   exact profile SID read to be granted. The profile grant is a positive
   control; API failure or an indiscriminately denied token cannot pass. No
   ACL, privilege, token attribute, or host policy is changed by this probe.
   Descriptor or duplicated-token cleanup failure also prevents acceptance.
   A plain AppContainer must fail. Registry/profile protections, job limits,
   loopback-exemption checks and pre-ResumeThread ordering remain required.
3. Token-query exceptions now retain the real WinError, query class, size/data
   phase and returned/required size. Invalid/oversized results fail closed.

The AccessCheck pattern is an implementation derived from Microsoft's documented
LPAC semantics; it is not an individually documented Microsoft LPAC-validation
routine. It requires independent native review and the controls below. It does
not inspect private token attributes, accept a failed query, or fall back to
plain AppContainer. File sharing protects normal file opens during verification;
it is not protection against a compromised kernel/administrator, nor a lifetime
guarantee after the hash returns. Protected immutable software ACLs still matter.

Primary contracts reviewed:

- [LPAC and ALL_APPLICATION_PACKAGES semantics](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ne-winnt-token_information_class)
- [AccessCheck, including impersonation token, owner/group and API/access-status distinction](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-accesscheck)
- [DuplicateTokenEx](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-duplicatetokenex)
- [GetTokenInformation](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-gettokeninformation)
- [CreateFileW sharing contract](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
- [GetFileInformationByHandleEx](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex)
- [FILE_BASIC_INFO.ChangeTime](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_basic_info)

## 1. Select the exact reviewed source in a separate tree

After this source PR is merged, fetch the repository and select its exact merge
commit in a fresh task worktree/source copy. Record that commit, its tree and
the runtime source ID. Use LF source bytes; avoid checkout conversion that would
silently change the reviewed identity. Read the source diff and this guide before
execution. Include both new runtime helper modules and both new test modules.
Preserve existing Windows work/fixes/bundles. Do not replace Program Files, an
installed payload, the original application, or an existing dirty checkout with
source files.

The earlier local-only patch kit targets the PR #33 baseline and predates the
final review's cleanup-failure fix. It is historical evidence, not the final
merged source; do not apply it over a merged checkout. Any new Windows fixes
should remain local until separately requested. Source-only tests below do not
require certificate or enrollment changes.

## 2. Native primitive tests before model work

Use the already reviewed pinned native x64 CPython 3.14.8 environment with its
declared dependencies. Use a fresh local fixed NTFS synthetic temp/evidence
directory outside cloud sync and outside the source tree. Run ordinary-account
tests first. In the following commands set `$Source`, `$ReviewedPython` and
`$Evidence` to the reviewed source, interpreter and a fresh evidence directory.
Use a new report filename each time; preserve every first failure separately.

```powershell
$env:SILO_RUN_NATIVE_LPAC_PROBES='1'
try {
    & $ReviewedPython -I -B (Join-Path $Source 'scripts\run_windows_regressions.py') --source $Source --pattern 'test_asset_integrity.py,test_windows_asset_file.py,test_windows_lpac.py' --output (Join-Path $Evidence 'issue34-native-primitives-first.json')
    $PrimitiveExit=$LASTEXITCODE
} finally {
    Remove-Item Env:SILO_RUN_NATIVE_LPAC_PROBES -ErrorAction SilentlyContinue
}
if ($PrimitiveExit -ne 0) { throw 'Preserve native primitive failure before any dependent model work' }
```

The native LPAC tests are explicitly opted in because they create temporary
AppContainer profiles and inert suspended processes. They deliberately abort
before ResumeThread, close owned process/job/pipe/token handles and delete their
new profiles. They use the reviewed current interpreter and do not modify its
ACL. `private_desktop=False` is used only for these never-resumed token probes;
the real RunnerContainer still uses its private desktop. No model is loaded.
Failure to create/probe/clean up is a real failure, not an expected skip.

Require these actual results:

- An ordinary own token is rejected as non-AppContainer. A zero-capability
  **plain AppContainer** must yield Everyone=false, AAP=true, profile=true and
  fail LPAC verification. An LPAC must yield false/false/true and pass. Both
  suspended-process probes must establish base token identity, never call
  ResumeThread, and complete owned cleanup. Retain any native WinError/stage.
- One mutation method runs **100 same-size/restored-mtime write attempts** with
  unchanged-file and post-lease-write controls on every trial. Expect WinError
  32 on each attempted normal write, the original bytes to remain unchanged,
  and the correct digest. A changed file accepted with its old digest is a
  failure. This is one method containing 100 trials, not 100 passed methods.
- The original issue's mutation test must now either detect an actual change or
  receive Windows sharing error 32 with unchanged original bytes. No sleeps or
  removed assertions are used. A pre-existing writer must prevent digest
  acquisition; rename/delete attempts must fail while hashing, then succeed
  after release. Empty files, concurrent readers, legitimate edits before
  hashing and write-after-cancellation must work.
- Portable error fixtures must still reject failed AccessCheck calls, wrong or
  incomplete control patterns, inconsistent outputs, oversized requests and
  malformed token responses and cleanup failures. An API error must never become a denied-access
  success. The real ChangeTime query must succeed; no fallback is permitted.

Repeat the targeted run from an elevated window for the same lab account, with
a new evidence filename, to catch owner/ACL differences. Do not elevate merely
to make a skipped symlink fixture pass or change Developer Mode/host policy.

## 3. Full regressions, preparation and protected candidate retest

After the targeted native probes pass, run the full source suite with the
existing reviewed runner and fresh output. Record successful execution records,
distinct methods, skipped methods/subtests, failures and errors separately.
Do not infer successes by subtracting skips. The full suite must have zero
failures/errors, including the previously failing mutation method. Source
regressions and skipped native cases are not the 23 technical acceptance checks.

```powershell
& $ReviewedPython -I -B (Join-Path $Source 'scripts\run_windows_regressions.py') --source $Source --output (Join-Path $Evidence 'issue34-full-first.json')
if ($LASTEXITCODE -ne 0) { throw 'Preserve and investigate the full-suite failure' }
```

Only then rebuild the exact changed candidate using the existing reviewed lab
process. Include both new runtime modules. Sign source PowerShell before payload
inventory/signing, verify the rebuilt source/archive/postimages, prepare at a
fresh state identity (reuse only already verified caches), repeat actual native
component/advisory review, and use a reviewed protected update/recovery procedure
for the already-enrolled host. Do not blindly rerun the kit's fresh-host
initializer/enroller: they refuse existing protected state. Preserve anchors and
monotonic records; never delete/reset machine state, patch installed files in
place, or reuse an old payload's approvals/activation plan. Stop with the exact
missing update prerequisite if no reviewed update path is available.

For the rebuilt, signed, reviewed and properly enrolled **candidate**, rerun
the lab's real `check_evaluation_install.py --candidate` invocation with its
**new** prepared manifest digest, model ID, account, settings and synthetic
Reference root. Require actual model startup/placement, complete LPAC access
evidence, the synthetic 37-crates answer with the exact citation, PDF/DOCX parser
results and cancellation/cleanup. Retain the first failed report before retest.

Then run the real protected candidate terminal and desktop launchers. Exercise
actual inference, default-deny access, explicit Reference/Drafts grants,
revocation, a reviewed synthetic draft save, cancellation/restart and cleanup.
Do not substitute a scripted tour/preview. Keep Code/OCR/schedules disabled for
this documents-only milestone. Ordinary launch must continue refusing until
independent exact-release technical acceptance and a reviewed activation plan
exist. A candidate session is not ordinary-user activation.

## 4. Return evidence

Return sanitized source/postimage/archive/installed identities, native OS and
Python versions, exact commands, primitive control results, the 100 mutation
trial outcomes, unchanged-file controls, first failures/retests, regression
counts, actual model/document/UI outcomes, cleanup and remaining prerequisites.
Keep raw personal logs, keys, lab signatures, vaults, model weights and private
`context.md` out of GitHub. No push, merge, release publication or issue closure
is requested by this handoff. All 23 checks remain pending until actually
performed and independently reviewed for the rebuilt release. Successful Mac
fixtures do not close issue #34 or qualify Windows containment.
