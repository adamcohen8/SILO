"""Actual Qt/GPU-session checks of public project directory listings."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtWidgets import QApplication
from local_ai_appliance.windows_desktop import WindowsAssistantWindow, configure_fonts


def main():
    app = QApplication([])
    configure_fonts(app)
    app.setQuitOnLastWindowClosed(False)
    window = WindowsAssistantWindow(ROOT, folder_settings=False)
    window.show()
    report = {'evaluation_only': True, 'checks': {}, 'answers': {}, 'errors': []}

    def wait(predicate, timeout=190):
        started = time.monotonic()
        last_status = None
        while time.monotonic()-started < timeout:
            app.processEvents()
            if window.status.text() != last_status:
                last_status = window.status.text()
                print(last_status, flush=True)
            if predicate():
                return
            time.sleep(.02)
        raise TimeoutError('UI wait timed out: '+window.status.text())

    def idle():
        wait(lambda: not window.busy and not window.jobs)

    try:
        wait(lambda: window.workspace is not None or window.session.closed)
        idle()
        assert window.session.ready, window.status.text()
        report['checks']['full_gpu_ready'] = window.session.evidence.get('full_gpu') is True
        for kind, path in (('inner', ROOT), ('outer', ROOT.parent)):
            window.grant(str(path), 'read-only')
            folder = window.workspace.broker.folders()[0]
            expected_path = 'docs' if kind == 'inner' else ROOT.name+'/docs'
            expected = window.workspace.broker.list_directory(folder.id, expected_path)
            window.prompt.setPlainText('Please list the files under the docs folder')
            window.ask_button.click()
            idle()
            assert window.last_result, window.status.text()
            answer = window.answer.toPlainText()
            report['answers'][kind] = {'answer': answer, 'expected_path': expected_path,
                'expected_files': [e['name'] for e in expected['entries']],
                'model_calls': window.last_result.model_calls, 'tool_calls': window.last_result.tool_calls}
            report['checks'][kind+'_all_names_listed'] = (not expected['truncated']
                and all(e['name'] in answer for e in expected['entries']))
            report['checks'][kind+'_no_document_read_or_draft'] = (not window.last_result.citations
                and not window.last_result.proposals)
            report['checks'][kind+'_verified_listing_without_inference'] = window.last_result.model_calls == 0
            window.grab().save(str(ROOT/'artifacts/windows-ui'/('docs-listing-'+kind+'.png')))
            window.revoke(folder.id)
        tokens = window.session.evidence['worker_tokens']
        report['checks']['no_graph_or_parser_for_name_listing'] = not tokens and not window.session.evidence['parser_tokens']
        report['worker_tokens'] = tokens
    except Exception:
        report['errors'].append(traceback.format_exc())
    finally:
        window.close()
        wait(lambda: window.cleaned and not window.jobs, timeout=90)
        report['checks']['cleanup_complete'] = window.session.evidence.get('cleanup_complete') is True
        report['source_hashes'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT/'src/local_ai_appliance').glob('*.py'))}
        (ROOT/'artifacts/windows-ui/docs-listing-results.json').write_text(
            json.dumps(report, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({'checks': report['checks'], 'errors': report['errors']}, indent=2), flush=True)
    return int(bool(report['errors']) or not all(report['checks'].values()))


if __name__ == '__main__':
    raise SystemExit(main())
