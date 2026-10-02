"""Jarvis's staged web/app workflow, backed by real project tooling."""
import json
from pathlib import Path
from .agent_context import coding_context, scoped, instruction_context
from .development_design import specification, save_spec
from .development_knowledge import detect_stack
from .development_projects import scaffold, batches
from .development_tools import DevelopmentTools

def tools_for(actions):
    value=getattr(actions,'development_tools',None)
    if not isinstance(value,DevelopmentTools):
        value=actions.development_tools=DevelopmentTools(actions.base,actions.report)
    return value

def checkpoint(actions, stage, **details):
    from .task_state import TaskState
    state=getattr(actions,'task_state',None)
    if isinstance(state,TaskState):
        state.checkpoint(stage,**details)

def functional_tests(client, project, goal, cancelled, observations=None):
    from .coder import project_files
    from .agent_context import bounded_text
    sources={}
    for name in project_files(project):
        if Path(name).suffix in {'.tsx','.jsx','.html'}:
            try: sources[name]=bounded_text(scoped(project,name),20000)
            except (OSError,ValueError,UnicodeError): pass
        if len(sources)>=3: break
    contract=(
            'Each scenario {name,steps}. Each step {action,role,name,value}. Use only click,fill,select,press,assert_text,assert_count,assert_attribute. '
            'Roles button,textbox,combobox,dialog,heading,link,checkbox,status,listitem,tab,main only; no text or generic role. Names exact accessible labels. '
            'press keys Tab,Shift+Tab,Enter,Escape,Space,ArrowDown,ArrowUp. assert_text value must be visible text from expected result. '
            'assert_count value integer, role/name match control. assert_attribute only aria-expanded,aria-invalid,aria-pressed,open,value,data-motion. '
            'At least 3 assertions of outcomes, including primary interaction, empty/error handling and keyboard if implemented. '
            'Each scenario reloads page. Do not invent missing controls or features. No arbitrary CSS selectors, JS evaluation, URLs or shell. '
            'Example shape: [{"name":"Search outcome","steps":[{"action":"fill","role":"textbox","name":"Search","value":"missing"},{"action":"assert_text","value":"No results"}]}]. '
            'Use actual source labels and expected outcomes instead of these example labels. Omit role/name on assert_text.')
    contract+=' Ground role/name in the fresh accessibility snapshot when supplied. fill requires textbox, select requires combobox. assert_text checks rendered text nodes, never input placeholders, accessible labels or input values. Use fill with empty value to clear a search; no unsupported key shortcuts.'
    from .development_browser import validate_tests
    context={'source':sources,'fresh_observations':observations or []}
    for attempt in range(2):
        if cancelled(): raise ValueError('Functional verification planning cancelled.')
        response=client.request('tool_text',cancelled,tool='test_writer',development=True,
            goal='Return 3–10 browser scenarios in the tests array for the actual requested behavior: '+goal+'\n'+contract,
            context=context)
        text=response.get('text') if isinstance(response,dict) else None
        try:
            if isinstance(response,dict) and isinstance(response.get('tests'),list):tests=response['tests']
            else:
                if not isinstance(text,str): raise ValueError('Missing functional verification plan.')
                if text.startswith('```'): text=text.split('\n',1)[-1].rsplit('```',1)[0]
                tests=json.loads(text)
            if not 3<=len(tests)<=10 or validate_tests(tests)<3 or not any(s['action'] in {'click','fill','select','press'} for t in tests for s in t['steps']):
                raise ValueError('Functional plan needs 3–10 scenarios, at least three outcome assertions and an interaction.')
            return tests
        except (ValueError,TypeError,KeyError) as exc:
            if attempt: raise ValueError('Functional verification plan invalid after bounded inference correction: '+str(exc)) from exc
            # Only inference is repeated. No build, write or UI action has run.
            context={**context,'rejected_proposal':json.dumps(response)[:12000],'validation_error':str(exc)}

def verify(actions, project, stack, tests, cancelled, install=True, test_client=None, goal=None):
    tools=tools_for(actions)
    # Execute after the exact generated files and design are available for review.
    actions._approve('command',f'Development project: {project}\n'
        f'Run project-local TypeScript and {stack} build, start a loopback preview and test its controls with isolated Chromium + axe. '
        + ('Install package.json dependencies from official npm registry with package hooks disabled. ' if install else '')
        + 'Project configuration can execute code. No arbitrary model shell commands or command retries. '
        'Native packaging and external publication are separate actions.',cancelled)
    checkpoint(actions,'development_execution_approved',target=project)
    if install:
        checkpoint(actions,'action_attempted',action='development_install',target=project,evidence='Inspect package lock and dependencies after interruption; no automatic replay')
        result=tools.install(project,cancelled)
        if result['exit_code']:
            raise ValueError('Dependency installation failed; no retry: '+result['output'][-1500:])
    checkpoint(actions,'action_attempted',action='development_build',target=project,evidence='Run approved type/build once; inspect output after interruption')
    from .development_learning import fingerprint
    source_hash=fingerprint(project)
    checks=tools.build(project,stack,cancelled)
    build_passed=len(checks)==2 and all(r['exit_code']==0 for r in checks)
    evidence={'stack':stack,'project':str(project),'build':checks,'build_passed':build_passed,'goal_verified':False,'source_fingerprint':source_hash}
    if build_passed:
        url=tools.start_preview(project,stack,cancelled)
        actions.report('action','Owned development preview: '+url)
        evidence['preview_url']=url
        from .progress import status
        if tests is None:
            status(actions.report,'Observing interface and planning browser checks',project)
            observed=tools.inspect(project,url,[],cancelled)
            evidence['initial_observation']=observed
            client=test_client or actions.brain.client
            tests=functional_tests(client,project,goal or actions.task_state.snapshot()['goal'],cancelled,
                observations=[{'view':v['name'],'snapshot':v['observation']} for v in observed['views'][:2]])
        evidence['tests']=tests
        status(actions.report,'Inspecting desktop, mobile and reduced motion',project)
        evidence['browser']=tools.inspect(project,url,tests,cancelled)
        evidence['goal_verified']=evidence['browser']['goal_verified']
    if fingerprint(project)!=source_hash:
        evidence['goal_verified']=False
        evidence['source_changed_during_verification']=True
    directory=scoped(project,'.jarvis/development')
    directory.mkdir(parents=True,exist_ok=True)
    import uuid
    path=scoped(project,'.jarvis/development/verification-'+uuid.uuid4().hex+'.json')
    path.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    evidence['evidence_file']=str(path)
    checkpoint(actions,'development_observed',target=path,evidence='Actual build/browser evidence; native packaging not verified')
    return evidence

def run(coder, project, goal, cancelled, selected):
    actions,client=coder.actions,coder.client
    project=Path(project).resolve(strict=True)
    stack=detect_stack(project,goal)
    if stack=='react':
        raise ValueError('Existing React project has no supported build adapter; identify its build tool. No replacement framework created.')
    instruction_context(project)
    checkpoint(actions,'development_understand',target=project,evidence='Detected '+stack)
    spec=specification(project,goal,stack)
    from .development_learning import preferences, recall
    spec['human_preferences']=preferences(actions.base,project)
    approved={p.get('approved_reference') for p in spec['human_preferences']}
    spec['reference_interfaces']=[{**r,'approved':r['id'] in approved} for r in spec['reference_interfaces']]
    path=save_spec(project,spec,cancelled)
    actions.report('plan','Design brief: '+str(path)+'; '+spec['layout'])
    checkpoint(actions,'development_design',target=path,evidence='Brief saved before implementation')
    from .progress import status
    status(actions.report,'Designing interface',path,file=str(path),preview=json.dumps(spec,indent=2)[:1600],outcome='Design brief; implementation pending')
    created=scaffold(project,stack,cancelled,actions.report,lambda stage,**kw:checkpoint(actions,stage,**kw))
    from .coder import project_files, strip_project_prefix
    files=project_files(project)
    context={**coding_context(project,goal,files=files),'design_spec':spec,'skill_project':str(project),'development':True,'development_lessons':recall(actions.base,stack,goal)}
    import re
    if re.search(r'\bonly (?:edit|create|change|modify|write) (?:this|that|the) file\b',goal,re.I):
        targets=re.findall(r'\b(?:[A-Za-z0-9_-]+/)*[A-Za-z][\w-]*\.(?:tsx?|jsx?|html|css)\b',goal)
        if len(set(targets))==1:
            target=targets[0]
            matches=[f for f in files if Path(f).name.casefold()==Path(target).name.casefold()]
            context['allowed_output_paths']=[target if '/' in target or not matches else matches[0]]
    plan=client.request('code_plan',cancelled,goal=goal,project=project.name,files=files,**context)
    if not isinstance(plan,dict): raise ValueError('Development model omitted project plan.')
    plan={**plan,'directories':[strip_project_prefix(name,project) for name in plan.get('directories',[])],
          'files':[{**step,'path':strip_project_prefix(step.get('path'),project)} for step in plan.get('files',[])]}
    groups=batches(plan)
    if context.get('allowed_output_paths') and {s['path'].casefold() for s in plan['files']} != {p.casefold() for p in context['allowed_output_paths']}:
        raise ValueError('Development plan exceeded the explicit single-file scope; no generated changes applied.')
    import re
    from .coder import SOURCE_PATTERN
    named={m.group(0).casefold() for m in re.finditer(r'\b[a-z][\w-]{0,80}\.(?:'+SOURCE_PATTERN+r')\b',goal,re.I)}
    planned={Path(s['path']).name.casefold() for s in plan['files']}
    if not named <= planned:
        raise ValueError('Development plan omitted a named file: '+', '.join(sorted(named-planned)))
    # Validate the complete path set before a first generated edit.
    from .coder import relative_parts
    dirs={scoped(project,name) for name in plan.get('directories',[])}
    for folder in dirs:
        if folder.exists() and not folder.is_dir(): raise ValueError('Planned folder is not a directory.')
        if not folder.parent.is_dir() and folder.parent not in dirs: raise ValueError('Missing planned parent folder.')
    for step in plan['files']:
        path=scoped(project,relative_parts(step['path']).as_posix())
        if not path.parent.is_dir() and path.parent not in dirs: raise ValueError('Missing planned file parent.')
    changes=[]
    for index,group in enumerate(groups):
        if cancelled(): raise ValueError('Development cancelled at a batch checkpoint; inspect existing drafts before resuming.')
        stage='components' if index==0 else ('styling' if any(Path(s['path']).suffix=='.css' for s in group) else 'functionality')
        checkpoint(actions,'development_'+stage,target=project,evidence=f'Batch {index+1}/{len(groups)}; at most three generated files')
        actions.report('plan',f'Development {stage}, batch {index+1}/{len(groups)}')
        changes.append(coder._run(project,goal,cancelled,selected=selected,
            plan_override={'directories':plan.get('directories',[]) if index==0 else [],'files':group},
            staged=True,development_context={'design_spec':spec,'development_lessons':context['development_lessons']}))
    # Tests are inference proposals; only the browser establishes their results.
    evidence=verify(actions,project,stack,None,cancelled,test_client=client,goal=goal)
    tests=evidence.get('tests')
    # One correction pass, based on observed errors. Writes/commands themselves
    # are never retried. All new changes are planned, backed up and approved anew.
    history=[]
    if not evidence['goal_verified'] and not cancelled():
        history.append(evidence)
        try:
            from .development_learning import record
            record(actions.base,project,goal,evidence)
        except (OSError,ValueError,KeyError) as exc:
            actions.report('warning','Development failure case could not be stored: '+str(exc))
        tools_for(actions).stop_preview()
        actions.report('warning','Development verification found problems; one correction pass from observed evidence.')
        from .development_learning import fingerprint
        before_fix=fingerprint(project)
        fix_goal='Fix implementation for this requested behavior: '+goal+' based on development_evidence. Preserve the requested features.'
        before_package=scoped(project,'package.json').read_bytes()
        coder._run(project,fix_goal[:1200],cancelled,selected=True,staged=True,
                   development_context={'design_spec':spec,'development_evidence':evidence})
        if fingerprint(project)==before_fix:
            raise ValueError('Correction proposed no new source changes. Build/browser commands were not replayed; inspect '+evidence['evidence_file'])
        evidence=verify(actions,project,stack,tests,cancelled,install=scoped(project,'package.json').read_bytes()!=before_package,
            test_client=client,goal=goal)
    if not evidence['goal_verified']:
        try:
            from .development_learning import record
            record(actions.base,project,goal,evidence,history)
        except (OSError,ValueError,KeyError) as exc:
            actions.report('warning','Final failed case could not be stored: '+str(exc))
        raise ValueError('Project written but verification is incomplete. Inspect '+evidence['evidence_file'])
    try:
        from .development_learning import record
        record(actions.base,project,goal,evidence,history)
    except (OSError,ValueError,KeyError) as exc:
        actions.report('warning','Development checks passed; case was not learned: '+str(exc))
    checkpoint(actions,'goal_verified',source='development_browser',target=evidence['evidence_file'],
        evidence='Typecheck/build and goal-specific assertions passed in desktop/mobile/reduced-motion Chromium; native package behavior not verified')
    native=' Native build, installer and device behavior still need platform verification.' if stack in {'electron','expo'} else ''
    return f"{project.name}: design and {len(groups)} implementation batches completed. Typecheck/build and desktop/mobile browser checks passed. Preview: {evidence['preview_url']}. Evidence: {evidence['evidence_file']}."+native
