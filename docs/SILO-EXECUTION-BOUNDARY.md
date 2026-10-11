# SILO generated-code execution boundary

10 October 2026 — Phase 1 design with Phase 2 candidate implementation; native acceptance pending

The runner candidate uses a verified offline Python toolchain in a disposable Windows workspace. This design is an acceptance gate, not evidence of containment. The [Phase 2 implementation](SILO-PHASE-2.md) supplies an LPAC/fixed-NTFS-VHD candidate and code tools. Code requests remain unavailable without complete independently reviewed native evidence; `DisabledExecutionService` remains the default. The document graph/parser/inference workers keep their existing child-process denial.

## Assets, threats, and authority

Protect original reference files, installed toolchains/model assets, other user files, credentials, host connectivity, and reviewed output destinations. Treat model replies, generated Python, source documents, CSV cells, filenames, proposed output files, and parser output as hostile. Assume generated code deliberately tries to read outside its workspace, modify references, open network transports, create children, exhaust disk/memory/output, or forge approval. Host/supervisor compromise and local administrators modifying the OS are outside this candidate boundary; they still matter to organizational deployment.

The model asks for a registered operation. The trusted host validates policy and inputs, launches and owns the process, captures bounded output, and decides what can be presented for review. The harness cannot modify authority. No arbitrary executable, shell string, PowerShell, batch file, `pip`, installer hook, or downloaded dependency is available to the model. Python's ability to call Win32 APIs means a language-level restriction cannot serve as the security boundary.

## Host services and data flow

1. The user requests a Code workspace through a host interface and reviews its purpose, selected configuration, budgets, inputs, and export destinations. Reference/Draft grants never acquire Code authority implicitly. The approved policy belongs to this session and expires on close/cancel.
2. The host creates a private run identity and staging area outside user reference/destination trees. It reads explicitly selected input files through the existing broker, records locators/hash/permission revision, copies exact verified bytes, and rechecks the copied versions. No original reference path or broker handle is passed to generated code.
3. Generated script/tests are proposed as bounded ordinary UTF-8 files inside this disposable workspace. Host tools validate paths, sizes, file inventory, links, and policy before a run. The agent may revise its own workspace files within the approved policy. Installed runtime/input files stay immutable.
4. The host chooses the pinned executable and fixed isolated-mode flags (`-I`, `-S`, unbuffered output as needed). Reviewed bootstrap code explicitly supplies the immutable offline library path. User/global site packages, startup hooks, `PYTHONPATH`, credential/proxy/tracing variables, and ambient working-directory imports cannot select a different runtime. No shell expansion occurs. Arguments are a structured bounded list of workspace-relative names.
5. The supervisor starts Python suspended, verifies the token/job/ACL/network settings, then resumes. Its child receives only selected private pipe ends and the minimum OS/runtime access. Any failed verification aborts; there is no uncontained fallback.
6. The supervisor records bounded stdout/stderr, exit status, timeout/cancel/resource events, input/configuration hashes, and a verified output inventory. Text output is displayed with terminal control escaping. A successful exit alone is not task or isolation acceptance.
7. The host validates outputs and presents a reviewable artifact set. Publication into a Draft grant requires separate user approval bound to exact bytes, input hashes, permission revision, and destination. Changed files, stale sources, collisions, revoked grants, and replay fail. Runner files cannot self-publish or approve.

## Candidate native enforcement

Use a **separate zero-capability AppContainer per owned runner**, created by the trusted host, with low integrity, no loopback exemption, a verified unique SID, a scrubbed environment, and an explicit handle inheritance list. Reuse reviewed native launch/token checks where they apply, without changing the inference/document workers to allow descendants. A Windows Job Object enforces kill-on-close, process-memory and active-process limits; disallow child creation as well. Initially one Python process runs one entrypoint; tests run in a subsequent owned invocation. No subprocess-based test runner or multiprocessing is supported.

Use a private NTFS area with explicit ACLs: runner read/execute on immutable runtime/library files; read-only on staged inputs; write only on its disposable working/output area. Keep host files and Draft destinations outside it. Reject reparse points, symlinks, hard links, alternate data streams, device/UNC names, and path escapes before staging or exporting. ACL/identity validation must hold under rename and replacement attempts. An AppContainer can still read some Windows system resources and has its own profile storage; qualification must enumerate those exceptions and prevent them from exposing user/project data.

Network denial must come from Windows enforcement for the token across TCP/UDP, IPv4/IPv6, DNS, loopback, LAN, Wi-Fi/Ethernet/VPN, and reachable responder paths. Python transport checks are supplementary. IPC probes must test named pipes, inherited handles, shared objects, COM/RPC, and a host relay. Only the private bounded result channel is allowed; it cannot relay arbitrary bytes to a network destination or invoke host commands. Do not alter machine-wide firewall settings or disconnect host Wi-Fi as the implementation.

Resource defaults are a 60 s wall-clock deadline, 512 MiB process memory, 64 KiB combined captured output, one active process, and 16 MiB logical working/output budget. Policy validation permits narrower/defined larger limits, but only implemented enforceable combinations may be enabled. Job Objects do not enforce a directory disk quota. **Disk containment is an unresolved native implementation gate:** use a capacity-limited private volume/container or another proven hard quota, accounting for metadata, profile/temp/cache storage, and all runner-writable locations. A periodically polled directory size is insufficient because writes can exhaust host disk before detection. If a hard storage bound cannot be demonstrated, keep the runner disabled or select a stronger native boundary. Do not silently reinterpret the policy limit as a soft watchdog.

Likewise, an AppContainer/ACL prototype that leaves an unintended user-data or relay path reachable is a failed boundary. A VM-based runner is a permissible later choice if these controls cannot meet the accepted access policy. No weaker fallback may be selected at launch time.

## Ownership, cancellation, and cleanup

The host owns run IDs, AppContainer profiles, job/process/pipe handles, storage, and any temporary ACL leases. Record a local lease/cleanup receipt without sensitive document content. Cancellation, wall-clock expiry, output overrun, invalid result frames, or UI exit terminate the job, wait for every owned process to exit, close pipes, and invalidate export approval. Unknown outcomes never trigger automatic retry/publication.

On successful exit, the host must obtain an immutable verified snapshot or deny further runner access before artifact review. A later invocation cannot retain write access to a reviewed output snapshot. Hashing a still-writable output path is insufficient approval binding. The host validates exact bytes copied into private publish staging and uses the broker's new-file/collision checks to save approved copies.

Remove temporary access/profile/storage only after owned work is gone. Verify the exact owned identities before cleanup; never delete arbitrary folders named by the model. Retain only user-approved outputs or explicit diagnostic receipts under local retention policy. On crash/reboot, reconcile abandoned leases before new work; stale output/proposals are not automatically trusted or resumed. Failed cleanup blocks reuse and reports the affected owned resources. Test profile deletion and disk detach recovery as well as normal cleanup.

## Acceptance matrix for Phase 2

Each result must record configuration, policy, host positive control, observed denial/enforcement, and cleanup. A skipped/unreachable test is pending, not a denial pass.

| ID | Required test and observation |
| --- | --- |
| RUN-01 | Suspended token has expected SID, low integrity, zero capabilities, no loopback exemption; wrong SID/token/job aborts before any generated instruction runs |
| FS-01 | Normal staged input read/output write succeeds; original Reference and runtime writes fail; unrelated user/credential/destination reads and writes fail |
| FS-02 | Traversal, absolute/UNC/device paths, junction/reparse/symlink/hard-link/ADS escapes, and rename/replacement races cannot stage, read, overwrite, or publish outside the accepted surface |
| NET-01 | Host controls reach approved external/LAN TCP and UDP responders over IPv4/IPv6; runner attempts are denied with enforcement evidence |
| NET-02 | DNS, loopback, VPN/interface changes, named pipes, COM/RPC/shared objects and host-relay attempts cannot obtain an unauthorized path; host connectivity remains usable |
| RES-01 | Child creation, memory exhaustion, timeout, infinite output, and disk/temp/profile growth hit verified hard limits and terminate owned work without host exhaustion |
| AUTH-01 | Model/source attempts to grant, change policy, replace executable, run a shell, install dependencies, or self-approve are refused by host dispatch |
| DATA-01 | Selected input identities/hashes survive staging; originals are unchanged; unknown/missing dependency fails offline without acquisition |
| REVIEW-01 | No Draft write before review; changed outputs, stale inputs, permission revocation, collisions, cross-session IDs, and replay fail; reviewed exact-byte export succeeds |
| LIFE-01 | Cancel during execution/export, UI crash, sleep/resume, reboot, and launch failure terminate/reconcile owned resources; fresh session succeeds only after verified cleanup |
| TASK-01 | Actual local model writes/runs/repairs Python/tests; normal fixture is exactly 108 kg; independent malformed/negative fixtures fail explicitly; chart/report content is inspected |

Retain synthetic evidence without exporting operational prompts/documents. Passing this matrix qualifies only the named development configuration and supported surface. The broader [isolation plan](ISOLATION-VALIDATION.md), installation acceptance, supply-chain review, and organizational authorization are separate requirements before CUI use.
