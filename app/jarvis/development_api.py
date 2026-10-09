"""Planner-facing development tools with explicit scope and human feedback."""
import json
from pathlib import Path

TOOLS={
 'development_native':('development','Native packaging/build only when explicitly requested: folder project, value windows for Electron or android/ios for Expo. Requires toolchain readiness and exact execution approval; no automatic publication.',(),True),
 'development_status':('development','Read stack, Node readiness, last verification, design references and practice progression; folder project, value dot.',(),False),
 'development_verify':('development','Type-check/build and functionally test the identified project using reviewed Node tooling; folder project, value dot, content optional JSON {tests:[...]}. Requires execution approval.',(),True),
 'development_preview':('development','Start an owned loopback preview of an existing build, or stop only the current owned preview; folder project, value start or stop. Starting requires execution approval.',(),True),
 'development_feedback':('development','Retain exact human design feedback only; folder project, value exact user feedback, content optional JSON {approve_reference:workspace|forms|motion}. No execution permissions.',(),False),
 'development_practice':('development','Run one explicitly requested development practice project through the normal staged coder; folder project, value practice ID. Execution approval occurs after generated code is available.',(),False),
}

def execute(actions,step,cancelled):
    from .development import tools_for,verify,functional_tests
    from .development_knowledge import detect_stack
    from .development_learning import PRACTICE,feedback
    from .agent_context import scoped,bounded_text
    name=step['action']
    root=Path(actions._task_folder(step.get('folder',''),cancelled)).resolve(strict=True)
    if root.parent==root:raise ValueError('Select an individual development project.')
    stack=detect_stack(root)
    tools=tools_for(actions)
    from .task_state import TaskState
    state=getattr(actions,'task_state',None)
    task=state.snapshot() if isinstance(state,TaskState) else None
    goal=task.get('goal','') if task else ''
    if name=='development_status':
        receipts=sorted(scoped(root,'.jarvis/development').glob('verification-*.json'),key=lambda p:p.stat().st_mtime,reverse=True)
        from .development_design import REFERENCES
        import shutil
        return json.dumps({'stack':stack,'node':bool(shutil.which('node')),'last_verification':str(receipts[0]) if receipts else None,
            'preview':tools.preview['url'] if tools.preview and tools.preview['project']==str(root) else None,
            'references':REFERENCES,'practice':PRACTICE,'native_platform_verified':False})
    if name=='development_feedback':
        if not goal or 'feedback' not in goal.casefold() or step['value'] not in goal:
            raise ValueError('Design feedback must be explicitly given by the human in this task.')
        args=json.loads(step.get('content') or '{}')
        reference=args.get('approve_reference')
        if reference and not ('approve' in goal.casefold() and reference in goal.casefold()):
            raise ValueError('Reference approval must be explicitly named by the human.')
        return json.dumps(feedback(actions.base,root,step['value'],reference))
    if name=='development_native':
        if not goal or not any(word in goal.casefold() for word in ('package','native','android','ios','windows build')):
            raise ValueError('Native packaging or device build must be explicitly requested.')
        from .development_native import run
        return json.dumps(run(actions,root,stack,step['value'],cancelled))
    if name=='development_practice':
        if 'practice' not in goal.casefold() or step['value'] not in goal:
            raise ValueError('Name the practice project explicitly before starting it.')
        lesson=next((p for p in PRACTICE if p['id']==step['value']),None)
        if not lesson:raise ValueError('Unknown development practice ID.')
        from .coder import Coder
        return Coder(actions,actions.brain.client).run(root,lesson['goal'],cancelled,selected=True)
    if name=='development_preview':
        if tools.preview and tools.preview['project']!=str(root):
            raise ValueError('Choose the project that owns the current preview.')
        if step['value']=='stop':
            tools.stop_preview()
            return 'Owned development preview stopped deliberately.'
        if step['value']!='start':raise ValueError('Preview supports start or stop.')
        actions._approve('command',f'Start project-local {stack} preview in {root}, bound to 127.0.0.1; existing configuration can execute code.',cancelled)
        return tools.start_preview(root,stack,cancelled)
    if name=='development_verify':
        if not task or task.get('status')!='running':raise ValueError('Verification requires a current development task.')
        args=json.loads(step.get('content') or '{}')
        tests=args.get('tests') or None
        return json.dumps(verify(actions,root,stack,tests,cancelled,install=not scoped(root,'node_modules').is_dir(),
            test_client=actions.brain.client,goal=goal))
    raise ValueError('Unknown development operation.')
