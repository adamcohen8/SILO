# Local TUI improvements and Windows retest handoff

Prepared 11 October 2026 from merged main `09f3447`. This is a local implementation,
not a published installer or native Windows qualification. The existing runtime,
models, grants, reviewed-save gates and code-acceptance requirements are unchanged.
The historical Windows report applies to its recorded source, not this revision.

## Navigation and presentation

- Tab completes slash commands, subcommands, model/project/proposal IDs and granted
  folder/file mentions. F2 opens commands when the composer is empty; F3 inserts
  `@` and opens the granted-file picker. Enter accepts a displayed completion;
  another Enter sends. Completions never execute an action.
- Granted names come from the existing bounded `MentionCatalog`, not a home-drive
  search. The host refreshes the snapshot between operations; revision drift hides
  stale mentions. Choosing a name does not read its contents or grant access. The
  normal host mention resolver rechecks the reference when a request is sent.
- Model, project, folder, workflow, schedule and hardware listings use labeled
  tables. Hardware results remain declared capacity estimates, not measured fit.
- Assistant replies render headings, bold text, inline code, bullets, block quotes,
  Markdown tables and fenced code. Python and JSON receive conservative token
  highlighting; other languages remain literal code. Citation tokens remain intact.
  HTML and links are inert text. Reviewed diffs remain literal exact-byte previews.
- Formatting adds no dependency or model/runtime pin. Color is optional. Tables
  wrap cells without deleting their values and use labeled rows in narrow windows.

## Live output and interaction

The Windows worker opts into SSE only when the full-screen host installs live
display sinks. Non-TUI callers retain the existing complete-response protocol.
The client keeps its explicit private AF_UNIX transport, token, deadlines, size
limits, no redirect/retry and no download behavior. SSE wire data is bounded to
four times the response budget, capped at 2 MiB; the assembled reply must still
fit the original response budget. A missing finish/DONE, malformed data, invalid
tool fragment or incomplete response fails without executing its partial calls.

Only content deltas reach a separate **provisional** live panel. Private reasoning
and tool arguments remain outside it. Tool actions still require a complete,
validated response and fixed host dispatch. The host accepts only reset, bounded
text and fixed progress metadata over session/sequence-bound display frames.
Display frames have a separate 128-event / 64 KiB text budget and cannot extend
the existing tool-request allowance. A long preview may stop before the final
response. The provisional panel clears on success, failure or cancellation; only
the host-accepted final answer enters the transcript and saved conversation.

Progress updates target the full-screen status instead of printing behind it.
The composer stays editable during work. Enter while busy preserves the composed
message and asks the user to send when Ready; it never queues or automatically
replays a request. Page Up/Down and mouse navigation preserve the reading position
when new output arrives. Ctrl+End returns to following the latest message. The
transcript remains bounded to 4,000 lines.

Ctrl+C retains the hard stop of owned inference/parser/code work. After the ask
has drained, the host closes the old session, verifies cleanup, constructs and
starts a fresh session through normal asset/policy/hardware checks, reserves
private project paths and restores only grants with matching saved identities.
Changed grants are omitted and reported. Instructions and saved-project identity
survive; old chat, pending approvals and code authority do not. The next composed
message is kept. Failure to verify cleanup or restart leaves the session
unavailable. Ctrl+D during cancellation/recovery stops and drains owned work
instead of launching another session. Scrollback cancellation also attempts this
verified recovery but remains a non-streaming presentation.

## Local validation

[SILO-TUI-LOCAL-VALIDATION.json](SILO-TUI-LOCAL-VALIDATION.json) binds the tested
source files and records the portable result. Focused tests exercise real SSE
delivery before EOF, arbitrary UTF-8 chunk boundaries, private reasoning,
fragmented tool calls, truncated/oversized/malformed events, the actual IPC parser
with inert Win32 pipe shims, worker display caps, completion and actual screen
keypresses, editable busy input, reading anchors, provisional-output disposal,
identity drift, private-path reservation, cleanup failure and cancelled recovery.
The shim tests do not establish Windows token, pipe ACL, GPU or cleanup acceptance.

The local suite passed **411 tests**, with **170 skipped** and no failures or
errors. Sixteen focused tests cover the new contracts. A rendered 30-row screen
check preserved the composer at 40, 80 and 120 columns. The pinned llama.cpp
server's streaming serialization was also inspected at revision
`50569eb87df530daff11afda229ceb9ab8e6cae8`; this is structural evidence, not an
actual-weight streaming qualification.

## Required Windows retest

Install this exact source in a new disposable root; do not patch immutable
installed files. Record the source/manifest/model/OS/driver identities and use
synthetic inputs. Keep previous Windows results intact.

1. Launch the default full-screen interface in an actual Windows console. Check
   40/80/120-column windows, resize, display scaling, plain/color, paste, Unicode,
   multiline editing, Tab/Enter, F2/F3, Page Up/Down, Ctrl+End and mouse scrolling.
2. Grant only a synthetic Reference/Drafts tree. Check quoted filenames, duplicate
   folder names, revoked/renamed/replaced folders and empty/truncated inventories.
   Completion must never expose ungranted paths or execute a selection.
3. Inspect model/project/workflow/schedule/hardware tables and literal review
   diffs. Run text/PDF/DOCX citation and real draft-review/save workflows; verify
   that highlighted text does not change the reviewed bytes or approval binding.
4. With actual selected weights and the pinned CUDA server, confirm content
   appears before the request finishes, progress stays in the screen, reasoning
   and tool arguments stay hidden, and the accepted final answer appears once.
   Exercise tool calls, correction turns, truncated streams, socket failure,
   malformed/replayed display events and cancellation. Provisional text must not
   enter retained history or become a saveable proposal.
5. While generating, compose another message and scroll up. Incoming output must
   keep the reading position and composed text. Sending while busy must not queue
   inference. Return to latest explicitly and send once Ready.
6. Cancel during inference/parsing/code (only if separately accepted), wait for
   verified model reload and ask again without closing SILO. Check exact grant
   identities, private-tree exclusions, fresh reviews, cleared chat/code authority,
   saved instructions and owned-process cleanup. Inject changed model/policy,
   changed grants, cleanup/reload failure and cancellation/exit during recovery;
   these paths must refuse unverified reuse. Repeat in scrollback mode.
7. Retest model switching/removal, no-model menu, scheduled cancellation and
   Ctrl+U update protections/default interactive restart with the new composer.
   Repeat the relevant containment/lifecycle matrix for the changed worker IPC.

The Mac preview remains scripted. Run `scripts/preview_terminal.py` with the
existing development terminal dependencies to work on presentation; it does not
load weights, grant real files or qualify native recovery/streaming.
