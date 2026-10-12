"""Public bootstrap packaging and source integrity; no release is published."""
import hashlib
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from local_ai_appliance.evaluation_install import unpack, verify_release, release_id
from local_ai_appliance.release_bootstrap import assemble, curl_command, git_snapshot, write_assets, repin_bootstrap

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('git'), 'Maintainer Git snapshot tooling required')
class ReleaseBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = git_snapshot(ROOT, subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip())
        # Tests use the pending reviewed template/helper edits before commit.
        for name in ('installer/Bootstrap-Evaluation.ps1.in','installer/Evaluation-Common.ps1','installer/Install-Evaluation.ps1',
                     'installer/Activate-SILO.ps1','src/local_ai_appliance/managed_installation.py','scripts/install_managed.py',
                     'src/local_ai_appliance/machine_security.py','src/local_ai_appliance/managed_deployment.py',
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
        self.assertTrue(metadata['reviewed_activation_supported'])
        self.assertIn('Default: prepare an inactive candidate', assets['INSTALL.md'].decode())
        incomplete={name: data for name, data in self.source.items() if name != 'scripts/install_managed.py'}
        with self.assertRaisesRegex(ValueError, 'complete managed installer'): self.build(incomplete)
    def test_repeat_generation_and_no_existing_output_replacement(self):
        assets, metadata = self.build()
        self.assertEqual(self.build()[0],assets)
        write_assets(assets,self.root/'release')
        with self.assertRaises(FileExistsError):write_assets(assets,self.root/'release')
        self.assertEqual((self.root/'release/install.ps1').read_bytes(),assets['install.ps1'])
    def test_external_signature_repin_preserves_source_and_requires_native_verification(self):
        assets, metadata = self.build()
        # Inert comment fixture exercises pin regeneration, never real signing.
        signed = assets['install.ps1'] + b'\r\n# SIG # Begin signature block\r\n# U3ludGhldGlj\r\n# SIG # End signature block\r\n'
        result = repin_bootstrap(assets, signed)
        fresh = json.loads(result['release.json'])
        self.assertEqual(fresh['bootstrap']['sha256'], hashlib.sha256(signed).hexdigest())
        self.assertEqual(fresh['bootstrap']['size'], len(signed))
        self.assertIn(fresh['bootstrap']['sha256'], result['INSTALL.md'].decode())
        self.assertFalse(fresh['authenticode_signed'])
        self.assertEqual(fresh['authenticode_status'], 'supplied_pending_native_verification')
        self.assertEqual(result[metadata['source_archive']['filename']], assets[metadata['source_archive']['filename']])
        for bad in (signed.replace(b'#Requires', b'#Changed', 1), signed + b'Write-Output injected\n', assets['install.ps1']):
            with self.assertRaises(ValueError): repin_bootstrap(assets, bad)
    def test_signed_helper_is_archived_exactly_and_embedded_without_nested_signature(self):
        source = dict(self.source)
        helper = source['installer/Evaluation-Common.ps1']
        trailer = b'\r\n# SIG # Begin signature block\r\n# U3ludGhldGlj\r\n# SIG # End signature block\r\n'
        source['installer/Evaluation-Common.ps1'] = helper + trailer
        assets, metadata = self.build(source)
        self.assertNotIn(b'# SIG # Begin signature block', assets['install.ps1'])
        archive = self.root / 'source.zip'; archive.write_bytes(assets[metadata['source_archive']['filename']])
        unpack(archive, self.root / 'source')
        self.assertEqual((self.root / 'source/payload/installer/Evaluation-Common.ps1').read_bytes(), helper + trailer)
        repin_bootstrap(assets, assets['install.ps1'] + trailer)
        source['installer/Evaluation-Common.ps1'] += b'Write-Output injected\n'
        with self.assertRaisesRegex(ValueError, 'unsupported signature'): self.build(source)
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
    def test_activation_arguments_are_literal_and_cannot_inject_powershell(self):
        value = "C:\\Approved\\plan'$(Write-Output injected)`n.json"
        command = curl_command('https://example.invalid/install.ps1', 'a' * 64, 123,
                               installer_arguments={'Activate': True, 'ActivationPlan': value,
                                                    'ActivationPlanSha256': 'b' * 64})
        self.assertIn(" -Activate -ActivationPlan 'C:\\Approved\\plan''$(Write-Output injected)`n.json'", command)
        for arguments in ({'ExecutionPolicy': 'Bypass'}, {'ActivationPlan': 'bad\nvalue'}, {'Activate': 1}):
            with self.assertRaises(ValueError):
                curl_command('https://example.invalid/install.ps1', 'a' * 64, 123, installer_arguments=arguments)
    def test_activation_command_builder_checks_pins_paths_and_preserves_existing_output(self):
        assets, metadata = self.build()
        release = self.root / 'release'; write_assets(assets, release)
        prepared_source = self.root / 'prepared-source'
        unpack(release / metadata['source_archive']['filename'], prepared_source)
        source_id = release_id(prepared_source / 'payload')
        public = b'Public inert structural fixture!'  # 32 bytes; not a signing key.
        self.assertEqual(len(public), 32)
        record = {'key': base64.b64encode(public).decode(), 'sha256': hashlib.sha256(public).hexdigest()}
        plan = {'format': 1, 'source_id': source_id, 'release_name': 'synthetic-release',
                'user_sid': 'S-1-5-21-1-2-3-1001', 'state_root': 'C:\\SILO-Preparation\\state',
                'model_id': 'synthetic-profile', 'anchors': {role: record for role in
                                                          ('trust-anchor', 'release-anchor', 'reviewer-anchor')},
                'settings': {'reference_roots': ['C:\\Synthetic\\References'], 'draft_roots': ['C:\\Synthetic\\Drafts'],
                             'excluded_roots': ['C:\\SILO-Preparation\\state'], 'allow_code': False,
                             'allow_code_exports': False, 'allow_ocr': False, 'allow_schedules': False,
                             'maximum_retention_days': 30}}
        # The command builder checks structure/pins. Real signatures and model/OS
        # acceptance are deliberately not claimed here; activation rejects these.
        for field in ('model_policy', 'advisories', 'maintenance', 'release_envelope', 'technical_receipt'):
            plan[field] = base64.b64encode(b'Unsigned inert document fixture').decode()
        plan_path = self.root / 'plan.json'; plan_path.write_bytes(json.dumps(plan).encode())
        output = self.root / 'activation.md'
        args = [sys.executable, str(ROOT / 'scripts/build_install_command.py'), '--release', str(release),
                '--plan', str(plan_path), '--plan-sha256', hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                '--install-root', 'c:\\silo-preparation', '--target-plan-path', "C:\\Approved\\plan'$(inert).json",
                '--output', str(output)]
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        original = output.read_bytes()
        self.assertIn(metadata['bootstrap']['sha256'].encode(), original)
        self.assertIn(b" -InstallRoot 'C:\\SILO-Preparation'", original)
        self.assertIn(b" -Activate -ActivationPlan 'C:\\Approved\\plan''$(inert).json'", original)
        self.assertNotEqual(subprocess.run(args, capture_output=True, timeout=30).returncode, 0)
        self.assertEqual(output.read_bytes(), original)
        output.unlink()
        plan['source_id'] = '0' * 16
        plan_path.write_bytes(json.dumps(plan).encode())
        args[args.index('--plan-sha256') + 1] = hashlib.sha256(plan_path.read_bytes()).hexdigest()
        mismatch = subprocess.run(args, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(mismatch.returncode, 0); self.assertFalse(output.exists())
        self.assertIn('Release source differs', mismatch.stderr)
        plan['source_id'] = source_id
        plan_path.write_bytes(json.dumps(plan).encode())
        args[args.index('--plan-sha256') + 1] = hashlib.sha256(plan_path.read_bytes()).hexdigest()
        (release / 'install.ps1').write_bytes(b'Changed bootstrap')
        corrupt = subprocess.run(args, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(corrupt.returncode, 0); self.assertFalse(output.exists())
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
            policy = ['-ExecutionPolicy','RemoteSigned'] if os.name == 'nt' else []
            return subprocess.run([pwsh,'-NoLogo','-NoProfile',*policy,'-File',str(runner),str(self.root),str(fixture),str(receipt),mode],capture_output=True,text=True,timeout=30)
        good=invoke()
        if os.name == 'nt':
            # The generated command preserves Internet-zone provenance. Our
            # unsigned fixture must remain blocked under process RemoteSigned.
            self.assertNotEqual(good.returncode,0)
            # PowerShell may wrap this phrase with error-view gutters.
            self.assertIn('not digitally signed', ' '.join(good.stderr.replace('|', ' ').split()))
            self.assertFalse(receipt.exists())
        else:
            self.assertEqual(good.returncode,0,good.stderr)
            self.assertEqual(receipt.read_text(),'verified')
        fixture.write_bytes(b'# Inert wrong bootstrap bytes\n')
        wrong=invoke();self.assertNotEqual(wrong.returncode,0)
        self.assertIn('Bootstrap integrity failed',wrong.stderr)
        self.assertEqual(receipt.read_text() if receipt.exists() else None, None if os.name == 'nt' else 'verified')
        failed=invoke('fail');self.assertNotEqual(failed.returncode,0)
        self.assertIn('Bootstrap download failed',failed.stderr)
        self.assertEqual(receipt.read_text() if receipt.exists() else None, None if os.name == 'nt' else 'verified')
    @unittest.skipUnless(shutil.which('pwsh') or Path('/private/tmp/local-ai-powershell/pwsh').exists(), 'Optional portable PowerShell required')
    def test_standalone_bootstrap_source_gate_and_cached_source_drift(self):
        source={**self.source}
        source['installer/Install-Evaluation.ps1']=(
            'param([string]$InstallRoot,[string]$CachePath,[switch]$NoLaunch,[switch]$NoShortcut,[switch]$Repair,[switch]$PrepareOnly,[switch]$Offline,[string]$ModelId,[switch]$Activate,[string]$ActivationPlan,[string]$ActivationPlanSha256,[string]$Interface)\n'
            'if (-not $PrepareOnly -and -not $Activate) { throw "Mode was not forwarded" }\n'
            '[IO.File]::WriteAllText((Join-Path $InstallRoot "forwarded.json"),($PSBoundParameters | ConvertTo-Json))\n'
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
        runner.write_text("""
$env:OS='Windows_NT'
$parameters=@{InstallRoot=$args[1]; NoLaunch=$true; NoShortcut=$true}
switch ($args[2]) {
    'offline' { $parameters.Offline=$true; $parameters.ModelId='synthetic-cpu'; $parameters.CachePath='fixture-cache' }
    'activate' { $parameters.Activate=$true; $parameters.ActivationPlan='fixture-plan'; $parameters.ActivationPlanSha256='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'; $parameters.Interface='Desktop' }
    'conflict' { $parameters.Activate=$true; $parameters.PrepareOnly=$true }
    'unbound' { $parameters.ActivationPlan='fixture-plan' }
    'rollback' { $parameters.Rollback=$true }
}
& $args[0] @parameters
""",encoding='utf-8-sig')
        pwsh=shutil.which('pwsh') or '/private/tmp/local-ai-powershell/pwsh'
        def invoke(mode='prepare'):
            return subprocess.run([pwsh,'-NoLogo','-NoProfile','-File',str(runner),str(bootstrap),str(state),mode],capture_output=True,text=True,timeout=30)
        first=invoke();self.assertEqual(first.returncode,0,first.stderr)
        self.assertTrue(json.loads((state/'forwarded.json').read_text())['PrepareOnly'])
        second=invoke();self.assertEqual(second.returncode,0,second.stderr)
        offline=invoke('offline');self.assertEqual(offline.returncode,0,offline.stderr)
        forwarded=json.loads((state/'forwarded.json').read_text())
        self.assertTrue(forwarded['Offline']);self.assertEqual(forwarded['ModelId'],'synthetic-cpu')
        activation=invoke('activate');self.assertEqual(activation.returncode,0,activation.stderr)
        forwarded=json.loads((state/'forwarded.json').read_text())
        self.assertTrue(forwarded['Activate']);self.assertNotIn('PrepareOnly',forwarded)
        self.assertEqual(forwarded['ActivationPlan'],'fixture-plan');self.assertEqual(forwarded['Interface'],'Desktop')
        calls=(state/'install-called.txt').read_bytes()
        for mode in ('conflict','unbound','rollback'):
            refused=invoke(mode);self.assertNotEqual(refused.returncode,0)
            self.assertEqual((state/'install-called.txt').read_bytes(),calls)
        source_cache=cache/pin['filename']
        moved=cache/'fixture-retained.zip';source_cache.rename(moved)
        missing=invoke('offline');self.assertNotEqual(missing.returncode,0)
        self.assertIn('Offline source cache is missing',missing.stderr)
        self.assertEqual((state/'install-called.txt').read_bytes(),calls)
        moved.rename(source_cache)
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
