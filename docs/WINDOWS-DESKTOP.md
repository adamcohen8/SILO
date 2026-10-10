# Windows local evaluation interface

The prepared workstation can run the native desktop interface with Nemotron 3
Nano 30B-A3B on its RTX 4090. This is an evaluation of local capability using
public or synthetic documents. Production activation, CUI authorization, the
complete isolation matrix and a signed offline installer remain pending.

For a new machine, use the [one-command evaluation installer](EVALUATION-INSTALLER.md).
The application-local CPython 3.14 configuration and restored desktop review
workflow still need native Windows qualification.

## Start and try it

Double-click `Start-LocalAI.cmd` in the project folder. The window verifies the
prepared model/runtime hashes and loads the GPU model in the background.
Wait for **Ready**. Previously selected folders are restored automatically;
the first launch starts with no folders.

1. Click **Load sample folders**, then **Send**. The fictional
   capacity answer should be 37 crates, with a citation to line 2.
2. Click **Sources**, then select a citation to inspect the actual text excerpt
   and its source locator.
3. Click **Sample draft**, then **Send**. Generated draft text appears
   in the conversation, marked as unsaved.
4. Select the draft and click **Review draft…**. Inspect the source, destination,
   draft and diff, then **Review changes** and **Save reviewed copy**. A new file
   is saved only after this explicit approval; edits require another review.

The interface has a folder sidebar and one scrolling conversation with **You**
and **Nemotron** message bubbles. Type in the compact composer at the bottom;
**Enter** sends and **Shift+Enter** inserts a new line. **Ctrl+Enter** also sends.
The source inspector opens only when requested. The top-right **Open AGENTS.md**, **Clear chat**,
**Load sample folders**, **Restart model** and **Cancel request** controls remain.

**Open AGENTS.md** opens `AGENTS.md` in Windows Notepad. Installed evaluations
keep this editable file under their private `state` directory; the earlier
prepared-project workflow uses the application's root file.
It contains editable assistant preferences for response style and document work.
Save your edits, then click **Restart model** or reopen the app to apply them.
Restart clears the current chat and restores saved folder selections. The host
loads a UTF-8 snapshot (up to 8 KiB, optional BOM) during initialization and
passes it to each contained worker as system instructions. An empty file keeps
the built-in defaults. Missing, oversized or invalid files stop initialization
with an actionable message. Copies in shared document folders are ordinary
documents. Preferences cannot change the registered tools, folder grants, or
host-enforced citation and approval checks.

Sample files live in `state/samples/Reference` for installed evaluations or
`artifacts/windows-ui/samples/Reference` in the earlier workflow. For your own
public test documents, use **Add folder** or drop local folders in the reference
or draft area. Select a folder to browse; double-click a directory to navigate
or a file to prepare a summary question. Click **Send** to read and summarize it.
Follow-up messages include previous turns while the app remains open.

Type **/** to autocomplete folders or **@** to autocomplete files from your
granted folders. Continue typing to filter, use **Up/Down** to select, and press
**Enter** or **Tab** to insert the reference; clicking a suggestion also works.
**Escape** dismisses suggestions. Selecting a reference does not send the
message. Examples: `/Reference`, `/Reference/docs`, `@Reference/specs.pdf`.
Names with spaces are quoted automatically, such as
`@"Reference/Radio specs.pdf"`. Duplicate folder names get distinct aliases,
and hover text shows their locations. Full qualified paths are rechecked
against current grants before sending; an ambiguous bare filename is rejected.

Autocomplete scans names only in a bounded preview (32 directories, four levels
of descent, 512 entries). Explicit qualified references can address allowed
paths outside that preview. Suggestions refresh on a new mention trigger and
after access changes. A mention selects an existing grant; it cannot add access.

Conversation history is held in host memory, with no history file or recovery
after closing. **Clear chat** erases the conversation and pending drafts while
keeping the model running and folder grants intact. Changing folder permissions,
cancelling, restarting or closing clears the conversation. Retained document
sources are checked against the current file bytes before each follow-up and
again before accepting an answer; changed sources clear the previous chat.

Folder selections and their Reference/Draft access levels are saved immediately
in `state/folders.json` for installed evaluations or
`artifacts/windows-ui/folders.json` in the earlier workflow. Startup and **Restart model** reacquire
fresh native handles and verify the saved volume and directory identity using
the same local-drive, NTFS, non-reparse and overlap checks. Unavailable or
replaced folders are skipped with a status notice; select them again to grant
access. **Remove** updates the saved selections, so removed access does not
return after reopening. These settings contain only paths, access levels and
directory identities; chat history, source contents and drafts remain in memory.

Memory retains at most 16 complete turns and 48 KiB of serialized history and
source context. The actual model template is token-counted before generation;
older complete turns may be removed to fit its 8,192-token context, reserving
space for the answer. A status notice appears when history is trimmed. Each
request still uses a fresh contained graph worker and current folder inventory.

Grants cover allowed subfolders as well as the selected directory. At the start
of each request the model receives a bounded, name-only preview of immediate
children (up to 24 entries per directory, 8 KiB total). If a directory contains
only one child directory, the preview follows up to three such wrapper levels.
Each preview and listing carries its relative path so that nested directories
can be resolved from the selected grant. File contents are fetched
only through the document tools. Listings cover one directory at a time; the
model can list a child with its relative path to find a document further down.
Large previews are marked truncated, and failed listings are reported as
errors rather than empty folders. Previews are refreshed for every request and
discarded when grants are revoked.

The downloaded project has two nested folders named `local-ai-appliance-main`.
When the outer folder is granted, the README path is
`local-ai-appliance-main/README.md`. Selecting the inner folder places the
README directly in the granted root.

Simple requests such as **Please list the files under the docs folder** use
the native folder broker directly. A folder name resolves to the nearest
matching directory under the current grants, with at most 32 directory
listings and four levels of descent. Multiple matches or incomplete searches
ask for a relative path. An explicit relative path is preserved. Results show
actual filenames, counts, subfolders and truncation without reading documents
or invoking the model. Revocation during lookup discards the result.

Adding a parent folder can conflict with existing grants inside it. For example,
the project folder contains the sample Reference and Drafts folders. The app
now offers **Replace folder access**: confirm to remove the conflicting grants
and add the selected folder with the chosen access. Cancel keeps the existing
grants and pending drafts. Rejected folders display an explicit error dialog.
Successfully added folders are selected immediately in the file browser.

## Supported scope

- UTF-8 text, text-based PDF and DOCX; maximum input file size 1 MiB.
- Bounded reads, with line, PDF page or DOCX paragraph citations. No OCR.
- Specific facts such as radio bandwidth can use targeted document search.
  The model locates files through granted directory listings, then searches a
  document for a short keyword or phrase. Search returns a small matching
  excerpt and its verified citation, with continuation information for further
  matches. It avoids filling the model context with whole specification pages.
  Ordinary PDF/DOCX read results include each excerpt's text only once.
- Failed requests remain visible in the chat with their error and retry hint;
  they are not added to model memory. The message composer retains the request
  for editing and retrying.
- A failed literal phrase search directs the model to retry a shorter property
  keyword. The contained agent can make one citation correction request, within
  its existing tool, context, deadline and model-call budgets. The corrected
  answer must pass the same host citation and source checks.
- Draft text is shown in the answer area, with pending drafts available through
  **Review draft…**. The separate window shows the editable destination, source
  hash, editable text and diff. **Review changes** rechecks the source and stores
  exact bytes; **Save reviewed copy** explicitly approves that single proposal.
  Editing the destination, filename or text invalidates review. Changed sources,
  revoked grants, existing destination files and replayed approval are rejected.
  Discarding or closing the window removes pending authority. Selecting an
  editable folder does not automatically save a file.
- Permission changes clear pending drafts and displayed answers.
- Folder changes are disabled during an operation. **Cancel request** stops
  the owned model and graph job. Use **Restart model** afterward; saved folders
  will be restored. Closing the window stops owned jobs and removes the temporary
  AppContainer profile, permission leases and private socket directory.
- One interface instance and one model slot. No automatic downloads, cloud
  fallback, TCP service, shell tool or web content rendering.

## Implementation and local evidence

`windows_desktop.py` is the trusted Qt host. `windows_session.py` starts the
prepared CUDA model and fixed graph worker in zero-capability, low-integrity
AppContainer jobs. `windows_workspace.py` shares the tested, fixed document
RPC registry and separately contained PDF/DOCX parsing. Folder handles, grants,
source checks, saved folder settings, pending proposals and approval stay in the host. Native token
and loopback-exemption checks run before resuming each contained job.
The endpoint is a private authenticated Windows AF_UNIX socket.

Logs are drained without storing prompts, document text or responses. Answers,
citations and proposals are held in memory; only explicitly approved new files
are saved. Evaluation evidence contains controlled synthetic data.

The standalone installer pins Python and Windows wheels in
`profiles/windows-evaluation-installer.json`. The earlier project-local workflow
uses `requirements/windows-ui-offline.txt` and `profiles/windows-ui-wheels.json`.
Qt is excluded from the contained interpreter stage in both workflows.

Before the layout simplification on 6 October 2026, the synthetic UI run passed 17 checks: GPU startup,
initial absence of grants, PDF and DOCX previews, a cited text answer, background
responsiveness, review gating, edit invalidation, exact-byte save, unchanged
source, single-use approval, combined PDF/Word citations, revocation, verified
worker tokens, cancellation and cleanup. An earlier combined-document answer
did not meet the expected citation/fact check; a subsequent run passed. Model
answers remain subject to human source review and broader quality evaluation.

Close the interface before running either evaluation command. Run the complete
synthetic UI evaluation with:

```powershell
& artifacts/windows-evaluation/venv/Scripts/python.exe -I -B scripts/validate_windows_ui.py
```

It drives the actual window, GPU model, contained parsers and draft-text display,
and writes `artifacts/windows-ui/interface-results.json` plus a rendered
screenshot. The evaluation also asks the contained model to summarize the
actual public README with the outer project folder granted. The regression
runner includes native Qt/host authority tests, including the picker route,
overlap confirmation, bounded inventories and reads inside a child directory:

```powershell
& artifacts/windows-evaluation/venv/Scripts/python.exe -I -B scripts/validate_windows_regressions.py
```

These are capability and development checks, not deployment qualification.

The conversation evaluation uses fictional prompts and a temporary synthetic
document to check recall, clearing, source invalidation, cited follow-ups and
cleanup through the actual Qt interface and GPU model:

```powershell
& artifacts/windows-evaluation/venv/Scripts/python.exe -I -B scripts/validate_windows_conversation.py
```

It saves check metadata in `artifacts/windows-ui/conversation-results.json` and
a synthetic screenshot. This explicit evaluation output is separate from the
application’s memory-only conversation behavior.

The discovery update passed 81 regressions (two expected POSIX-only skips).
The actual contained-model request **Summarize the readme in the folder.**
found the public README one level below the granted outer download directory
and returned nine verified line citations. The 19-check UI evidence includes
that nested-path scenario. Its PDF/Word deadline comparison was recomputed
from the saved synthetic answer after correcting a test-only Unicode-space
comparison; both document citations and the reported deadline were valid.

The simplified layout passed 80 existing regression checks with two expected
platform skips. Its Qt render was inspected with synthetic text and citations;
model/runtime/containment code was unchanged for this layout revision.

The folder-listing update passed 88 regressions with two expected platform
skips. `scripts/validate_windows_listing.py` verified the exact docs-listing
request through the Qt interface from both the inner and outer project folder;
both returned all 16 filenames. Its nine checks passed, including absence of
document reads, inference workers and drafts for name-only listings, plus
complete cleanup. Evidence is in `artifacts/windows-ui/docs-listing-results.json`.

The session-memory and chat-layout revision passed 99 regression checks with
two expected POSIX-only skips. The final actual GPU/Qt conversation run passed
20 checks, including cited follow-ups, Clear chat without a model restart,
source-change invalidation, message sizing at 980×740, zero-capability graph
workers and cleanup. Long synthetic listings and wrapped replies were also
inspected at 1280×900 and 980×740. The first run's exact-string codename recall
check failed; two subsequent runs returned the expected codename. Memory
delivery is tested independently with scripted replies; model answers still
require review.

Remembered folder access passed 107 regression checks with two expected
POSIX-only skips, plus 13 native folder checks with one privilege-dependent
skip. The Qt tests close and reopen the host, restore fresh native grants at
both access levels, verify unchanged file access and empty chat history, and
check that removal, malformed settings and replacement directories cannot
restore unintended access. Synthetic evaluation runners use separate or
disabled folder settings so fixtures do not replace the user's saved folders.

The targeted PDF-search and visible-error update passed 112 regression checks
with two expected POSIX-only skips. The reported radio question was reproduced
against the user's granted PDF: before the update it exceeded the request
budget; afterward the actual contained GPU model answered with a verified page
3 citation in two model calls and one document tool call. The application still
stores no prompt or response logs. Search matches are excerpts and require
source review, especially for specification qualifications and footnotes.

Folder/file autocomplete passed 122 regression checks with two expected
POSIX-only skips. The actual Qt/GPU check selected a folder with Tab, listed
the referenced directory without inference, selected the radio PDF with Enter,
and received a verified page 3 answer. Selection did not send the message.
An earlier model run stopped at a literal phrase miss and another failed
citation validation; keyword-retry guidance and one bounded citation correction
now address those failure paths, with validation retained.
