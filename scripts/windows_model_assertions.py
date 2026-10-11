"""Assertions for synthetic native model evidence, independent of model wording."""
import re


def exact_capacity(result):
    return bool(result and re.search(r'\b37\s+crates\b', result.answer, re.I) and any(
        s.path == 'capacity.txt' and s.unit_kind == 'line'
        and s.cited_start == s.cited_end == 2 for s in result.citations))


def exact_deadlines(result):
    if not result or '15 October' not in ' '.join(result.answer.split()):
        return False
    return all(any(s.path == path and s.unit_kind == kind
                   and s.cited_start == s.cited_end == 2 for s in result.citations)
               for path, kind in (('training.pdf', 'page'), ('training.docx', 'paragraph')))


def named_capacity_proposal(result, drafts, source_sha256):
    if not result or len(result.proposals) != 1 or any(drafts.iterdir()):
        return False
    proposal = result.proposals[0]
    return (proposal.destination_path == 'capacity-summary.md'
            and bool(re.search(r'\b37\s+crates\b', proposal.text, re.I))
            and proposal.source is not None and proposal.source.path == 'capacity.txt'
            and proposal.source.sha256 == source_sha256)
