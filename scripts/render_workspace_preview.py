"""Render a reproducible UI preview using synthetic documents only."""

import argparse
from pathlib import Path
import tempfile

from PySide6.QtWidgets import QApplication

from local_ai_appliance.desktop import WorkspaceWindow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts/workspace-preview.png"))
    parser.add_argument("--empty", action="store_true")
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    window = WorkspaceWindow()
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory).resolve()
        if not args.empty:
            reference = base / "Reference documents"
            drafts = base / "Working drafts"
            reference.mkdir()
            drafts.mkdir()
            (reference / "example-procedure.md").write_text(
                "# Example procedure\n\n"
                "This is a synthetic document for interface testing.\n"
                "It contains no operational or controlled information.\n\n"
                "1. Check the source document.\n"
                "2. Record the relevant requirements.\n"
                "3. Prepare a draft for review.\n", encoding="utf-8")
            window.add_folder(str(reference), "read-only")
            window.add_folder(str(drafts), "editable")
            window.read_only.list.setCurrentRow(0)
            window.open_entry(window.files.item(0))
            window.draft.setPlainText(window.source.text.replace(
                "3. Prepare a draft for review.\n",
                "3. Prepare a draft with source citations.\n4. Review changes before saving a new copy.\n"))
            window.review_draft()
        window.show()
        app.processEvents()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if not window.grab().save(str(args.output.resolve())):
            raise RuntimeError("Preview image could not be saved")
        window.close()
        app.processEvents()
    print(args.output.resolve())


if __name__ == "__main__":
    main()
