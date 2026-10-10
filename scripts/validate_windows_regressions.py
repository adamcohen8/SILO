"""Source-bound development regression summary; not deployment acceptance."""
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tests'), str(ROOT/'scripts')]


def main():
    if os.name != 'nt':
        raise SystemExit('Native Windows regression evaluation required')
    names = ['test_asset_integrity.AssetIntegrityTests', 'test_evaluation_install.EvaluationInstallTests',
             'test_evaluation_preflight.EvaluationPreflightTests',
             'test_agent.WindowsAgentTests', 'test_agent_instructions.AgentInstructionsTests', 'test_model.ModelTests', 'test_citations.CitationTests', 'test_folder_settings.FolderSettingsTests', 'test_mentions.MentionTests',
             'test_documents.DocumentTests', 'test_windows_container.WindowsContainerTests',
             'test_windows_contained_parsers.WindowsContainedParserTests',
             'test_windows_desktop.WindowsDesktopTests']
    result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromNames(names))
    report = {'deployment_ready': False, 'suite_names': names, 'tests_run': result.testsRun,
        'passes': result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),
        'failures': len(result.failures), 'errors': len(result.errors),
        'skips': [{'test': str(test), 'reason': reason} for test, reason in result.skipped],
        'regressions_passed': result.wasSuccessful()}
    files = list((ROOT/'src/local_ai_appliance').glob('*.py')) + [ROOT/'tests'/name for name in
        ('test_agent.py','test_model.py','test_citations.py','test_documents.py','test_windows_container.py',
         'test_windows_contained_parsers.py','test_windows_desktop.py','test_folder_settings.py','test_mentions.py',
         'test_agent_instructions.py')]+[ROOT/'AGENTS.md', ROOT/'scripts/contained_agent_worker.py']
    files += [ROOT/'tests'/name for name in ('test_asset_integrity.py','test_evaluation_install.py','test_evaluation_preflight.py')]
    report['source_hashes'] = {str(path.relative_to(ROOT)).replace('\\','/'): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    path = ROOT/'artifacts/windows-evaluation/windows-regressions.json'
    path.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('tests_run','passes','failures','errors','skips','regressions_passed')}))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
