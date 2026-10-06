"""Terminal development harness; not the offline Windows installer."""

import argparse
import sys
import unicodedata

from .agent import DocumentAgent
from .folders import AccessDenied
from .model import AgentError, LocalChatModel
from .workspace import Workspace


def terminal_text(text: str) -> str:
    """Display model/documents literally, including terminal escape controls."""
    return "".join(c if c in "\n\t" or not unicodedata.category(c).startswith("C")
                   else f"\\u{ord(c):04x}" for c in text)


def interact(workspace, agent, *, read=input, output=sys.stdout):
    reviewed = set()

    def show(text):
        print(terminal_text(text), file=output)

    show("DEVELOPMENT ONLY: UTF-8 text, local server required, OS isolation unverified.\n"
         "No folders granted. Each request starts a fresh conversation.\n"
         "/ro ABSOLUTE_FOLDER | /editable ABSOLUTE_FOLDER | /folders | /revoke ID\n"
         "/review ID | /approve ID | /discard ID | /quit\n"
         "Type a document request to call the model. Approval requires /review first.")
    while True:
        try:
            line = read("> ")
        except (EOFError, KeyboardInterrupt):
            show("Session closed.")
            return
        if not line.strip():
            continue
        try:
            if line.startswith("/"):
                command, _, argument = line.partition(" ")
                argument = argument.strip()
                if command == "/quit":
                    return
                if command in {"/ro", "/editable"}:
                    folder = workspace.grant(argument, "read-only" if command == "/ro" else "editable")
                    reviewed.clear()
                    show(f"Granted {folder.name}: {folder.access}, ID {folder.id}")
                elif command == "/folders":
                    for folder in workspace.broker.folders():
                        show(f"{folder.id}  {folder.access}  {folder.name}")
                elif command == "/revoke":
                    workspace.revoke(argument)
                    reviewed.clear()
                    show("Grant revoked; pending proposals invalidated.")
                elif command in {"/review", "/approve", "/discard"}:
                    proposals = {p.id: p for p in workspace.pending_proposals()}
                    if argument not in proposals:
                        raise AccessDenied("Pending proposal is unavailable")
                    proposal = proposals[argument]
                    if command == "/review":
                        show(f"Proposal {proposal.id}\nDestination folder ID: {proposal.destination_folder}\n"
                             f"New filename: {proposal.destination_path}\n{proposal.diff}")
                        reviewed.add(argument)
                    elif command == "/approve":
                        if argument not in reviewed:
                            raise AccessDenied("Run /review ID before approving that proposal")
                        workspace.approve(argument)
                        reviewed.discard(argument)
                        show("Saved the reviewed new copy.")
                    else:
                        workspace.discard(argument)
                        reviewed.discard(argument)
                        show("Proposal discarded.")
                else:
                    show("Unknown host command. No model call was made.")
            else:
                result = agent.run(line)
                show(result.answer)
                for source in result.citations:
                    show(f"{source.citation} folder {source.folder_id}, {source.path}, "
                         f"{source.unit_kind} {source.start_line}-{source.end_line}, SHA-256 {source.sha256}")
                for proposal in result.proposals:
                    show(f"Pending proposal {proposal.id}; /review {proposal.id}")
        except (AccessDenied, AgentError) as e:
            show(f"Request stopped: {e}")


def main():
    parser = argparse.ArgumentParser(description="Local document agent development harness (POSIX text only)")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--model", required=True, help="Alias of the model already loaded by your local server")
    args = parser.parse_args()
    workspace = None
    try:
        model = LocalChatModel(args.endpoint, args.model)
        workspace = Workspace()
        agent = DocumentAgent(workspace, model)
        interact(workspace, agent)
        return 0
    except (AgentError, AccessDenied, RuntimeError) as e:
        print(terminal_text(str(e)), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    finally:
        if workspace is not None:
            workspace.close()


if __name__ == "__main__":
    raise SystemExit(main())
