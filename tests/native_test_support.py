"""Opt-in installed worker adapter; never writes into the payload."""
from functools import lru_cache
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def native_worker_path():
    configured = os.environ.get('SILO_NATIVE_TEST_ROOT')
    return (Path(configured).resolve().parent/'worker' if configured
            else ROOT/'artifacts/isolation-evaluation/python')


@lru_cache(maxsize=1)
def verified_native_worker():
    worker = native_worker_path()
    configured = os.environ.get('SILO_NATIVE_TEST_ROOT')
    if configured:
        from local_ai_appliance.evaluation_install import installed_config
        from local_ai_appliance.managed_deployment import ManagedDeployment
        app = Path(configured).resolve()
        config = installed_config(app)
        if config is None:
            raise RuntimeError('Explicit native test root must be an installed payload/app')
        # Preparation produces no active.json. Authenticate the explicitly
        # enrolled candidate, including protected inventory and signed policy.
        security = ManagedDeployment(app, candidate=True)
        security.close()
    if os.name != 'nt' or not (worker/'python.exe').is_file():
        raise unittest.SkipTest('Native contained parser requires a staged or explicit installed worker')
    return worker


def parse_fixture_document(folder_id, path, data):
    """Use the production contained route for synthetic Windows parser inputs."""
    if os.name != 'nt':
        from local_ai_appliance.documents import parse_document
        return parse_document(folder_id, path, data)
    from local_ai_appliance.windows_container import AppContainer
    from local_ai_appliance.windows_workspace import ContainedWorkspace
    worker = verified_native_worker()
    with tempfile.TemporaryDirectory(prefix='silo-parser-fixture-') as temp:
        folder = Path(temp)
        (folder/path).write_bytes(data)
        with AppContainer(evaluation=True) as container:
            container.allow_read(worker, directory=True)
            workspace = ContainedWorkspace(container, worker/'python.exe', {'parser_tokens': []})
            try:
                grant = workspace.grant(folder, 'read-only')
                return workspace.open_document(grant.id, path)
            finally:
                workspace.close()
