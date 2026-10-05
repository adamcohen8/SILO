# Target validation

## Current evidence

The development folder broker passes 21 tests on macOS/Python 3.14. These cover default-deny access, read-only enforcement, editable document creation, revoked grants, overlapping grants, traversal, symlinks, hard links, special files, size limits, destination races, and an opened-parent substitution scenario. A test verifies deliberate refusal to run the adapter on Windows.

No Windows, PowerShell execution, CUDA, model-quality, document-ingestion, UI, or network-isolation validation has been performed. The project does not yet supply an installable AI system.

## Read-only target inventory

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
| Folder UI | No initial grants; explicit selection/drop and revocation | Not implemented |
| Native Windows folder adapter | Reparse/junction/ADS/network/device/traversal rejection and editable-only writes | Not implemented |
| Existing-file editing | User-reviewed diff; source-change handling; editable-only apply | Not implemented |
| GPU runtime | Exact quantization fits with the document workload and bounded concurrency | Not implemented |
| Host transport | Only defined requests/responses cross the boundary; no arbitrary commands | Not implemented |
| Network isolation | External DNS, IPv4/IPv6, TCP/UDP, proxies, interoperation, and UI requests denied | Not implemented |
| Host connectivity | Authorized ordinary Windows connectivity remains usable | Pending target testing |
| Persistence | Reboot/resume and network/VPN changes do not relax isolation | Not implemented |
| Document workflow | Local PDF/Word ingestion, retrieval, source/page citations, and safe drafting | Not implemented |
| Supply chain | Signed payload/manifests; missing or altered assets rejected; offline operation | Not implemented |
| Installer | Fresh installation, repair, reboot/resume, rollback, and accurate readiness | Not implemented |

All functional acceptance uses public or synthetic documents first. Real CUI use depends on the unit's authorized system configuration and handling process.
