"""Actual Qt, fresh contained graph workers and GPU session-memory checks.

Only fictional prompts and a synthetic text fixture are used. The application
does not persist history; this explicit test saves metadata-only check results.
"""
import hashlib
import json
import os
import re
from pathlib import Path
import sys
import tempfile
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
    report = {'evaluation_only': True, 'checks': {}, 'errors': []}

    def wait(predicate, timeout=190):
        started, last_status = time.monotonic(), None
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

    def ask(prompt):
        window.prompt.setPlainText(prompt)
        window.ask_button.click()
        report['checks']['clear_disabled_during_request'] = not window.clear_chat_button.isEnabled()
        idle()
        assert window.last_result, window.status.text()
        return window.last_result

    try:
        wait(lambda: window.workspace is not None or window.session.closed)
        idle()
        assert window.session.ready, window.status.text()
        report['checks']['starts_without_history'] = not window.session.conversation.turns
        server = window.session.server.info.pid
        ask('For this chat, remember my fictional project codename is ORION-27. Reply briefly.')
        result = ask('What project codename did I give you? Reply briefly.')
        print(json.dumps({'synthetic_recall_answer': result.answer}, ensure_ascii=True), flush=True)
        report['checks']['follow_up_recalls_previous_turn'] = 'ORION27' in re.sub(r'[^A-Z0-9]', '', result.answer.upper())
        report['checks']['transcript_retains_both_turns'] = (len(result.conversation) == 2
            and 'You\n' in window.answer.toPlainText() and not window.prompt.toPlainText())
        window.clear_chat_button.click()
        report['checks']['clear_erases_memory_and_display'] = (not window.session.conversation.turns
            and not window.answer.toPlainText() and not window.prompt.toPlainText())
        report['checks']['clear_keeps_model_running'] = window.session.server.info.pid == server and window.session.ready
        result = ask("What project codename did I give you? If it isn't in this conversation, say 'not provided'. Reply briefly.")
        report['checks']['cleared_codename_is_not_remembered'] = 'ORION-27' not in result.answer and 'not provided' in result.answer.lower()
        with tempfile.TemporaryDirectory(prefix='chat-synthetic-', dir=ROOT/'artifacts/windows-ui') as temp:
            reference = Path(temp)/'Reference'
            reference.mkdir()
            path = reference/'capacity.txt'
            path.write_text('Fictional storage approval.\nThe approved capacity is 37 crates.\n', encoding='utf-8')
            window.grant(str(reference), 'read-only')
            folder = window.workspace.broker.folders()[0]
            report['checks']['grant_clears_old_chat'] = not window.session.conversation.turns
            result = ask('Read capacity.txt in Reference. What capacity was approved? Cite the exact supporting line.')
            report['checks']['document_answer_cited'] = '37' in result.answer and bool(result.citations)
            result = ask('Rewrite that answer as one short sentence, retaining its supporting citation.')
            report['checks']['document_follow_up_has_revalidated_citation'] = ('37' in result.answer
                and any(s.path == 'capacity.txt' and s.cited_start == 2 for s in result.citations))
            window.sources_toggle.click()
            window.citations.setCurrentRow(0)
            app.processEvents()
            report['checks']['source_inspector_opens_verified_excerpt'] = '37 crates' in window.excerpt.toPlainText()
            for _ in range(10):
                app.processEvents()
                time.sleep(.01)
            window.grab().save(str(ROOT/'artifacts/windows-ui/conversation-tested.png'))
            window.resize(980, 740)
            for _ in range(10):
                app.processEvents()
                time.sleep(.01)
            report['checks']['message_content_fits_bubbles'] = all(content.height() >= content.heightForWidth(content.width())
                for _wrapper, _bubble, content, _title in window.answer._rows)
            report['checks']['latest_reply_scrolled_into_view'] = window.answer.verticalScrollBar().value() == window.answer.verticalScrollBar().maximum()
            window.grab().save(str(ROOT/'artifacts/windows-ui/conversation-tested-small.png'))
            window.clear_chat_button.click()
            report['checks']['clear_preserves_folder_grants'] = window.workspace.broker.folders()[0].id == folder.id
            ask('Read capacity.txt in Reference. What capacity was approved? Cite the exact supporting line.')
            path.write_text('Fictional storage approval.\nThe approved capacity is 41 crates.\n', encoding='utf-8')
            result = ask('Read capacity.txt in Reference. What is the current approved capacity? Cite the supporting line.')
            report['checks']['changed_source_resets_chat_and_uses_new_bytes'] = (result.history_reset
                and '41' in result.answer and len(result.conversation) == 1 and '37' not in window.answer.toPlainText())
            window.revoke(folder.id)
            report['checks']['revocation_erases_memory_and_display'] = not window.session.conversation.turns and not window.answer.toPlainText()
        report['checks']['all_graph_workers_zero_capabilities'] = bool(window.session.evidence['worker_tokens']) and all(
            token['appcontainer'] and token['capability_count'] == 0 and not token['profile_loopback_exempt']
            for token in window.session.evidence['worker_tokens'])
        report['checks']['full_gpu_placement'] = window.session.evidence.get('full_gpu') is True
    except Exception:
        report['errors'].append(traceback.format_exc())
    finally:
        window.close()
        wait(lambda: window.cleaned and not window.jobs, timeout=90)
        report['checks']['close_erases_memory'] = not window.session.conversation.turns
        report['checks']['cleanup_complete'] = window.session.evidence.get('cleanup_complete') is True
        report['source_hashes'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT/'src/local_ai_appliance').glob('*.py'))}
        (ROOT/'artifacts/windows-ui/conversation-results.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({'checks': report['checks'], 'errors': report['errors']}, indent=2), flush=True)
    return int(bool(report['errors']) or not all(report['checks'].values()))


if __name__ == '__main__':
    raise SystemExit(main())
