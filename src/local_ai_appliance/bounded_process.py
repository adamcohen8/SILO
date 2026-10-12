"""Bounded trusted host tooling; never a generated-code containment service."""
import subprocess
import threading


def run_bounded(command,*,cwd,env,timeout,limit):
    process=subprocess.Popen(command,cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    output=[bytearray(),bytearray()];errors=[];guard=threading.Lock()
    def read(index,stream):
        try:
            while block:=stream.read(4096):
                with guard:
                    if sum(map(len,output))+len(block)>limit: raise RuntimeError('Host tool output exceeded its limit')
                    output[index].extend(block)
        except BaseException as e: errors.append(e);process.kill()
        finally: stream.close()
    threads=[threading.Thread(target=read,args=(i,s),daemon=True) for i,s in enumerate((process.stdout,process.stderr))]
    for t in threads:t.start()
    try: process.wait(timeout=timeout)
    except BaseException: process.kill();process.wait();raise
    finally:
        for t in threads:t.join(timeout=2)
    if errors: raise errors[0]
    if any(t.is_alive() for t in threads): raise RuntimeError('Host tool pipe cleanup incomplete')
    return process.returncode,bytes(output[0]),bytes(output[1])
