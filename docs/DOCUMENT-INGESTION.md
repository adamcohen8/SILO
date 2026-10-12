# Document ingestion, retrieval, and office output

Current source review: 12 October 2026. SILO reads approved document bytes through
the folder broker, records their original SHA-256, parses supported formats in
bounded workers, and returns excerpts with exact source locators. The current
registry includes UTF-8 text, PDF, DOCX, CSV, XLSX and PPTX. Word paragraphs are
not page numbers; table row metadata identifies sheets and physical rows.

## Reads and citations

`read_text` returns up to 200 lines / 32 KiB. `read_document` returns up to five
PDF pages or 200 other document units / 32 KiB, with total-unit and continuation
metadata. Unit kinds are PDF pages, DOCX paragraphs, CSV/XLSX rows, and PPTX
slides. Use further bounded reads/searches before claiming coverage of an entire
document. Copy the exact returned source token for the supporting unit.

The host checks provenance against sources actually read and revalidates source
bytes before retaining answers or approving outputs. A citation proves which
excerpt was available; it does not prove truth, complete coverage, or correct
interpretation. Document instructions and filenames cannot change authority.

## Parsing and fidelity

Optional parser pins include pypdf 6.19.0 and defusedxml 0.7.1. Dependencies are
prepared before runtime work; reading a document downloads nothing. Parser inputs
are bytes, not host paths. The portable subprocess has a ten-second deadline,
sanitized environment, closed descriptors and isolated Python invocation. POSIX
resource controls vary by platform; a subprocess alone cannot enforce containment.
The Windows session uses separately contained parser jobs and managed launch gates;
complete current-release acceptance remains pending.

Input parsing is limited to 8 MiB and extracted text to 512 KiB; broker policies
may impose a smaller input bound. PDF reads allow at most 100 pages. Image-only
and encrypted PDFs are rejected by the text parser. DOCX reads cover main-body
paragraphs/tables and reject hostile archive/XML features, macros, tracked changes
and unsupported relationships. Legacy `.doc` is unsupported. CSV/XLSX ingestion
uses literal cells; XLSX formulas are rejected and CSV cells are never evaluated.
PPTX reads slide text,
not a full visual rendering. Full Office/PDF fidelity is not claimed.

## Search, analysis, and OCR

`search_document` performs literal keyword/phrase search with source locators and
continuation positions. `search_folder` searches one explicitly requested grant,
with limits of 16 documents, 32 directories and depth six; partial coverage is
reported. This is bounded retrieval, not an embedding/vector index or exhaustive
semantic search. A partial miss cannot establish that a fact is absent.

`analyze_table` computes deterministic decimal statistics for one unique CSV/XLSX
column and selected sheet, with missing/nonnumeric counts and source metadata.
It does not evaluate formulas or arbitrary code.

`read_image_ocr` is an optional separately signed, contained image-transcription
path. OCR text is uncertain and critical numbers need source review. It does not
convert scanned PDFs; that conversion is not implemented. These OCR controls
are independent of the text-model catalog, whose image/audio inputs are disabled.

## Outputs and continuity

`propose_text` creates an unsaved new-file draft. `propose_artifact` uses bounded,
deterministic writers for DOCX, XLSX, CSV and PPTX, with explicit source metadata.
Only host review/approval saves the exact stored bytes in an editable grant;
existing documents are preserved. This produces new documents rather than editing
an arbitrary original binary document in place. Mac samples passed independent
reader/rendering checks; arbitrary Windows/Microsoft Office compatibility needs
its own qualification.

Ordinary follow-ups retain bounded in-memory context. Explicit saved projects
can persist encrypted conversation/task records, rechecking grants and source
hashes on reuse. No parser cache or retained excerpt can supply stale authority.
See [agent development](AGENT-DEVELOPMENT.md), [project/office mechanisms](SILO-REMAINING-PHASES.md),
[operating procedures](SILO-OPERATIONS.md), and [current evidence](SILO-STATUS.md).
