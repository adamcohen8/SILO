"""Shared hostile parser fixtures through actual AppContainer jobs."""
import os
from pathlib import Path
import tempfile
import unittest

from local_ai_appliance.windows_container import AppContainer
from local_ai_appliance.windows_workspace import ContainedWorkspace
from test_documents import DocumentTests, AVAILABLE

STATE = Path(__file__).resolve().parents[1]/'artifacts/isolation-evaluation'
PYTHON = STATE/'python'


@unittest.skipUnless(os.name == 'nt' and AVAILABLE and (PYTHON/'python.exe').exists(),
                     'Staged native interpreter and parser dependencies required')
class WindowsContainedParserTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='contained-parser-', dir=STATE)
        self.root = Path(self.temp.name)
        self.container = AppContainer(evaluation=True)
        self.container.allow_read(PYTHON, directory=True)
        self.workspace = ContainedWorkspace(self.container, PYTHON/'python.exe', {'parser_tokens': []})
        self.folder = self.workspace.grant(self.root, 'read-only')

    def tearDown(self):
        self.workspace.close()
        self.container.close()
        self.temp.cleanup()

    def parse(self, path, data):
        (self.root/path).write_bytes(data)
        return self.workspace.open_document(self.folder.id, path)

    test_pdf_pages_and_original_digest = DocumentTests.test_pdf_pages_and_original_digest
    test_word_paragraphs_and_literal_instructions = DocumentTests.test_word_paragraphs_and_literal_instructions
    test_external_relationship_rejected = DocumentTests.test_external_relationship_rejected
    test_xml_entities_and_archive_escape_rejected = DocumentTests.test_xml_entities_and_archive_escape_rejected
    test_archive_expansion_and_extracted_size_rejected = DocumentTests.test_archive_expansion_and_extracted_size_rejected
    test_bad_type_and_oversize_rejected = DocumentTests.test_bad_type_and_oversize_rejected
    test_no_text_and_encrypted_pdf_rejected = DocumentTests.test_no_text_and_encrypted_pdf_rejected
