"""Redistribution review inventory. A hash pin is never a license approval."""
from pathlib import Path
from .asset_integrity import inference_pins,ordinary
from .model import strict_json


def license_inventory(root):
    root=Path(root)
    path=root/'profiles/windows-evaluation-installer.json'
    if ordinary(path).st_size>1024*1024:raise ValueError('Installer profile is oversized')
    profile=strict_json(path.read_bytes()); pins=inference_pins(root)
    rows=[]
    for item in [profile['python'],*profile['wheels']]:
        rows.append({'component':item.get('name','CPython'),'version':item['version'],
            'file':item['filename'],'sha256':item['sha256'],'source':item['url'],
            'role':'host-only' if item.get('ui_only') else 'contained-worker',
            'license_review':'pending','redistribution_approved':False})
    for item in pins['assets']:
        rows.append({'component':item['role'],'file':item['name'],'sha256':item['sha256'],
            'source':item.get('url','Review the pinned inference asset source'),
            'role':item['role'],'license_review':'pending','redistribution_approved':False})
    return {'format':1,'redistribution_ready':False,'components':rows,
            'required_review':'Record license text, notices, restrictions, model weight terms, runtime and CUDA redistribution rights, and organization approval for the exact bytes.'}
