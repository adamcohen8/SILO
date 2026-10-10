import unittest
from local_ai_appliance.agent import DocumentAgent, Source
from local_ai_appliance.folders import AccessDenied


class CitationTests(unittest.TestCase):
    def setUp(self):
        self.source = Source("S1", "folder", "synthetic.txt", "a"*64, 2, 4, "Two.\nThree.\nFour.\n")

    def test_checked_locator_and_whole_excerpt_are_distinct(self):
        citations = DocumentAgent._citations("Fact [source:S1:line:3] and context [source:S1]", [self.source])
        self.assertEqual([s.locator for s in citations], ["line 3", "line 2-4"])
        self.assertEqual(citations[0].reference, "[source:S1:line:3]")
        self.assertEqual(citations[0].sha256, self.source.sha256)
        self.assertEqual(citations[1], self.source)

    def test_unread_wrong_kind_outside_or_malformed_locator_rejected(self):
        for token in ("S99:line:3", "S1:page:3", "S1:line:1", "S1:line:5",
                      "S1:line:4-2", "S1:line:0", "S1:line:03", "S1:line:+3", "S1:line:3:extra"):
            with self.subTest(token=token), self.assertRaises(AccessDenied):
                DocumentAgent._citations(f"Fact [source:{token}]", [self.source])

    def test_pdf_page_and_word_paragraph_keep_their_unit_types(self):
        for kind in ("page", "paragraph"):
            source = Source("S1", "folder", "synthetic", "b"*64, 2, 3, "Synthetic excerpt", kind)
            citation = DocumentAgent._citations(f"Fact [source:S1:{kind}:2-3]", [source])[0]
            self.assertEqual(citation.locator, f"{kind} 2-3")
            self.assertEqual(citation.unit_kind, kind)
