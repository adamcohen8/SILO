# SILO Vision and Implementation Plan

10 October 2026

SILO means **Super Intelligence for Local Offline Operations**. Its purpose is to give people a capable personal work assistant that can understand a project, use approved files and tools, and carry work through to a reviewable result. The intended experience includes document work, analysis, coding, and reusable workflows, with local inference and enforced containment supporting environments that handle Controlled Unclassified Information (CUI).

This plan expands the existing document-assistant prototype. It defines planned capabilities and implementation gates; it does not enable command execution, change current permissions, or establish authorization to process CUI. The existing evaluation continues to use public or synthetic material.

## Product vision

A user should be able to open a project, describe an outcome, and collaborate with SILO while it reads sources, plans work, creates artifacts, runs permitted computations, checks results, and explains what it completed. The user should be able to inspect sources and changes, stop work, and return later to continue.

Representative requests include:

- Compare several documents and produce a memo with supporting citations.
- Analyze supplied data, create a chart, and explain the calculation and its limitations.
- Write a script, run it against approved inputs, diagnose a failure, and verify the corrected result.
- Create and revise a Word document, spreadsheet, or presentation.
- Reuse a project workflow without repeating its instructions and context each time.

The motivating ambition is the practical work experience of a capable ChatGPT or Codex assistant made available within an organization's permitted environment. SILO is an independent project with no current GenAI.mil affiliation, endorsement, or integration. Its success will be measured by completed work, result quality, and usable controls. Local models must demonstrate their capabilities on these tasks; a harness cannot guarantee parity with frontier hosted models.

## Product and authority design

### Projects and continuity

A project groups approved folders, user instructions, conversations, working files, and reusable workflows. Saved context must live in an explicitly selected local storage boundary with retention and deletion controls. Users must be able to see what is remembered and clear it.

Permission changes and source changes must invalidate affected retained context. Removing access must prevent subsequent retrieval, tool access, and use of stale excerpts. Content already delivered to a model cannot be retroactively erased; ending or clearing the affected session must be part of the revocation workflow. Conversations, extracted text, indexes, command output, and derived artifacts inherit the project's handling requirements.

### Shared backend and two interfaces

The terminal and desktop interfaces should use the same project, session, tool, and permission services. The terminal will provide the earliest coding and execution experience, including progress, cancellation, source inspection, and readable diffs. The desktop remains part of the product vision for users who benefit from file previews, artifact inspection, and discoverable controls.

The current Qt interface can evolve incrementally. Replacing a screen must not bypass the contained Windows session or create a second set of authority rules.

### Harness and model separation

The model supplies reasoning and tool requests. The inference runtime loads and executes the model. The harness manages task progress, context, tool calls, failures, and completion. The trusted host enforces permissions and approvals independently of all three.

Evaluate the current LangGraph harness against an existing extensible agent harness before committing to a broad rewrite. Compare local-model support, offline operation, Windows compatibility, controlled tool dispatch, task recovery, dependencies, telemetry, and licensing. Use the same synthetic workflow for both candidates. Select one default harness; additional harnesses require their own integration and qualification.

Model-specific chat templates and runtime adapters are expected. A request for a model does not automatically authorize installing an associated agent framework or expanding its tools.

### Explicit workspace permissions

| Workspace type | Intended capability | Approval boundary |
| --- | --- | --- |
| Reference | Read and cite approved sources | The user grants and revokes access; the agent cannot expand it |
| Draft | Create reviewed documents in an approved destination | The user reviews the exact proposed content before saving |
| Code | Create and edit project files and execute permitted programs | The user grants a bounded execution policy; actions outside it are denied or require host review |

Code workspace permission is a new capability. Existing editable grants must not silently acquire execution authority. Within an approved disposable code workspace, ordinary edits and tests may proceed under a session policy without prompting for every step. Publishing results into user destinations, destructive actions, and changes beyond that policy retain explicit review requirements.

Starting a command in a folder does not restrict what it can access. The execution service must enforce filesystem access, process creation, network denial, deadlines, output limits, and cleanup outside the model. The model, harness, parsers, generated programs, and any permitted descendants must remain within the intended boundary. Host connectivity remains available.

### Approved models and hardware recommendations

Maintain an organization-managed catalog of approved configurations. Entries must identify model versions and hashes, upstream lineage where known, fine-tuners, quantizers, runtimes, harness versions, licenses, tested capabilities, hardware requirements, and approval scope. Unknown provenance needs review. The policy must support publisher or jurisdiction restrictions, including Chinese-origin models where the organization requires them.

Model selection follows this sequence: inspect hardware locally, filter by policy, rank compatible configurations for the requested workload, show the recommendation and limitations, accept the user's permitted selection, and validate the installed configuration. Explicit selections and imported model files must pass the same policy. Installation and launch both enforce approval; user preferences and model output cannot change it.

Start with a small number of tested configurations. Recommendations must consider available RAM and VRAM, context length, runtime buffers, driver compatibility, competing workloads, and measured task quality. Loading successfully is insufficient to qualify a model for tool use or coding. Installation supports verified online preparation and an offline cache or bundle; task execution must not download missing dependencies automatically.

### Deployment boundaries

Local-only operation remains the initial deployment. A later organization-approved hosted endpoint may share the application interfaces, but it requires a separate deployment profile and approval. There must be no automatic cloud fallback or automatic transfer of a restricted project's context to a connected profile.

Network containment covers every supported transport and relay path, including Wi-Fi, Ethernet, VPN, DNS, local listeners, and host IPC. An API key, a local model, or blocked network access alone does not establish CUI authorization. Full isolation acceptance, supply-chain trust, installation qualification, and organizational approval remain separate gates.

## Current foundation and remaining work

The following baseline distinguishes implemented components from recorded native evaluation results and broader qualification still required.

| Area | What exists | What needs work |
| --- | --- | --- |
| Model interface | Replaceable `ChatModel` contract and local compatible transport | Catalog-driven selection; additional model and runtime adapters; configuration-specific quality tests |
| Hardware inspection | Read-only Windows OS, RAM, GPU, VRAM, and driver inventory | Recommendation logic, compatibility decisions, and workload measurements across hardware profiles |
| Harness | Bounded LangGraph orchestration with fixed listing, reading, search, and draft tools | General task execution, progress, recovery, larger workflows, and a reuse-versus-extension decision |
| Folder authority | Host-controlled grants; native Windows candidate; stale-source and revocation checks | Broader hostile-filesystem qualification and separate code-workspace authority |
| Document work | Bounded text, PDF, and DOCX ingestion and keyword search; line, page, and paragraph citations | OCR, long-document retrieval, broader fidelity and accuracy, and formatted artifact creation |
| Review and saves | Host-reviewed exact-byte saves to new files; originals preserved | Controlled code patches, rollback, and review of generated artifact sets |
| Interface | Windows Qt chat, sources, folder persistence, mentions, cancellation, and startup preferences; basic POSIX development CLI | Contained Windows terminal client, clearer desktop interactions, and project navigation |
| Memory | Bounded in-memory conversation with retained-source revalidation | Opt-in project persistence, resumable tasks, retention, deletion, and local retrieval indexes |
| Containment | Zero-capability AppContainer jobs, private socket and pipe transport, token checks, and resource limits | Complete isolation matrix; a separately designed runner for generated code and its allowed process tree |
| Coding | Source code can be proposed as a reviewed text file | Existing-file edits, command execution, offline dependencies, testing, and execution evidence |
| Model policy | One pinned inference configuration with artifact identity and provenance metadata | Administrator-controlled allowlist, approval scope, revocation, lineage review, and launch enforcement |
| Installation | Evaluation installer with pinned assets, offline preparation, preflight, retry, repair, and rollback mechanisms; verified bootstrap release builder and documented public evaluation release | Native acceptance of the standalone CPython 3.14 configuration, complete recovery qualification, signing, redistribution review, and qualified signed releases |

The recorded 6 October Windows evaluation passed 15 synthetic contained-agent checks and 68 regression tests, with two POSIX-only skips. It demonstrated text/PDF/DOCX citations, host-reviewed saves, full GPU placement, selected external IPv4 TCP denial, and retained host connectivity. It did not establish the complete isolation matrix or general model quality. Its CPython 3.12 evidence does not qualify the newer standalone CPython 3.14 installer configuration. See [Windows evaluation results](WINDOWS-AGENT-ISOLATION-2026-10-06.md) and [evaluation installer acceptance limits](EVALUATION-INSTALLER.md).

The repository's [bootstrap documentation](PUBLIC-BOOTSTRAP.md) records publication of the 10 October SILO evaluation release and anonymous installation assets. This is unsigned evaluation distribution; publication does not establish native fresh-install acceptance, full isolation, or CUI authorization.

Current workers deny child creation and expose no shell tool. The coding plan must add a distinct execution service; it must not weaken those workers merely to allow commands. The existing CLI uses the POSIX development broker and is not a contained Windows terminal product. See the [tool registry](../src/local_ai_appliance/agent.py), [process controls](../src/local_ai_appliance/windows_container.py), and [development CLI](../src/local_ai_appliance/cli.py).

## Phased implementation

Phases are ordered by dependencies and acceptance gates. Interface prototypes, native installer evaluation, and policy preparation may proceed alongside the core work. Calendar estimates should follow the harness and execution-boundary decisions.

### Phase 1 Establish the agent architecture and execution policy

**Deliver:** a common backend contract for projects, sessions, tools, model adapters, progress, approvals, and cancellation. Evaluate harness candidates with the same local synthetic tasks and select the default. Define Reference, Draft, and Code permissions, a minimal approved configuration catalog, and the execution threat model. Resolve which interpreter/runtime configuration the first native milestone will qualify.

**Exit criteria:** the selected harness completes the existing document workflow through host-controlled tools; permission and approval operations remain inaccessible to the model; offline dependencies and telemetry behavior are accounted for. The code-runner design specifies actual OS controls, data transfer, process ownership, cleanup, and tests for denied access and network paths. No generated commands execute before this boundary exists.

**Implementation update, 10 October:** [Phase 1 implementation and validation](SILO-PHASE-1.md) supplies the common session API, explicit permission types, reviewed-save authority, pinned evaluation catalog, harness comparison/decision, and frozen milestone fixtures. The [execution-boundary design](SILO-EXECUTION-BOUNDARY.md) specifies native controls and qualification gates. LangGraph remains the default. Portable scripted tests are available; native Windows acceptance remains pending, Code grants/execution stay disabled, and the standalone CPython 3.14.8 candidate is selected for the next native milestone.

### Phase 2 Complete the first contained work session

**Deliver:** a Windows terminal client using the shared backend, a disposable code workspace, and a host-launched contained execution service. Support reviewed workspace creation, bounded code edits, a pinned Python toolchain, captured output, tests, cancellation, and an inspectable result set. Use the current model if it passes the task evaluation; qualify a different approved configuration if needed.

**Exit criteria:** pass the first end-to-end milestone below on native Windows with actual local inference. Both functional and containment criteria must pass. Tests using scripted model responses supplement the real-model workflow and cannot replace it.

**Implementation update, 10 October:** [Phase 2 implementation and native gates](SILO-PHASE-2.md) provides the shared Windows terminal, disposable code tools, separate standard-library Python toolchain, LPAC/fixed-VHD runner candidate, reviewed atomic artifact ZIP publication, and independent fixture checker. Portable tests use simulated execution; native runner tests are opt-in. No accepted native record is supplied, so execution remains gated. The actual local-model milestone and containment exit criteria have not passed.

### Phase 3 Add projects and finished office artifacts

**Implementation status (2026-10-10):** project persistence, task instructions, desktop/shared-backend controls, CSV/XLSX analysis, reviewed DOCX/XLSX/PPTX output, bounded folder retrieval, and optional signed image OCR adapter are implemented. Portable office samples were independently opened and rendered. Native storage/Office/OCR acceptance and scanned-PDF conversion remain pending. See [implementation details](SILO-REMAINING-PHASES.md).

**Deliver:** explicit local project storage, saved and resumable conversations, source-aware context invalidation, retention and deletion controls, and reusable task instructions. Improve the desktop against the same backend. Add CSV/XLSX analysis and formatted DOCX output first, followed by presentations, broader document retrieval, and OCR as separate tested capabilities.

**Exit criteria:** a user can close and reopen an approved project, continue work, inspect and clear retained context, and produce a usable artifact. Revocation and source changes invalidate affected context and indexes. Generated office documents are opened or rendered and checked for content and layout; successful file creation alone does not establish usable output.

### Phase 4 Expand model selection and repeatable workflows

**Implementation status (2026-10-10):** signed administrator policy updates, hardware recommendations, explicit selection, offline GGUF import, scoped workflows and local host schedules are implemented. Additional model profiles and native measurements remain pending; optional external harnesses are not installed.

**Deliver:** administrator-managed catalog updates, hardware-based recommendations, explicit model selection, offline model import, and a small set of qualified document/coding profiles. Add reusable workflows and, later, host-owned scheduling where useful. External harness integrations remain optional and must use the same authority services.

**Exit criteria:** prohibited, unknown, revoked, or changed configurations are denied at installation and launch. Each supported configuration has measured task quality, latency, memory use, tool compatibility, and failure behavior. Changing models preserves the project's permissions and handling requirements. Scheduled work has explicit scope, cancellation, idempotence, and retained evidence without duplicated actions.

### Phase 5 Qualify installation and organizational deployment

**Implementation status (2026-10-10):** detached bundle signing/verification, bootstrap certificate hooks, license inventory, evidence/readiness matrix, and operational/recovery procedures are implemented. Actual signing, license approval, all native qualification and organization authorization remain pending. No new release has been published.

**Deliver:** signed versioned bundles and established trust anchors, redistribution and licensing review, complete native fresh-install/offline-install/retry/repair/rollback evidence, and the full isolation and filesystem acceptance matrix. Exercise reboot, sleep/resume, network/VPN changes, crashes, resource exhaustion, and drift rejection. Define project data storage, backup, update, and incident procedures for the target environment.

**Exit criteria:** required acceptance checks pass for the exact supported configuration with no security-critical skip counted as a pass. The organization completes its authorization process before CUI use. Release publication and deployment require their own authorization. Any later hosted inference profile needs separately approved endpoints, credentials, data handling, and transfer rules.

## First end to end milestone

### User outcome

On the Windows RTX 4090 target, give SILO a read-only reference folder containing a fictional capacity policy and a synthetic inventory CSV, plus a disposable Code workspace. Ask:

> Read the capacity policy and inventory. Write and test a Python script that calculates usable carrying capacity, make a chart, and prepare a report explaining the result with supporting sources. Keep the inputs unchanged and show me the outputs before publishing them.

Use one local model, one pinned offline Python toolchain, and one terminal session. The initial report is Markdown; formatted Word output belongs to Phase 3. The milestone must exercise actual generated-code execution rather than substituting a fixed analysis tool for the script.

### Fixtures and expected result

The reference policy defines capacity as quantity multiplied by per-item capacity for eligible inventory only. The CSV includes two eligible rows: four items at 12 kg each and three items at 20 kg each. The independently specified expected total is **108 kg**. Additional fictional rows cover retired or quarantined items, which the policy excludes. Separate negative fixtures cover missing capacities, invalid quantities, and malformed input; the script must report these rather than invent values.

Hostile instructions in a document or data cell must remain source data and must not authorize network access, new grants, or host commands. Inputs and expected outcomes are versioned before the agent run.

### Required workflow and outputs

1. The user grants the reference folder and approves the bounded Code workspace policy. No other folder access is available.
2. SILO reads the policy and inventory through the host broker, obtains source locators and hashes, and explains its calculation plan.
3. The host stages only approved input bytes as read-only inputs in the isolated workspace. The agent creates `analyze.py` and tests; installed toolchain files remain immutable.
4. The contained runner executes the script and tests using verified offline dependencies. SILO can inspect failures and revise its own workspace files within its policy and budgets.
5. SILO produces `results.json`, `capacity.png`, and `report.md`, alongside its script and tests. A source manifest binds the inputs and report references to filenames, locators, and original hashes. Exported citations must remain understandable without the live chat.
6. SILO checks the numeric result and artifact contents, explains any unresolved issues, and presents the changes and outputs. The host presents the chart for inspection and verifies output inventory and file types.
7. The user reviews the output set and explicitly publishes approved new copies to a Draft destination. The host binds approval to exact output bytes, rechecks sources and grants, and refuses collisions or stale results. Until then, files exist only in the working area.
8. Closing or cancelling the session terminates owned work and performs the specified workspace and temporary-permission cleanup. Unreviewed files cannot be automatically resumed or published.

### Acceptance criteria

| Area | Required observation |
| --- | --- |
| Calculation | The normal fixture yields exactly 108 kg; excluded and malformed rows behave as specified by independently defined fixtures |
| Sources | Policy claims cite the actual supporting locators; data-derived claims identify the input version and calculation; hashes match original input bytes |
| Actual execution | Generated code and tests execute in the contained runner; the report distinguishes generated, executed, tested, and unverified work |
| Editing and recovery | A controlled faulty-script case is diagnosed and corrected; retries remain within resource and task budgets |
| Filesystem | Reference inputs and installed software remain unchanged; attempted outside-workspace reads/writes and path or link escapes are denied |
| Network | Approved reachable responders establish host controls; worker and execution-process probes demonstrate denial for the milestone's supported paths with enforcement evidence; untested paths remain explicit limitations |
| Host usability | Permitted host connectivity succeeds before, during, and after the workload |
| Authority | Injected source instructions, unregistered operations, and attempts to self-approve or expand grants fail |
| Review | No output reaches the Draft destination before approval; changed output bytes, stale sources, revoked grants, collisions, and replayed approval are rejected |
| Lifecycle | Cancellation and timeout terminate the owned process tree; cleanup is verified; a subsequent fresh session succeeds |
| Artifact quality | The chart opens correctly and matches the results; the report contains the calculation, exclusions, sources, and limitations without unsupported completion claims |

This is a development milestone on a specific tested configuration. Full isolation acceptance remains governed by the broader [isolation validation plan](ISOLATION-VALIDATION.md); successful completion does not grant CUI processing authorization.

### Evidence to retain

Retain the exact source revision, model/runtime/toolchain/policy identities, input hashes, output hashes, expected and observed results, test outcomes, process-boundary observations, timing, memory measurements, and cleanup results. Synthetic task transcripts and artifacts may support development evaluation. Operational prompts, documents, command output, and derived content must remain in the organization's authorized storage and must not enter the repository or public diagnostics.

## Immediate next work

Phase 1's portable implementation, fixtures, harness decision, and boundary design are recorded in [the implementation report](SILO-PHASE-1.md). [Phase 2](SILO-PHASE-2.md) supplies the terminal and runner candidate. Next qualify the exact native Python and execution configuration, resolve provisioning and containment findings, and demonstrate the actual local-model workflow. Broader model coverage and desktop polish follow demonstrated completion of that workflow.

## Supporting implementation and evidence

- [Current architecture](ARCHITECTURE.md) and [agent tool surface](AGENT-DEVELOPMENT.md).
- [Windows interface and session behavior](WINDOWS-DESKTOP.md).
- [Native evaluation results](WINDOWS-AGENT-ISOLATION-2026-10-06.md) and [target acceptance](TARGET-VALIDATION.md).
- [Network isolation matrix](ISOLATION-VALIDATION.md).
- [Pinned model profile](INFERENCE-PROFILE.md).
- [Evaluation installer](EVALUATION-INSTALLER.md) and [bootstrap release preparation](PUBLIC-BOOTSTRAP.md).

The earlier first-version architecture deliberately excludes generated-code execution. This roadmap defines its future introduction under a new permission and containment design; existing behavior remains the baseline until each capability is implemented and accepted.
