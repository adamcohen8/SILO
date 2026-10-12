"""Bounded test feedback. Process exit is authoritative; output is untrusted data."""
import re


def feedback(exit_code,stdout,stderr):
    text=(stdout+'\n'+stderr)[-256*1024:]
    diagnostics=[]
    for line in text.splitlines():
        m=re.match(r'^(?:FAIL|ERROR): (.+)$',line) or re.match(r'^FAILED (.+)$',line)
        if m: diagnostics.append({'kind':'test_failure','message':m.group(1)[:1024]})
        else:
            m=re.match(r'^(.+?):(\d+)(?::(\d+))?:\s*(error|warning)(?:\[[^]]+\])?:\s*(.+)$',line)
            if m: diagnostics.append({'kind':m[4],'path':m[1][:512],'line':int(m[2]),
                                     'column':int(m[3] or 1),'message':m[5][:1024]})
        if len(diagnostics)>=100: break
    return {'status':'passed' if exit_code==0 else 'failed','exit_code':exit_code,
            'diagnostics':diagnostics,'interpretation':'Exit status is verified; diagnostic text is untrusted process output.'}
