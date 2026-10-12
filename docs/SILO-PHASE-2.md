# SILO Phase 2 implementation

> These are implementation/validation notes for the original phase and its recorded updates.
> For the 12 October source, shipped-release distinction and qualification status,
> use [current status](SILO-STATUS.md), [long work](SILO-LONG-WORK-AND-CODING.md)
> and [expanded coding workflow](SILO-CODING-WORKFLOW.md). Dated tool counts and
> deferred-feature statements describe that phase snapshot; current interactive
> work has no lifetime call/run quota, while per-operation resource limits remain.

10 October 2026. Source implementation delivered; native Windows acceptance
and the actual local-model milestone remain pending. This source is included
in the 11 October 2026 evaluation installer; publication does not complete
native acceptance or authorize CUI use.

## What is implemented

- A Windows scrolling terminal connected to `WindowsSessionAdapter` and the
  contained inference/document graph. Reference and Draft grants, follow-up
  context, citations, clear, review, approval, discard, and cancellation use the
  shared host services. Terminal control characters from model/document text are
  escaped. The separate terminal design preview remains available.
- An explicit `/code` host action requesting a disposable Code workspace under
  a displayed policy. It requires accepted native evidence and a synthetic
  project. It accepts no user folder path. Changing grants closes the workspace.
- Six bounded code tools: list, read, create/edit by current hash, stage a
  previously read Reference, run one Python entrypoint, and prepare an export.
  There is no shell, arbitrary executable, package installation, network,
  permission management, policy change, or approval tool. Original inputs are
  copied as exact verified bytes and their source identities remain revalidated.
- A separate Windows runner candidate using a less-privileged, zero-capability
  AppContainer (LPAC), verified token, inherited-handle list, child denial and
  job limits. Document/inference workers retain their existing restrictions.
  The candidate attempts to close private profile/registry write paths and puts
  writable code, inputs and temporary files on an owned fixed-size NTFS VHD.
- A separate pinned CPython 3.14.8 toolchain prepared from the existing verified
  interpreter archive. Its `._pth` contains only the standard-library ZIP and
  executable directory; no site import or third-party packages. The contained
  bootstrap supplies the disposable module directory and bundled `silo_plot`
  PNG helper. There are no task-time dependency downloads.
- Host snapshots of exit status, bounded combined stdout/stderr and artifact
  hashes after owned execution stops. Malformed results, cancellation and source
  changes cannot authorize publication. Interactive workspaces have no lifetime run quota. Their inventory is
  limited to 4,096 files and the configured byte capacity, with four pending
  exports. Only the latest 16 run receipts remain in active memory; saved-task
  journals retain each tool result. Export manifests identify omitted older runs.
- Review and atomic publication of one new ZIP containing scripts, tests,
  results, chart, report and a host manifest of inputs, runs, configuration and
  policy. Input copies are excluded. The terminal displays text and a bounded
  chart preview before approval. Existing destinations are never overwritten;
  edits, revocation, collisions, stale reviews and replay are denied.
- An independent frozen-fixture artifact checker and opt-in native probes.
  Scripted LangGraph tests use a clearly labelled simulated runner and execute
  no generated Python on the development Mac.

The VHD's capacity is the disk policy limit, including filesystem metadata.
Usable task space is consequently smaller. Defaults are 60 seconds/run, 512 MiB
process memory, 16 MiB fixed disk, 64 KiB combined output and one process.
Timeout, cancellation and output overrun terminate the owned job. Failed cleanup
leaves receipts and disables reuse; unresolved leases are not silently deleted.

## Execution stays gated

The source checkout contains no accepted native boundary record. `/code` fails
closed unless the host supplies a complete independently reviewed record and
its independently trusted SHA-256. The record binds the installed release,
bootstrap, plotting helper, Windows version, interpreter, boundary version and
exact resource policy. Runtime inventory and support hashes are checked again
before each run. Missing, changed, failed, skipped or pending checks refuse
execution. POSIX execution fallback and environment activation bypasses are absent.

Acceptance requires all 19 checks in `windows_code_runner.BOUNDARY_TESTS`: token,
immutable inputs/runtime, outside filesystem, profile/registry storage, IPv4
TCP/UDP, IPv6, DNS, loopback, IPC, children, memory, output, disk, timeout, cleanup
and recovery. Each must have status `passed` and an independently reviewed
64-character evidence SHA-256. The record's exact schema is enforced by `qualify`;
the supplied digest is the host's trust decision, not a model tool argument.
Do not manufacture a passed record from portable tests or a template.

Native verification must still establish LPAC startup and runtime compatibility,
all filesystem and IPC exceptions, reachable network positive controls, hard
resource enforcement, and cleanup/recovery under crashes, sleep and reboot.
The fixed-VHD candidate currently uses host-owned DiskPart commands, which may
require privileges unavailable to the normal host session. It never elevates or
changes machine policy. A separately reviewed storage provisioning mechanism
may be needed. Run the terminal as an ordinary user; do not treat administrator
execution as evidence of the intended access boundary. The small NTFS volume,
DiskPart path encoding and native API behavior also require target verification.
If these controls cannot pass, implement a stronger boundary before activation.

## Try the terminal on Windows

Prepare a **new synthetic evaluation installation from this reviewed source**
using the existing installer process. The 11 October 2026 evaluation release
contains this source; earlier installers require a one-time bootstrap upgrade.
A new installation includes `payload/code` and the
new launcher; never copy these files into a manifest-verified older installation.

From the prepared `payload/app` directory:

```powershell
.\Start-SILO-Terminal.cmd --plain
```

The model starts contained with no folder grants. Use literal paths:

```text
/reference C:\Synthetic\Reference
/draft C:\Synthetic\Results
/folders
Read the capacity policy and explain the eligible inventory.
/sources
/review PROPOSAL_ID
/approve PROPOSAL_ID
/clear
/quit
```

`/help` lists the commands. `/artifact PATH` previews a code artifact; `/files`
lists its hashes. Ctrl+C during a request cancels owned work and waits for the
request to finish cleanup; exit and restart before continuing. Closing the
terminal removes unpublished code state. Published ZIPs remain in the selected
Draft destination. No project persistence is added in this phase.

Only after complete independent native acceptance:

```powershell
python scripts/manage_security.py update-code-acceptance --signed-record C:\Evidence\independently-signed-code-boundary.json
# Administrative enrollment only. Start the protected managed launcher afterward.
.\installer\Start-SILOManaged.ps1 -Interface Terminal
```

Grant Reference and Draft first, then `/code`. This host command displays and
requests the fixed execution policy. The ordinary document terminal remains
usable without enabling code.

## Native probes and first milestone

The initial fixed developer probe can be run from `payload/app`:

```powershell
..\host\python.exe -I -B .\scripts\validate_code_boundary.py --output C:\Evidence\candidate-observations.json
```

It exercises a normal input read/output write, immutable input/runtime opens,
and child denial. It emits **candidate observations only**; other checks remain
pending, it never activates code tools, and it is not an acceptance record.

Optional developer tests use a prepared synthetic installation:

```powershell
$env:SILO_NATIVE_TEST_ROOT='C:\Prepared\payload\app'
# Run from the reviewed development source with its test interpreter:
$env:PYTHONPATH='src'
python -m unittest discover -s tests -p test_windows_code_runner.py -v
```

These fixed probes add unrelated user-file access, reachable host loopback,
timeout, combined output, memory and fixed-disk exhaustion checks. Their
results supplement the complete [boundary acceptance matrix](SILO-EXECUTION-BOUNDARY.md).
They do not cover external transports, DNS, all IPC or lifecycle recovery.

For the actual local-model milestone, use the frozen
`tests/fixtures/silo-milestone` inputs. Grant that folder as Reference and an
empty results directory as Draft, then enable accepted Code. Ask the model to:

1. Read `policy.txt`, `inventory.csv` and the three negative CSV fixtures, then
   stage their exact bytes. Leave `expected.json` with the independent reviewer.
2. Create `analyze.py` accepting one staged CSV argument and `tests.py`. Validate
   required fields, numeric capacities and quantities, and malformed data.
3. Run the current `analyze.py` on `inventory.csv` and each negative fixture.
   Run the current `tests.py` successfully. A repair must be followed by reruns
   of the current script; interactive sessions have no lifetime run quota.
4. Produce `results.json` with keys `capacity_kg`, `contributions_kg` and
   `excluded_assets`; create `capacity.png` with
   `silo_plot.write_bar_chart('capacity.png', labels, values)` in eligible inventory
   order. Write `report.md` citing the actual policy line returned by the tools.
5. Inspect the output text and chart, prepare one artifact ZIP in the Draft
   grant, and let the user `/review` and `/approve` it.

The independent expectation is exactly **108 kg**, contributed by SYN-001
(48 kg) and SYN-002 (60 kg); retired/quarantined rows are excluded. Missing
capacity, negative quantity and malformed CSV must fail explicitly. A separate
controlled-error task must demonstrate the actual local model inspecting and
repairing its own failure; review the native task transcript.

```powershell
..\host\python.exe -I -B .\scripts\check_code_milestone.py C:\Synthetic\Results\capacity-artifacts.zip
```

The checker verifies frozen input identities, declared artifact hashes, the
independent result, chart pixels, supporting report locator, and recorded native
normal/negative/test runs for the current script hashes. Use the exact ZIP hash
shown by the trusted host review; detached records can be forged and do not
prove origin. The checker refuses simulation labels. It does not establish
real-model task quality, controlled repair, OS containment or CUI authorization.

## Development validation

Portable authority and graph tests cover exact staging, edit hashes, immutable
source checks, malformed/late results, eight-run bounds, cancellation, artifact
review/publication/replay, tool forgery, terminal escaping and grant revocation.
Installer tests check the separate standard-library-only code toolchain. Native
candidate tests are skipped on macOS. The final regression run on Python 3.14.3
completed with **256 passed and 130 skipped** (386 discovered). The skips include
native Windows and unavailable optional dependencies; none count as acceptance.
`git diff --check` passed. Results are retained locally in
`artifacts/phase2/portable-tests-final.txt`; no model-driven native run was performed.

The startup configuration follows [Python's isolated path documentation](https://docs.python.org/3.14/library/sys_path_init.html)
and accounts for the override in [CPython 3.14.8 getpath](https://github.com/python/cpython/blob/v3.14.8/Modules/getpath.py).
LPAC launch follows [Microsoft's AppContainer guidance](https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer).
Those references inform the candidate implementation; native tests must still
establish its behavior on the target configuration.
