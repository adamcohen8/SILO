import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local_ai_appliance.configuration_catalog import CATALOG_PATH, authorize_configuration, parse_catalog
from local_ai_appliance.evaluation_install import prepare
from local_ai_appliance.windows_session import WindowsSession

ROOT=Path(__file__).resolve().parents[1]
CP312='nemotron-4090-cp312-evaluation-1'
CP314='nemotron-4090-cp314-evaluation-1'


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        shutil.copytree(ROOT/'profiles',self.root/'profiles')
        self.data=json.loads((self.root/CATALOG_PATH).read_text())

    def test_exact_evaluation_profiles_allowed_without_native_readiness(self):
        for identifier in (CP312,CP314):
            for operation in ('install','launch'):
                entry=authorize_configuration(self.root,identifier,operation=operation)
                self.assertIn(entry.native_acceptance,('partial','pending'))
                self.assertIn('documents',entry.workloads)

    def test_unknown_cui_code_and_invalid_operation_denied(self):
        for kwargs in ({'configuration_id':'unlisted'},{'configuration_id':CP314,'data_scope':'cui'},
                       {'configuration_id':CP314,'workload':'code'},{'configuration_id':CP314,'operation':'approve'}):
            with self.assertRaises(RuntimeError):
                authorize_configuration(self.root,operation='launch',**kwargs) if 'operation' not in kwargs else \
                    authorize_configuration(self.root,**kwargs)

    def test_catalog_and_each_profile_drift_fail_closed(self):
        for pin in self.data['configurations'][1]['profile_pins']:
            path=self.root/pin['path']; original=path.read_bytes()
            path.write_bytes(original+b' ')
            with self.assertRaisesRegex(RuntimeError,'profile changed'):
                authorize_configuration(self.root,CP314,operation='install')
            path.write_bytes(original)
        path=self.root/CATALOG_PATH
        path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(RuntimeError,'reviewed host policy'):
            authorize_configuration(self.root,CP314,operation='launch')

    def test_revocation_and_provenance_restrictions_with_trusted_policy_snapshot(self):
        for field,value in (('status','revoked'),('blocked_publishers',['unsloth']),('blocked_jurisdictions',['unknown'])):
            data=json.loads(json.dumps(self.data))
            if field=='status': data['configurations'][1][field]=value
            else: data[field]=value
            with self.assertRaises(RuntimeError):
                parse_catalog(json.dumps(data)).authorize(self.root,CP314,operation='launch')

    def test_schema_duplicate_keys_bool_versions_and_scope_expansion_rejected(self):
        values=[b'{"format_version":1,"format_version":1}']
        for mutation in ('bool','duplicate','cui','path','unknown-field','wrong-type'):
            data=json.loads(json.dumps(self.data))
            if mutation=='bool': data['format_version']=True
            if mutation=='duplicate': data['configurations'].append(data['configurations'][0])
            if mutation=='cui': data['configurations'][0]['data_scopes'].append('cui')
            if mutation=='path': data['configurations'][0]['profile_pins'][0]['path']='../escape'
            if mutation=='unknown-field': data['configurations'][0]['execute']=True
            if mutation=='wrong-type': data['blocked_publishers']=[{}]
            values.append(json.dumps(data).encode())
        for value in values:
            with self.assertRaises(RuntimeError): parse_catalog(value)

    def test_launch_policy_denied_before_any_runtime_is_returned(self):
        session=WindowsSession.__new__(WindowsSession)
        session.root=self.root
        session.check_cancelled=lambda:None
        (self.root/CATALOG_PATH).write_text('{}')
        with patch('local_ai_appliance.windows_session.verify_inference',side_effect=AssertionError('must not launch')):
            with self.assertRaises(RuntimeError): session.verify_assets()

    def test_install_policy_denied_before_obtaining_assets(self):
        # Install snapshot is inspected, but no dependency/model download starts.
        source=ROOT
        destination,cache,state=[self.root/n for n in ('transaction','cache','state')]
        for p in (destination,cache,state): p.mkdir()
        with patch('local_ai_appliance.evaluation_install.authorize_configuration',side_effect=RuntimeError('revoked')), \
             patch('local_ai_appliance.evaluation_install.source_files',return_value=[]), \
             patch('local_ai_appliance.evaluation_install.obtain',side_effect=AssertionError('must not download')):
            with self.assertRaisesRegex(RuntimeError,'revoked'):
                prepare(source,destination,cache,state,offline=True)


if __name__=='__main__': unittest.main()
