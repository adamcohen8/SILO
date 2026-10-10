"""Acquire two pinned interface wheels; install separately with the offline lock."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
def main():
    target = ROOT / 'artifacts/windows-ui/wheels'
    target.mkdir(parents=True, exist_ok=True)
    inventory, requirements = [], ['# Windows x64 native Qt interface; pinned PyPI hashes.']
    for name, metadata in [('PySide6-Essentials', 'pyside'), ('shiboken6', 'shiboken')]:
        value = json.loads((ROOT / f'artifacts/{metadata}-metadata.json').read_text(encoding='utf-8-sig'))
        wheels = [w for w in value['urls'] if w['filename'].endswith('win_amd64.whl')]
        if len(wheels) != 1:
            raise ValueError('Expected exactly one Windows x64 wheel')
        item = wheels[0]
        path = target / item['filename']
        if not path.exists():
            with urllib.request.urlopen(item['url'], timeout=60) as response, path.open('wb') as out:
                while data := response.read(1024*1024):
                    out.write(data)
        if path.stat().st_size != item['size'] or hashlib.sha256(path.read_bytes()).hexdigest() != item['digests']['sha256']:
            raise ValueError('Interface wheel verification failed')
        inventory.append({'name': name, 'version': '6.10.2', 'filename': path.name,
                          'size': item['size'], 'sha256': item['digests']['sha256'], 'url': item['url']})
        requirements.append(f"{name}==6.10.2 --hash=sha256:{item['digests']['sha256']}")
    (ROOT/'profiles/windows-ui-wheels.json').write_text(json.dumps(inventory, indent=2)+'\n')
    (ROOT/'requirements/windows-ui-offline.txt').write_text('\n'.join(requirements)+'\n')
    print(json.dumps({'verified_wheels': [i['filename'] for i in inventory]}))
if __name__ == '__main__':
    main()
