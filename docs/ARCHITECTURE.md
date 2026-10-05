# First-version architecture and decisions

## Accepted requirements, 2026-10-05

The user accepted a local PDF/Word document assistant for search, comparison, and drafting with citations. Folder access starts empty. Users explicitly grant folders read-only or editable access. Document writes are confined to editable folders. Administrator installation, Windows feature changes, and reboots are permitted. The target is a unit Windows workstation; the developer currently has macOS only. Generated-code execution is deferred.

GenAI.mil integration is an aspiration, not an existing affiliation or interface requirement.

## Folder authority

Only the trusted host interface can select folders, assign access, change permissions, and revoke access. Drag/drop will be implemented in a native folder-selection interface; a web file-upload control is not equivalent to granting a directory.

The model receives opaque folder IDs, display names, access modes, and relative paths. It has no permission-management tool, absolute-path file tool, shell, executable launch, or HTTP tool. Files, retrieved passages, and generated answers are untrusted data and cannot change authority.

Overlapping grants are rejected rather than resolving conflicts between an editable ancestor and a read-only descendant. Whole-filesystem grants, traversal, symbolic links, alternate streams, and unsupported path forms are denied. Model-created files are bounded in size. Existing files are preserved; a subsequent host-reviewed editing workflow must include a displayed diff and detect source changes.

Revocation prevents subsequent tool access and must invalidate the retrieval index and cached source passages for that grant. It cannot erase content already seen in the active conversation; the final UI must explain this and offer to clear that conversation. The development broker currently has no retrieval index or conversation cache. Grants are in memory and start empty after restart.

Application-owned configuration and indexes are separate from model document tools. Their approved storage location and retention must be explicit in the deployment design. No operational content belongs in the source checkout or diagnostics uploaded to GitHub.

## Implemented development component

`src/local_ai_appliance/folders.py` provides a POSIX development adapter with directory-descriptor-relative operations. Read operations validate file type, link count, device, and size before reading. New documents are published without replacing existing destinations. The limited model tool facade exposes folder metadata, UTF-8 reads, and UTF-8 document creation.

This adapter is not a process sandbox. It assumes the trusted broker is uncompromised and that the model can only invoke registered tool schemas, not inspect or execute Python. The local tests cover specified filesystem attacks, not every hostile same-user filesystem mutation or operating-system escape. It is not the production Windows access-control implementation.

The Windows adapter currently fails closed. A Windows implementation must validate directory/file handles and reject reparse points, junctions, network shares, alternate data streams, device paths, hard links, and path substitution. The target tests must verify those behaviors with native Windows fixtures. Pure path-prefix checks are insufficient.

## Candidate runtime architecture

The planned local interface and host-owned folder broker mediate all document access. Only allowed document bytes and structured requests are passed to the AI worker. The AI worker has no host drive mounts or document filesystem permissions. Inference, parsing/OCR, embeddings, and workflow tools run locally; all required assets are included in the bundle.

WSL2 is a GPU-runtime candidate, not a security sandbox. Two possible transports need on-target evaluation:

- Disconnected WSL networking and a narrowly defined host/worker IPC protocol.
- Filtered WSL networking with explicit local transport and enforced denial of all external traffic.

Neither design is selected or validated yet. Do not assume Windows localhost forwarding works when WSL networking is disabled. Preserve existing WSL workloads and configuration: `.wslconfig` and common WSL firewall settings can affect more than one distribution. Do not silently overwrite configuration or run a global shutdown.

The complete communication path, including DNS tunneling, Windows interoperation, host proxies, parsers, and rendered output, is in scope for isolation tests. The interface must not load generated remote URLs, images, fonts, scripts, or arbitrary HTML. A trusted Windows host is part of the system boundary. A stronger containment requirement for compromised software or code execution will require revisiting architecture.

## Offline installation

The intended entry point is a PowerShell installer operating on a complete offline bundle. A distributable bundle must contain a signed manifest, verified payloads, pinned model/runtime/dependency identities, licensing/provenance, and a target-supported configuration. No installer may fetch missing assets or declare success after a partial setup.

The installer must distinguish inventory, prerequisite changes, payload installation, reboot/resume, isolation verification, functional verification, and readiness. It must preserve unrelated settings, be idempotent, and support rollback of its own changes. Signing and trust anchors must be established before distributing installation software.

No installation entry point is shipped yet. `installer/Test-Target.ps1` is an inspection-only prerequisite inventory and cannot grant readiness.

## Source references

- [Microsoft WSL configuration](https://learn.microsoft.com/en-us/windows/wsl/wsl-config): networking, Windows interoperation, mounts, and global configuration scope.
- [Microsoft WSL security model](https://github.com/microsoft/WSL/blob/master/doc/docs/technical-documentation/security.md): WSL is not a security sandbox.
- [Hyper-V Firewall](https://learn.microsoft.com/en-us/windows/security/operating-system-security/network-security/windows-firewall/hyper-v-firewall): WSL traffic filtering.
- [WSL commands](https://learn.microsoft.com/en-us/windows/wsl/basic-commands): runtime management and import/export.
