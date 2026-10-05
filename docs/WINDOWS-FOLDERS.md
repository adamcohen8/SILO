# Windows folder adapter candidate

This is an unqualified implementation for native synthetic validation. The ordinary `Workspace`, desktop preview, and agent command continue to refuse Windows folder access. They do not automatically select this candidate. Only trusted test code explicitly creates `WindowsFolderBroker(validation_mode=True)` and injects it into the existing review controller.

No Windows machine is available in the development environment. Portable tests validate policy decisions against an inert API fixture and check native structure layouts/record parsing. They cannot validate Windows sharing, reparse handling, native API behavior, or filesystem races.

## Implemented controls

- Absolute drive-letter folders on fixed local NTFS disks only. Whole-drive grants, UNC/network paths, relative-drive paths, and device/extended namespaces are rejected.
- Every directory component is opened relative to a retained parent handle. Native opens use `OBJ_DONT_REPARSE` and `FILE_OPEN_REPARSE_POINT`; opened objects are checked again for reparse attributes, local disk type, and volume identity.
- Granted directories and all their ancestors are retained without delete sharing until revocation. Nested operation handles also exclude delete sharing. This is intended to prevent directory rename/substitution while authority is active; native tests must establish that behavior.
- Overlaps/aliases are rejected using canonical volume paths and file-ID ancestry. Case/short-name alias behavior still requires target evidence.
- Model paths use forward-slash relative components. Traversal, alternate streams, reserved DOS devices (including superscript variants), wildcards, control characters, invalid Unicode, overlong components, and trailing dots/spaces are denied.
- Reads first open a metadata handle and require a bounded, single-link, non-directory disk file. Offline/recall attributes (including the shared EA/recall bit) are rejected conservatively before requesting data access. The checked object is reopened for data while the no-delete metadata handle remains held, with an identity check and no write/delete sharing. Opens request no recall; those flags are not an OS egress boundary. Metadata is rechecked after reading. Lists restart the native directory cursor under the broker lock and filter forbidden entries. Arbitrary host filesystem filters still require full-stack OS enforcement.
- New writes create an exclusive temporary file through the parent handle, write/flush it, then rename it through that same parent with replacement disabled. Publication failures mark the owned temporary file for deletion before closing. Existing destinations are preserved, including files created during publication.
- The broker implements the existing controller contract: empty initial grants, revision changes, revocation, and user-reviewed new-copy approval. No model approval, permission, shell, or network tool is added.

The implementation uses standard-library `ctypes` and loads `kernel32`/`ntdll` only on native 64-bit Windows. It deliberately supports a narrow filesystem configuration. Native directory/file operations are serialized. Unsupported native operations fail; there is no path-based fallback.

## Running native synthetic validation

Use the unit's permitted software-execution process and an approved 64-bit Windows Python 3.11+ runtime. From a reviewed source checkout, with no CUI involved:

```powershell
python .\scripts\validate_windows_folders.py
```

This needs no model, agent/UI dependencies, administrator installation, Internet connection, or script-policy changes. It creates synthetic folders/files under the local temporary directory, including hard links, a junction created through `DeviceIoControl`, and a symbolic-link fixture. It neither reads operational documents nor changes firewall/WSL settings. Directory handles are closed before temporary cleanup. Symbolic-link creation may require the unit's already-approved elevation or developer-mode configuration; do not change policy to make a test pass.

The runner emits a metadata-only JSON summary to stdout and unittest diagnostics to stderr. A non-Windows host, any test failure/error, no executed tests, or any skipped fixture produces a nonzero exit. Skipping a privilege-dependent fixture does not establish acceptance. `deployment_ready` is always false, even when these folder tests pass.

The native fixtures cover reads/listings, reviewed writes, read-only rejection, original-file preservation, hard links, symbolic links, junctions, nested paths/streams/devices, source changes, revocation, destination races, case/ancestor overlaps, and a grant-directory rename attempt. Additional native evidence is still needed for short-name aliases where enabled, mounted/cross-volume directories, mapped network drives, file growth/mapped writers, sharing conflicts, cleanup failures, OS upgrades, and hostile same-user filesystem changes.

This remains a trusted application broker, not a process sandbox. Windows target folder tests alone cannot establish GPU fit, model quality, full-stack network isolation, host connectivity, authorized CUI handling, or installer readiness.

## API references

- [NtCreateFile and handle-relative opens](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntcreatefile)
- [OBJECT_ATTRIBUTES](https://learn.microsoft.com/en-us/windows/win32/api/ntdef/ns-ntdef-_object_attributes)
- [FILE_RENAME_INFO and no-replace publication](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info)
- [ReOpenFile](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-reopenfile)
- [Volume information by handle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getvolumeinformationbyhandlew)
- [Reparse point operations](https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-point-operations)
- [File attribute constants](https://learn.microsoft.com/en-us/windows/win32/fileio/file-attribute-constants)
- [DeviceIoControl](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-deviceiocontrol) and [reparse data structure](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_reparse_data_buffer)
