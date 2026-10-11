"""Real signed policies and bounded synthetic responses; no weight download/inference."""
import copy
import hashlib
import io
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from local_ai_appliance.backend import SessionCancelled
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.signed_policy import canonical
from local_ai_appliance.model_management import SUPER_ID, builtin_profiles, model_download_assets
import test_model_management as fixtures

ROOT = Path(__file__).resolve().parents[1]


class BoundedResponse(io.BytesIO):
    def __init__(self, data, url):
        super().__init__(data)
        self.url, self.status, self.read_sizes = url, 200, []

    def read1(self, size):
        if not 0 < size <= 1024*1024:
            raise AssertionError('Unbounded synthetic download read')
        self.read_sizes.append(size)
        return self.read(size)


@unittest.skipUnless(os.name == 'posix', 'Portable synthetic signed-policy fixture')
class ShardedModelMenuTests(unittest.TestCase):
    update = fixtures.ModelManagementTests.update

    def setUp(self):
        fixtures.ModelManagementTests.setUp(self)
        self.super = next(p for p in builtin_profiles(ROOT) if p['id'] == SUPER_ID)
        self.super['workloads'] = ['documents']
        self.payloads = {}
        for index, pin in enumerate(self.super['model_shards'], 1):
            payload = b'GGUF inert shard '+str(index).encode()
            self.payloads[pin['name']] = payload
            pin.update(size=len(payload), sha256=hashlib.sha256(payload).hexdigest())
        self.super['model'] = copy.deepcopy(self.super['model_shards'][0])
        self.super['source'].update(upstream='fixture/model', upstream_revision='a'*40,
            repository='fixture/model', revision='a'*40, subdirectory='Q4',
            url='https://huggingface.co/fixture/model/resolve/'+'a'*40+'/Q4/'+self.super['model']['name'])
        self.policy['profiles'].append(self.super); self.update()
        self.manager.import_model(self.profile['id'], self.source)
        self.manager.select(self.profile['id'])
        self.total = sum(pin['size'] for pin in self.super['model_shards'])
        self.directory = self.manager.managed_model_path(self.super).parent

    def responses(self):
        return [BoundedResponse(self.payloads[pin['name']], pin['url'])
                for pin in model_download_assets(self.super)]

    def install(self, **kwargs):
        with patch('urllib.request.build_opener') as build:
            build.return_value.open.side_effect = self.responses()
            return self.manager.install(SUPER_ID, **kwargs)

    def assert_no_staging(self):
        self.assertEqual(list(self.manager.model_cache.glob('.model-set-*')), [])

    def revise(self, change):
        policy = copy.deepcopy(self.policy)
        policy['sequence'] = self.manager.policy.current(lambda v: None)['sequence']+1
        change(policy)
        self.update(policy)
        return policy

    def test_install_fetches_exact_set_without_credentials_or_proxies_and_does_not_select(self):
        responses = self.responses(); progress = []
        with patch.dict(os.environ, {'HTTPS_PROXY': 'http://bad.invalid', 'HF_TOKEN': 'inert-credential'}), \
             patch('urllib.request.build_opener') as build:
            build.return_value.open.side_effect = responses
            path = self.manager.install(SUPER_ID, progress=progress.append)
        self.assertEqual(build.call_args.args[0].proxies, {})
        calls = build.return_value.open.call_args_list
        self.assertEqual([c.args[0].full_url for c in calls], [p['url'] for p in model_download_assets(self.super)])
        for call in calls:
            self.assertEqual(call.kwargs['timeout'], 15)
            headers = {k.lower(): v for k, v in call.args[0].header_items()}
            self.assertNotIn('authorization', headers); self.assertNotIn('proxy-authorization', headers)
        self.assertEqual(path.parent, self.directory)
        self.assertEqual(self.manager.selected(), self.profile['id'])
        self.assertTrue(self.manager.installed(self.super))
        for asset, pin in self.manager.model_asset_paths(self.super):
            self.assertEqual(asset.read_bytes(), self.payloads[pin['name']])
        self.assertTrue(all(r.read_sizes for r in responses))
        self.assertTrue(any('shard 3/3' in message for message in progress))
        self.assert_no_staging()

    def test_installed_requires_all_shards_without_hashing_and_selection_still_checks_hashes(self):
        self.install()
        with patch('local_ai_appliance.model_management.digest_file', side_effect=AssertionError('Listing hashes weights')):
            self.assertTrue(self.manager.installed(self.super))
            second = self.directory/self.super['model_shards'][1]['name']; second.unlink()
            self.assertFalse(self.manager.installed(self.super))
        with self.assertRaises(FileNotFoundError): self.manager.select(SUPER_ID)
        self.assertEqual(self.manager.selected(), self.profile['id'])

    def test_storage_identity_is_stable_across_catalog_and_signed_policy_key_order(self):
        signed = self.manager.authorize(SUPER_ID)
        self.assertNotEqual(list(self.super['model_shards'][0]), list(signed['model_shards'][0]))
        expected = self.manager.model_cache/hashlib.sha256(canonical(self.super['model_shards'])).hexdigest()
        self.assertEqual(self.manager.managed_model_path(self.super).parent, expected)
        self.assertEqual(self.manager.managed_model_path(signed).parent, expected)
        transfer = self.root/'transfer'; transfer.mkdir()
        for pin in self.super['model_shards']:
            (transfer/pin['name']).write_bytes(self.payloads[pin['name']])
        imported = self.manager.import_model(SUPER_ID, transfer/self.super['model']['name'])
        self.assertEqual(imported, self.manager.managed_model_path(self.super))
        self.assertTrue(self.manager.installed(self.super))
        with patch('urllib.request.build_opener') as build:
            self.assertEqual(self.manager.install(SUPER_ID), imported)
            build.assert_not_called()

    def test_complete_set_is_published_only_after_every_shard_is_verified(self):
        observations = []
        def progress(_):
            observations.append(self.manager.installed(self.super))
            self.assertFalse(self.directory.exists())
        self.install(progress=progress)
        self.assertEqual(observations, [False]*3)
        self.assertTrue(self.directory.exists())

    def test_integrity_tls_status_and_truncation_failures_on_later_shards_publish_nothing(self):
        for bad in ('hash', 'oversize', 'truncated', 'tls', 'status', 'network'):
            responses = self.responses()
            if bad == 'hash': responses[1] = BoundedResponse(b'x'*len(self.payloads[self.super['model_shards'][1]['name']]), responses[1].url)
            if bad == 'oversize': responses[1] = BoundedResponse(self.payloads[self.super['model_shards'][1]['name']]+b'x', responses[1].url)
            if bad == 'truncated': responses[1] = BoundedResponse(b'GGUF', responses[1].url)
            if bad == 'tls': responses[1].url = 'http://bad.invalid/model'
            if bad == 'status': responses[1].status = 206
            if bad == 'network': responses[1] = OSError('Synthetic interrupted download')
            with self.subTest(bad=bad), patch('urllib.request.build_opener') as build:
                build.return_value.open.side_effect = responses
                with self.assertRaises((AccessDenied, OSError)): self.manager.install(SUPER_ID)
            self.assertFalse(self.directory.exists()); self.assert_no_staging()
            self.assertTrue(self.manager.installed(self.profile))

    def test_matching_hashes_cannot_publish_non_gguf_shard(self):
        pin = self.super['model_shards'][2]; payload = b'NOTG inert'
        self.payloads[pin['name']] = payload
        pin.update(size=len(payload), sha256=hashlib.sha256(payload).hexdigest())
        self.revise(lambda p: p['profiles'].__setitem__(1, self.super))
        with self.assertRaisesRegex(AccessDenied, 'GGUF'): self.install()
        self.assertEqual(len(list(self.manager.model_cache.iterdir())), 1)
        self.assert_no_staging()

    def test_cancel_between_shards_cleans_the_set_without_affecting_active_single_model(self):
        cancelled = [False]
        def progress(_): cancelled[0] = True
        def cancel():
            if cancelled[0]: raise SessionCancelled('Synthetic cancellation')
        with self.assertRaises(SessionCancelled): self.install(cancel=cancel, progress=progress)
        self.assertFalse(self.directory.exists()); self.assert_no_staging()
        self.assertEqual(self.manager.verify_model(self.profile).read_bytes(), self.data)

    def test_cancel_during_later_shard_read_and_before_publication_leaves_no_set(self):
        responses = self.responses(); cancelled = [False]
        read = responses[1].read1
        def cancel_read(size):
            value = read(size); cancelled[0] = True; return value
        responses[1].read1 = cancel_read
        def cancel():
            if cancelled[0]: raise SessionCancelled('Synthetic interrupted read')
        with patch('urllib.request.build_opener') as build:
            build.return_value.open.side_effect = responses
            with self.assertRaises(SessionCancelled): self.manager.install(SUPER_ID, cancel=cancel)
        self.assertFalse(self.directory.exists()); self.assert_no_staging()

    def test_cancel_after_publication_removes_only_our_complete_set(self):
        verify = self.manager.verify_model
        def fail(profile, cancel=lambda: None):
            if profile['id'] == SUPER_ID:
                self.assertTrue(self.directory.exists())
                self.assertEqual(len(list(self.directory.iterdir())), 3)
                raise SessionCancelled('Synthetic cancelled final verification')
            return verify(profile, cancel)
        with patch.object(self.manager, 'verify_model', side_effect=fail):
            with self.assertRaises(SessionCancelled): self.install()
        self.assertFalse(self.directory.exists()); self.assert_no_staging()
        self.assertTrue(self.manager.installed(self.profile))

    def test_cancel_immediately_before_publication_leaves_no_managed_set(self):
        authorize = self.manager.authorize; checks = [0]
        def checkpoint():
            if checks[0] == 2: raise SessionCancelled('Cancelled before publication')
        def policy(*args, **kwargs):
            value = authorize(*args, **kwargs); checks[0] += 1; return value
        with patch.object(self.manager, 'authorize', side_effect=policy):
            with self.assertRaises(SessionCancelled): self.install(cancel=checkpoint)
        self.assertFalse(self.directory.exists()); self.assert_no_staging()

    def test_final_failure_cannot_delete_a_replaced_directory(self):
        from local_ai_appliance import model_management
        publish = model_management._publish_model_set
        preserved = self.root/'preserved-published-set'
        def replace(temporary, destination):
            publish(temporary, destination)
            destination.rename(preserved)
            destination.mkdir(); (destination/'unowned.txt').write_bytes(b'Preserve this')
        with patch.object(model_management, '_publish_model_set', side_effect=replace):
            with self.assertRaisesRegex(AccessDenied, 'identity changed'): self.install()
        self.assertEqual((self.directory/'unowned.txt').read_bytes(), b'Preserve this')
        self.assertEqual(len(list(preserved.iterdir())), 3); self.assert_no_staging()

    def test_failure_cleanup_cannot_delete_a_set_activated_by_another_operation(self):
        verify = self.manager.verify_model
        def activate(profile, cancel=lambda: None):
            path = verify(profile, cancel)
            self.manager.vault.put('selected-model', {'id': SUPER_ID})
            raise SessionCancelled('Synthetic final cancellation')
        with patch.object(self.manager, 'verify_model', side_effect=activate):
            with self.assertRaisesRegex(AccessDenied, 'active model'): self.install()
        self.assertTrue(self.manager.installed(self.super)); self.assert_no_staging()

    def test_policy_revocation_or_changed_last_shard_before_publication_is_denied(self):
        for change in ('revoked', 'last-shard'):
            changed = [False]
            def progress(_):
                if changed[0]: return
                changed[0] = True
                def mutation(p):
                    if change == 'revoked': p['profiles'][1]['status'] = 'revoked'
                    else: p['profiles'][1]['model_shards'][2]['sha256'] = '0'*64
                self.revise(mutation)
            with self.subTest(change=change), self.assertRaises(AccessDenied): self.install(progress=progress)
            self.assertFalse(self.directory.exists()); self.assert_no_staging()
            self.revise(lambda p: p['profiles'].__setitem__(1, self.super))

    def test_disk_floor_covers_all_shards_before_any_download(self):
        from collections import namedtuple
        usage = namedtuple('usage', 'total used free')(10**9, 0, self.total+256*1024**2-1)
        with patch('shutil.disk_usage', return_value=usage), patch('urllib.request.build_opener') as build:
            with self.assertRaisesRegex(AccessDenied, 'complete model shard set'): self.manager.install(SUPER_ID)
            build.assert_not_called()
        self.assert_no_staging()

    def test_existing_partial_set_is_never_repaired_or_replaced(self):
        self.directory.mkdir()
        first = self.directory/self.super['model']['name']; first.write_bytes(self.payloads[first.name])
        with patch('urllib.request.build_opener') as build:
            with self.assertRaises(FileNotFoundError): self.manager.install(SUPER_ID)
            build.assert_not_called()
        self.assertEqual(list(self.directory.iterdir()), [first])

    def test_atomic_publication_does_not_replace_concurrently_created_empty_directory(self):
        from local_ai_appliance import model_management
        publish = model_management._publish_model_set
        def compete(temporary, destination):
            destination.mkdir()
            return publish(temporary, destination)
        with patch.object(model_management, '_publish_model_set', side_effect=compete):
            with self.assertRaises(FileNotFoundError): self.install()
        self.assertTrue(self.directory.is_dir()); self.assertEqual(list(self.directory.iterdir()), [])
        self.assert_no_staging()

    def test_atomic_publication_reuses_and_does_not_remove_concurrent_complete_set(self):
        from local_ai_appliance import model_management
        publish = model_management._publish_model_set
        def compete(temporary, destination):
            destination.mkdir()
            for pin in self.super['model_shards']:
                (destination/pin['name']).write_bytes(self.payloads[pin['name']])
            return publish(temporary, destination)
        with patch.object(model_management, '_publish_model_set', side_effect=compete):
            path = self.install()
        self.assertEqual(path.parent, self.directory); self.assert_no_staging()

    def test_remove_deletes_complete_inactive_set_and_preserves_other_model(self):
        self.install()
        self.assertEqual(self.manager.remove(SUPER_ID), self.total)
        self.assertFalse(self.directory.exists())
        self.assertTrue(self.manager.installed(self.profile))

    def test_active_or_shared_set_cannot_be_removed(self):
        self.install(); self.manager.select(SUPER_ID)
        with self.assertRaisesRegex(AccessDenied, 'active model'): self.manager.remove(SUPER_ID)
        self.manager.select(self.profile['id'])
        alias = copy.deepcopy(self.super); alias['id'] = 'shared-sharded-model'
        self.revise(lambda p: p['profiles'].append(alias))
        with self.assertRaisesRegex(AccessDenied, 'shared'): self.manager.remove(SUPER_ID)
        self.assertEqual(len(list(self.directory.iterdir())), 3)

    def test_revoked_sharded_set_is_removable(self):
        self.install()
        self.revise(lambda p: p['profiles'][1].update(status='revoked'))
        with self.assertRaises(AccessDenied): self.manager.install(SUPER_ID)
        self.assertEqual(self.manager.remove(SUPER_ID), self.total)

    def test_remove_rejects_undeclared_files_or_unsafe_shards_before_deleting_anything(self):
        self.install()
        for unsafe in ('extra-file', 'directory', 'symlink', 'hardlink'):
            extra = self.directory/'unowned.txt'
            shard = self.directory/self.super['model_shards'][2]['name']
            if unsafe == 'extra-file': extra.write_bytes(b'Preserve this')
            else:
                shard.unlink()
                if unsafe == 'directory': shard.mkdir()
                if unsafe == 'symlink': shard.symlink_to(self.source)
                if unsafe == 'hardlink': os.link(self.source, shard)
            with self.subTest(unsafe=unsafe), self.assertRaises((AccessDenied, RuntimeError)):
                self.manager.remove(SUPER_ID)
            self.assertTrue((self.directory/self.super['model']['name']).exists())
            if unsafe == 'extra-file': extra.unlink()
            elif unsafe == 'directory': shard.rmdir()
            else: shard.unlink()
            if unsafe != 'extra-file': shard.write_bytes(self.payloads[shard.name])
        self.assertEqual(self.source.read_bytes(), self.data)

    def test_broken_managed_directory_symlink_cannot_fall_back_to_legacy_or_be_installed_over(self):
        self.directory.symlink_to(self.root/'missing')
        with self.assertRaises(RuntimeError): self.manager.installed(self.super)
        with patch('urllib.request.build_opener') as build:
            with self.assertRaises(RuntimeError): self.manager.install(SUPER_ID)
            build.assert_not_called()
        with self.assertRaises(RuntimeError): self.manager.remove(SUPER_ID)
        self.assertTrue(self.directory.is_symlink())

    def test_legacy_shards_are_not_removable_application_assets(self):
        legacy = self.root/'artifacts/inference/downloads'; legacy.mkdir(parents=True)
        for pin in self.super['model_shards']:
            (legacy/pin['name']).write_bytes(self.payloads[pin['name']])
        self.assertTrue(self.manager.installed(self.super))
        with self.assertRaisesRegex(AccessDenied, 'verified application payload'): self.manager.remove(SUPER_ID)
        self.assertEqual(len(list(legacy.iterdir())), 3)


if __name__ == '__main__': unittest.main()
