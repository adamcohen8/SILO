"""Resolve exact pre-acquired wheel pins from actual metadata; no network or hooks."""
from email.parser import BytesParser
from pathlib import Path
import zipfile
import re
from .asset_integrity import digest_file,ordinary
from .folders import AccessDenied


def resolve_wheels(root,pins,requirements,*,python_version='3.14.8',platform='win_amd64'):
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name,parse_wheel_filename
    from packaging.markers import default_environment
    from packaging.version import Version
    from packaging.specifiers import SpecifierSet
    short='.'.join(python_version.split('.')[:2])
    marker=default_environment(); marker.update(python_version=short,python_full_version=python_version,
        sys_platform='win32',os_name='nt',platform_system='Windows',platform_machine='AMD64',extra='',
        implementation_name='cpython',implementation_version=python_version,platform_python_implementation='CPython')
    def applies(requirement):
        if requirement.marker is None:return True
        if re.search(r'\b(?:platform_release|platform_version)\b',str(requirement.marker)):
            raise AccessDenied('OS-version dependency markers need an explicit target-specific reviewed closure')
        return requirement.marker.evaluate(marker)
    if platform!='win_amd64': raise AccessDenied('This preparation resolver targets Windows x64 wheels')
    packages={}
    for pin in pins:
        if set(pin)!={'filename','size','sha256','source'}: raise AccessDenied('Wheel requires independent size/hash/source pins')
        name=pin['filename']
        if not isinstance(name,str) or Path(name).name!=name or '/' in name or '\\' in name:
            raise AccessDenied('Unsafe wheel filename')
        path=Path(root)/name
        if ordinary(path).st_size!=pin['size'] or digest_file(path)!=pin['sha256']: raise AccessDenied('Wheel pin mismatch')
        project,version,_,tags=parse_wheel_filename(name)
        cp='cp'+short.replace('.','')
        def compatible(t):
            stable=t.abi=='abi3' and t.interpreter.startswith('cp3') and t.interpreter[2:].isdigit() and int(t.interpreter[2:])<=int(cp[2:])
            return t.platform in {'any',platform} and (stable or t.interpreter in {'py3',cp} and t.abi in {'none',cp})
        if not any(compatible(t) for t in tags):
            raise AccessDenied('Wheel does not match the explicit interpreter target')
        with zipfile.ZipFile(path) as z:
            names=[n for n in z.namelist() if n.endswith('.dist-info/METADATA')]
            if len(names)!=1 or z.getinfo(names[0]).file_size>1024*1024: raise AccessDenied('Invalid wheel metadata')
            m=BytesParser().parsebytes(z.read(names[0]))
        if canonicalize_name(m['Name'])!=project or Version(m['Version'])!=version:
            raise AccessDenied('Filename and package metadata disagree')
        if m.get('Requires-Python') and Version(python_version) not in SpecifierSet(m['Requires-Python']):
            raise AccessDenied('Package does not support the target interpreter')
        if project in packages: raise AccessDenied('Select exactly one pinned version of each package')
        packages[project]=(pin,m,version)
    selected={}; pending=[Requirement(r) for r in requirements]
    while pending:
        req=pending.pop()
        if req.url or req.extras: raise AccessDenied('Direct URLs and extras need a separate reviewed closure')
        if not applies(req): continue
        name=canonicalize_name(req.name)
        if name not in packages or packages[name][2] not in req.specifier:
            raise AccessDenied('Missing or conflicting offline dependency: '+name)
        if name in selected: continue
        pin,m,version=packages[name]
        deps=[]
        for text in m.get_all('Requires-Dist',[]):
            dependency=Requirement(text)
            if applies(dependency): deps.append(dependency)
        selected[name]={'name':name,'version':str(version),'license':m.get('License-Expression') or m.get('License') or 'Review required',
                        'source':pin['source'],'requires':{},'wheel':pin}
        pending.extend(deps)
        for dep in deps:
            dn=canonicalize_name(dep.name)
            if dn not in packages or packages[dn][2] not in dep.specifier:
                raise AccessDenied('Missing or conflicting offline dependency: '+dn)
            selected[name]['requires'][dn]=str(packages[dn][2])
    return [selected[n] for n in sorted(selected)]
