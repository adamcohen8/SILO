"""Prevent false passes in the native model validation ledger."""
from pathlib import Path
from types import SimpleNamespace as Record
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from windows_model_assertions import exact_capacity, exact_deadlines, named_capacity_proposal


def source(path='capacity.txt', kind='line', start=2, end=2):
    return Record(path=path, unit_kind=kind, cited_start=start, cited_end=end)


def result(answer='37 crates.', citations=None, proposals=()):
    return Record(answer=answer, citations=[source()] if citations is None else citations,
                  proposals=proposals)


class NativeModelAssertionsTests(unittest.TestCase):
    def test_capacity_requires_fact_units_and_exact_supporting_line(self):
        self.assertTrue(exact_capacity(result('The capacity is 37\u202fcrates.')))
        for candidate in (None, result('37 boxes.'), result('137 crates.'), result('Heading.'),
                          result(citations=[]), result(citations=[source(start=None,end=None)]),
                          result(citations=[source(start=1,end=2)]),
                          result(citations=[source(start=1,end=1)]),
                          result(citations=[source(path='other.txt')]),
                          result(citations=[source(kind='page')])):
            with self.subTest(candidate=candidate): self.assertFalse(exact_capacity(candidate))

    def test_both_document_deadlines_need_the_actual_page_and_paragraph(self):
        citations=[source('training.pdf','page'),source('training.docx','paragraph')]
        self.assertTrue(exact_deadlines(result('15 October 2026.',citations)))
        for candidate in (None,result('16 October 2026.',citations),
                          result('15 October 2026.',citations[:1]),
                          result('15 October 2026.',[source('training.pdf','page',1,1),citations[1]]),
                          result('15 October 2026.',[citations[0],source('training.docx','paragraph',None,None)])):
            with self.subTest(candidate=candidate): self.assertFalse(exact_deadlines(candidate))

    def test_named_sourced_proposal_is_unsaved_and_unique(self):
        with tempfile.TemporaryDirectory(prefix='silo-model-assert-') as temp:
            drafts=Path(temp)
            provenance=Record(path='capacity.txt',sha256='a'*64)
            proposal=Record(destination_path='capacity-summary.md',text='37 crates. [source:S1:line:2]',source=provenance)
            self.assertTrue(named_capacity_proposal(result(proposals=[proposal]),drafts,'a'*64))
            for candidate in (None,result(proposals=[]),result(proposals=[proposal,proposal]),
                              result(proposals=[Record(destination_path=proposal.destination_path,text=proposal.text,source=Record(path='other.txt',sha256='a'*64))]),
                              result(proposals=[Record(destination_path=proposal.destination_path,text=proposal.text,source=Record(path='capacity.txt',sha256='b'*64))]),
                              result(proposals=[Record(destination_path='wrong.md',text=proposal.text,source=provenance)]),
                              result(proposals=[Record(destination_path=proposal.destination_path,text='37 crates.',source=None)]),
                              result(proposals=[Record(destination_path=proposal.destination_path,text='137 crates. [source:S1]',source=provenance)])):
                with self.subTest(candidate=candidate): self.assertFalse(named_capacity_proposal(candidate,drafts,'a'*64))
            (drafts/'capacity-summary.md').write_text(proposal.text)
            self.assertFalse(named_capacity_proposal(result(proposals=[proposal]),drafts,'a'*64))


if __name__ == '__main__': unittest.main()
