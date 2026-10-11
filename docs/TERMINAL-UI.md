# SILO terminal interface preview

The default design fills the terminal window. A scrollable conversation occupies
the center; a fixed message box, activity status, and keyboard hints remain at
the bottom. It can be designed and tried on macOS before native Windows work.
The full-screen preview uses prompt_toolkit. It needs no model or server. Its
replies, sources, folders, and output destination are fictional. It never reads
user documents, saves files, or runs generated commands.

## Try it on your Mac

The prepared Mac development environment is ready to run:

```sh
/private/tmp/silo-terminal-ui-venv/bin/python scripts/preview_terminal.py
```

Type `/example` to see activity messages, a cited capacity result, and a pending
draft. Then type `/review D1` to inspect its full text and `/approve D1` to simulate
approval. The preview explicitly reports that no file was saved. `/help` lists
the other commands. Enter sends, Alt+Enter inserts a newline, Page Up/Down scroll
the conversation, Ctrl+End jumps to the latest message, Ctrl+C cancels input or
sample activity, and Ctrl+D or `/quit` exits. The terminal's previous screen is
restored when the application exits. On a Mac keyboard, Page Up/Down are usually
Fn+Up/Down. Option+Return works where the terminal sends Alt+Enter; `/multiline`
also explains the shortcut.

To recreate the temporary environment after it is removed, run from this folder:

```sh
python3 -m venv /private/tmp/silo-terminal-ui-venv
/private/tmp/silo-terminal-ui-venv/bin/python -m pip install -r requirements/terminal-preview.txt
```

The optional package extra `terminal` installs the same pins. Installation is a
development preparation step; the running UI never downloads dependencies.

For a noninteractive tour or a narrow-terminal check:

```sh
python3 scripts/preview_terminal.py --tour
python3 scripts/preview_terminal.py --tour --plain --width 40
```

On Windows, prepare a development environment with the same requirement file
and run its Python interpreter against `scripts/preview_terminal.py`. Windows
rendering and keyboard behavior still need native testing. `--plain`, `NO_COLOR`,
and `TERM=dumb` disable color. Full-screen mode requires an interactive terminal;
use `--tour` for redirected output. Python 3.11 or newer is supported.

## Interaction choices

- A compact SILO header names the project and identifies preview mode.
- The application occupies the whole terminal using its alternate screen.
- Conversation has its own scrollable area with distinct YOU and SILO labels.
- Activity appears inline, above the reply. It does not replace prior messages.
- Answers retain source citation tokens. `/sources` shows locators, hashes and
  sample contents separately, keeping the main conversation concise.
- Unsaved drafts show a destination and a review command. Review displays the
  complete text before the separate approval command becomes valid.
- Errors, cancellation, and empty lists explain what happened and how to continue.
- The fixed status shows readiness and the number of pending drafts.
- The message box supports editable multiline input without moving the status.
- Resizing reflows existing text and keeps the composer at the bottom.
- Color is optional and no meaning depends on it. The colored theme is dark.
- Clear resets demo state and removes the conversation from the visible area.
- Cancellation and exit wait for the sample request to stop before disposing it.

Command completion and file mentions can follow once the layout is agreed. The
preview does not pretend to stream model tokens. `--scrolling` retains the earlier
dependency-free line-input version, and `--tour` prints its sample transcript.

## Integration boundary

`terminal_ui.py` and `terminal_fullscreen.py` handle presentation;
`terminal_demo.py` owns fictional state. These remain separate from the existing
`cli.py` and the Phase 1 work being developed concurrently. The preview is not
another model harness. The full-screen controller keeps the event loop responsive
while the sample workflow runs, so cancellation and resizing remain available.

The eventual production controller should map requests to the shared
`SessionBackend` contract: `ask`, `grant`, `revoke`, `review`, `approve`, `discard`,
`clear_chat`, `cancel`, and `close`. Responses map `AgentResult.answer`, citations,
and proposals into this presentation. Progress events supply actual activity.
Folder listings come from the host broker; source details must come from its
verified metadata. The host remains responsible for approving exact bytes and
rechecking grants, sources, and destinations.

On Windows, the controller must use the contained Windows service through
`WindowsSessionAdapter`. The POSIX development backend is not a Windows
containment substitute. Cooperative cancellation on Mac and hard process
cancellation on Windows must be presented according to their actual behavior.
Code workspace controls remain unavailable until the separate runner exists.

The preview demonstrates interaction design only. Native containment, inference,
execution, and Windows installation acceptance remain separate work.

## Platform references

- [prompt_toolkit full-screen applications](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/full_screen_apps.html)
- [Python terminal size detection](https://docs.python.org/3/library/shutil.html#shutil.get_terminal_size)
- [Microsoft console virtual terminal sequences](https://learn.microsoft.com/en-us/windows/console/console-virtual-terminal-sequences)

## Production integration

The native Windows terminal now reuses this full-window layout with `TerminalClient` and the shared host backend. `--scrollback` retains the earlier presentation. The preview remains scripted; connecting the real backend does not make the portable preview an isolation or inference test. Production project/model/workflow commands are documented in [phases 3–5](SILO-REMAINING-PHASES.md). Ctrl+C in a native session terminates owned inference and requires restarting SILO before continuing. Production event-loop fixtures cover actual controller dispatch, reviewed saves, clearing, cancellation, and waiting for a request before exit.
