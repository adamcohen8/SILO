import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.mentions import MentionCatalog, parsed_mentions
from local_ai_appliance.windows_folders import WindowsFolderBroker
from local_ai_appliance.workspace import Workspace
from local_ai_appliance.directory_requests import list_directory_request


@unittest.skipUnless(os.name == 'nt', 'Native Windows folder metadata required')
class MentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.reference = self.root/'Reference'
        (self.reference/'sub folder').mkdir(parents=True)
        (self.reference/'root.txt').write_bytes(b'Private fixture text.')
        (self.reference/'sub folder'/'Radio spec.pdf').write_bytes(b'Metadata fixture only.')
        self.workspace = Workspace(WindowsFolderBroker(validation_mode=True))
        self.addCleanup(self.workspace.close)
        self.broker = self.workspace.broker
        self.folder = self.workspace.grant(self.reference, 'read-only')

    def test_name_only_suggestions_and_quoted_nested_resolution(self):
        with patch.object(self.broker, 'read_file', side_effect=AssertionError('Mention lookup read contents')):
            catalog = MentionCatalog(self.broker)
            file = catalog.suggestions('@', 'radio')[0]
            self.assertEqual(file.token, '@"Reference/sub folder/Radio spec.pdf"')
            self.assertEqual(catalog.suggestions('/', 'sub')[0].token, '/"Reference/sub folder"')
            result = catalog.resolve(self.broker, 'Summarize '+file.token)
        self.assertEqual(result[0]['folder_id'], self.folder.id)
        self.assertEqual(result[0]['path'], 'sub folder/Radio spec.pdf')
        self.assertEqual(result[0]['kind'], 'file')

    def test_emails_urls_ratios_and_inline_slashes_are_not_mentions(self):
        self.assertEqual(parsed_mentions('user@example.com https://example.com/a/b TCP/IP 1/2 C:/folder'), [])
        self.assertEqual(parsed_mentions('Read @root.txt in /Reference.'),
                         [('@root.txt', '@', 'root.txt'), ('/Reference.', '/', 'Reference.')])

    def test_unknown_traversal_wrong_type_and_revocation_cannot_expand_access(self):
        catalog = MentionCatalog(self.broker)
        for prompt in ('Read @Reference/../outside.txt', 'Read @Unknown/private.txt',
                       'Read @Reference/sub', 'List /Reference/root.txt'):
            with self.subTest(prompt=prompt), self.assertRaises(AccessDenied):
                catalog.resolve(self.broker, prompt)
        self.workspace.revoke(self.folder.id)
        with self.assertRaisesRegex(AccessDenied, 'changed'):
            catalog.resolve(self.broker, 'Read @Reference/root.txt')

    def test_duplicate_names_are_distinguished_and_bare_filename_is_ambiguous(self):
        other = self.root/'Other'/'Reference'
        other.mkdir(parents=True)
        (other/'root.txt').write_bytes(b'Other synthetic file.')
        self.workspace.grant(other, 'read-only')
        catalog = MentionCatalog(self.broker)
        self.assertEqual(len(catalog.suggestions('@', 'root.txt')), 2)
        with self.assertRaises(AccessDenied):
            catalog.resolve(self.broker, 'Read @root.txt')
        with self.assertRaises(AccessDenied):
            catalog.resolve(self.broker, 'List /Reference')
        resolved = [catalog.resolve(self.broker, 'Read '+item.token)[0]['folder_id']
                    for item in catalog.suggestions('@', 'root.txt')]
        self.assertEqual(len(set(resolved)), 2)

    def test_preview_bounds_allow_explicit_paths_but_do_not_guess_basenames(self):
        catalog = MentionCatalog(self.broker, max_entries=1)
        self.assertTrue(catalog.incomplete)
        result = catalog.resolve(self.broker, 'Read @"Reference/sub folder/Radio spec.pdf"')
        self.assertEqual(result[0]['path'], 'sub folder/Radio spec.pdf')
        with self.assertRaises(AccessDenied):
            catalog.resolve(self.broker, 'Read @root.txt')

    def test_folder_listing_uses_the_exact_resolved_root(self):
        catalog = MentionCatalog(self.broker)
        prompt = 'Please list the files in /Reference'
        with patch.object(self.broker, 'read_file', side_effect=AssertionError('Listing read contents')):
            refs = catalog.resolve(self.broker, prompt)
            result = list_directory_request(self.workspace, prompt, references=refs)
        self.assertIn('- root.txt', result.answer)
        self.assertEqual(result.model_calls, 0)

