# Windows real-agent and isolation evaluation, 6 October 2026

The real Nemotron document workflow passed **15 synthetic checks** with the GPU
runtime, LangGraph worker and PDF/DOCX parsers in separate native AppContainer
jobs. The target regression run passed **68 of 70 tests**; the two skips are
POSIX-only fixtures. All six native private-pipe attack tests and all seven
contained parser fixture tests passed. This establishes a development result
on this workstation, not full isolation acceptance or deployment readiness.

## Dependencies and model settings

The project-local evaluation environment uses the existing native CPython
3.12.14 runtime. Forty Windows-compatible wheels were downloaded, matched to
exact-version PyPI filename/size/SHA-256 metadata, license-file inventoried, and
installed offline with `--no-index --no-deps --require-hashes`. `pip check`
passes. See [wheel provenance](../profiles/windows-python312-wheels.json) and
[offline evaluation requirements](../requirements/windows-evaluation-offline.txt).
This lock excludes a redistributable interpreter, UI and complete signed
installer qualification.

The model and all 55 runtime files were reverified against the existing asset
inventory before launching. The pinned b11433 CUDA build loaded **53/53 model
layers** on the RTX 4090. The contained server became ready in **6.078 seconds**
with cached local files. Total GPU memory sampled after the workload was
**18,459 MiB** out of 24,564 MiB; this is a sample, not a continuously measured
peak. Text/PDF/DOCX requests took 6.250/6.188/5.265 seconds, including fresh
worker startup, parsing when required and two model calls each.

The passing agent settings use 8,192 context tokens, one inference slot,
2,048 generated tokens per call, reasoning enabled with a 512-token budget,
temperature 0.6 and top-p 0.95. The earlier reasoning-disabled GPU baseline
remains historical evidence: its short performance result does not describe
this document workload. Initial reasoning-disabled agent attempts produced
incorrect or incomplete facts; bounded reasoning resolved this small fixture
set. Broader model quality remains unmeasured.

## Functional checks

| Check | Observed result |
|---|---|
| No initial folder grants | Worker asks for access; no source returned |
| Host authority and child launch | Approval RPC, shell tool and ungranted read denied; child creation rejected with Windows error 367 |
| External IPv4 TCP | Worker connections to approved GitHub/PyPI literals denied with Windows error 10013 before and after a graph request |
| Text answer | 37 crates; verified `[source:S1:line:2]` |
| PDF answer | 15 October; verified `[source:S1:page:2]` |
| DOCX answer | 23 November; verified `[source:S1:paragraph:2]` |
| Draft review | Pending new copy retains the complete original source reference/hash; no file exists before host approval |
| Approved bytes | Trusted synthetic host approval saves exactly the stored proposal bytes |
| Original preserved | Read-only source bytes remain unchanged |
| Stale source | Changed source causes approval denial; no stale draft saved |
| Revocation | Fresh worker request sees no revoked folder grants or old citations |
| Tracing | No LangSmith tracing enabled in the worker |
| Loopback | No traffic reaches controlled IPv4/IPv6 TCP/UDP listeners after successful host controls |
| GPU placement | All 53 layers on the GPU during real document generation |
| Host connectivity | HTTPS to GitHub and PyPI succeeds before, during and after evaluation |

The host now supplies fresh grant metadata on every request. Document excerpts
report total units and whether more remain; each PDF page/DOCX paragraph carries
its own citation token. Citation locators are checked against actual units read
and rendered from trusted source metadata. This validates provenance and range,
not the truth of every model claim. Draft wording can change additional source
content; the stored diff remains the host's review surface.

## Actual process and communication boundary

Each process is created suspended with a unique profile's AppContainer SID,
**zero capabilities** and low integrity. Its actual token and absence from the
effective loopback exemption list are checked before resuming. Each owned job
allows one process, denies child creation, limits process memory and kills its
process on close. Graph/parser jobs have a 512-MiB ceiling; the model job has a
32-GiB process-memory ceiling. These ceilings do not measure or limit GPU VRAM.

The launcher uses detached processes with three explicitly inherited private
pipe ends. `CREATE_NO_WINDOW` initially caused `0xC0000142` during console
initialization, including for system curl; detached startup resolved it. No
console registry setting was changed. A private low-integrity desktop is owned
and closed by the evaluation; interactive UI isolation is not qualified.

The server listens only on a private **Windows AF_UNIX socket**, with an explicit
ephemeral API token. The socket directory is created with a protected DACL for
the current user, SYSTEM and the unique profile SID, and a low-integrity label.
No TCP listener or loopback exemption is added. A small Winsock connector handles
the local address because this Python build lacks AF_UNIX address conversion.
The chat adapter keeps its request/response deadlines and size limits, strict
JSON/tool parsing, no retries/redirects and disabled prompt caching.

The graph runs in a separate AppContainer process. Its private framed pipe
protocol carries only registered document tools, pending proposal IDs and
session-scoped discard requests. Frames have a fresh session ID, sequential
numbers, size/call limits and a deadline. The host does not import/execute
LangGraph to dispatch tools. It owns the native folder broker, checks authority,
and revalidates the returned answer's citations against its own read records.
Approval and permission changes are absent from the worker protocol.

Parsers run as separate contained jobs. They receive bounded document bytes,
not host document paths, and return bounded validated text/locators. The shared
hostile fixtures reject external relationships, XML entities, archive escapes,
macros, expanded/extracted-size excess, unsupported/oversized input, image-only
and encrypted PDFs. Private IPC tests reject a wrong session, replayed sequence,
oversized frame and unknown frame kind before unauthorized dispatch, and verify
timeout termination followed by successful fresh-worker recovery.

Software directories and the selected model file receive temporary read/execute
or read-only leases for the unique profile SID. Document directories receive no
AppContainer ACL grant. All worker jobs, the profile, temporary software ACLs,
synthetic document fixtures and private socket/token directory were cleaned up.
The ordinary application still refuses production Windows folder/parser use.

A subsequent metadata check found zero remaining evaluation profiles or model
servers and zero matching test-profile ACEs across 59 model/runtime/software
objects. GPU memory returned to 683 MiB after shutdown. The exact synthetic
fixture left by the first failed ordinary-user run was also removed after
checking its resolved path and known fixture children.

## Isolation observations and remaining gates

GitHub/PyPI host controls returned HTTPS 200 and succeeded on literal IPv4 TCP.
The contained Python probe received `WSAEACCES` 10013 for both external TCP
connections. DNS resolution failed with 11001; this alone is not complete DNS
policy evidence. Attempts to read an ungranted synthetic file or write staged
software were rejected. LangGraph/LangSmith/pypdf/defusedxml imports and contained
CUDA enumeration succeeded.

Loopback TCP timed out. UDP send APIs accepted the synthetic datagram, but none
arrived at the controlled receivers. The receivers first received host controls,
and the effective exemption list contained no evaluation-profile SID. API
success is therefore reported separately from delivery. Windows documents
[WFP capability enforcement and default loopback restrictions](https://learn.microsoft.com/en-us/windows/security/operating-system-security/network-security/windows-firewall/troubleshooting-uwp-firewall)
and the [read-only exemption query](https://learn.microsoft.com/en-us/windows/win32/api/netfw/nf-netfw-networkisolationgetappcontainerconfig).

Full acceptance still requires external IPv6 and UDP responders, WFP block-event
or counter evidence, direct DNS/proxy/LAN/generic IPC relay coverage, peer/asset
drift qualification, parser resource-exhaustion stress, reboot/resume and
network/VPN-change startup gates. Windows UI, the remaining native symlink
fixture, signing/trust, licensing for redistribution and fresh-install/repair/
rollback qualification are also pending. No global firewall/WSL policy or
unrelated host workload was changed.

## Local evidence and reruns

Detailed synthetic answers, diffs and diagnostics remain in ignored `artifacts/`:

- `windows-evaluation/real-agent-results.json`: ordinary-user development run;
  ten checks passed, with OS containment explicitly false.
- `isolation-evaluation/appcontainer-results.json`: controlled probes and token/
  policy evidence, with full acceptance false.
- `isolation-evaluation/contained-server-results.json`: contained GPU answer and
  53/53 layer evidence over the private socket.
- `isolation-evaluation/contained-agent-results.json`: 15 passing checks, actual
  graph/parser/server token evidence, source hashes and retained host controls.
- `windows-evaluation/windows-regressions.json`: 68 passes, two POSIX skips,
  zero failures/errors, bound to tested source and fixture hashes.

The initial failed diagnostics are historical local files, not successful-run
evidence. No operational documents were used. The original asset inventory
continues to bind the exact model and runtime; these development source hashes
are not a signature or independent authentication of the downloaded archive.

From an authorized native session with the local evaluation environment prepared:

```powershell
& .\artifacts\windows-evaluation\venv\Scripts\python.exe -I -B scripts\validate_contained_agent.py
& .\artifacts\windows-evaluation\venv\Scripts\python.exe -I -B scripts\validate_windows_regressions.py
```

These runners are explicit synthetic evaluation tools, not an installer or a
production launch path. The complete [isolation matrix](ISOLATION-VALIDATION.md)
and [target acceptance gates](TARGET-VALIDATION.md) remain authoritative.
