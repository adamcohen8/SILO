"""Capacity and policy selection contracts; no weights, network or execution."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.model_management import (
    GPU_DEFAULT, Hardware, ModelManager, _parse_gpu_inventory, builtin_profiles,
    preparation_default)

ROOT = Path(__file__).resolve().parents[1]
CPU = 'gemma4-e4b-q4-cpu-evaluation-1'
SMALL = 'gemma4-12b-q4-evaluation-1'
MEDIUM = 'gpt-oss-20b-mxfp4-evaluation-1'


def hardware(ram=32768, gpu=(), threads=8, platform='win32', architecture='amd64'):
    return Hardware(ram, threads, tuple({'name':'Inert GPU', 'vram_mib':v} for v in gpu), platform, architecture)


class HardwareSelectionTests(unittest.TestCase):
    def test_fresh_default_tiers_and_insufficient_or_unknown_hardware(self):
        for hw, expected in (
            (hardware(gpu=(24576,)), GPU_DEFAULT),
            (hardware(gpu=(16384,)), MEDIUM),
            (hardware(ram=16384,gpu=(12288,)), SMALL),
            (hardware(ram=16384,gpu=(24576,)), SMALL),
            (hardware(gpu=(8192,24576)), CPU),
            (hardware(gpu=(12288,24576)), SMALL),
            (hardware(ram=15872,threads=4), CPU),
            (hardware(ram=15871), None),
            (hardware(ram=8192), None),
            (hardware(ram=None,gpu=(24576,)), None),
            (hardware(ram=True,gpu=(24576,)), None),
            (hardware(threads=2), None),
            (hardware(threads=None), None),
            (hardware(threads=True), None),
            (hardware(architecture='arm64',gpu=(24576,)), None),
            (hardware(platform='darwin',gpu=(24576,)), None),
            (hardware(ram=131072,gpu=(98304,)), GPU_DEFAULT),
        ):
            with self.subTest(hw=hw): self.assertEqual(preparation_default(ROOT,hw),expected)

    def test_preparation_catalog_restrictions_apply_before_capacity(self):
        from local_ai_appliance.configuration_catalog import authorize_configuration
        def blocked(root, identifier, **kwargs):
            if identifier == GPU_DEFAULT: raise RuntimeError('Revoked fixture')
            return authorize_configuration(root,identifier,**kwargs)
        with patch('local_ai_appliance.model_management.authorize_configuration',side_effect=blocked):
            self.assertEqual(preparation_default(ROOT,hardware(gpu=(24576,))),
                             'nemotron-4090-cp314-evaluation-1')

    def test_recommendation_respects_scope_revocation_and_keeps_selection_unchanged(self):
        profiles = copy.deepcopy(builtin_profiles(ROOT))
        profiles = [p for p in profiles if p['id'] in {GPU_DEFAULT,CPU,SMALL}]
        profiles[0]['data_scopes'] = ['synthetic']
        manager = object.__new__(ModelManager)
        manager.profiles = lambda: profiles
        def authorize(identifier, *, data_scope, operation, workload):
            profile = next(p for p in profiles if p['id']==identifier)
            if profile['status']=='revoked' or data_scope not in profile['data_scopes']:
                raise AccessDenied('Restricted fixture')
            return profile
        manager.authorize = authorize
        # Selection access or any mutation would fail this test.
        manager.selected = lambda: self.fail('Recommendation read or wrote selection')
        rows=manager.recommendations(hardware(gpu=(24576,)),data_scope='public')
        self.assertNotIn(profiles[0]['id'],{r['id'] for r in rows})
        self.assertEqual(sum(r['recommended'] for r in rows),1)
        for p in profiles: p['status']='revoked'
        self.assertEqual(manager.recommendations(hardware(gpu=(24576,))),[])

    def test_policy_failure_never_falls_back_to_builtin_models(self):
        manager=object.__new__(ModelManager)
        manager.profiles=lambda: (_ for _ in ()).throw(AccessDenied('Expired policy'))
        with self.assertRaisesRegex(AccessDenied,'Expired'):
            manager.recommendations(hardware(gpu=(24576,)))

    def test_unknown_hardware_explains_missing_capacity_without_recommendation(self):
        manager=object.__new__(ModelManager)
        manager.profiles=lambda: builtin_profiles(ROOT)
        manager.authorize=lambda *args,**kwargs: None
        rows=manager.recommendations(hardware(ram=None,threads=None))
        self.assertTrue(rows)
        self.assertFalse(any(r['recommended'] for r in rows))
        self.assertTrue(all('System RAM is unknown' in r['reasons'] for r in rows))

    def test_gpu_inventory_keeps_slot_zero_and_rejects_partial_or_malformed_results(self):
        rows=_parse_gpu_inventory(b'"First, GPU", 8192\nSecond GPU, 24576\n')
        self.assertEqual([r['vram_mib'] for r in rows],[8192,24576])
        for data in (b'', b'First, unknown\nSecond, 24576\n', b'First, 8192\nBad\n',
                     b'First, -1\n', b'First, 0\n', b'First, 1048577\n',
                     b', 24576\n', b'\xff, 24576\n', b'"unclosed, 24576\n',
                     b'GPU, 8192\n'*33, b'x'*8193):
            with self.subTest(data=data[:50]): self.assertEqual(_parse_gpu_inventory(data),())
