"""Exact-release independent enrollment for additional trusted host operations."""
import base64
import hashlib
import platform
import os
import time
import math
from .folders import AccessDenied
from .machine_security import anchor
from .signed_policy import verify_document,canonical


def require_capability(security,name,configuration,checks):
    if os.name!='nt':raise AccessDenied('Native Windows is required for '+name)
    if security is None or security.candidate: raise AccessDenied('Independent ordinary-user '+name+' enrollment is required')
    security.check()
    record=security.store.get(name+'-acceptance')
    if not isinstance(record,dict) or set(record)!={'envelope','sha256'}:
        raise AccessDenied('Independent '+name+' acceptance is missing')
    data=base64.b64decode(record['envelope'],validate=True)
    if hashlib.sha256(data).hexdigest()!=record['sha256']: raise AccessDenied('Acceptance envelope drift')
    key,digest=anchor(security.store,'reviewer-anchor')
    v=verify_document(data,key,digest,limit=128*1024)
    expected={'release_sha256':security.release_sha256,'native_version':platform.version(),**configuration}
    if (set(v)!={'format','scope','configuration','checks','expires'} or type(v['format']) is not int or v['format']!=1
            or v['scope']!=name or canonical(v['configuration'])!=canonical(expected) or type(v['expires']) not in (int,float)
            or not math.isfinite(v['expires']) or v['expires']<=time.time() or not isinstance(v['checks'],dict) or set(v['checks'])!=set(checks)):
        raise AccessDenied('Exact configuration acceptance is required')
    for r in v['checks'].values():
        if (not isinstance(r,dict) or set(r)!={'status','evidence_sha256'} or r['status']!='passed'
                or not isinstance(r['evidence_sha256'],str) or len(r['evidence_sha256'])!=64
                or any(c not in '0123456789abcdef' for c in r['evidence_sha256'])):
            raise AccessDenied('Every native capability check needs independent evidence')
    return v


def environment_registry(security):
    security.check()
    record=security.store.get('build-environments-review')
    if not isinstance(record,dict) or set(record)!={'envelope','sha256'}:
        raise AccessDenied('Independent offline environment registry review is missing')
    data=base64.b64decode(record['envelope'],validate=True)
    if hashlib.sha256(data).hexdigest()!=record['sha256']: raise AccessDenied('Environment registry review drift')
    key,digest=anchor(security.store,'reviewer-anchor');v=verify_document(data,key,digest,limit=1024*1024)
    if (set(v)!={'format','scope','environments','expires'} or type(v['format']) is not int or v['format']!=1
            or v['scope']!='offline-environments' or type(v['expires']) not in (int,float)
            or not math.isfinite(v['expires']) or v['expires']<=time.time()
            or v['environments']!=security.store.get('build-environments')):
        raise AccessDenied('Offline environment registry review is expired or changed')
    return v['environments']
