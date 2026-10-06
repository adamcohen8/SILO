# Target validation

## Current evidence

The development folder broker passes 21 tests on macOS/Python 3.14. These cover default-deny access, read-only enforcement, editable document creation, revoked grants, overlapping grants, traversal, symlinks, hard links, special files, size limits, destination races, and an opened-parent substitution scenario. A test verifies deliberate refusal to run the adapter on Windows.

The complete 50-test suite passes on macOS/Python 3.14 with PySide6 Essentials/shiboken6 6.10.2. Additional controller and native UI tests cover folder selection/drop, bounded listings, review-before-write, stale-source rejection, revocation, one-use approvals, concurrent destination creation, plain-text markup display, and review invalidation. Populated and empty native screens were rendered offscreen from synthetic data and visually inspected. Local Qt platform plugins were materialized outside the cloud-synced checkout for this run. See the desktop preview documentation for running the full suite with optional UI dependencies.

The project does not yet supply an installable AI system. Native Windows, CUDA, real-model quality, and network-isolation validation remain pending. Historical milestone evidence is followed by the latest preparation results below.

The expanded 87-test suite passes without skips on macOS/Python 3.14 with LangGraph 1.2.13, LangSmith 0.14.4, and the existing UI dependencies. The agent development tests exercise a real LangGraph graph with scripted model replies, plus an end-to-end synthetic loopback HTTP fixture through the chat adapter, graph, folder broker, pending proposal, and trusted approval. They cover unknown/authority tools, injected document instructions, type/extra-field rejection, path escapes, replayed call IDs, call/context budgets, permission changes, source provenance, failed-run proposal cleanup, fresh request state, and terminal review/control-character handling. Transport tests cover remote/ambiguous endpoint rejection, DNS/proxy/credential avoidance, redirects/errors without retry, size limits, timeouts including slow header reception, short bodies, malformed/duplicate JSON, and incomplete completions. Tracing is checked with enabled environment settings and an enabled outer context while unexpected socket connections raise errors. The editable package and installed agent command were verified with a startup/quit session; dependency consistency, Python compilation, and diff whitespace checks pass. See [agent development](AGENT-DEVELOPMENT.md) for setup and limitations.

The Windows/bundle milestone adds 17 portable native-contract/ABI tests, 13 manifest/payload tests, and 11 native Windows fixtures. On macOS/Python 3.14, 108 tests pass and 20 are explicitly skipped: 11 native Windows fixtures and nine unchanged UI tests whose optional environment is unavailable after disk-exhaustion cleanup. Native tests are not certified by the portable API fixture. The native validation runner rejects a non-Windows host with exit 2 and false acceptance/readiness, and must reject skipped/failing fixtures when run on Windows. No native Windows API execution or target qualification has occurred. See [Windows candidate](WINDOWS-FOLDERS.md) and [bundle prototype](OFFLINE-BUNDLE.md).

## Read-only target inventory

For 6 October, prefer the [portable kit instructions](WINDOWS-TEST-KIT.md) and [session checklist](TARGET-SESSION-CHECKLIST.md). The kit can run inventory plus native synthetic fixtures without GitHub access or agent/UI dependencies.

Using the unit's permitted software-execution process, run this script on the target Windows machine. An elevated PowerShell session can read optional-feature state; without elevation some values may be unknown.

```powershell
.\installer\Test-Target.ps1
```

The script prints JSON to stdout. It queries OS/RAM, administrative elevation, Windows feature state, installed WSL availability, existing distribution count, configuration-file presence, firewall-command availability, and GPU/driver information. It avoids document reads, host/user identifiers, network probes, installation, policy changes, and creation of an output file. It deliberately does not execute an uninstalled WSL launcher. Some MSI/inbox WSL configurations will therefore be reported as unknown and need a later focused check.

The script has not been executed or parsed by PowerShell on a Windows host. Review it before on-target execution; do not bypass the unit's script-execution policy. Only share permitted hardware/software inventory, never CUI, source documents, prompts, or sensitive logs.

## Required acceptance evidence

| Area | Required observation | Status |
|---|---|---|
| Prerequisites | Target OS, GPU, driver, virtualization, installation constraints | Pending target inventory |
| Folder UI | No initial grants; explicit selection/drop and revocation | macOS development prototype; Windows pending |
| Native Windows folder adapter | Reparse/junction/ADS/network/device/traversal rejection and editable-only writes | Explicit validation candidate implemented; native target evidence pending |
| Existing-file editing | User-reviewed diff; source-change handling; editable-only apply | Reviewed new-copy workflow implemented; in-place replacement pending |
| GPU runtime | Exact quantization fits with the document workload and bounded concurrency | Not implemented |
| Host transport | Only defined requests/responses cross the boundary; no arbitrary commands | Not implemented |
| Network isolation | External DNS, IPv4/IPv6, TCP/UDP, proxies, interoperation, and UI requests denied | Not implemented |
| Host connectivity | Authorized ordinary Windows connectivity remains usable | Pending target testing |
| Persistence | Reboot/resume and network/VPN changes do not relax isolation | Not implemented |
| Agent orchestration | Local model, bounded tool dispatch, default-deny access, host review | LangGraph/protocol fixture tested on macOS; real model pending |
| Document workflow | Local PDF/Word ingestion, retrieval, source/page citations, and safe drafting | Bounded UTF-8/PDF/DOCX development path with line/page/paragraph locators and reviewed text copies; containment, fidelity, OCR/retrieval pending |
| Supply chain | Signed payload/manifests; missing or altered assets rejected; offline operation | POSIX integrity/staging tested; native Windows payload/ACL candidates; signatures/trust and full asset lock pending |
| Installer | Fresh installation, repair, reboot/resume, rollback, and accurate readiness | Development plan/private-stage/checkpoint/reboot-gate/rollback framework tested on POSIX; Windows wrapper/native execution and production activation pending |

All functional acceptance uses public or synthetic documents first. Real CUI use depends on the unit's authorized system configuration and handling process.

## Windows-session preparation evidence

On macOS/Python 3.14, the final 160-test suite completes with **134 passes and 26 skips**: 11 native folder fixtures, six native ACL/staging fixtures, and nine unchanged optional UI fixtures. New passing evidence covers PDF page provenance, DOCX paragraph extraction/host review/stale sources, hostile archive/XML inputs, parser deadlines, private staging/idempotence, changed/unowned-content rollback refusal, boot checkpoint gating, source corruption/no-space/lock rejection, and deterministic kit manifests/archives. These are development fixtures, not real GPU or native Windows evidence.

The two hash-pinned parser wheels were installed into a fresh environment using `--no-index --no-deps --require-hashes`; all nine portable parser fixtures then passed. Four PowerShell scripts parsed with Microsoft's portable PowerShell 7.6.6 on macOS. The kit verifier accepted a complete synthetic source kit and rejected a changed file, an undeclared empty directory, and a wrong manifest hash. Native Windows filesystem attributes, Windows PowerShell 5.1 execution, ACL creation, sharing/races, and protection between verification/execution remain pending. Both native runners refuse macOS with exit 2 and false readiness. Python compilation, dependency consistency, and diff whitespace checks pass.

The data-only inference profile records pinned upstream/runtime/quantizer revisions and publisher model size/hash metadata. No model weights, Windows CUDA build, or complete dependency bundle was downloaded. GPU fit, tool templates, final license reconciliation, complete isolation implementation, signed trust, and activation remain explicit unresolved gates.
