"""Combined host/TUI contracts with real authority and portable security brokers.

Service startup, model verification and machine policy handles are inert. These
checks establish interface behavior, not native isolation or signed-policy trust.
"""
import asyncio
import copy
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from local_ai_appliance.agent import AgentResult
from local_ai_appliance.backend import SessionCancelled, WindowsSessionAdapter
from local_ai_appliance.contracts import Project, WorkspaceKind
from local_ai_appliance.conversation import Conversation
from local_ai_appliance.data_security import SecurityBroker, StoragePolicy
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.project_store import ProjectSession, ProjectStore
from local_ai_appliance.windows_session import WindowsSession
from local_ai_appliance.workspace import Workspace

try:
    from prompt_toolkit.data_structures import Size
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput
    from local_ai_appliance.terminal_fullscreen import FullScreenPreview
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


class MemoryVault:
    """Injected persistence interface, never an encryption qualification."""
    def __init__(self, path): self.path, self.values = path, {}
    def get(self, name): return copy.deepcopy(self.values.get(name))
    def put(self, name, value): self.values[name] = copy.deepcopy(value)
    def names(self, prefix): return sorted(name for name in self.values if name.startswith(prefix))
    def delete(self, name): self.values.pop(name, None)
    def close(self): self.values.clear()


@unittest.skipUnless(AVAILABLE and os.name == 'posix', 'Portable terminal/security broker fixture required')
class TUISecurityIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def wait_for(self, predicate):
        async with asyncio.timeout(5):
            while not predicate(): await asyncio.sleep(.01)

    def fixture(self):
        temporary = tempfile.TemporaryDirectory(prefix='silo-tui-security-')
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve()
        for name in ('reference', 'drafts', 'private', 'outside'):
            (root/name).mkdir()
        ctx = SimpleNamespace(root=root, services=[], factories=[], authorizations=[], audit=[],
            fail_cleanup=False, block_restart=False, restart_entered=threading.Event(),
            restart_release=threading.Event(), ask_entered=threading.Event(), ask_release=threading.Event())
        vault = MemoryVault(root/'private')
        vault.put('selected-model', {'id': 'cpu-fixture'})
        profiles = [{'id': identifier, 'display_name': label,
                     'model': {'name': identifier+'.gguf', 'size': 4, 'sha256': 'a'*64},
                     'minimum_ram_mib': 1, 'minimum_vram_mib': 0,
                     'license': {'id': 'fixture-only'}}
                    for identifier, label in [('cpu-fixture', 'CPU fixture'), ('super-fixture', 'Super fixture')]]
        class Manager:
            def __init__(self, root, vault, *, clock=lambda: 1000, required_key_sha256='a'*64,
                         model_cache=None, policy_store=None):
                self.root, self.vault, self.model_cache = root, vault, model_cache
                self.required_key_sha256 = required_key_sha256
                self.policy = SimpleNamespace(clock=clock, vault=policy_store)
            def selected(self): return self.vault.get('selected-model')['id']
            def profiles(self): return profiles
            def installed(self, profile): return True
            def authorize(self, identifier, *, operation='launch', data_scope='synthetic'):
                ctx.authorizations.append((self.policy.vault, identifier, data_scope))
                if data_scope != 'synthetic': raise AccessDenied('Fixture model policy requires synthetic data')
                return next(p for p in profiles if p['id'] == identifier)
            def verify_model(self, profile, cancel=lambda: None): cancel()
        def manager_factory(*args, **kwargs):
            ctx.factories.append(kwargs)
            return Manager(*args, **kwargs)
        class Audit:
            def __init__(self): self.closed, self.events = False, []
            def emit(self, event, outcome, **metadata):
                if self.closed: raise AccessDenied('Fixture audit sink is closed')
                self.events.append((event, outcome, metadata))
                ctx.audit.append((event, outcome, metadata))
            def close(self): self.closed = True
        class Service:
            # Exercise the production recreation method, including protected-store rebinding.
            recreate = WindowsSession.recreate
            def __init__(self, root, *, evaluation=False):
                self.root, self.evaluation = root, evaluation
                self.instructions, self.code = 'Fixture instructions', None
                self.workspace, self.conversation = Workspace(), Conversation()
                policy = StoragePolicy([root/'reference'], [root/'drafts'], excluded_roots=[root/'private'])
                self.security = SimpleNamespace(store=object(), storage=policy, audit=Audit(),
                    settings={'maximum_retention_days': 9 if ctx.services else 7})
                self.workspace.broker = SecurityBroker(self.workspace.broker, policy, self.security.audit)
                self.model_manager = None
                self.closed = self.ready = False
                self.model_profile, self.questions = None, []
                self.cancelled = threading.Event()
                ctx.services.append(self)
            def start(self, progress=lambda _: None):
                self.model_profile = self.model_manager.authorize(self.model_manager.selected())
                if ctx.block_restart and len(ctx.services) > 1:
                    ctx.restart_entered.set()
                    if not ctx.restart_release.wait(4): raise AccessDenied('Fixture restart gate timed out')
                self.ready = True
                progress('Fixture started')
            def ask(self, prompt, *, on_progress=None, on_text=None):
                self.questions.append(prompt)
                if on_text: on_text('provisional fixture content')
                ctx.ask_entered.set()
                if not ctx.ask_release.wait(4): raise AccessDenied('Fixture ask gate timed out')
                if self.cancelled.is_set(): raise SessionCancelled('Fixture hard cancellation')
                return AgentResult('Fixture answer', (), (), 1, 0)
            def clear_chat(self): self.conversation.clear()
            def cancel(self):
                self.cancelled.set(); self.ready = False; ctx.ask_release.set()
            def close(self):
                if ctx.fail_cleanup: raise AccessDenied('Fixture cleanup could not be verified')
                self.ready, self.closed = False, True
                self.workspace.close(); self.conversation.clear()
                self.security.audit.close()
        service = Service(root)
        service.model_manager = Manager(root, vault, model_cache=root/'private', policy_store=service.security.store)
        service.start()
        adapter = WindowsSessionAdapter(Project('unsaved', 'Unsaved fixture'), service)
        host = ProjectSession(adapter, ProjectStore(vault, maximum_retention_days=7, audit=service.security.audit))
        host.create_project('Managed fixture')
        self.assertEqual(host.record['retention_days'], 7)
        replacement_patch = patch('local_ai_appliance.model_management.ModelManager', side_effect=manager_factory)
        replacement_patch.start(); self.addCleanup(replacement_patch.stop)
        def cleanup():
            ctx.fail_cleanup = False
            ctx.ask_release.set(); ctx.restart_release.set()
            host.close()
        self.addCleanup(cleanup)
        return ctx, host

    async def start(self, pipe, host):
        class Output(DummyOutput):
            def get_size(self): return Size(rows=30, columns=100)
        screen = FullScreenPreview(backend=host, input=pipe, output=Output(), plain=True)
        task = asyncio.create_task(screen.app.run_async(pre_run=screen.start))
        async def stop():
            if not task.done():
                host.service.cancel(); screen.close()
            await asyncio.wait_for(task, 5)
        self.addAsyncCleanup(stop)
        await self.wait_for(lambda: screen.app.renderer.last_rendered_screen is not None)
        return screen

    def footer(self, screen):
        rendered = screen.app.renderer.last_rendered_screen
        return ''.join(rendered.data_buffer[29][x].char for x in range(100)).rstrip()

    async def grant_dialog(self, screen, pipe, path, kind):
        screen.folder_dialog.begin()
        pipe.send_text('\x1b[200~'+"'"+str(path)+"'"+'\x1b[201~')
        await self.wait_for(lambda: screen.folder_dialog.choosing)
        screen.folder_dialog.access.current_value = kind
        screen.folder_dialog.grant()
        await self.wait_for(lambda: not screen.busy)

    async def test_structured_folder_grant_uses_project_authority_and_resets_review_context(self):
        ctx, host = self.fixture()
        draft = host.grant(ctx.root/'drafts', WorkspaceKind.DRAFT)
        proposal = host.workspace.propose(draft.id, 'old.md', 'Unsaved fixture')
        host.review(proposal.id)
        host.conversation.append('Prior question', 'Prior accepted context', (), host.workspace.broker.revision)
        selected = ctx.root/'reference'/r'Literal\folder with trailing space '
        selected.mkdir()
        with create_pipe_input() as pipe:
            screen = await self.start(pipe, host)
            screen.composer.text = 'Keep the next question'
            screen.controller.sources = {'old': 'old source registry'}
            await self.grant_dialog(screen, pipe, selected, 'reference')
            self.assertFalse(screen.folder_dialog.opened)
            self.assertEqual(host.record['grants'][-1]['path'], str(selected))
            self.assertEqual(host.record['grants'][-1]['access'], 'read-only')
            self.assertFalse(host.backend._reviewed)
            self.assertFalse(host.workspace.pending_proposals())
            self.assertFalse(host.conversation.display())
            self.assertFalse(screen.controller.sources)
            self.assertEqual(screen.composer.text, 'Keep the next question')
            self.assertNotIn('Prior accepted context', screen.transcript.text)
            self.assertIn(('grant', 'success'), [(event, outcome) for event, outcome, _ in ctx.audit])

    async def test_dialog_cannot_expand_administrator_roots_or_private_project_storage(self):
        ctx, host = self.fixture()
        with create_pipe_input() as pipe:
            screen = await self.start(pipe, host)
            for path, kind in [(ctx.root/'reference', 'draft'), (ctx.root/'outside', 'reference'),
                               (ctx.root/'private', 'reference')]:
                await self.grant_dialog(screen, pipe, path, kind)
                self.assertTrue(screen.folder_dialog.opened)
                self.assertFalse(host.workspace.broker.folders())
                self.assertFalse(host.record['grants'])
                screen.folder_dialog.cancel()
            denied = [(event, outcome) for event, outcome, _ in ctx.audit if outcome == 'denied']
            self.assertEqual(denied, [('grant', 'denied'), ('grant', 'denied')])

    async def test_model_switch_rebinds_machine_policy_and_updates_loaded_footer(self):
        ctx, host = self.fixture()
        host.grant(ctx.root/'reference', WorkspaceKind.REFERENCE)
        old = host.service
        with create_pipe_input() as pipe:
            screen = await self.start(pipe, host)
            screen._begin_request('/model switch')
            await self.wait_for(lambda: not screen.busy)
            self.assertEqual(screen.controller.model_menu.pending[0], 'switch')
            screen._begin_request('super-fixture')
            await self.wait_for(lambda: not screen.busy)
            self.assertEqual(screen.state, 'Ready')
            await self.wait_for(lambda: self.footer(screen).endswith('Super fixture'))
            self.assertTrue(old.closed)
            self.assertIs(ctx.factories[-1]['policy_store'], host.service.security.store)
            self.assertIsNot(host.service.security.store, old.security.store)
            self.assertEqual(ctx.factories[-1]['required_key_sha256'], 'a'*64)
            self.assertFalse(host.service.evaluation)
            self.assertEqual(len(host.workspace.broker.folders()), 1)
            self.assertEqual(host.record['configuration_id'], 'super-fixture')
            self.assertIn((host.service.security.store, 'super-fixture', 'synthetic'), ctx.authorizations)

    async def test_replacement_project_persistence_uses_live_audit_and_retention(self):
        for action in ('switch', 'recover'):
            with self.subTest(action=action):
                ctx, host = self.fixture()
                old = host.service
                if action == 'switch': host.switch_model('super-fixture')
                else:
                    host.cancel()
                    host.recover()
                self.assertTrue(old.security.audit.closed)
                with self.assertRaisesRegex(AccessDenied, 'sink is closed'):
                    old.security.audit.emit('retention', 'success')
                self.assertIs(host.store.audit, host.service.security.audit)
                self.assertEqual(host.store.maximum_retention_days, 9)
                host.set_retention(9)
                host.persist()
                stored = host.store.vault.get('project-'+host.project.id)
                self.assertEqual(stored['retention_days'], 9)
                self.assertIn(('retention', 'success'),
                              [(event, outcome) for event, outcome, _ in host.service.security.audit.events])

    async def test_cancel_recovery_keeps_policy_grants_and_input_but_discards_provisional_text(self):
        ctx, host = self.fixture()
        host.grant(ctx.root/'reference', WorkspaceKind.REFERENCE)
        old = host.service
        ctx.block_restart = True
        with create_pipe_input() as pipe:
            screen = await self.start(pipe, host)
            pipe.send_text('First request\r')
            await self.wait_for(ctx.ask_entered.is_set)
            await self.wait_for(lambda: bool(screen.live_text))
            screen.composer.text = 'Next request'
            screen.controller.sources = {'old': 'prior source'}
            pipe.send_text('\x03')
            await self.wait_for(ctx.restart_entered.is_set)
            await self.wait_for(lambda: self.footer(screen).endswith('No active model'))
            self.assertTrue(screen.recovering)
            ctx.restart_release.set()
            await self.wait_for(lambda: not screen.busy)
            await self.wait_for(lambda: self.footer(screen).endswith('CPU fixture'))
            self.assertFalse(screen.recovery_failed)
            self.assertEqual(screen.composer.text, 'Next request')
            self.assertFalse(screen.live_text)
            self.assertFalse(screen.controller.sources)
            self.assertTrue(old.closed)
            self.assertIs(ctx.factories[-1]['policy_store'], host.service.security.store)
            self.assertEqual(len(host.workspace.broker.folders()), 1)
            self.assertFalse(host.conversation.display())

    async def test_failed_cleanup_prevents_recreation_and_blocks_new_folder_or_model_work(self):
        ctx, host = self.fixture()
        with create_pipe_input() as pipe:
            screen = await self.start(pipe, host)
            pipe.send_text('Cancelled request\r')
            await self.wait_for(ctx.ask_entered.is_set)
            ctx.fail_cleanup = True
            pipe.send_text('\x03')
            await self.wait_for(lambda: not screen.busy)
            self.assertTrue(screen.recovery_failed)
            self.assertFalse(ctx.factories)
            await self.wait_for(lambda: self.footer(screen).endswith('No active model'))
            screen.folder_dialog.begin()
            self.assertFalse(screen.folder_dialog.opened)
            screen.composer.text = '/model'
            screen.submit()
            self.assertEqual(screen.composer.text, '/model')
            self.assertFalse(screen.busy)
            self.assertEqual(len(host.service.questions), 1)
            ctx.fail_cleanup = False

    async def test_models_listing_remains_available_from_an_open_model_menu(self):
        ctx, host = self.fixture()
        with create_pipe_input() as pipe:
            screen = await self.start(pipe, host)
            screen._begin_request('/model')
            await self.wait_for(lambda: not screen.busy)
            screen._begin_request('/models')
            await self.wait_for(lambda: not screen.busy)
            self.assertEqual(screen.state, 'Ready')
            self.assertIn('Profile ID', screen.transcript.text)
            self.assertFalse(host.service.questions)


if __name__ == '__main__': unittest.main()
