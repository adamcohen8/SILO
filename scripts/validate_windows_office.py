import datetime,json,os,pathlib,subprocess,sys,time
import argparse
parser=argparse.ArgumentParser(description='Bounded native Office compatibility for synthetic approved fixtures; no model qualification.')
parser.add_argument('--fixtures',type=pathlib.Path,required=True)
parser.add_argument('--evidence',type=pathlib.Path,required=True)
parser.add_argument('--kinds',nargs='+',choices=['word-control','word','excel','powerpoint-control','powerpoint'],default=['word-control','word','excel','powerpoint-control','powerpoint'])
args=parser.parse_args();root=args.fixtures.resolve();evidence=args.evidence.resolve()
if not root.is_dir():raise SystemExit('Synthetic fixture directory required')
if evidence == root or root in evidence.parents or evidence in root.parents:raise SystemExit('Keep evidence separate from synthetic fixture inputs')
if len(set(args.kinds)) != len(args.kinds):raise SystemExit('Choose each Office kind once')
evidence.mkdir(parents=True,exist_ok=False)
script=pathlib.Path(__file__).resolve().parents[1]/'installer/Check-WindowsOffice.ps1'
# Let Windows PowerShell 5.1 construct its own module path when called from pwsh.
child_env={key:value for key,value in os.environ.items() if key.upper() != 'PSMODULEPATH'}
for kind in args.kinds:
 output=evidence/('native-office-'+kind+'.json')
 if output.exists():raise RuntimeError('Preserve previous Office evidence')
 start=time.monotonic()
 try:
  run=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','RemoteSigned','-File',str(script),'-Kind',kind,'-Root',str(root),'-Output',str(output)],capture_output=True,text=True,timeout=120,creationflags=0x08000000,env=child_env)
  (evidence/('native-office-'+kind+'.log')).write_text(run.stdout+'\n'+run.stderr,encoding='utf-8')
  if not output.exists():output.write_text(json.dumps({'kind':kind,'status':'failed','helper_exit':run.returncode})+'\n')
  # COM Quit can return before Office exits. Wait only for this operation's
  # exact recorded instance before starting the next isolated operation.
  owner=output.with_name(output.name+'.owner.json')
  if owner.exists():
   recorded=json.loads(owner.read_text(encoding='utf-8-sig'));pid=int(recorded['ProcessId']);name=recorded['Name'];ticks=int(recorded['StartTimeUtcTicks'])
   if pid <= 0 or ticks <= 0 or name not in ('WINWORD.EXE','EXCEL.EXE','POWERPNT.EXE'):raise RuntimeError('Unexpected Office owner identity')
   check=f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}'; if ($null -ne $p) {{$owned=Get-Process -Id {pid}; if ($p.Name -ne '{name}' -or $owned.StartTime.ToUniversalTime().Ticks -ne {ticks} -or !($p.CommandLine -like '*/Automation*' -or $p.CommandLine -like '*-Embedding*')) {{throw 'Owned Office identity changed'}}; if (!$owned.WaitForExit(15000)) {{throw 'Owned Office instance has not exited'}}}}"
   waited=subprocess.run(['powershell.exe','-NoProfile','-Command',check],capture_output=True,text=True,timeout=30,creationflags=0x08000000,env=child_env)
   (evidence/('native-office-'+kind+'-exit.log')).write_text(waited.stdout+'\n'+waited.stderr,encoding='utf-8')
   receipt=json.loads(output.read_text(encoding='utf-8-sig'))
   receipt.setdefault('checks',{})['owned_process_exited']=waited.returncode==0
   if waited.returncode:receipt.setdefault('errors',[]).append('Recorded Office instance did not exit cleanly; see exit log')
   output.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
 except subprocess.TimeoutExpired:
  owner=output.with_name(output.name+'.owner.json')
  if owner.exists():
   recorded=json.loads(owner.read_text(encoding='utf-8-sig'));pid=int(recorded['ProcessId']);name=recorded['Name'];ticks=int(recorded['StartTimeUtcTicks'])
   if name not in ('WINWORD.EXE','EXCEL.EXE','POWERPNT.EXE'):raise RuntimeError('Unexpected Office owner identity')
   check=f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}'; if ($p.Name -eq '{name}' -and (Get-Process -Id {pid}).StartTime.ToUniversalTime().Ticks -eq {ticks} -and ($p.CommandLine -like '*/Automation*' -or $p.CommandLine -like '*-Embedding*')) {{Stop-Process -Id {pid} -Force}} else {{throw 'Owned Office identity changed'}}"
   cleanup=subprocess.run(['powershell.exe','-NoProfile','-Command',check],capture_output=True,text=True,timeout=15,creationflags=0x08000000,env=child_env)
   cleanup_code=cleanup.returncode
  else:cleanup_code=None
  output.write_text(json.dumps({'kind':kind,'status':'blocked','reason':'Native Office operation exceeded 120 seconds','owned_office_cleanup_exit':cleanup_code},indent=2)+'\n')
 print(json.dumps({'kind':kind,'seconds':round(time.monotonic()-start,3),'evidence':output.name}),flush=True)
reports=[json.loads((evidence/('native-office-'+kind+'.json')).read_text(encoding='utf-8-sig')) for kind in args.kinds]
raise SystemExit(0 if all(r.get('checks') and all(r['checks'].values()) and not r.get('errors') for r in reports) else 1)
