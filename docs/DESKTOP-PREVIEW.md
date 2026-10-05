# Native folder workspace preview

This is a development interface for public/synthetic UTF-8 text, not an AI assistant or a CUI deployment. It has no model, PDF/Word parser, network-isolation enforcement, or installer. It uses native Qt widgets, not a browser or an HTML document renderer. File content and draft differences are displayed as plain text.

## Run on macOS

With Python 3.11 through 3.14, create a development environment and install the pinned optional UI dependencies. Keep the virtual environment outside cloud-synced folders if their file-provider behavior interferes with native library loading.

```sh
python3 -m venv /private/tmp/local-ai-workspace-env
/private/tmp/local-ai-workspace-env/bin/python -m pip install '.[ui]'
/private/tmp/local-ai-workspace-env/bin/local-ai-workspace
```

These are online developer setup commands. The final offline installer will supply dependencies in its signed bundle and will not run pip against the internet on the unit computer. Qt runtime redistribution and license notices must be included before packaging.

## Folder and draft workflow

1. Start with zero folder grants and no open documents.
2. Drop local folders into the read-only or editable category, or use the native Add folder picker. Remote URLs, files dropped as folders, symlinks, and overlapping grants are rejected.
3. Select an allowed folder. Double-click subfolders or UTF-8 text files to navigate and preview.
4. Draft a revision or a new document. Select an editable destination and a new filename.
5. Review the exact proposed changes, then select Save reviewed copy. Saving is a separate trusted host action; the planned agent tool facade can only propose a write.
6. Remove a folder to revoke access. The interface clears loaded source text, draft text, differences, and pending proposals. Closing the application removes all session grants.

Revisions are saved as new files. This iteration does not replace existing documents in place. Existing destinations, including files created concurrently after review, are preserved. A source digest is checked when proposing and approving a revision; stale source versions must be reloaded. This is a check at those boundaries, not a lock on external editors. Changes made to draft text, filename, or destination invalidate an existing review.

Folder listing is bounded and reports truncation. The current UI is synchronous and limits file reads/drafts to 1 MiB. PDF/Word ingestion, large-corpus search, background workers, and persistent permission settings are later work.

## Tests and reproducible preview

Run the full suite with the UI dependencies installed:

```sh
QT_QPA_PLATFORM=offscreen PYTHONPATH=src /private/tmp/local-ai-workspace-env/bin/python -m unittest discover -s tests -v
```

Without the UI dependency, desktop tests are explicitly skipped; that run is not UI validation.

Render a synthetic preview without reading personal files:

```sh
QT_QPA_PLATFORM=offscreen PYTHONPATH=src /private/tmp/local-ai-workspace-env/bin/python scripts/render_workspace_preview.py
```

Generated images are kept in the ignored `artifacts/` directory. No operational documents are included in preview fixtures.

## Windows status

The toolkit provides Windows packages, but this application still deliberately refuses Windows filesystem access. The native Windows folder adapter and GPU/transport/isolation acceptance must be implemented and tested on the target workstation before deployment.

## Dependency references

- [Pinned PySide6 Essentials 6.10.2 distribution and licensing](https://pypi.org/project/PySide6-Essentials/6.10.2/)
- [Qt native folder selection](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QFileDialog.html)
- [Qt drag/drop handling](https://doc.qt.io/qtforpython-6/overviews/qtgui-dnd.html)
