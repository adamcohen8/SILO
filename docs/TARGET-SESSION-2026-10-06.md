# Windows target session — 6 October 2026

## Scope and outcome

The native Python prerequisite was verified and both prepared synthetic Windows
validation runners were executed, diagnosed, corrected and rerun. The final
result is **36 passes, zero failures/errors, and one skipped symlink fixture**:
13 native folder passes, six native installer passes, and 17 portable policy/ABI
passes. Installer fixture acceptance is true; complete folder acceptance remains
false because the symlink fixture lacks privilege. During this filesystem phase no model/runtime was
installed, no inference was started, and no firewall, WSL, execution policy,
Windows feature, or developer-mode setting was changed.

This session used the extracted source archive. It has no Git metadata, test-kit
manifest, or independently supplied kit hash. Source revision and authenticated
kit integrity therefore remain unverified. The PowerShell test-kit wrapper was
not used. These results are local development observations, not deployment
qualification or authorization to process CUI.

## Observed prerequisites

| Item | Observation |
|---|---|
| Windows | Windows 11 Pro 25H2, 64-bit, build 26200 |
| CPU | Intel Core i9-14900KF, 24 cores / 32 logical processors |
| RAM | Approximately 64 GiB visible memory |
| GPU | NVIDIA GeForce RTX 4090, 24,564 MiB reported VRAM |
| Driver | 591.86 |
| C: free storage | Approximately 790 GB / 736 GiB |
| WSL package | 3.0.1.0 present; distributions/features not qualified |
| Global WSL configuration | `.wslconfig` absent at inspection |
| Python | Codex-bundled native Windows Python 3.12.14, 64-bit |
| Python prerequisite | `os.name == 'nt'`, 64-bit pointers, version >= 3.11: passed |
| Ordinary Python command | Windows app execution alias; not used |
| PowerShell wrapper execution | Downloaded unsigned inventory script blocked under existing RemoteSigned policy; policy preserved |

Python was invoked through its explicit bundled executable, using `-I -B`.
No standalone Python installation or dependency download was required for the
standard-library native tests. The bundled interpreter is a development testing
runtime; a redistributable offline Python payload remains a separate requirement.

## Initial native synthetic results (before correction)

| Runner | Tests run | Failures | Errors | Skips | Accepted |
|---|---:|---:|---:|---:|---|
| `scripts/validate_windows_folders.py` | 11 | 0 | 11 | 0 | No |
| `scripts/validate_windows_installation.py` | 6 | 0 | 6 | 0 | No |

Both runners returned exit code 1 and `deployment_ready: false`.
The folder fixtures fail during initial folder grants. The installer fixtures
fail while opening source/storage ancestor directories. Consequently, later
assertions about links, reviewed writes, ACL rejection, checkpoints and rollback
were not established by this run. Zero assertion failures does not mean success:
the errors prevented the fixtures from reaching their intended checks.

Initial attempts inside the Codex command sandbox could not create/clean up
nested temporary fixtures and are excluded from target acceptance results.
The table records reruns outside that sandbox under the current Windows user;
this does not establish administrator elevation or symlink privileges.

## Shared failure diagnosis

The shared `NativeFiles.open_child` call returns `NTSTATUS 0xC000000D`.
The exception now includes the numeric NTSTATUS without emitting a source path
or document data. The following observations describe the initial diagnosis;
the final acquisition changes and results are recorded below.

A separate read-only diagnostic opened the existing `Users` directory relative
to a retained drive-root handle, preserving object-attribute flags `0x1040`:

| Native CreateOptions | NTSTATUS |
|---|---|
| `0x00600021` — existing directory acquisition flags | `0xC000000D` |
| `0x00200021` — diagnostic without OPEN_NO_RECALL | `0x00000000` |
| `0x00400021` — diagnostic with OPEN_NO_RECALL, without OPEN_REPARSE_POINT | `0xC000000D` |
| `0x00000021` — diagnostic synchronous directory open | `0x00000000` |

This identifies the no-recall option in this directory-open combination as the
trigger on this target. Follow-up diagnostics also found that `ReOpenFile`
rejects the Win32 no-recall flag with error 87, while `OpenFileById` accepts it.
The Win32 rename wrapper rejected the handle-relative publication form; the
native rename API accepts it. Arbitrary host filters and full-stack network
isolation remain separate acceptance gates.

Reference: [Microsoft NtCreateFile API contract](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntcreatefile).

## Final corrections and validation

- Native directory and file-metadata acquisition uses supported synchronous,
  handle-relative, no-follow options. Existing-file metadata handles request no
  content-read access. The unused direct-read shortcut now fails closed.
- Only a checked local, non-directory, non-reparse, non-offline, single-link
  object is opened for data, using its retained metadata handle as the volume
  hint and its NTFS file ID with `OpenFileById`. The Win32 no-recall/no-follow
  flags remain requested on the data handle. Identity/attributes are checked
  again before returning it; mismatches close the acquired handle and fail.
- Publication uses `NtSetInformationFile(FileRenameInformation)` relative to
  the retained parent. Replacement remains disabled. Directory creation uses
  the directory-specific add-subdirectory access bit.
- Added native regressions establish that metadata handles cannot read content,
  offline files are rejected before data acquisition, data handles block
  ordinary writers, and reopening after an allowed filename rename still
  selects the original file rather than replacement bytes at the old name.
  Added file-ID descriptor ABI checks to the portable policy suite.

**Observed sharing limitation:** on this Windows build, metadata/by-ID file
handles may allow a filename rename despite requesting no delete sharing.
They therefore must not be treated as a pathname lock. The retained identity,
file-ID acquisition and subsequent validation preserve the selected object;
there is no pathname fallback. Granted directory rename/substitution rejection
passes. This does not qualify every hostile filesystem mutation.

| Final check | Passes | Failures | Errors | Skips | Exit / acceptance |
|---|---:|---:|---:|---:|---|
| Native folders (expanded to 14 tests) | 13 | 0 | 0 | 1 | Exit 1; not accepted |
| Native ACL/staging | 6 | 0 | 0 | 0 | Exit 0; fixture acceptance true |
| Portable Windows policy/ABI | 17 | 0 | 0 | 0 | Exit 0 |

The skipped test is `test_native_symlink_and_ancestor_reparse_rejected`:
fixture creation reports Windows error 1314 (required privilege unavailable).
The run is not elevated and the current token contains no Administrators group.
No elevation, account-rights, developer-mode or execution-policy change was made.
A permitted account/session with the existing symlink privilege must execute
the remaining fixture before full folder acceptance can be recorded. The
runner deliberately returns nonzero when a fixture is skipped.

Detailed synthetic diagnostics and a source-hash-bound JSON summary are saved
locally under ignored `artifacts/`. Those hashes identify the tested edited
files; they do not authenticate the downloaded source archive. These tests
are not a real installation, actual reboot, GPU test or isolation test.

API references: [OpenFileById](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-openfilebyid),
[FILE_ID_DESCRIPTOR](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_descriptor),
[native rename contract](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_rename_information).

## Subsequent GPU evaluation

After the filesystem phase, the pinned model and Windows CUDA runtime were
acquired and hash-verified. The [GPU baseline](GPU-BASELINE-2026-10-06.md) records
53/53 model layers on the RTX 4090, short generation measurements and a synthetic
tool round trip. One requested line locator failed. The temporary inference
server was stopped; full agent and isolation qualification remain pending.

## Remaining work

The subsequent [real-agent/isolation evaluation](WINDOWS-AGENT-ISOLATION-2026-10-06.md)
prepared a project-local CPython 3.12 environment and 40 verified, hash-pinned
Windows evaluation wheels. Fifteen real-model synthetic checks passed with the
GPU runtime, graph and parsers in AppContainer jobs. Text line, PDF page and DOCX
paragraph citations passed, as did host-reviewed saves, stale-source rejection,
revocation, approved external IPv4 TCP denial and retained host connectivity.
All six pipe attack tests and seven contained parser fixtures passed; the final
regression summary records 68 passes, two POSIX-only skips and no failures/errors.
All owned jobs/profiles/ACL leases/temporary fixtures were cleaned up. Complete
isolation acceptance and deployment readiness remain false.

- Complete the privilege-dependent symlink fixture and the wider native
  filesystem acceptance matrix before promoting the Windows folder candidate.
- Verify the intended source/test-kit identity through an independent trusted
  channel; no expected hash was invented from this archive.
- Determine the permitted execution route for the PowerShell wrappers.
- Qualify the remaining interpreter/UI/platform dependencies and broader model
  quality; the Windows Python evaluation wheel lock and synthetic agent workflow
  are now recorded.
- Implement and verify full-stack isolation, retained host connectivity,
  reboot/resume behavior and signed offline installation.

Optional parser tests were not run during the initial filesystem phase; they
passed in the subsequent evaluation above. Production Windows folder and parser
use remains disabled; deployment readiness remains false.
