"""Drive the actual Qt window, contained GPU model and reviewed synthetic saves."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile, contextlib
import time
import threading
import subprocess
import traceback

import argparse
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', type=Path, required=True, help='Disposable installed payload/app')
parser.add_argument('--evidence', type=Path, required=True, help='New private evidence directory outside source and installation state')
parser.add_argument('--model-id', help='Require this exact loaded profile before testing')
args = parser.parse_args()
ROOT, EVIDENCE = args.root.resolve(), args.evidence.resolve()
if ROOT == EVIDENCE or ROOT in EVIDENCE.parents or EVIDENCE in ROOT.parents:
    raise SystemExit('Keep synthetic grants and evidence outside the source/payload tree.')
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tests'), str(Path(__file__).resolve().parent)]
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from local_ai_appliance.windows_desktop import WindowsAssistantWindow, configure_fonts
from local_ai_appliance.folders import AccessDenied
from synthetic_documents import pdf_bytes, docx_bytes
from windows_model_assertions import exact_capacity, exact_deadlines, named_capacity_proposal
from windows_validation_support import host_connected
from local_ai_appliance.evaluation_install import installed_config
from local_ai_appliance.project_store import LocalVault
from local_ai_appliance.agent_instructions import load_instructions
config = installed_config(ROOT)
if config is None:
    raise SystemExit('A disposable standalone installation is required.')
installation_state = Path(config['state_root']).resolve()
installed_identity = json.loads((installation_state.parent/'active.json').read_bytes())
if ROOT.parent.parent != installation_state.parent/'versions'/installed_identity['version']:
    raise SystemExit('Qt validation requires the active installed version.')
if EVIDENCE == installation_state or EVIDENCE in installation_state.parents or installation_state in EVIDENCE.parents:
    raise SystemExit('Keep test evidence and grants outside private installation state.')
if (installation_state/'projects').exists():
    vault = LocalVault(installation_state/'projects', windows_validation=True)
    try:
        if vault.get('active-project'):
            raise SystemExit('Close the saved project in this disposable test installation before validation.')
    finally:
        vault.close()


def main():
    state = EVIDENCE/'desktop'
    state.mkdir(parents=True, exist_ok=False)
    report = {'test_driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'evaluation_only': True, 'deployment_ready': False, 'full_isolation_accepted': False, 'checks': {}, 'errors': []}
    started = time.monotonic()
    report['host_before_inference'] = host_connected(report, 'before')
    app = QApplication([])
    configure_fonts(app)
    app.setQuitOnLastWindowClosed(False)
    window = WindowsAssistantWindow(ROOT, folder_settings=False)
    window.show()
    ticks = []
    gpu_samples = []
    stop_samples = threading.Event()
    def sample_gpu():
        while not stop_samples.is_set():
            try:
                v = subprocess.check_output(['nvidia-smi.exe','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True,timeout=8)
                gpu_samples.append({'elapsed_seconds': round(time.monotonic()-started,3),'used_mib':int(v.strip())})
            except Exception: pass
            stop_samples.wait(1)
    gpu_thread = threading.Thread(target=sample_gpu,daemon=True)
    gpu_thread.start()
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
        report['startup_seconds'] = round(time.monotonic()-started, 3)
        report['profile'] = window.session.model_profile
        report['installed_identity'] = installed_identity
        report['connectivity_support_sha256'] = hashlib.sha256(Path(sys.modules[host_connected.__module__].__file__).read_bytes()).hexdigest()
        report['validation_support_sha256'] = hashlib.sha256(Path(sys.modules[exact_capacity.__module__].__file__).read_bytes()).hexdigest()
        if args.model_id is not None:
            report['checks']['requested_model_loaded'] = report['profile']['id'] == args.model_id
            assert report['checks']['requested_model_loaded'], 'Loaded profile differs from requested test profile'
        report['host_during_inference'] = host_connected(report, 'during')
        report['checks']['test_preferences_loaded'] = window.session.instructions == load_instructions(window.session.state)
        report['checks']['full_gpu_ready'] = window.session.evidence.get('full_gpu') is True
        report['checks']['starts_without_grants'] = not window.workspace.broker.folders()
        project = window.project_backend.create_project('Synthetic desktop review')
        window.project_changed()
        report['project_id'] = project.id
        with contextlib.nullcontext(str(state/'synthetic-fixture')) as temp:
            root = Path(temp)
            root.mkdir(exist_ok=False)
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
            report['checks']['question_correct_and_cited'] = exact_capacity(window.last_result)
            report['checks']['ui_responsive_during_model_work'] = len(ticks)-before >= 3
            window.project_backend.close_project(); window.project_changed()
            outcome = window.project_backend.open_project(project.id); window.project_changed()
            report['checks']['saved_project_reopens_verified_context_and_grants'] = (not outcome['context_invalidated'] and outcome['restored_grants'] == 2 and bool(window.session.conversation.turns) and not window.workspace.pending_proposals())
            folders = {f.name: f for f in window.workspace.broker.folders()}
            # A missing real-model proposal must not hide independent later stages.
            try:
                window.prompt.setPlainText('Read capacity.txt in Reference. Propose a new capacity-summary.md in Drafts. '
                    'Summarize the approved capacity in one sentence. Use capacity.txt as the source for the proposal. '
                    'Do not save anything. Cite the supporting line in your answer.')
                window.ask_button.click()
                idle()
                report['checks']['named_sourced_unsaved_proposal'] = named_capacity_proposal(window.last_result, rw, hashlib.sha256(original).hexdigest())
                assert report['checks']['named_sourced_unsaved_proposal'], window.status.text()+' '+window.answer.toPlainText()
                report['checks']['draft_text_visible_without_saving'] = (not list(rw.iterdir())
                    and window.drafts.count() == len(window.last_result.proposals)
                    and bool(window.workspace.pending_proposals()))
                window.open_draft_review()
                dialog = window.review_dialog
                report['checks']['model_proposal_requires_human_review'] = not dialog.save_button.isEnabled()
                report['checks']['exact_draft_text_visible_in_review'] = dialog.text.toPlainText() == window.last_result.proposals[0].text
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
            except Exception:
                report['checks']['text_draft_review_flow'] = False
                report['errors'].append(traceback.format_exc())
                if window.review_dialog:
                    window.review_dialog.close()
                window.clear_chat_button.click(); idle()
            snapshot = window.workspace.open_text(folders['Reference'].id, 'capacity.txt')
            stale = window.workspace.propose(folders['Drafts'].id, 'stale-review.md', 'Synthetic pending copy', snapshot)
            window.host_backend.review(stale.id)
            (ro/'capacity.txt').write_bytes(original+b'Host-created synthetic change.\n')
            try:
                window.host_backend.approve(stale.id)
                report['checks']['source_drift_refuses_reviewed_save'] = False
            except AccessDenied:
                report['checks']['source_drift_refuses_reviewed_save'] = not (rw/'stale-review.md').exists()
            (ro/'capacity.txt').write_bytes(original)
            collision = window.workspace.propose(folders['Drafts'].id, 'collision.md', 'Synthetic pending copy')
            window.host_backend.review(collision.id)
            (rw/'collision.md').write_bytes(b'SYNTHETIC EXISTING COPY')
            try:
                window.host_backend.approve(collision.id)
                report['checks']['destination_collision_preserves_existing_copy'] = False
            except AccessDenied:
                report['checks']['destination_collision_preserves_existing_copy'] = (rw/'collision.md').read_bytes() == b'SYNTHETIC EXISTING COPY'

            window.resize(1000, 760); app.processEvents()
            window.grab().save(str(state/'interface-tested.png'))
            report['checks']['resize_window_functional'] = window.width() == 1000 and window.height() == 760
            window.clear_chat_button.click(); idle()
            report['checks']['clear_chat_keeps_grants_and_removes_context'] = (not window.answer.toPlainText() and window.citations.count() == 0 and len(window.workspace.broker.folders()) == 2 and not window.workspace.pending_proposals())
            # Exact Office bytes remain pending until separate artifact review/save.
            (ro/'data.csv').write_text('Asset,Capacity kg\nOne,48\nTwo,60\n',encoding='utf-8')
            artifact_evidence=EVIDENCE/'office-approved'
            artifact_evidence.mkdir(exist_ok=False)
            report['office_artifacts']=[]
            for kind,request in (
                ('docx','Create capacity.docx in Drafts with title Capacity study and one short Findings paragraph stating both asset capacities and their total. No table.'),
                ('xlsx','Create capacity.xlsx in Drafts containing Asset and Capacity kg columns, the two source rows, and a total row of 108 kg.'),
                ('pptx','Create capacity.pptx in Drafts with one slide showing One 48 kg, Two 60 kg, and Total 108 kg.')):
                before_files={p.name for p in rw.iterdir()}
                window.prompt.setPlainText('Read data.csv in Reference. '+request+' Use propose_artifact with structured content and the verified source. Do not save it. Cite data.csv.')
                window.ask_button.click();idle()
                if not window.last_result or not window.last_result.proposals:
                    report['checks']['office_'+kind+'_model_proposal']=False
                    report['office_artifacts'].append({'kind':kind,'status':'failed','answer':window.answer.toPlainText()})
                    window.clear_chat_button.click();idle();continue
                proposal=next((p for p in window.last_result.proposals if p.destination_path.endswith('.'+kind)),None)
                if proposal is None:
                    report['checks']['office_'+kind+'_correct_format']=False
                    window.clear_chat_button.click();idle();continue
                report['checks']['office_'+kind+'_unsaved']=bool(proposal.data) and {p.name for p in rw.iterdir()}==before_files
                index=next(i for i in range(window.drafts.count()) if proposal.destination_path in window.drafts.item(i).text())
                window.drafts.setCurrentRow(index);window.open_draft_review();dialog=window.review_dialog
                report['checks']['office_'+kind+'_review_required']=not dialog.save_button.isEnabled()
                dialog.review_button.click();idle();assert dialog.reviewed,dialog.notice.text()
                exact=dialog.proposal;dialog.save_button.click();idle()
                approved=(rw/exact.destination_path).read_bytes()
                report['checks']['office_'+kind+'_exact_bytes']=approved==exact.data
                (artifact_evidence/('capacity.'+kind)).write_bytes(approved)
                parsed=window.workspace.open_document(folders['Drafts'].id,exact.destination_path)
                content='\n'.join(parsed.units)
                report['checks']['office_'+kind+'_contained_roundtrip']='48' in content and '60' in content and (kind=='docx' or '108' in content)
                report['office_artifacts'].append({'kind':kind,'sha256':hashlib.sha256(approved).hexdigest(),'bytes':len(approved),'preview':exact.text})
                window.clear_chat_button.click();idle()
            from local_ai_appliance.workflows import Workflows,ScheduleEngine
            workflows=Workflows(window.project_backend)
            workflows.save('capacity-review','Read capacity.txt in Reference. Propose scheduled-capacity.md in Drafts summarizing its approved capacity. Do not save it.')
            now=int(time.time());schedule=ScheduleEngine(window.project_backend,clock=lambda:now)
            schedule_id=schedule.create('capacity-review',interval_seconds=60,first_due=now)
            before_files={p.name for p in rw.iterdir()}
            events=schedule.tick()
            report['schedule_events']=events
            report['checks']['schedule_real_model_runs_without_approving_exports']=bool(events) and events[0]['state']=='complete' and events[0]['pending_reviews']>0 and {p.name for p in rw.iterdir()}==before_files
            items=schedule.listing();items[schedule_id]['state']='running';schedule._save(items)
            events=schedule.tick()
            report['checks']['uncertain_schedule_slot_not_replayed']=bool(events) and events[0]['state']=='unknown' and not schedule.listing()[schedule_id]['enabled']
            schedule.reconcile(schedule_id)
            report['checks']['schedule_reconciliation_skips_slot']=schedule.listing()[schedule_id]['next_due']==now+60
            schedule.cancel(schedule_id);window.clear_chat_button.click();idle()
            # Actual model reads both contained document formats through the UI.
            window.prompt.setPlainText('Read training.pdf and training.docx in Reference. What training deadline do they give? '
                                       'Cite the exact page in the PDF and paragraph in the DOCX for the deadline.')
            window.ask_button.click()
            idle()
            assert window.last_result, window.status.text()
            report['document_answer'] = {'answer': window.answer.toPlainText(),
                'sources': [{'path': s.path, 'locator': s.locator, 'reference': s.reference}
                            for s in window.last_result.citations]}
            report['checks']['model_pdf_and_docx_citations'] = exact_deadlines(window.last_result)
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
        # Cancel an actual active request, ensure owned GPU job stops and restart
        # cannot receive the old result. The model is closed for final cleanup.
        window.prompt.setPlainText('Write a long fictional story about a training exercise.')
        window.ask_button.click()
        wait(lambda: window.session.active is not None)
        window.cancel_button.click()
        idle()
        report['checks']['cancel_discards_result_and_stops_model'] = (not window.session.ready
            and window.last_result is None and not window.workspace.pending_proposals())
        window.restart_button.click(); idle()
        report['checks']['restart_after_cancel_ready_without_old_result'] = window.session.ready and window.last_result is None
    except Exception:
        report['errors'].append(traceback.format_exc())
    finally:
        window.close()
        wait(lambda: window.cleaned and not window.jobs, timeout=90)
        report['checks']['temporary_permissions_removed'] = window.session.evidence.get('cleanup_complete') is True
        report['host_after_inference'] = host_connected(report, 'after')
        report['checks']['host_connectivity_preserved'] = all(report.get(key) for key in ('host_before_inference','host_during_inference','host_after_inference'))
        stop_samples.set(); gpu_thread.join(timeout=10)
        report['gpu_samples'] = gpu_samples
        report['peak_gpu_used_mib'] = max((v['used_mib'] for v in gpu_samples),default=None)
        report['verification_route'] = 'installed native Qt window and real AppContainer/GPU inference with offscreen rendering; manual display scaling and host console keys not qualified'
        report['source_sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT/'src/local_ai_appliance').glob('*.py'))}
        (state/'interface-results.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps({'checks': report['checks'], 'errors': report['errors']}, indent=2), flush=True)
    return int(bool(report['errors']) or not all(report['checks'].values()))

if __name__ == '__main__':
    raise SystemExit(main())
