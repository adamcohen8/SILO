"""Held-handle failure contracts and real Windows mutation/unchanged controls."""
import ctypes as C
import hashlib
import io
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from local_ai_appliance import windows_asset_file as waf
from local_ai_appliance.asset_integrity import digest_file
from local_ai_appliance.windows_native import FileInformation


def fill(pointer, kind, **fields):
    value = C.cast(pointer, C.POINTER(kind)).contents
    for name, data in fields.items():
        setattr(value, name, data)
    return 1


def kernel_fixture(*, attributes=0x20, links=1, disk=1, change=101):
    return SimpleNamespace(
        GetFileInformationByHandle=Mock(side_effect=lambda handle, ptr:
            fill(ptr, FileInformation, Attributes=attributes, Links=links,
                 VolumeSerial=7, IndexLow=11, SizeLow=24)),
        GetFileInformationByHandleEx=Mock(side_effect=lambda handle, kind, ptr, size:
            fill(ptr, waf.FileBasicInfo, creation=1, write=2, change=change, attributes=attributes)),
        GetFileType=Mock(return_value=disk), CreateFileW=Mock(return_value=123),
        CloseHandle=Mock())


class WindowsAssetContracts(unittest.TestCase):
    def test_native_snapshot_keeps_change_time_distinct_from_creation_and_write(self):
        self.assertEqual(C.sizeof(waf.FileBasicInfo), 40)
        self.assertEqual(waf.FileBasicInfo.change.offset, 24)
        before = waf.snapshot(kernel_fixture(change=101), 123)
        after = waf.snapshot(kernel_fixture(change=102), 123)
        self.assertNotEqual(before, after)
        self.assertEqual(before[:8], after[:8])

    def test_unsafe_native_objects_are_refused_before_hashing(self):
        for attrs, links, disk in ((0x10, 1, 1), (0x400, 1, 1), (0x1000, 1, 1),
                                  (0x40000, 1, 1), (0x400000, 1, 1), (0x20, 2, 1), (0x20, 1, 3)):
            with self.subTest(attributes=attrs, links=links, disk=disk):
                with self.assertRaisesRegex(RuntimeError, 'unsupported native object'):
                    waf.snapshot(kernel_fixture(attributes=attrs, links=links, disk=disk), 123)

    def test_missing_native_change_time_is_a_failure_not_a_python_stat_fallback(self):
        kernel = kernel_fixture()
        kernel.GetFileInformationByHandleEx.return_value = 0
        kernel.GetFileInformationByHandleEx.side_effect = None
        with patch.object(C, 'get_last_error', return_value=87, create=True):
            with self.assertRaises(OSError) as caught:
                waf.snapshot(kernel, 123)
        self.assertEqual(caught.exception.winerror, 87)
        self.assertIn('ChangeTime', str(caught.exception))

    def test_conflicting_writer_never_causes_a_permissive_open_retry(self):
        kernel = kernel_fixture()
        kernel.CreateFileW.return_value = C.c_void_p(-1).value
        crt = SimpleNamespace(open_osfhandle=Mock())
        with patch.object(waf, '_kernel', return_value=kernel), \
             patch.dict('sys.modules', msvcrt=crt), \
             patch.object(C, 'get_last_error', return_value=32, create=True):
            with self.assertRaises(OSError) as caught:
                with waf.locked_stream('synthetic.txt'):
                    self.fail('A writer conflict must prevent content access')
        self.assertEqual(caught.exception.winerror, 32)
        self.assertEqual(kernel.CreateFileW.call_count, 1)
        self.assertEqual(kernel.CreateFileW.call_args.args[1:],
                         (0x80000000, 1, None, 3, 0x08300000, None))
        crt.open_osfhandle.assert_not_called()
        kernel.CloseHandle.assert_not_called()

    def test_failure_before_crt_transfer_closes_owned_native_handle(self):
        kernel = kernel_fixture(attributes=0x400)
        crt = SimpleNamespace(open_osfhandle=Mock())
        with patch.object(waf, '_kernel', return_value=kernel), patch.dict('sys.modules', msvcrt=crt):
            with self.assertRaises(RuntimeError):
                with waf.locked_stream('synthetic.txt'):
                    self.fail('Unsafe handle must not be yielded')
        kernel.CloseHandle.assert_called_once_with(123)
        crt.open_osfhandle.assert_not_called()

    def test_crt_ownership_transfer_closes_stream_on_consumer_failure(self):
        kernel = kernel_fixture()
        crt = SimpleNamespace(open_osfhandle=Mock(return_value=456))
        stream = io.BytesIO(b'SYNTHETIC')
        with patch.object(waf, '_kernel', return_value=kernel), patch.dict('sys.modules', msvcrt=crt), \
             patch.object(waf.os, 'O_BINARY', 0x8000, create=True), \
             patch.object(waf.os, 'fdopen', return_value=stream):
            with self.assertRaisesRegex(RuntimeError, 'consumer cancelled'):
                with waf.locked_stream('synthetic.txt') as (opened, stamp):
                    self.assertEqual(opened.read(), b'SYNTHETIC')
                    self.assertEqual(stamp(), waf.snapshot(kernel, 123))
                    raise RuntimeError('consumer cancelled')
        self.assertTrue(stream.closed)
        kernel.CloseHandle.assert_not_called()  # Owned/closed by CRT stream.


@unittest.skipUnless(os.name == 'nt', 'Actual Windows file sharing and ChangeTime required')
class NativeWindowsAssetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='silo-integrity-34-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name).resolve()/'synthetic.bin'

    def test_repeated_same_size_writes_are_blocked_and_unchanged_hashes_pass(self):
        original, changed = b'Original synthetic bytes', b'Changed! synthetic bytes'
        for trial in range(100):
            with self.subTest(trial=trial):
                self.path.write_bytes(original)
                before = self.path.stat()
                refusals = []
                def mutate():
                    try:
                        self.path.write_bytes(changed)
                        os.utime(self.path, ns=(before.st_atime_ns, before.st_mtime_ns))
                    except OSError as error:
                        self.assertEqual(error.winerror, 32)
                        refusals.append(error.winerror)
                    else:
                        self.fail('A same-size writer bypassed the live verification lease')
                self.assertEqual(digest_file(self.path, cancel=mutate), hashlib.sha256(original).hexdigest())
                self.assertEqual(refusals, [32])
                self.assertEqual(self.path.read_bytes(), original)
                self.assertEqual(digest_file(self.path), hashlib.sha256(original).hexdigest())
                # The read lease must also be released after successful hashing.
                self.path.write_bytes(changed)
                self.assertEqual(digest_file(self.path), hashlib.sha256(changed).hexdigest())

    def test_existing_writer_blocks_verification_and_no_digest_is_returned(self):
        self.path.write_bytes(b'SYNTHETIC EXISTING WRITER')
        with self.path.open('r+b'):
            with self.assertRaises(OSError) as caught:
                digest_file(self.path)
        self.assertEqual(caught.exception.winerror, 32)
        self.assertEqual(digest_file(self.path), hashlib.sha256(self.path.read_bytes()).hexdigest())

    def test_rename_and_delete_are_denied_until_final_verification_finishes(self):
        content = b'SYNTHETIC NAME STABILITY'
        self.path.write_bytes(content)
        target = self.path.with_name('renamed.bin')
        def mutate():
            for operation in (lambda: self.path.rename(target), self.path.unlink):
                with self.assertRaises(OSError) as caught:
                    operation()
                self.assertEqual(caught.exception.winerror, 32)
        self.assertEqual(digest_file(self.path, cancel=mutate), hashlib.sha256(content).hexdigest())
        self.path.rename(target)
        target.unlink()

    def test_empty_file_and_independent_readers_remain_supported(self):
        for content in (b'', b'SYNTHETIC READ SHARING'):
            with self.subTest(content=content):
                self.path.write_bytes(content)
                with self.path.open('rb') as reader:
                    self.assertEqual(digest_file(self.path), hashlib.sha256(content).hexdigest())
                    self.assertEqual(reader.read(), content)
