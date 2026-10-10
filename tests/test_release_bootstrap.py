"""Public bootstrap packaging and source integrity; no release is published."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from local_ai_appliance.evaluation_install import unpack, verify_release
from local_ai_appliance.release_bootstrap import assemble, curl_command, git_snapshot, write_assets

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('git'), 'Maintainer Git snapshot tooling required')
class ReleaseBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = git_snapshot(ROOT, subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip())
        # Tests use the pending reviewed template/helper edits before commit.
        for name in ('installer/Bootstrap-Evaluation.ps1.in','installer/Evaluation-Common.ps1',
                     'assets/branding/silo.png','assets/branding/silo.ico'):
            cls.source[name] = (ROOT/name).read_bytes()
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
    def build(self, source=None):
        return assemble(self.source if source is None else source, 'a'*40, 'example/local-ai', 'evaluation-test-1')
    def test_source_package_manifest_bootstrap_bindings_and_exact_command(self):
        assets, metadata = self.build()
        pin = metadata['source_archive']
        self.assertEqual(hashlib.sha256(assets[pin['filename']]).hexdigest(),pin['sha256'])
        self.assertEqual(len(assets[pin['filename']]),pin['size'])
        archive = self.root/'source.zip';archive.write_bytes(assets[pin['filename']])
        unpack(archive,self.root/'source')
        verify_release(self.root/'source',metadata['source_manifest_sha256'])
        self.assertEqual((self.root/'source/payload/assets/branding/silo.ico').read_bytes(), self.source['assets/branding/silo.ico'])
        script = assets['install.ps1'].decode('utf-8-sig')
        self.assertNotIn('@@',script)
        self.assertNotIn('$PSScriptRoot',script)
        self.assertIn(pin['sha256'],script)
        self.assertIn(metadata['source_manifest_sha256'],script)
        self.assertIn('Test-EvaluationRelease $source $sourceManifestSha256',script)
        self.assertIn(':Zone.Identifier',script)
        command = assets['INSTALL.md'].decode()
        self.assertIn('curl.exe --disable --fail',command)
        self.assertIn(metadata['bootstrap']['sha256'],command)
        self.assertLess(command.index('ComputeHash'),command.index('; & $b'))
        self.assertIn("[IO.File]::Open($b,'Open','Read','Read')",command)
        for text in (script,command):
            self.assertNotIn('Invoke-Expression',text)
            self.assertNotIn('ExecutionPolicy Bypass',text)
            self.assertNotIn('Unblock-File',text)
        self.assertFalse(metadata['published'])
        self.assertFalse(metadata['deployment_ready'])
        self.assertFalse(metadata['authenticode_signed'])
    def test_repeat_generation_and_no_existing_output_replacement(self):
        assets, metadata = self.build()
        self.assertEqual(self.build()[0],assets)
        write_assets(assets,self.root/'release')
        with self.assertRaises(FileExistsError):write_assets(assets,self.root/'release')
        self.assertEqual((self.root/'release/install.ps1').read_bytes(),assets['install.ps1'])
    def test_source_drift_and_undeclared_file_are_denied(self):
        assets, metadata = self.build()
        archive = self.root/'source.zip';archive.write_bytes(assets[metadata['source_archive']['filename']])
        unpack(archive,self.root/'source')
        icon = self.root/'source/payload/assets/branding/silo.ico'
        original_icon = icon.read_bytes(); icon.write_bytes(b'Inert changed icon')
        with self.assertRaises(RuntimeError):verify_release(self.root/'source',metadata['source_manifest_sha256'])
        icon.write_bytes(original_icon)
        target=self.root/'source/payload/installer/Install-Evaluation.ps1'
        original=target.read_bytes();target.write_bytes(b'Inert changed script')
        with self.assertRaises(RuntimeError):verify_release(self.root/'source',metadata['source_manifest_sha256'])
        target.write_bytes(original)
        (target.parent/'unexpected.ps1').write_bytes(b'Inert undeclared file')
        with self.assertRaises(RuntimeError):verify_release(self.root/'source',metadata['source_manifest_sha256'])
    def test_incomplete_source_unsafe_tags_credentials_and_aliases_are_denied(self):
        for repository,tag in [('example/repo',"bad';exit"),('example/repo','../tag'),('bad/repo?query','safe')]:
            with self.assertRaises(ValueError):assemble(self.source,'a'*40,repository,tag)
        with self.assertRaises(ValueError):assemble(self.source,'main','example/repo','safe')
        with self.assertRaises(ValueError):self.build({})
        for name in ('.env','models/model.gguf','docs/../escape.md','Readme.md', 'assets/branding/unreviewed.ico'):
            source={**self.source,name:b'Inert fixture'}
            with self.assertRaises((ValueError,RuntimeError)):self.build(source)
    @unittest.skipUnless(shutil.which('pwsh') or Path('/private/tmp/local-ai-powershell/pwsh').exists(), 'Optional portable PowerShell required')
    def test_curl_command_checks_download_status_and_held_bytes_before_execution(self):
        fixture=self.root/'curl-fixture.ps1'
        data=b'[IO.File]::AppendAllText($env:BOOTSTRAP_RECEIPT,"verified")\n'
        fixture.write_bytes(data)
        receipt=self.root/'receipt.txt'
        command=curl_command('https://example.invalid/install.ps1',hashlib.sha256(data).hexdigest(),len(data))
        # Curl is a controlled file-copy fixture. The generated command's
        # download-status/hash/held-handle/ordinary script invocation are real.
        runner=self.root/'curl-test.ps1'
        runner.write_text('''
$ErrorActionPreference='Stop'
$env:TEMP=$args[0]
$env:BOOTSTRAP_RECEIPT=$args[2]
$sourceFixture=$args[1]
$failDownload=$args[3]
function curl.exe {
    if ($failDownload -eq 'fail') { $global:LASTEXITCODE=22; return }
    $index=[Array]::IndexOf($args,'--output')
    [IO.File]::Copy($sourceFixture,$args[$index+1],$false)
    $global:LASTEXITCODE=0
}
'''+command,encoding='utf-8-sig')
        pwsh=shutil.which('pwsh') or '/private/tmp/local-ai-powershell/pwsh'
        def invoke(mode='ok'):
            return subprocess.run([pwsh,'-NoLogo','-NoProfile','-File',str(runner),str(self.root),str(fixture),str(receipt),mode],capture_output=True,text=True,timeout=30)
        good=invoke();self.assertEqual(good.returncode,0,good.stderr)
        self.assertEqual(receipt.read_text(),'verified')
        fixture.write_bytes(b'# Inert wrong bootstrap bytes\n')
        wrong=invoke();self.assertNotEqual(wrong.returncode,0)
        self.assertIn('Bootstrap integrity failed',wrong.stderr)
        self.assertEqual(receipt.read_text(),'verified')
        failed=invoke('fail');self.assertNotEqual(failed.returncode,0)
        self.assertIn('Bootstrap download failed',failed.stderr)
        self.assertEqual(receipt.read_text(),'verified')
    @unittest.skipUnless(shutil.which('pwsh') or Path('/private/tmp/local-ai-powershell/pwsh').exists(), 'Optional portable PowerShell required')
    def test_standalone_bootstrap_source_gate_and_cached_source_drift(self):
        source={**self.source}
        source['installer/Install-Evaluation.ps1']=(
            'param([string]$InstallRoot,[string]$CachePath,[switch]$NoLaunch,[switch]$NoShortcut,[switch]$Repair,[switch]$Rollback)\n'
            '[IO.File]::AppendAllText((Join-Path $InstallRoot "install-called.txt"),"called\\n")\n').encode()
        assets,metadata=self.build(source)
        state=self.root/'state';state.mkdir()
        cache=state/'source-cache';cache.mkdir()
        pin=metadata['source_archive'];(cache/pin['filename']).write_bytes(assets[pin['filename']])
        # Only native path/ACL/ADS behavior is mocked. Actual held-handle archive
        # verification and complete extracted-source verification are retained.
        mocks='''
function Test-LocalPath([string]$Path,[switch]$Directory) { return [IO.Path]::GetFullPath($Path) }
function New-PrivateDirectory([string]$Path) { [IO.Directory]::CreateDirectory($Path) | Out-Null; return $Path }
function Set-Content { param([string]$LiteralPath,[string]$Encoding,[string]$Value) }
'''
        script=assets['install.ps1'].decode('utf-8-sig').replace("$sourcePin = @'",mocks+"\n$sourcePin = @'",1)
        bootstrap=self.root/'bootstrap.ps1';bootstrap.write_text(script,encoding='utf-8-sig')
        runner=self.root/'run.ps1'
        runner.write_text("$env:OS='Windows_NT'\n& $args[0] -InstallRoot $args[1] -NoLaunch -NoShortcut\n",encoding='utf-8-sig')
        pwsh=shutil.which('pwsh') or '/private/tmp/local-ai-powershell/pwsh'
        def invoke():
            return subprocess.run([pwsh,'-NoLogo','-NoProfile','-File',str(runner),str(bootstrap),str(state)],capture_output=True,text=True,timeout=30)
        first=invoke();self.assertEqual(first.returncode,0,first.stderr)
        second=invoke();self.assertEqual(second.returncode,0,second.stderr)
        calls=(state/'install-called.txt').read_bytes()
        (cache/pin['filename']).write_bytes(b'Inert corrupted archive')
        corrupt=invoke();self.assertNotEqual(corrupt.returncode,0)
        self.assertEqual((state/'install-called.txt').read_bytes(),calls)
        (cache/pin['filename']).write_bytes(assets[pin['filename']])
        source_dir=next(p for p in (state/'sources').iterdir() if p.is_dir())
        entry=source_dir/'payload/installer/Install-Evaluation.ps1'
        entry.write_bytes(entry.read_bytes()+b'\n# Inert tamper\n')
        failed=invoke()
        self.assertNotEqual(failed.returncode,0)
        self.assertEqual((state/'install-called.txt').read_bytes(),calls)
        self.assertIn('reviewed size or SHA-256',failed.stderr)


@unittest.skipUnless(shutil.which('git'), 'Maintainer Git snapshot tooling required')
class GitSourceSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.hooks=self.root/'disabled-hooks';self.hooks.mkdir()
        self.git('init','-q')
        self.git('config','user.name','Synthetic Test')
        self.git('config','user.email','test@example.invalid')
        (self.root/'README.md').write_bytes(b'Committed public fixture')
        self.commit()
    def git(self,*args):
        return subprocess.check_output(['git','-c','commit.gpgsign=false','-c','core.hooksPath='+str(self.hooks),*args],cwd=self.root,stderr=subprocess.PIPE)
    def commit(self):
        self.git('add','--all');self.git('commit','-qm','Synthetic source')
        self.revision=self.git('rev-parse','HEAD').decode().strip()
    def test_snapshot_uses_committed_bytes_ignores_dirty_and_untracked_files(self):
        (self.root/'README.md').write_bytes(b'Dirty local fixture')
        (self.root/'.env').write_bytes(b'Inert untracked credential fixture')
        source=git_snapshot(self.root,self.revision)
        self.assertEqual(source,{'README.md':b'Committed public fixture'})
        with self.assertRaises(ValueError):git_snapshot(self.root,'HEAD')
    def test_unexpected_tracked_files_stop_publication_packaging(self):
        (self.root/'.env').write_bytes(b'Inert tracked credential fixture');self.commit()
        with self.assertRaises(ValueError):git_snapshot(self.root,self.revision)
    @unittest.skipUnless(os.name=='posix','Native Windows link fixture needs separate privileges')
    def test_git_link_cannot_enter_release(self):
        (self.root/'docs').mkdir()
        (self.root/'docs/link.md').symlink_to(self.root/'README.md')
        self.commit()
        with self.assertRaisesRegex(ValueError,'links'):git_snapshot(self.root,self.revision)


if __name__=='__main__':unittest.main()
