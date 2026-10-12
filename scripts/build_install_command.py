"""Generate a pinned activation command for prepared release assets. Never downloads."""
import argparse
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from local_ai_appliance.managed_installation import read_plan
from local_ai_appliance.model import strict_json
from local_ai_appliance.release_bootstrap import curl_command
from local_ai_appliance.evaluation_install import asset, verify_download, unpack, verify_release, release_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', required=True, type=Path)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--install-root', required=True, help='Exact target Windows preparation root')
    parser.add_argument('--target-plan-path', required=True, help='Approved plan location on the target Windows host')
    parser.add_argument('--interface', choices=('Terminal', 'Desktop'), default='Terminal')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        plan = read_plan(args.plan, args.plan_sha256)
        from pathlib import PureWindowsPath
        if not PureWindowsPath(args.install_root).is_absolute() or not PureWindowsPath(args.target_plan_path).is_absolute():
            raise ValueError('Use absolute target Windows paths for installation and the reviewed plan')
        if PureWindowsPath(plan['state_root']) != PureWindowsPath(args.install_root) / 'state':
            raise ValueError('Install root differs from the reviewed private state')
        metadata = strict_json((args.release / 'release.json').read_bytes())
        if metadata.get('reviewed_activation_supported') is not True:
            raise ValueError('This release bootstrap does not support reviewed managed activation')
        for field in ('source_archive', 'bootstrap'):
            pin = metadata[field]
            verify_download(args.release / asset(pin), pin)
        with tempfile.TemporaryDirectory(prefix='silo-command-source-') as temporary:
            source = Path(temporary).resolve() / 'source'
            unpack(args.release / asset(metadata['source_archive']), source)
            verify_release(source, metadata['source_manifest_sha256'])
            if release_id(source / 'payload') != plan['source_id']:
                raise ValueError('Release source differs from the reviewed activation plan')
        bootstrap = metadata['bootstrap']
        command = curl_command(bootstrap['url'], bootstrap['sha256'], bootstrap['size'],
                               installer_arguments={'InstallRoot': str(PureWindowsPath(plan['state_root']).parent), 'Activate': True,
                                                    'ActivationPlan': args.target_plan_path,
                                                    'ActivationPlanSha256': args.plan_sha256, 'Interface': args.interface})
        instructions = ('# Prepared one-command managed installation\n\n'
                        'For the exact reviewed target account in an approved elevated native Windows PowerShell session.\n'
                        'Release publication, Authenticode validation and native installation testing remain separate.\n'
                        'The plan must be delivered to the target through the approved process.\n'
                        'Installation creates no model session; open the resulting shortcut as the ordinary target account.\n\n'
                        '```powershell\n' + command + '\n```\n')
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(instructions)
        print('Prepared command saved locally; nothing was downloaded, published or activated.')
        return 0
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
