"""Trusted system tools and pinned application assets have distinct identities."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from local_ai_appliance.asset_integrity import ordinary
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.model_management import _gpu_inventory_tool, scan_hardware

@unittest.skipUnless(os.name == 'nt', 'Native Windows system inventory')
class WindowsHardwareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='silo-hardware-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tool = self.root/'nvidia-smi.exe'

    def test_driver_hardlink_allowed_only_for_fixed_system_tool(self):
        self.tool.write_bytes(b'INERT FIXTURE; NEVER EXECUTED')
        (self.root/'driver-store-copy').hardlink_to(self.tool)
        self.assertEqual(self.tool.stat().st_nlink,2)
        self.assertEqual(_gpu_inventory_tool(self.root),self.tool)
        with self.assertRaisesRegex(RuntimeError,'unsupported object'):
            ordinary(self.tool)

    def test_directory_and_reparse_or_recalled_tool_refused(self):
        self.tool.mkdir()
        with self.assertRaises(AccessDenied): _gpu_inventory_tool(self.root)
        self.tool.rmdir(); self.tool.write_bytes(b'INERT FIXTURE')
        real_lstat = Path.lstat
        for flags in (0x400, 0x1000, 0x400000):
            def fixture_stat(path, *, follow_symlinks=False):
                if path == self.tool:
                    return SimpleNamespace(st_mode=self.tool.stat().st_mode,st_file_attributes=flags)
                return real_lstat(path)
            with patch.object(Path,'lstat',fixture_stat):
                with self.assertRaises(AccessDenied): _gpu_inventory_tool(self.root)

    def test_extended_attribute_bit_is_not_a_directory_recall_claim(self):
        self.tool.write_bytes(b'INERT FIXTURE; NEVER EXECUTED')
        real_lstat=Path.lstat
        info=self.tool.lstat()
        def stat_with_ea(path, *, follow_symlinks=False):
            if path==self.tool:
                return SimpleNamespace(st_mode=info.st_mode,st_file_attributes=0x40020)
            return real_lstat(path)
        with patch.object(Path,'lstat',stat_with_ea):
            # Actual directory enumeration of this local inert file has no recall.
            self.assertEqual(_gpu_inventory_tool(self.root),self.tool)
            # The stricter general software guard is deliberately unchanged.
            with self.assertRaises(RuntimeError):ordinary(self.tool)

    def test_directory_enumeration_recall_reparse_offline_and_directory_are_denied(self):
        self.tool.write_bytes(b'INERT FIXTURE; NEVER EXECUTED')
        for flags in (0x40000,0x400000,0x400,0x1000,0x10,0xffffffff):
            with self.subTest(flags=flags),patch('local_ai_appliance.model_management._gpu_directory_attributes',return_value=flags):
                with self.assertRaises(AccessDenied):_gpu_inventory_tool(self.root)

    def test_native_scanner_reads_installed_gpu_without_path_fallback(self):
        import ctypes as C
        buffer=C.create_unicode_buffer(32768)
        count=C.windll.kernel32.GetSystemDirectoryW(buffer,len(buffer))
        self.assertGreater(count,0)
        if not (Path(buffer.value)/'nvidia-smi.exe').exists():
            self.skipTest('Trusted NVIDIA inventory tool absent; GPU coverage not available')
        import subprocess
        original_run=subprocess.run
        calls=[]
        def record(*args,**kwargs):
            calls.append((args,kwargs))
            return original_run(*args,**kwargs)
        with patch('local_ai_appliance.model_management.subprocess.run',side_effect=record):
            result=scan_hardware()
        self.assertEqual(len(calls),1)
        self.assertEqual(set(calls[0][1]['env']),{'SystemRoot','ProgramFiles'})
        self.assertEqual(calls[0][0][0][0],str(Path(buffer.value)/'nvidia-smi.exe'))
        self.assertGreater(result.ram_mib,0)
        self.assertTrue(result.gpus)
        for gpu in result.gpus:
            self.assertGreater(gpu['vram_mib'],0)
            self.assertLessEqual(len(gpu['name']),128)
