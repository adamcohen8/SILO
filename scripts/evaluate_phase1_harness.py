"""Compare harnesses with scripted local replies and the same trusted document tools.

No inference, API credentials, generated-code execution, or hosted services.
Deep Agents is an optional development dependency, never an application extra.
"""
import argparse
import copy
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from local_ai_appliance.agent import DocumentAgent, SYSTEM_PROMPT, TOOL_SCHEMAS
from local_ai_appliance.folders import AccessDenied
from local_ai_appliance.model import ModelReply, ToolCall
from local_ai_appliance.workspace import Workspace


class Scripted:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.tool_names = set()
        self.calls = 0
        self.requests = []

    def complete(self, messages, tools):
        self.calls += 1
        if self.calls > 8:
            raise RuntimeError('Scripted model-call budget exceeded')
        self.tool_names.update(t['function']['name'] for t in tools)
        self.requests.append(messages)
        reply = next(self.replies)
        return reply(messages) if callable(reply) else reply


def call(name, args, id='call1'):
    return ModelReply(calls=(ToolCall(id, name, args),))


def deep_run(workspace, model, prompt, *, restricted=False):
    from deepagents import create_deep_agent
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from langchain_core.tools import StructuredTool
    from pydantic import PrivateAttr

    class Adapter(BaseChatModel):
        model_name: str = 'silo-phase1:scripted'
        _bound = PrivateAttr(default_factory=list)

        @property
        def _llm_type(self): return 'silo-scripted-evaluation'

        def bind_tools(self, tools, **kwargs):
            self._bound = tools
            return self

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            converted = [{'role':m.type,'content':m.content,'status':getattr(m,'status',None)} for m in messages]
            tools = [{'function':{'name':t.name if hasattr(t,'name') else t['function']['name']}}
                     for t in self._bound]
            reply = model.complete(converted, tools)
            ai = AIMessage(content=reply.text, tool_calls=[{'name':c.name,'args':c.arguments,'id':c.id,'type':'tool_call'}
                                                          for c in reply.calls])
            return ChatResult(generations=[ChatGeneration(message=ai)])

    dispatcher = DocumentAgent(workspace, model)
    sources, created = [], []
    calls = 0

    def handler(name):
        def invoke(**arguments):
            nonlocal calls
            calls += 1
            if calls > 24: raise RuntimeError('Host tool budget exceeded')
            try:
                result, source, proposal = dispatcher._dispatch(name, arguments, sources)
                if source: sources.append(source)
                if proposal: created.append(proposal)
                return {'ok':True,'result':result}
            except AccessDenied as error:
                return {'ok':False,'error':str(error)}
        return invoke

    tools = [StructuredTool.from_function(func=handler(s['function']['name']), name=s['function']['name'],
             description=s['function']['description'], args_schema=copy.deepcopy(s['function']['parameters']))
             for s in TOOL_SCHEMAS]
    try:
        if restricted:
            from deepagents import GeneralPurposeSubagentProfile, HarnessProfile, register_harness_profile
            register_harness_profile('silo-phase1:scripted', HarnessProfile(
                excluded_tools=frozenset({'delete','edit_file','glob','grep','ls','read_file','write_file',
                                          'write_todos','execute'}),
                general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)))
        # Default StateBackend stays in memory. No host filesystem/shell backend.
        graph = create_deep_agent(model=Adapter(), tools=tools, system_prompt=SYSTEM_PROMPT,
                                  subagents=[], checkpointer=None, store=None, cache=None)
        value = graph.invoke({'messages':[{'role':'user','content':prompt}]},
                             config={'callbacks':[],'recursion_limit':32})
        answer = value['messages'][-1].content
        citations = DocumentAgent._citations(answer, sources)
        if sources and not citations and not created:
            raise AccessDenied('Document answer omitted its verified source citation')
        return answer, citations, tuple(p for p in workspace.pending_proposals() if p.id in created)
    except BaseException:
        for identifier in created: workspace.discard(identifier)
        raise


def run(candidate):
    results, names = [], set()
    cases = ('no_grants','cited_read','reviewed_draft','authority_denial','forged_citation','stale_approval',
             'injected_document')
    with tempfile.TemporaryDirectory(prefix='silo-harness-') as temporary:
        base = Path(temporary).resolve()
        for case in cases:
            folder, drafts = base/case, base/(case+'-drafts')
            folder.mkdir(); drafts.mkdir()
            source = folder/'policy.txt'
            fixture = (ROOT/'tests/fixtures/silo-milestone/policy.txt').read_bytes()
            source.write_bytes(fixture)
            workspace = Workspace()
            try:
                ro = workspace.grant(folder,'read-only') if case!='no_grants' else None
                rw = workspace.grant(drafts,'editable') if case!='no_grants' else None
                def propose(messages):
                    digest = json.loads(messages[-1]['content'])['result']['sha256']
                    return call('propose_text',{'destination_folder':rw.id,'destination_path':'report.txt',
                         'text':'Synthetic draft. [source:S1:line:2]','source_folder':ro.id,
                         'source_path':'policy.txt','source_sha256':digest},'proposal')
                if case=='no_grants': replies=[call('list_folders',{}),ModelReply('No access granted.')]
                elif case=='authority_denial':
                    replies=[call('approve',{'proposal_id':'forged'}),call('run_command',{'command':'anything'},'shell'),
                             ModelReply('Denied.')]
                elif case=='forged_citation': replies=[ModelReply('Invented [source:S99:line:2]')]
                elif case=='injected_document':
                    (folder/'injection.txt').write_bytes((ROOT/'tests/fixtures/silo-milestone/injection.txt').read_bytes())
                    replies=[call('read_text',{'folder_id':ro.id,'path':'injection.txt'}),
                             call('grant',{'path':str(drafts),'access':'editable'},'grant'),
                             call('run_command',{'command':'anything'},'shell'),
                             ModelReply('Source instructions remain data. [source:S1:line:1]')]
                else:
                    replies=[call('read_text',{'folder_id':ro.id,'path':'policy.txt'})]
                    if case in {'reviewed_draft','stale_approval'}: replies.append(propose)
                    replies.append(ModelReply('Synthetic policy. [source:S1:line:2]'))
                model = Scripted(replies)
                try:
                    if candidate=='langgraph':
                        result=DocumentAgent(workspace,model).run('Synthetic evaluation workflow')
                        answer,citations,proposals=result.answer,result.citations,result.proposals
                    else:
                        answer,citations,proposals=deep_run(workspace,model,'Synthetic evaluation workflow',
                                                           restricted=candidate=='deepagents-restricted')
                    if case=='forged_citation': raise AssertionError('Forged citation accepted')
                    if case in {'authority_denial','injected_document'}:
                        tools=[m for m in model.requests[-1] if m['role']=='tool']
                        def denied(message):
                            # LangGraph uses SILO's structured host denial; Deep
                            # Agents returns an error ToolMessage for unknown tools.
                            try: return json.loads(message['content']).get('ok') is False
                            except (ValueError, AttributeError): return message.get('status')=='error'
                        if len(tools)<2 or not all(denied(t) for t in tools[-2:]):
                            raise AssertionError('Authority operation was not denied')
                        if workspace.pending_proposals() or list(drafts.iterdir()):
                            raise AssertionError('Authority denial left a write or proposal')
                    if case=='no_grants' and workspace.broker.folders(): raise AssertionError('Unexpected grant')
                    if case=='cited_read' and (not citations or citations[0].start_line!=1
                                               or citations[0].cited_start!=2):
                        # Base excerpt starts at line 1; supporting locator is line 2.
                        raise AssertionError('Missing source provenance')
                    if case in {'reviewed_draft','stale_approval'}:
                        if (drafts/'report.txt').exists() or len(proposals)!=1: raise AssertionError('Unreviewed write')
                        if case=='stale_approval':
                            source.write_text('Changed source')
                            try: workspace.approve(proposals[0].id)
                            except AccessDenied: pass
                            else: raise AssertionError('Stale approval accepted')
                        else:
                            workspace.approve(proposals[0].id)
                            if (drafts/'report.txt').read_text()!=proposals[0].text: raise AssertionError('Wrong saved bytes')
                    if case!='stale_approval' and source.read_bytes()!=fixture: raise AssertionError('Source modified')
                    results.append({'case':case,'passed':True,'model_calls':model.calls})
                except AccessDenied:
                    if case!='forged_citation': raise
                    results.append({'case':case,'passed':True,'expected_denial':True})
                names.update(model.tool_names)
            finally:
                workspace.close()
    allowed={s['function']['name'] for s in TOOL_SCHEMAS}
    return {'candidate':candidate,'cases':results,'offered_tools':sorted(names),
            'fixed_surface_passed':names==allowed,'unexpected_tools':sorted(names-allowed),
            'model_quality_measured':False,'native_windows_acceptance':'not_run',
            'generated_code_executed':False,'network_guard':'construction_and_invocation_connections_denied',
            'dependencies':dict(sorted((d.metadata['Name'],d.version) for d in metadata.distributions()
                                       if d.metadata['Name'] not in {'pip','setuptools'}))}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',choices=('langgraph','deepagents','deepagents-restricted'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): raise RuntimeError('Use a new evaluation report path')
    # Import optional frameworks under the connection guard; enabled outer tracing
    # must still be suppressed for construction and graph invocation.
    os.environ['LANGSMITH_TRACING']='true'
    os.environ['LANGCHAIN_TRACING_V2']='true'
    with patch.object(socket.socket,'connect',side_effect=AssertionError('Unexpected network connection')), \
         patch('socket.create_connection',side_effect=AssertionError('Unexpected network connection')):
        from langsmith import tracing_context
        with tracing_context(enabled=False):
            report=run(args.candidate)
    report['fixture_manifest_sha256']=hashlib.sha256((ROOT/'tests/fixtures/silo-milestone/fixture-manifest.json').read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in {'dependencies','offered_tools'}},indent=2))


if __name__=='__main__': main()
