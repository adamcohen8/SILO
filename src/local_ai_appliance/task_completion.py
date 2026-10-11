"""Conservative completion checks for explicit document-workflow requests.

Only the current user prompt supplies requirements. This is not a general
intent classifier or a factual-support checker, and it grants no authority.
"""
from dataclasses import dataclass
import re

from .folders import AccessDenied

PROPOSAL_MISSING = 'Requested draft proposal was not created'
EXACT_CITATION_MISSING = 'Requested exact source citation was omitted'


class TaskIncomplete(AccessDenied):
    pass


@dataclass(frozen=True)
class TaskRequirements:
    proposal_names: tuple[str, ...] = ()
    citation_units: tuple[str, ...] = ()

    @classmethod
    def from_prompt(cls, prompt):
        names, units = [], set()
        prompt = re.sub(r'```.*?```', '', prompt, flags=re.S)
        prompt = re.sub(r'(?<!\w)([\"\'])([^\"\']*\s[^\"\']*)\1', '', prompt)
        for clause in re.split(r'[;\n]+|(?<=[.!?])\s+', prompt):
            # Preserve quoted filenames, but do not interpret quoted prose as
            # task requirements. Documents/history never enter this parser.
            clause = clause.strip()
            action = re.match(r'(?i)^(?:(?:please|then|and then)\s+|(?:can|could|would) you (?:please )?)*'
                              r'(propose|create|write|draft|prepare)\b(.*)', clause)
            if action and (action[1].lower() == 'propose' or
                           re.search(r'(?i)\bdrafts?\b|\bfor (?:user )?review\b', action[2])):
                # Require an explicit output filename; prose-only and code
                # requests do not become mandatory proposal operations.
                if not re.match(r'(?i)\s+(?:python|code|a (?:script|program))\b', action[2]):
                    match = re.match(r'(?i)\s+(?:(?:a|an|new|text|draft|file|document|named|called)\s+)*[\"\'`]?'
                                     r'([\w-][\w.-]{0,120}\.(?:md|txt|csv|docx|xlsx|pptx))(?![\w-]|[./\\][\w])', action[2])
                    if match and match[1].casefold() not in {n.casefold() for n in names}:
                        names.append(match[1])
            if re.match(r'(?i)^(?:please\s+)?(?:do not|don\'t|never)\b', clause):
                continue
            citation_request = re.search(
                r'(?i)(?:^|\band\s+)(?:(?:please|then)\s+|(?:can|could|would) you (?:please )?)*'
                r'(?:cite\b[^.!?]*\bexact\b|(?:give|provide|include|use)\b[^.!?]*\bexact\b[^.!?]*\bcitations?\b)', clause)
            if citation_request and not re.search(r'(?i)\b(?:without|not|no)\b[^.!?]*\bexact\b', clause):
                for plural, singular in (('lines?', 'line'), ('pages?', 'page'),
                                         ('paragraphs?', 'paragraph'), ('rows?', 'row'), ('slides?', 'slide')):
                    if re.search(r'(?i)\b'+plural+r'\b', clause):
                        units.add(singular)
        return cls(tuple(names), tuple(sorted(units)))

    def validate(self, citations, proposals):
        actual = {getattr(p, 'destination_path', '').replace('\\', '/').casefold() for p in proposals}
        if any(name.casefold() not in actual for name in self.proposal_names):
            raise TaskIncomplete(PROPOSAL_MISSING)
        for kind in self.citation_units:
            matching = [s for s in citations if s.unit_kind == kind]
            if not matching or any(s.cited_start is None or s.cited_end is None for s in matching):
                raise TaskIncomplete(EXACT_CITATION_MISSING)

    def instruction(self):
        from .model import json_bytes
        return ('Complete the explicit requested document workflow. Named output files: '
                + json_bytes(list(self.proposal_names)).decode('utf-8')
                + ' Use propose_text or propose_artifact for these files; plain reply text is not a pending proposal. '
                  'Never save or approve. Required exact citation unit kinds: '
                + json_bytes(list(self.citation_units)).decode('utf-8')
                + ' Copy exact supporting locator tokens returned by reads. Whole-excerpt tokens do not satisfy '
                  'these exact requests. If an excerpt only contains a heading, read/search further bounded '
                  'ranges in the requested document. Do not invent facts, locators, grants or proposals.')
