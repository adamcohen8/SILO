"""Real LangGraph orchestration with scripted replies and simulated execution."""
import io
import json
from pathlib import Path
import tempfile
import unittest

from local_ai_appliance.agent import TOOL_SCHEMAS
from local_ai_appliance.code_agent import CodeAgent,ALL_SCHEMAS
from local_ai_appliance.code_workspace import CodeWorkspace
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.model import ModelReply,ToolCall
from local_ai_appliance.workspace import Workspace
from local_ai_appliance.windows_workspace import BrokerSession
from test_code_workspace import SimulatedRunner,ROOT

try:
    import langgraph.graph
    AVAILABLE=True
except ImportError: AVAILABLE=False


class Model:
    def __init__(self,replies): self.replies=iter(replies); self.tools=set(); self.messages=[]
    def complete(self,messages,tools):
        self.tools.update(t['function']['name'] for t in tools); self.messages.append(messages)
        return next(self.replies)


def call(name,args,identifier): return ModelReply(calls=(ToolCall(identifier,name,args),))


@unittest.skipUnless(AVAILABLE and __import__('os').name=='posix','Portable graph required')
class CodeAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve(); self.reference=self.root/'ref'; self.reference.mkdir()
        self.destination=self.root/'dest'; self.destination.mkdir()
        (self.reference/'policy.txt').write_bytes((ROOT/'tests/fixtures/silo-milestone/policy.txt').read_bytes())
        self.workspace=Workspace(); self.addCleanup(self.workspace.close)
        self.ro=self.workspace.grant(self.reference,'read-only'); self.rw=self.workspace.grant(self.destination,'editable')
        self.code=CodeWorkspace(self.workspace,SimulatedRunner()); self.addCleanup(self.code.close)

    def test_read_stage_edit_simulated_run_inspect_and_export_through_real_graph(self):
        model=Model([call('read_text',{'folder_id':self.ro.id,'path':'policy.txt'},'read'),
            call('stage_input',{'source_id':'S1','name':'policy.txt'},'stage'),
            call('code_write',{'path':'analyze.py','text':'# inert simulated entrypoint'},'edit'),
            call('run_python',{'entrypoint':'analyze.py'},'run'),
            call('code_read',{'path':'results.json'},'inspect'),
            call('prepare_export',{'destination_folder':self.rw.id,'destination_path':'result.zip'},'export'),
            ModelReply('Simulated result is 108 kg. [source:S1:line:2]')])
        result=CodeAgent(self.workspace,model,self.code).run('Synthetic fixture exercise')
        self.assertEqual(result.tool_calls,6)
        self.assertEqual(model.tools,{t['function']['name'] for t in ALL_SCHEMAS})
        self.assertEqual(list(self.destination.iterdir()),[])
        export=next(iter(self.code.exports))
        with self.assertRaises(AccessDenied): self.code.approve(export)
        self.code.review(export); self.code.approve(export)
        self.assertTrue((self.destination/'result.zip').is_file())

    def test_rpc_without_code_policy_cannot_dispatch_execution(self):
        broker=BrokerSession(self.workspace)
        response=broker.handle({'op':'tool','name':'run_python','arguments':{'entrypoint':'test.py'}})
        self.assertFalse(response['ok']); self.assertFalse(self.code.runs)

    def test_code_rpc_keeps_host_authority_and_requires_prior_read(self):
        broker=BrokerSession(self.workspace,code=self.code)
        for request in ({'op':'approve','id':'fabricated'},{'op':'tool','name':'run_command','arguments':{}},
                {'op':'tool','name':'stage_input','arguments':{'source_id':'S99','name':'policy.txt'}}):
            self.assertFalse(broker.handle(request)['ok'])
        for schema in TOOL_SCHEMAS:
            self.assertNotIn(schema['function']['name'],{'run_python','code_write'})

    def test_invalid_schema_and_forged_citation_cannot_prepare_export(self):
        for args in ({'entrypoint':'a.py','command':'anything'},{'entrypoint':None},{'entrypoint':'\ud800'}):
            with self.assertRaises(AccessDenied): CodeAgent._validate_arguments('run_python',args)
        self.code.write('a.py','# inert'); self.code.run('a.py')
        self.code.write('report.md','[source:S99:line:1]',self.code.read('report.md')['sha256'])
        agent=CodeAgent(self.workspace,Model([]),self.code)
        with self.assertRaises(AccessDenied):
            agent._dispatch('prepare_export',{'destination_folder':self.rw.id,'destination_path':'result.zip'},[])
        self.assertEqual(self.code.exports,{})


if __name__=='__main__': unittest.main()
