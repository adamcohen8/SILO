"""Registered code-workspace operations; no shell or host approval authority."""
from .agent import DocumentAgent, SYSTEM_PROMPT, TOOL_SCHEMAS
from .folders import AccessDenied


def schema(name, description, properties, required):
    return {'type':'function','function':{'name':name,'description':description,
            'parameters':{'type':'object','properties':properties,'required':required,'additionalProperties':False}}}


S = {'type':'string'}
OPTIONAL = {'type':['string','null']}
CODE_SCHEMAS = [
    schema('code_list','Page disposable workspace files and hashes.',{'offset':{'type':'integer'},'limit':{'type':'integer'}},[]),
    schema('code_read','Read bounded workspace text and its hash.',{'path':S,'start_line':{'type':'integer'},'end_line':{'type':'integer'}},['path']),
    schema('code_write','Create or revise workspace text; revisions require the last read hash.',
           {'path':S,'text':S,'expected_sha256':OPTIONAL},['path','text']),
    schema('code_patch','Apply one exact unique text patch against a verified file hash.',
           {'path':S,'old_text':S,'new_text':S,'expected_sha256':S},['path','old_text','new_text','expected_sha256']),
    schema('code_delete','Delete a disposable file against its current hash.',{'path':S,'expected_sha256':S},['path','expected_sha256']),
    schema('code_rename','Rename a disposable file without overwriting.',{'path':S,'destination':S,'expected_sha256':S},['path','destination','expected_sha256']),
    schema('code_search','Search literal text in workspace files, with paginated results.',
           {'query':S,'offset':{'type':'integer'},'limit':{'type':'integer'}},['query']),
    schema('code_navigate','Inspect snapshot symbols, references or syntax diagnostics without execution.',
           {'action':S,'query':S,'offset':{'type':'integer'},'file_offset':{'type':'integer'}},['action']),
    schema('run_build','Run a fixed run/test/check/build operation in the separately qualified offline environment.',
           {'operation':S,'entrypoint':S},['operation','entrypoint']),
    schema('code_semantic','Query a qualified read-only language server over the disposable snapshot.',
           {'action':S,'path':S,'line':{'type':'integer'},'column':{'type':'integer'}},['action','path']),
    schema('stage_input' ,'Stage previously read Reference bytes as an immutable inputs/name file.',
           {'source_id':S,'name':S},['source_id','name']),
    schema('run_python','Execute one workspace .py file with the fixed offline toolchain; optional staged input.',
           {'entrypoint':S,'input_name':OPTIONAL},['entrypoint']),
    schema('prepare_export','Prepare one artifact ZIP for separate trusted-host review and approval.',
           {'destination_folder':S,'destination_path':S},['destination_folder','destination_path']),
]
ALL_SCHEMAS = TOOL_SCHEMAS+CODE_SCHEMAS
CODE_PROMPT = SYSTEM_PROMPT.replace('Do not claim to run commands, browse, or save a file.',
    'Report execution only from a successful host run_python result. Workspace files are unpublished.') + '''
Code tools operate only on the host-created disposable workspace. There is no shell, package installer,
network tool, or arbitrary executable. Read a Reference with document tools before stage_input.
Python uses only its standard library, your workspace modules, and silo_plot.write_bar_chart(path, labels, values).
When the host grants a separately qualified build environment, run_build selects its fixed operations.
No package acquisition or environment approval is available to you. Read structured feedback after every test run.
Inputs are at inputs/name and are immutable. Use code_read hashes before revising an existing file.
Run the generated script and a separate test entrypoint. A nonzero exit is a failed run: inspect output,
repair the workspace script, and rerun. Stop and ask for direction when work repeats without progress. Inspect results.json and report.md before export.
Cite actual source locators in the final answer and report. Describe execution and testing accurately.
prepare_export creates an unsaved artifact-set proposal. Only the user reviews and publishes it.
'''


class CodeAgent(DocumentAgent):
    def __init__(self, workspace, model, code, **kwargs):
        super().__init__(workspace,model,system_prompt=CODE_PROMPT,**kwargs)
        self.code=code
        self.tool_schemas=ALL_SCHEMAS

    @staticmethod
    def _validate_arguments(name, args):
        candidate=next((s['function']['parameters'] for s in CODE_SCHEMAS if s['function']['name']==name),None)
        if candidate is None: return DocumentAgent._validate_arguments(name,args)
        if not isinstance(args,dict) or set(args)-set(candidate['properties']) or not set(candidate['required'])<=set(args):
            raise AccessDenied('Unexpected or missing code tool arguments')
        for key,value in args.items():
            if value is None and candidate['properties'][key] is OPTIONAL: continue
            try: valid=(type(value)is int and value>=0) if candidate['properties'][key]['type']=='integer' else isinstance(value,str) and len(value.encode('utf-8'))<=32*1024
            except UnicodeError: valid=False
            if not valid:
                raise AccessDenied('Code tool arguments require bounded UTF-8 text')

    def _dispatch(self,name,args,sources):
        self._validate_arguments(name,args)
        if name not in {s['function']['name'] for s in CODE_SCHEMAS}:
            return super()._dispatch(name,args,sources)
        self.code.check()
        if name=='code_list': value=self.code.page(**args)
        elif name=='code_read': value=self.code.read(**args)
        elif name=='code_write': value=self.code.write(**args)
        elif name=='code_patch': value=self.code.patch(**args)
        elif name=='code_delete': value=self.code.delete(**args)
        elif name=='code_rename': value=self.code.rename(**args)
        elif name=='code_search': value=self.code.search(**args)
        elif name=='code_navigate':
            from .code_navigation import NavigationIndex
            args=dict(args);file_offset=args.pop('file_offset',0)
            value=NavigationIndex.for_code(self.code,file_offset=file_offset).query(**args)
        elif name=='run_build': value=self.code.run_operation(**args)
        elif name=='code_semantic': value=self.code.language_query(**args)
        elif name=='stage_input':
            source=next((s for s in sources if s.id==args['source_id']),None)
            if source is None: raise AccessDenied('Read the source before staging it')
            value=self.code.stage(source,args['name'])
        elif name=='run_python':
            value=self.code.run(args['entrypoint'],() if args.get('input_name') is None else (args['input_name'],))
        else:
            # Validates citation tokens in the generated report before export.
            for path,data in self.code.files.items():
                if path.endswith('.md'): self._citations(data.decode('utf-8'),sources)
            value=self.code.prepare_export(**args)
        return value,None,None
