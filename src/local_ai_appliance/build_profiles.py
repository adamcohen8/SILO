"""Fixed offline command adapters for reviewed pre-acquired SDKs."""
from .folders import AccessDenied
from .windows_folders import parts


def fixed_commands(language,*,executable,compiler=None,vendored=False,driver=None):
    parts(executable)
    if compiler is not None:parts(compiler)
    if driver is not None:parts(driver)
    def command(args,suffixes):return {'executable':executable,'arguments':args,'suffixes':suffixes}
    if language=='python':
        return {op:command(['-I','-S','-B','-u','{bootstrap}','{work}','{library}','{environment}',op,'{entrypoint}'],['.py'])
                for op in ('run','test','check')}
    if language=='javascript':
        return {'run':command(['--no-addons','{entrypoint}'],['.js','.cjs','.mjs']),
                'test':command(['--no-addons','--test','{entrypoint}'],['.js','.cjs','.mjs']),
                'check':command(['--no-addons','--check','{entrypoint}'],['.js','.cjs','.mjs'])}
    if language=='typescript':
        if compiler is None:raise AccessDenied('Pinned TypeScript compiler module required')
        return {op:command(['--no-addons','{payload}/'+compiler,*(['--noEmit'] if op=='check' else []),
                           '--pretty','false','{entrypoint}'],['.ts','.tsx']) for op in ('check','build')}
    if language=='rust':
        config=['--config','source.crates-io.replace-with="silo-vendor"','--config','source.silo-vendor.directory="{payload}/vendor"'] if vendored else []
        return {op:command([op,'--frozen','--offline',*config,'--manifest-path','{entrypoint}'],['.toml'])
                for op in ('run','test','check','build')}
    if language=='cpp':
        result={'check':command(['-fsyntax-only','{entrypoint}'],['.c','.cpp']),
                'build':command(['{entrypoint}','-o','silo_build.exe'],['.c','.cpp'])}
        if driver is not None:
            for op in ('run','test'):
                result[op]={'executable':driver,'arguments':['-I','-S','-B','-u','{bootstrap}','{work}','{library}','{environment}',op,'{entrypoint}'],
                            'suffixes':['.c','.cpp']}
        return result
    raise AccessDenied('Unsupported reviewed build language')
