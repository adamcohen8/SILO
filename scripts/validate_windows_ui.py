"""Drive the actual Qt window, contained GPU model and reviewed synthetic saves."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tests')]
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from local_ai_appliance.windows_desktop import WindowsAssistantWindow, configure_fonts
from local_ai_appliance.folders import AccessDenied
from synthetic_documents import pdf_bytes, docx_bytes


def main():
    state = ROOT/'artifacts/windows-ui'
    state.mkdir(parents=True, exist_ok=True)
    report = {'evaluation_only': True, 'checks': {}, 'errors': []}
    app = QApplication([])
    configure_fonts(app)
    app.setQuitOnLastWindowClosed(False)
    window = WindowsAssistantWindow(ROOT, folder_settings=False)
    window.show()
    ticks = []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(time.monotonic()))
    timer.start(100)
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
        report['checks']['starts_without_grants'] = not window.workspace.broker.folders()
        with tempfile.TemporaryDirectory(prefix='ui-synthetic-', dir=state) as temp:
            root = Path(temp)
            ro, rw = root/'Reference', root/'Drafts'
            ro.mkdir()
            rw.mkdir()
            (ro/'capacity.txt').write_text('Fictional storage approval note.\nThe approved capacity is 37 crates.\n', encoding='utf-8')
            (ro/'training.pdf').write_bytes(pdf_bytes())
            (ro/'training.docx').write_bytes(docx_bytes())
            original = (ro/'capacity.txt').read_bytes()
            window.grant(str(ro), 'read-only')
            window.grant(str(rw), 'editable')
            folders = {f.name: f for f in window.workspace.broker.folders()}
            window.select_folder(folders['Reference'].id)
            for filename in ('training.pdf', 'training.docx'):
                item = next(window.files.item(i) for i in range(window.files.count()) if filename in window.files.item(i).text())
                window.open_entry(item)
                idle()
                report['checks']['file_question_'+Path(filename).suffix[1:]] = filename in window.prompt.toPlainText()
            before = len(ticks)
            window.prompt.setPlainText('Read capacity.txt in Reference. What is the approved capacity? Cite the exact supporting line.')
            window.ask_button.click()
            report['checks']['grant_controls_disabled_during_request'] = not window.read_zone.isEnabled()
            idle()
            assert window.last_result, window.status.text()
            report['checks']['question_correct_and_cited'] = ('37' in window.answer.toPlainText() and window.citations.count() >= 1
                and window.last_result.citations[0].path == 'capacity.txt'
                and window.last_result.citations[0].cited_start == 2)
            report['checks']['ui_responsive_during_model_work'] = len(ticks)-before >= 3
            window.prompt.setPlainText('Read capacity.txt in Reference. Propose a new capacity-summary.md in Drafts. '
                'Summarize the approved capacity in one sentence. Use capacity.txt as the source for the proposal. '
                'Do not save anything. Cite the supporting line in your answer.')
            window.ask_button.click()
            idle()
            assert window.last_result and window.last_result.proposals, window.status.text()+' '+window.answer.toPlainText()
            report['checks']['draft_text_visible_without_saving'] = (not list(rw.iterdir())
                and all(p.text in window.answer.toPlainText() for p in window.last_result.proposals)
                and bool(window.workspace.pending_proposals()))
            window.open_draft_review()
            dialog = window.review_dialog
            report['checks']['model_proposal_requires_human_review'] = not dialog.save_button.isEnabled()
            dialog.review_button.click(); idle()
            assert dialog.reviewed, dialog.notice.text()
            original_review = dialog.reviewed.id
            dialog.text.setPlainText(dialog.text.toPlainText()+'\nSynthetic user review note.\n')
            report['checks']['editing_invalidates_review'] = (not dialog.save_button.isEnabled()
                and all(p.id != original_review for p in window.workspace.pending_proposals()))
            dialog.review_button.click(); idle()
            assert dialog.reviewed, dialog.notice.text()
            reviewed = dialog.reviewed
            expected_bytes = reviewed.text.encode('utf-8')
            report['checks']['no_file_before_save_click'] = not (rw/reviewed.destination_path).exists()
            dialog.save_button.click(); idle()
            report['checks']['reviewed_copy_exact_bytes'] = (rw/reviewed.destination_path).read_bytes() == expected_bytes
            try:
                window.workspace.approve(reviewed.id)
                report['checks']['approval_single_use'] = False
            except AccessDenied:
                report['checks']['approval_single_use'] = True
            report['checks']['source_unchanged'] = (ro/'capacity.txt').read_bytes() == original
            window.grab().save(str(state/'interface-tested.png'))
            # Actual model reads both contained document formats through the UI.
            window.prompt.setPlainText('Read training.pdf and training.docx in Reference. What training deadline do they give? '
                                       'Cite the exact page in the PDF and paragraph in the DOCX for the deadline.')
            window.ask_button.click()
            idle()
            assert window.last_result, window.status.text()
            report['document_answer'] = {'answer': window.answer.toPlainText(),
                'sources': [{'path': s.path, 'locator': s.locator, 'reference': s.reference}
                            for s in window.last_result.citations]}
            report['checks']['model_pdf_and_docx_citations'] = ('15 October' in ' '.join(window.answer.toPlainText().split())
                and {'page', 'paragraph'} <= {s.unit_kind for s in window.last_result.citations})
            # Revision authority remains host controlled and clears stale content.
            window.revoke(folders['Reference'].id)
            report['checks']['revoke_clears_answer_sources_drafts'] = (not window.answer.toPlainText()
                and window.citations.count() == 0 and not window.workspace.pending_proposals())
            for folder in tuple(window.workspace.broker.folders()):
                window.revoke(folder.id)
        report['server_token'] = window.session.evidence['server_token']
        report['worker_tokens'] = window.session.evidence['worker_tokens']
        report['parser_tokens'] = window.session.evidence['parser_tokens']
        report['checks']['all_workers_zero_capabilities'] = all(
            t['capability_count'] == 0 for t in report['worker_tokens']+report['parser_tokens'])
        # Reproduce selecting the outer extracted download folder, where the
        # public README is one level down in a similarly named directory.
        window.grant(str(ROOT.parent), 'read-only')
        folder = window.workspace.broker.folders()[0]
        from local_ai_appliance.windows_workspace import BrokerSession
        preview = BrokerSession(window.workspace).inventory()
        report['checks']['nested_project_directory_in_initial_inventory'] = any(
            e['name'] == ROOT.name and e['kind'] == 'directory'
            for p in preview for e in p.get('entries', []))
        window.prompt.setPlainText('Summarize the readme in the folder.')
        window.ask_button.click()
        idle()
        assert window.last_result, window.status.text()
        report['readme_answer'] = {'answer': window.answer.toPlainText(),
            'sources': [{'path': s.path, 'locator': s.locator} for s in window.last_result.citations]}
        report['checks']['nested_readme_summary_has_verified_source'] = any(
            s.path == ROOT.name+'/README.md' for s in window.last_result.citations)
        window.grab().save(str(state/'nested-readme-tested.png'))
        window.revoke(folder.id)
        # Cancel an actual active request, ensure owned GPU job stops and restart
        # cannot receive the old result. The model is closed for final cleanup.
        window.prompt.setPlainText('Write a long fictional story about a training exercise.')
        window.ask_button.click()
        wait(lambda: window.session.active is not None)
        window.cancel_button.click()
        idle()
        report['checks']['cancel_discards_result_and_stops_model'] = (not window.session.ready
            and window.last_result is None and not window.workspace.pending_proposals())
    except Exception:
        report['errors'].append(traceback.format_exc())
    finally:
        window.close()
        wait(lambda: window.cleaned and not window.jobs, timeout=90)
        report['checks']['temporary_permissions_removed'] = window.session.evidence.get('cleanup_complete') is True
        report['source_sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT/'src/local_ai_appliance').glob('*.py'))}
        (state/'interface-results.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps({'checks': report['checks'], 'errors': report['errors']}, indent=2), flush=True)
    return int(bool(report['errors']) or not all(report['checks'].values()))

if __name__ == '__main__':
    raise SystemExit(main())
