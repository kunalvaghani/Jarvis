"""Discover real local coding programs; never installs or borrows credentials."""
from pathlib import Path
import shutil
import re
import sys

PROFILES = {
    'python': ('Python scripts, unittest, pytest and syntax checks', '-m unittest discover -v'),
    'node': ('JavaScript scripts, node:test and syntax checks', '--test test_main.mjs'),
    'rg': ('Literal/regex repository searches and file discovery', '--files'),
    'git': ('Repository observations; assembly writes belong to LocalGithub', 'diff --stat'),
    'pwsh': ('PowerShell versions; use checked file tools for source edits', '--version'),
    'powershell': ('Windows PowerShell version discovery; translated to a fixed version query', '--version'),
    'cmd': ('Windows version discovery; manual commands use the separate explicit approval flow', '--version'),
    'npm': ('Existing project scripts; no dependency installation', 'run build'),
    'npx': ('Discovery only; network package execution disabled', '--version'),
    'pnpm': ('Existing project scripts', 'run test'),
    'yarn': ('Existing project scripts', 'run test'),
    'uv': ('Discovery only; use configured Python runtime', '--version'),
    'pip': ('Discovery only; installs require dependency workflow', '--version'),
    'pytest': ('Python behavioral tests', '-q'),
    'ruff': ('Python lint checks', 'check .'),
    'black': ('Python formatting checks', '--check .'),
    'mypy': ('Python type checks', '.'),
    'tsc': ('TypeScript type checking', '--noEmit'),
    'eslint': ('JavaScript lint checks', '.'),
    'prettier': ('Formatting checks', '--check .'),
    'go': ('Go project tests/build', 'test ./...'),
    'cargo': ('Rust project tests/build/check', 'test --offline'),
    'rustc': ('Rust compiler', '--version'),
    'dotnet': ('.NET project tests/build', 'test --no-restore'),
    'java': ('Java runtime', '--version'),
    'javac': ('Java compiler', '--version'),
    'gcc': ('C compiler', '--version'),
    'g++': ('C++ compiler', '--version'),
    'clang': ('C/C++ compiler', '--version'),
    'cmake': ('CMake build tools', '--version'),
    'make': ('Existing build recipes', '--version'),
    'deno': ('Deno tests/checks', 'test --no-prompt'),
    'bun': ('Bun tests', 'test'),
    'ruby': ('Ruby scripts', '--version'),
    'php': ('PHP syntax checks', '-l main.php'),
    'perl': ('Perl syntax checks', '-c main.pl'),
    'lua': ('Lua scripts', '-v'),
    'Rscript': ('R scripts', '--version'),
    'julia': ('Julia scripts', '--version'),
    'swift': ('Swift tests', 'test'),
    'kotlinc': ('Kotlin compiler', '-version'),
    'scalac': ('Scala compiler', '-version'),
    'docker': ('Discovery only; containers require explicit workflow', '--version'),
    'adb': ('Discovery only; device mutations require explicit workflow', 'version'),
    'ffmpeg': ('Discovery only; media uses existing Jarvis tools', '-version'),
    'magick': ('Discovery only; image operations use existing Jarvis tools', '--version'),
    'ollama': ('Local inference managed by the shared GPU scheduler', '--version'),
    'gh': ('Discovery only; external GitHub actions require explicit authorization', '--version'),
    'codex': ('Optional legacy backend; never launched by native coding', '--version'),
    'mvn': ('Maven discovery; archetypes/dependency installation need setup approval', '--version'),
    'sqlite3': ('SQLite discovery; user database writes need explicit workflow', '--version'),
    'bundle': ('Bundler discovery; gem installation needs dependency workflow', '--version'),
    'bash': ('Bash reference commands translate to native typed tools', '--version'),
    'sh': ('Shell reference commands translate to native typed tools', '--version'),
    'sed': ('Source replacements use guarded Edit/apply_patch', '--version'),
    'jq': ('JSON field lookup uses parse_json', '--version'),
    'tar': ('Extraction requires reviewed destination/member validation', '--version'),
    'base64': ('Source encoding uses encode_base64', '--version'),
}


def locate(name, root=None):
    if name == 'python': return sys.executable
    if root:
        local = Path(root)/'node_modules/.bin'/(name+('.cmd' if sys.platform == 'win32' else ''))
        if local.is_file(): return str(local)
    return shutil.which(name)


def inventory(root=None):
    return [{'program':name,'path':locate(name,root),'available':bool(locate(name,root)),
             'purpose':purpose,'example_arguments':example}
            for name,(purpose,example) in PROFILES.items()]


def checked_argv(root, argv):
    """Finite no-shell operations; not an OS filesystem sandbox."""
    if not isinstance(argv,list) or not 1<=len(argv)<=32 or any(not isinstance(s,str) or len(s)>500 for s in argv):
        raise ValueError('Use a bounded argv array, never a shell command string.')
    name=Path(argv[0]).name.lower().removesuffix('.exe')
    if name not in PROFILES: raise ValueError('Unknown program; call programs to inspect installed capabilities.')
    binary=locate(name,root)
    if not binary: raise ValueError('Program is not installed: '+name+'. No installation was attempted.')
    args=argv[1:]
    version=args in [['--version'],['-version'],['-v'],['version']]
    if name in {'codex','npx','uv','pip','docker','adb','ffmpeg','magick','ollama','gh','pwsh','powershell','cmd','mvn','sqlite3','bundle','bash','sh','sed','jq','tar','base64'} and not version:
        raise ValueError('This program is discovery-only in model coding. Use the relevant configured Jarvis workflow or approved manual command.')
    if not version:
        if not args: raise ValueError('Provide a finite test/check/build operation.')
        if any(s in {'-c','-e','--eval','--exec','--write','--fix','--force','--global','-g'} or s.startswith(('--output=', '--outDir=')) for s in args):
            raise ValueError('Inline execution, automatic rewrites and unreviewed output locations are disabled.')
        if name=='git' and args[0] not in {'status','diff','log','show','ls-files','rev-parse'}:
            raise ValueError('Git writes belong to the LocalGithub assembly pipeline.')
        if name=='git' and any(s.startswith(('--output','--ext-diff','--textconv','--config','--exec-path','--git-dir','--work-tree')) for s in args):
            raise ValueError('Git external commands/configuration and output writes are not observations.')
        if name=='python' and args[0]=='-m' and (len(args)<2 or args[1] not in {'unittest','pytest','compileall'}):
            raise ValueError('Only configured Python test/syntax modules are available.')
        if name in {'npm','pnpm','yarn'}:
            if len(args)!=2 or args[0]!='run' or args[1] not in {'test','build','typecheck','lint'}:
                raise ValueError('Use an existing test/build/typecheck/lint script; installs are not coding commands.')
            import json
            script=json.loads((Path(root)/'package.json').read_text()).get('scripts',{}).get(args[1],'')
            if not re.fullmatch(r'(?:tsc(?: --noEmit)?|(?:vite|next) build|vitest run|playwright test|node --test|eslint [\w./-]+)',script):
                raise ValueError('Package script is missing or contains unreviewed shell instructions.')
        if name in {'go','cargo','dotnet','deno','bun','swift'} and args[0] not in {'test','build','check'}:
            raise ValueError('Use this program test, check or build workflow.')
        for arg in args:
            if not arg.startswith('-') and (Path(arg).is_absolute() or '..' in Path(arg).parts):
                raise ValueError('Command file arguments must stay project-relative.')
    if name=='git':args=['--no-pager','-c','core.fsmonitor=false','-c','core.pager=cat',*args]
    if name=='cargo' and not version and '--offline' not in args:args=[*args,'--offline']
    if name=='dotnet' and not version and '--no-restore' not in args:args=[*args,'--no-restore']
    # These Windows programs do not implement --version. Translate only the
    # recognized version aliases to fixed literals, never caller shell text.
    if version and name=='cmd':args=['/d','/c','ver']
    if version and name=='powershell':args=['-NoLogo','-NoProfile','-NonInteractive','-Command','$PSVersionTable.PSVersion.ToString()']
    if Path(binary).suffix.lower() in {'.cmd','.bat'}:
        # Windows command shims are not PE executables. Only finite validated
        # arguments reach a direct Node entry; no command shell is launched.
        if any(not re.fullmatch(r'[A-Za-z0-9_./\\:=@+,-]+',arg) for arg in args):
            raise ValueError('Command shim arguments must be literal flags/source paths without shell operators or expansion.')
        entries={'npm':'npm/bin/npm-cli.js','npx':'npm/bin/npx-cli.js','pnpm':'pnpm/bin/pnpm.cjs',
                 'tsc':'typescript/bin/tsc','eslint':'eslint/bin/eslint.js','prettier':'prettier/bin/prettier.cjs'}
        entry=entries.get(name)
        candidates=[Path(binary).parent/'node_modules'/entry] if entry else []
        if root and entry:candidates.insert(0,Path(root)/'node_modules'/entry)
        script=next((p for p in candidates if p.is_file()),None)
        if script and locate('node'):return [locate('node'),str(script),*args]
        raise ValueError('No checked direct executable for '+name+' shim; use its explicit setup/manual workflow.')
    return [binary,*args]
