"""Bounded host connectivity observations for native validation receipts."""
import urllib.request
from pathlib import Path


def candidate_installation(app, *, candidate, fixture_root=None):
    """Authenticate enrolled inactive software and approved synthetic folders.

    This is preparation for native evidence collection, never an acceptance
    receipt. The session independently repeats the managed security gate.
    """
    from local_ai_appliance.folders import AccessDenied
    from local_ai_appliance.evaluation_install import installed_config
    from local_ai_appliance.managed_deployment import ManagedDeployment
    if candidate is not True:
        raise AccessDenied('Native validation requires explicit --candidate enrollment')
    app = Path(app).resolve()
    config = installed_config(app)
    if config is None:
        raise AccessDenied('An enrolled installed candidate is required')
    security = ManagedDeployment(app, candidate=True)
    try:
        identity = {'release_sha256': security.release_sha256,
                    'version': security.bundle['version'],
                    'configuration_id': security.bundle['configuration_id'],
                    'candidate': True, 'technical_acceptance': 'pending'}
        if fixture_root is not None:
            fixture = Path(fixture_root).absolute()
            state = Path(config['state_root']).absolute()
            for forbidden in (app, state, security.release):
                if (fixture == forbidden or fixture in forbidden.parents
                        or forbidden in fixture.parents):
                    raise AccessDenied('Synthetic grants must stay outside software and private state')
            security.storage.directory(fixture/'Reference', 'read-only')
            security.storage.directory(fixture/'Drafts', 'editable')
            if any(any((fixture/name).iterdir()) for name in ('Reference', 'Drafts')):
                raise AccessDenied('Dedicated candidate fixture folders must be empty')
        return config, identity
    finally:
        security.close()


def host_connected(report, phase):
    """Record a failed observation without preventing evidence finalization."""
    try:
        with urllib.request.urlopen('https://pypi.org/simple/', timeout=12) as response:
            return response.status == 200
    except OSError as error:
        report.setdefault('connectivity_errors', []).append({
            'phase': phase, 'exception_type': type(error).__name__})
        return False
