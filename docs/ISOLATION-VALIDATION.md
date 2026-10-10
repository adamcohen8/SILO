# Network isolation design and acceptance plan

This is the complete acceptance plan. The [6 October native evaluation](WINDOWS-AGENT-ISOLATION-2026-10-06.md) now implements AppContainer jobs and private pipe/socket transport, with a passing synthetic graph/parser/GPU workflow and partial network coverage. Full matrix acceptance remains false. The portable test kit itself does not apply a boundary or probe. A successful folder or staging test cannot satisfy this plan. Use approved test responders and synthetic markers only; the user approved GitHub and PyPI for this workstation's connection checks.

## Boundary to implement

The trusted Windows interface owns folder grants and reviewed saves. Worker processes receive bounded document bytes and structured requests only. They receive no host document paths, drive mounts, permission-management API, arbitrary host command relay, browser, shell, or executable launcher. The model, workflow dependencies, parser/OCR, embedding engine, and inference runtime are all within the communication restriction; blocking the inference executable alone is insufficient.

The preferred first evaluation is native Windows GPU inference under a restricted worker identity/process configuration. The pinned CUDA runtime, model, graph and parsers have now run with verified zero-capability AppContainer tokens and owned jobs. External IPv4 TCP denial and controlled IPv4/IPv6 loopback observations passed; broader effective isolation remains unqualified. A Windows firewall rule alone is not an accepted substitute for testing local relays, child processes, and the complete communication path. Separate the narrowly defined host/worker IPC from general network access. Validate bounded lengths/types, peer identity/ACLs, timeouts, session ownership, and denial of all unregistered requests. Do not expose arbitrary named-pipe or host RPC endpoints to workers.

If this boundary cannot support the GPU/runtime, evaluate a dedicated WSL configuration separately. WSL is not a security sandbox. Disconnected networking still needs a proven transport; filtered networking still needs enforced external denial. Inventory existing workloads first. Never overwrite global `.wslconfig`, change unrelated WSL firewall settings, or shut down unrelated distributions. Microsoft documents [global/per-distribution settings](https://learn.microsoft.com/en-us/windows/wsl/wsl-config), [Hyper-V firewall](https://learn.microsoft.com/en-us/windows/security/operating-system-security/network-security/windows-firewall/hyper-v-firewall), and the [WSL security boundary](https://github.com/microsoft/WSL/blob/master/doc/docs/technical-documentation/security.md).

No final architecture is selected by this plan. A startup supervisor must refuse worker launch when required policy/asset/IPC checks are missing, changed, or unverifiable. Revalidation after restart/resume and network/VPN changes is required. Containment of arbitrary generated code remains outside this iteration; parser compromise is a distinct risk requiring a real process boundary, not just Python timeouts.

## Evidence method

Bind each run to test-kit/profile/runtime/model hashes, boundary revision, OS build, driver version, and a non-identifying random run ID. Record test ID, expected behavior, pass/fail/not-run, and a brief metadata-only observation. Do not record document text, prompts, addresses identifying the unit, host/user names, proxy credentials, packet payloads, or operational logs in GitHub. Keep detailed local evidence inside authorized storage.

For network tests, first establish the approved responder is reachable from the connected host. Then exercise the worker at OS level and inspect effective policy/block counters and responder observations. A timeout alone is not proof of containment. No supported route/protocol may be marked passed because a library was missing or the responder was down. Unavailable IPv6 or another untested vector remains not-run with an explicit coverage limitation.

| ID | Exercise | Required observation |
|---|---|---|
| N01 | External TCP with literal IPv4 and IPv6, including HTTPS | Worker cannot establish transport; host control succeeds; effective enforcement observed |
| N02 | External UDP, including DNS/QUIC-style datagrams | No worker traffic reaches approved responder; denial is attributable to policy |
| N03 | OS DNS, DNS tunneling, direct DNS, proxy/environment settings | No name resolution or proxy relay permits worker egress; no credentials exposed |
| N04 | Host/LAN/loopback listeners and relays, IPC endpoints | Only the defined authenticated protocol is reachable; no generic forwarding path |
| N05 | Every AI process/dependency and attempted child launch | Same restriction covers runtime, orchestration, parsing and descendants; unauthorized launch denied |
| N06 | Embedded URLs/images/links/fonts and document instructions | Rendered output makes no fetch; sources never authorize commands or network tools |
| N07 | Windows interoperation, drive mounts, WSL host services if used | No indirect host command/network path; unrelated host workloads remain usable |
| N08 | Worker restart, reboot, sleep/resume, VPN/network changes | Enforcement remains effective; unverifiable state prevents startup |
| N09 | Remove/change an owned enforcement rule or asset | Supervisor detects drift and refuses work; no permissive fallback |
| H01 | Ordinary permitted host browser/network use before/during/after inference | Host connectivity retained without disabling the workstation network adapter |
| I01 | Corrupt/oversized/unknown/replayed host-worker requests | Denied without additional authority, arbitrary reads, writes, or process launch |
| I02 | Parser exhaustion/malformed files and IPC timeout/crash | Bounded resources and cleanup; no partial approved write or network relaxation |

Run the matrix before GPU/document integration, again with the entire stack generating answers, and after reboot/resume. Isolation must pass alongside source/page citations, no initial grants, editable-only reviewed writes, and real GPU measurements. These observations support the tested configuration only; they do not establish organizational authorization to handle CUI.
