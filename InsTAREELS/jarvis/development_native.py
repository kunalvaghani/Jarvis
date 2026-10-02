"""Explicit native packaging/build adapters; no inference-controlled shell."""
import os
from pathlib import Path
import sys
import uuid
from .agent_context import scoped
from .development_tools import binary, executable

def readiness(project, stack, platform):
    if stack=='electron' and platform=='windows':
        return {'ready':os.name=='nt' and scoped(project,'node_modules/@electron/packager/bin/electron-packager.mjs').is_file(),
                'requires':'Windows, pinned @electron/packager and a successful renderer build', 'runtime_verified':False}
    if stack=='expo' and platform=='android':
        sdk=os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
        return {'ready':bool(sdk and Path(sdk).is_dir() and __import__('shutil').which('java')),
                'requires':'Android SDK, JDK, device/emulator; native permission and lifecycle tests', 'runtime_verified':False}
    if stack=='expo' and platform=='ios':
        return {'ready':sys.platform=='darwin','requires':'macOS, Xcode and iOS simulator/device','runtime_verified':False}
    raise ValueError('Native adapter supports Electron windows or Expo android/ios.')

def run(actions, project, stack, platform, cancelled):
    from .development import tools_for, checkpoint
    state=readiness(project,stack,platform)
    if not state['ready']:raise ValueError('Native prerequisites missing: '+state['requires'])
    tools=tools_for(actions)
    if stack=='electron':
        if not scoped(project,'dist/index.html').is_file():raise ValueError('Build the renderer before native packaging.')
        cli=scoped(project,'node_modules/@electron/packager/bin/electron-packager.mjs')
        out=scoped(project,'release-'+uuid.uuid4().hex)
        argv=[executable('node'),str(cli),'.','JarvisProject','--platform=win32','--arch=x64',
              '--out='+str(out),'--prune=true','--ignore=^/release-','--ignore=^/\\.jarvis']
        detail=f'Package this Electron project in {project} into new output {out}. Download official Electron runtime if needed. No signing, installer publication or app launch.'
    else:
        argv=binary(project,'expo')+['run:'+platform,'--no-install']
        out=Path(project)/platform
        detail=f'Build and run the Expo project in {project} on {platform}. It may generate native project files and invoke the local platform toolchain/device. No cloud publish.'
    actions._approve('command',detail+'\n'+repr(argv),cancelled)
    checkpoint(actions,'action_attempted',action='development_native',target=out,evidence='Explicitly approved platform operation; inspect output/device after interruption, never replay')
    result=tools.run(project,argv,cancelled,600)
    files=[str(p) for p in out.rglob('*.exe')][:8] if stack=='electron' and out.is_dir() else []
    return {'platform':platform,'exit_code':result['exit_code'],'output':result['output'],
            'artifacts':files,'build_command_passed':result['exit_code']==0,'native_functional_behavior_verified':False,
            'next':'Independently inspect installation, device/desktop lifecycle and permissions before reporting full native completion.'}
