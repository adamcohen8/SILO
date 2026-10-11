"""Independent frozen-fixture checks; never accepts a model completion claim."""
import hashlib
import io
import json
from pathlib import Path
import zipfile

from .code_artifacts import png_pixels
from .folders import AccessDenied
from .silo_plot import bar_chart
from .model import strict_json


def inspect_milestone(data,fixtures):
    try:
        if type(data) is not bytes or len(data)>1024*1024:
            raise AccessDenied('Milestone artifact ZIP exceeds inspection limits')
        return _inspect_milestone(data,fixtures)
    except (KeyError,TypeError,ValueError,UnicodeError,zipfile.BadZipFile) as error:
        raise AccessDenied('Malformed milestone artifact set') from error


def _inspect_milestone(data,fixtures):
    fixtures=Path(fixtures)
    expected=json.loads((fixtures/'expected.json').read_bytes())
    pins=json.loads((fixtures/'fixture-manifest.json').read_bytes())
    hashes={p['path']:p['sha256'] for p in pins['files']}
    for name,sha in hashes.items():
        if hashlib.sha256((fixtures/name).read_bytes()).hexdigest()!=sha:
            raise AccessDenied('Independent milestone fixtures changed')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names=archive.namelist()
        if len(set(names))!=len(names) or len(names)>65 or sum(p.file_size for p in archive.infolist())>4*1024*1024:
            raise AccessDenied('Milestone artifact set exceeds inspection limits')
        manifest=strict_json(archive.read('silo-manifest.json'))
        required={'analyze.py','tests.py','results.json','capacity.png','report.md'}
        inventory={f['path']:f for f in manifest['files']}
        if len(inventory)!=len(manifest['files']) or not required<=set(inventory) or set(names)!={'silo-manifest.json',*inventory}:
            raise AccessDenied('Milestone outputs are incomplete or undeclared')
        for name,pin in inventory.items():
            body=archive.read(name)
            if len(body)!=pin['size'] or hashlib.sha256(body).hexdigest()!=pin['sha256']:
                raise AccessDenied('Milestone output changed')
        inputs={i['staged_path'].removeprefix('inputs/'):i for i in manifest['inputs']}
        for name in ('policy.txt','inventory.csv',*expected['rejected_inputs']):
            if name not in inputs or inputs[name]['sha256']!=hashes[name]:
                raise AccessDenied('Milestone input identity is missing or changed')
        results=strict_json(archive.read('results.json'))
        if (set(results)!={'capacity_kg','contributions_kg','excluded_assets'}
                or type(results['capacity_kg']) not in (int,float) or results['capacity_kg']!=108
                or results['contributions_kg']!=expected['eligible_contributions_kg']
                or results['excluded_assets']!=expected['excluded_assets']):
            raise AccessDenied('Calculation differs from independently specified 108 kg result')
        wanted=png_pixels(bar_chart(list(expected['eligible_contributions_kg']),list(expected['eligible_contributions_kg'].values())))
        if png_pixels(archive.read('capacity.png'))!=wanted:
            raise AccessDenied('Chart differs from the independent contribution values')
        source_id=inputs['policy.txt']['source_reference'].split(':')[1].split(']')[0]
        report=archive.read('report.md').decode('utf-8')
        if '108' not in report or f'[source:{source_id}:line:2]' not in report:
            raise AccessDenied('Report lacks the result or actual supporting policy locator')
        runs=manifest['runs']
        if not runs or any(r['boundary']!='native-lpac-fixed-ntfs-vhd' for r in runs):
            raise AccessDenied('Actual native execution evidence is required; simulation is insufficient')
        script_sha=inventory['analyze.py']['sha256']
        for name in ('inventory.csv',*expected['rejected_inputs']):
            observed=[r for r in runs if r['entrypoint']=='analyze.py' and r['script_sha256']==script_sha and r['arguments']==[name]]
            if not observed or ((observed[-1]['exit_code']==0)!=(name=='inventory.csv')):
                raise AccessDenied('Independent normal/negative input execution is missing or failed')
        if not any(r['entrypoint']=='tests.py' and r['exit_code']==0
                   and r['script_sha256']==inventory['tests.py']['sha256'] for r in runs):
            raise AccessDenied('The current generated test entrypoint was not executed successfully')
    return {'capacity_kg':108,'artifacts_verified':True,'recorded_native_runs_verified':True,
            'real_model_quality':'requires separate native task transcript review',
            'controlled_repair':'requires separate native task transcript review',
            'full_isolation_acceptance':False,'cui_authorized':False}
