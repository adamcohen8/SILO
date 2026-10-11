"""Native startup and synthetic document preflight; full isolation acceptance stays false."""
import argparse
import importlib
import json
import os
from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP/'src'))
sys.path.insert(0, str(APP/'tests'))
from local_ai_appliance.evaluation_install import verify_release, installed_config
from local_ai_appliance.windows_session import WindowsSession
from synthetic_documents import pdf_bytes, docx_bytes


def update_models(state, required_key):
    from local_ai_appliance.project_store import LocalVault, project_data_directory
    from local_ai_appliance.model_management import ModelManager
    vault = LocalVault(project_data_directory(state), windows_validation=True)
    try:
        manager = ModelManager(APP, vault, required_key_sha256=required_key,
                               model_cache=project_data_directory(state, name='models'))
        manager.current_policy()
        return vault, manager
    except BaseException:
        vault.close()
        raise


def main(arguments=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--application-update', action='store_true')
    parser.add_argument('--required-policy-key-sha256')
    args = parser.parse_args(arguments)
    if args.required_policy_key_sha256 and not args.application_update:
        parser.error('The policy anchor requires application-update preflight')
    if os.name != 'nt' or sys.maxsize <= 2**32:
        raise SystemExit('Native 64-bit Windows preflight required.')
    verify_release(APP.parent.parent, args.manifest_sha256)
    config = installed_config(APP)
    # This run never loads remembered folder settings or operational documents.
    checks = dict.fromkeys(('host_ui_imports', 'full_gpu', 'default_deny', 'cited_document_answer',
                           'contained_pdf_parser', 'contained_docx_parser', 'no_remaining_grants',
                           'contained_tokens', 'cleanup'), False)
    checks['complete_installed_files'] = True
    state = Path(config['state_root'])
    session, vault, failure, stage = None, None, None, 'host_ui_imports'
    not_applicable, selected = [], None
    try:
        # AI/parser dependencies are imported only by the contained workflow below.
        for module in ('PySide6.QtWidgets', 'shiboken6'):
            importlib.import_module(module)
        from local_ai_appliance.model_management import scan_hardware, ModelManager, builtin_profiles, DEFAULT
        manager = None
        if args.application_update:
            vault, manager = update_models(state, args.required_policy_key_sha256)
            selected = manager.selected()
            # launch_assets verifies policy, hardware and the selected weights at startup.
        else:
            selected = DEFAULT
            profile = next(p for p in builtin_profiles(APP) if p['id'] == DEFAULT)
            if not ModelManager.hardware_fit(profile, scan_hardware()):
                raise RuntimeError('The default model hardware prerequisite is unavailable.')
        checks['host_ui_imports'] = True
        stage = 'synthetic_fixtures'
        fixture = state/'preflight'
        fixture.mkdir(exist_ok=True)
        for name, expected in [('source.txt', b'Synthetic installation check.\nThe approved capacity is 37 crates.\n'),
                               ('source.pdf', pdf_bytes()), ('source.docx', docx_bytes())]:
            source = fixture/name
            if source.exists() and source.read_bytes() != expected:
                raise RuntimeError('Preflight fixture collision; existing content was preserved.')
            if not source.exists():
                with source.open('xb') as stream: stream.write(expected)
        stage = 'model_startup'
        session = WindowsSession(APP, model_manager=manager) if manager is not None else WindowsSession(APP)
        session.start(lambda text: print(text, file=sys.stderr, flush=True))
        if selected is None:
            not_applicable = ['full_gpu', 'cited_document_answer']
        else:
            checks['full_gpu'] = session.evidence['full_gpu']
        checks['default_deny'] = not session.workspace.broker.folders()
        folder = session.workspace.grant(fixture, 'read-only')
        stage = 'cited_document_answer'
        if selected is not None:
            result = session.ask('Read source.txt in preflight. What is the approved capacity? Cite its exact line.')
            checks['cited_document_answer'] = ('37' in result.answer and bool(result.citations) and
                                              any(c.cited_start <= 2 <= c.cited_end for c in result.citations))
        stage = 'contained_pdf_parser'
        checks['contained_pdf_parser'] = session.workspace.open_document(folder.id, 'source.pdf').unit_kind == 'page'
        stage = 'contained_docx_parser'
        checks['contained_docx_parser'] = session.workspace.open_document(folder.id, 'source.docx').unit_kind == 'paragraph'
        stage = 'revocation_and_tokens'
        session.workspace.revoke(folder.id)
        checks['no_remaining_grants'] = not session.workspace.broker.folders()
        tokens = [*session.evidence['worker_tokens'], *session.evidence['parser_tokens']]
        if selected is not None: tokens.append(session.evidence['server_token'])
        checks['contained_tokens'] = (selected is None or bool(session.evidence['worker_tokens'])) and len(session.evidence['parser_tokens']) >= 2 and all(t['appcontainer'] and t['capability_count'] == 0 and
                                        t['profile_loopback_exempt'] is False for t in tokens)
    except Exception as error:
        failure = {'stage': stage, 'error_type': type(error).__name__}
    finally:
        if session is not None:
            try:
                session.close()
                checks['cleanup'] = session.evidence.get('cleanup_complete') is True
            except Exception as error:
                failure = {'stage': 'cleanup', 'error_type': type(error).__name__}
        if vault is not None:
            try: vault.close()
            except Exception as error: failure = {'stage': 'vault_cleanup', 'error_type': type(error).__name__}
    report = {'evaluation_only': True, 'deployment_ready': False, 'full_isolation_accepted': False,
              'manifest_sha256': args.manifest_sha256, 'python': sys.version.split()[0],
              'mode': 'application_update' if args.application_update else 'fresh_install',
              'selected_model': selected, 'not_applicable': not_applicable,
              'checks': checks, 'failure': failure,
              'evaluation_preflight_passed': failure is None and all(value for key, value in checks.items() if key not in not_applicable)}
    (state/'installation-preflight.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))
    return 0 if report['evaluation_preflight_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
