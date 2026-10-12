"""Terminal host controls. Menu responses never enter the model conversation."""
import threading
import time

from .backend import SessionCancelled
from .folders import AccessDenied
from .model_management import model_pins, scan_hardware, execution_backend


class ModelMenu:
    def __init__(self, client):
        self.client = client
        self.pending = None
        self.cancelled = threading.Event()
        self.working = False
        self.downloading = False

    @property
    def session(self): return self.client.managed()

    @property
    def manager(self):
        value = getattr(self.session.service, 'model_manager', None)
        if value is None: raise AccessDenied('Managed models require the standalone CPython 3.14 installation')
        return value

    def cancel(self):
        self.cancelled.set()
        self.pending = None
        if self.working and not self.downloading: self.client.backend.cancel_model_change()

    def checkpoint(self):
        if self.cancelled.is_set(): raise SessionCancelled('Model operation cancelled')

    def recommend(self, hardware=None):
        rows = self.manager.recommendations(hardware or scan_hardware(),
                                           data_scope=self.session.project.data_scope)
        choice = next((row for row in rows if row['recommended']), None)
        if choice:
            self.client.view.notice('Recommended for this hardware: '+choice['name']+' ('+choice['id']+').')
            self.client.view.notice('To use it: /model install '+choice['id']+' then /model switch '+choice['id']+
                                    '. If already installed, switch directly.')
        else:
            self.client.view.notice('No permitted model fits the detected hardware.', warning=True)
        self.client.view.table(['Model', 'Hardware fit'],
            [[row['name'], 'Recommended' if row['recommended'] else 'Fits declared floors' if row['fits']
              else '; '.join(row['reasons'])] for row in rows])
        self.client.view.notice('Capacity estimates only; model quality and native acceptance require testing. Selection is unchanged.')
        return rows

    def show(self, action=''):
        manager = self.manager
        if not action:
            self.pending = ('action', ('switch', 'install', 'remove'))
            self.client.view.body('Model menu\n1. Switch\n2. Install\n3. Remove\n/model recommend shows hardware recommendations.\nChoose a number or action; /cancel closes the menu.')
            return
        if action not in {'switch', 'install', 'remove'}:
            raise AccessDenied('/model | /model recommend | /model switch | /model install | /model remove')
        capacity = ({row['id']: row for row in manager.recommendations(scan_hardware(),
                     data_scope=self.session.project.data_scope)} if action != 'remove' else {})
        rows = []
        for profile in manager.profiles():
            installed = manager.installed(profile)
            if (action == 'install') == installed: continue
            if action != 'remove':
                try: manager.authorize(profile['id'], operation='install' if action == 'install' else 'launch',
                                       data_scope=self.session.project.data_scope)
                except (AccessDenied, RuntimeError): continue
            rows.append(profile)
        self.pending = (action, tuple(p['id'] for p in rows))
        self.client.view.notice(action.capitalize()+' model')
        if not rows:
            self.pending = None
            self.client.view.notice('No models available for '+action+'. /model returns to the menu.')
            return
        for index, profile in enumerate(rows, 1):
            label = profile.get('display_name', profile['id'])
            active = ' [active]' if profile['id'] == manager.selected() else ''
            fit = capacity.get(profile['id'])
            recommended = ' [recommended]' if fit and fit['recommended'] else ''
            device = (f'CPU {profile["cpu_threads"]} threads' if execution_backend(profile) == 'cpu'
                      else f'CUDA0 VRAM {profile["minimum_vram_mib"] / 1024:.0f} GiB')
            self.client.view.body(f'{index}. {label}{active}{recommended} — {sum(pin["size"] for pin in model_pins(profile)) / 1024**3:.1f} GiB\n'
                                  f'   {profile["id"]}; RAM {profile["minimum_ram_mib"] / 1024:.0f} GiB; '
                                  f'{device}; license {profile["license"]["id"]}')
            if fit and not fit['fits']:
                self.client.view.body('   Hardware: '+'; '.join(fit['reasons']))
        if action == 'install':
            self.client.view.notice('Selection downloads the pinned model using the host network. Offline: /cancel, then /model import ID PATH.')
        self.client.view.notice('Choose a number or model ID; /back returns, /cancel closes.')

    def choose(self, value):
        if value == '/cancel':
            self.cancel(); self.client.view.notice('Model menu closed.'); return
        if value == '/back': self.show(); return
        phase, choices = self.pending
        if phase == 'confirm':
            if value.lower() not in {'yes', 'no'}: raise AccessDenied('Type yes to delete this model, or no to cancel.')
            self.pending = None
            if value.lower() == 'yes': self.execute('remove', choices[0])
            else: self.client.view.notice('Removal cancelled.')
            return
        if value.startswith('/model import '):
            self.pending = None
            self.client.host_command('/model', value[len('/model '):]); return
        if value.isascii() and value.isdecimal() and 1 <= int(value) <= len(choices):
            value = choices[int(value)-1]
        if value not in choices: raise AccessDenied('Choose one of the listed options, /back or /cancel.')
        self.pending = None
        if phase == 'action': self.show(value)
        elif phase == 'remove': self.confirm(value)
        else: self.execute(phase, value)

    def confirm(self, identifier):
        profile = next((p for p in self.manager.profiles() if p['id'] == identifier), None)
        if profile is None or not self.manager.installed(profile): raise AccessDenied('Model is not installed')
        if self.manager.model_path(profile) != self.manager.managed_model_path(profile):
            raise AccessDenied('This legacy bundled model is part of the verified payload. Repair using the new installer to get removable model storage.')
        self.pending = ('confirm', (identifier,))
        self.client.view.notice('Delete '+profile.get('display_name', identifier)+'? Type yes or no. Removing the active model unloads it; use /model to select another.')

    def execute(self, action, identifier):
        manager = self.manager
        self.cancelled.clear(); self.working = True
        try:
            if action == 'switch':
                self.client.view.notice('Verifying and loading the selected model…')
                self.session.switch_model(identifier)
                self.client.sources.clear()
                self.client.view.notice('Model switched. Chat and pending reviews cleared; verified folder grants retained.')
                if self.session._model_grants_omitted:
                    self.client.view.notice('Changed or unavailable folders were not restored. Use /folders to check grants.', warning=True)
            elif action == 'install':
                self.downloading = True
                last = [0.0]
                def progress(message):
                    now = time.monotonic()
                    if now - last[0] >= 1:
                        self.client.view.notice(message); last[0] = now
                manager.install(identifier, data_scope=self.session.project.data_scope,
                                cancel=self.checkpoint, progress=progress)
                self.client.view.notice('Model installed and SHA-256 verified. Use /model switch to load it.')
            elif action == 'remove':
                selected = next((p for p in manager.profiles() if p['id'] == manager.selected()), None)
                target = next(p for p in manager.profiles() if p['id'] == identifier)
                if selected and manager.model_path(selected) == manager.model_path(target):
                    self.session.switch_model(None); self.client.sources.clear()
                    manager = self.manager
                self.checkpoint()
                manager.remove(identifier)
                self.client.view.notice('Model deleted. Use /model to install or switch models.')
            else: raise AccessDenied('Unknown model action')
        finally:
            self.downloading = self.working = False
