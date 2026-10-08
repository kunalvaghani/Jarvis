"""Actual Codex-generated frontend/backend project and automatic browser checks."""
from datetime import datetime, timezone
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
from uuid import uuid4
from jarvis.coder import Coder

BASE=Path(__file__).resolve().parent


def verify_reinitialization(project):
    """Independently check persistence without altering generated source or user data."""
    source=Path(project)/'server.py'
    spec=importlib.util.spec_from_file_location('owned_counter_persistence_check',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix='jarvis-counter-persistence-') as directory:
        database=str(Path(directory)/'counter.db')
        module.init_db(directory)
        assert module.change_count(database,'increment')==1
        assert module.change_count(database,'increment')==2
        module.init_db(directory)
        assert module.get_count(database)==2,'Database initialization lost the saved count'
    return {'passed':True,'count_before_reinitialization':2,'count_after_reinitialization':2,
            'server_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}


def verify():
    if len(sys.argv)==3 and sys.argv[1]=='--repair-fixture':
        identifier=sys.argv[2]
        if not __import__('re').fullmatch(r'[0-9a-f]{32}',identifier):raise ValueError('Use an owned fixture identifier.')
        project=(BASE/'.jarvis-runtime/codex-code-fixture'/identifier).resolve(strict=True)
    else:
        project=BASE/'.jarvis-runtime/codex-code-fixture'/uuid4().hex;project.mkdir(parents=True)
    events=[]
    def report(kind,value):
        events.append((kind,value))
        if kind=='brain' or (kind=='task_status' and any(word in value.get('phase','') for word in ('Checking','issues','repair'))):
            print(json.dumps({'kind':kind,'value':value}),flush=True)
    options=json.loads((BASE/'config.json').read_text(encoding='utf-8'))['brain']
    coder=Coder(SimpleNamespace(base=BASE,report=report),SimpleNamespace(options=options))
    record={'date':datetime.now(timezone.utc).isoformat(),'project':project.relative_to(BASE).as_posix(),'scope':'Actual local Codex/Qwen generated owned frontend/backend app; Jarvis runtime checks and browser/API interactions. User project untouched.'}
    goal=('Create a small full-stack counter app titled Local Counter with a real HTML frontend and Python stdlib backend in index.html and server.py. '
        'Use inline CSS/JS in index.html: dark glass responsive UI, h1 Local Counter, number in #count initially 0, button #add Increment and #reset Reset. '
        'Frontend fetches GET /api/count returning {count:N} and POST /api/count with JSON {action:"increment"} or {action:"reset"} returning updated count. '
        'Backend uses sqlite3 in its --data-dir for persistence across browser reload; use sqlite statements parameterized where relevant. '
        'Accept --port N --data-dir PATH with argparse; bind only 127.0.0.1; serve index.html at / and /index.html using the project folder. '
        'No external libraries/assets, no extra features. Include viewport meta. Create only these two files; browser checks are executed by Jarvis, so do not create an additional test script. '
        'Call Plan with both file purposes/roles and a browser check path=index.html server={kind:"python",path:"server.py"}. '
        'Its exact steps: text #count 0, click #add, text #count 1, reload, text #count 1, click #reset, text #count 0. '
        'Write complete source with real callbacks and error handling. Keep each source below 6000 characters. Jarvis will run your Plan checks and supply repair errors if needed.')
    if '--repair-fixture' in sys.argv:
        goal=('Repair the existing partial owned Local Counter project. Read current files before edits. '
              'Missing server.py must implement the backend below. Previous proposals contained an incomplete try: server.serve_forever(); '
              'use a direct server.serve_forever() call without that unnecessary try. '
              'Fix index.html initial GET to always use /api/count; its current /index.html/api/count URL is wrong. '
              'Existing test_server.py is not unittest: convert it into real unittest cases using a fresh SQLite temporary database and backend functions. '
              'Expose init_db(db_path), get_count(db_path), change_count(db_path, action) in server.py so unittest can verify increment/reset without starting another server. '
              'Include all three existing/required files in Plan and add python_tests path=test_server.py besides the browser check. '
              'Preserve the UI; no unrelated files. '+goal)
        record['scope']='Actual local Codex/Qwen repair of previously generated partial owned full-stack fixture; independent Python/browser/API checks. User project untouched.'
    try:
        if '--repair-fixture' in sys.argv:
            from jarvis.codex_code import run
            from jarvis.codex_validation import validate_project,repair_packet
            candidates=[]
            for path in (BASE/'.jarvis-runtime/codex-code').glob('*/request.json'):
                if json.loads(path.read_text(encoding='utf-8'))['project']==str(project) and (path.parent/'validation-contract.json').exists():
                    candidates.append(path.parent/'validation-contract.json')
            plan=json.loads(max(candidates,key=lambda p:p.stat().st_mtime).read_text(encoding='utf-8'))
            check_run=BASE/'.jarvis-runtime/codex-code-fixture-check'/uuid4().hex;check_run.mkdir(parents=True)
            diagnosis=validate_project(project,check_run,goal,[],plan,lambda:False,report)
            record['initial_errors']=diagnosis['errors']
            goal=('Repair the existing Local Counter backend from the attached observed failures. Read server.py first and apply small exact Edit calls. '
                'Keep the working index.html and seven existing unittest cases. Preserve the registered three-file Plan and both executable checks. '
                'Preserve init_db(data_dir), get_count(db_path), change_count(db_path, action), make_handler(data_dir), run(port, data_dir), '
                'the current start_server entry point, --port/--data-dir arguments and GET/POST /api/count behavior. '
                'Both / and /index.html must read index.html beside server.py, before sending headers; --data-dir is only for SQLite. '
                'Support independent HTTP connections without keep-alive starvation. Close the SQLite write connection after commit before returning get_count. '
                'Add a genuine unittest assertion for reinitialization preserving a count of two; keep all existing assertions. '
                'Save actual source with Edit tools and then finish for Jarvis independent checks. No unrelated files or feature removal.')
            server_source=(project/'server.py').read_text(encoding='utf-8') if (project/'server.py').is_file() else ''
            if "index_path = os.path.join(data_dir, 'index.html')" in server_source:
                goal+=(' Confirmed path defect: index_path uses the SQLite data directory, which contains no HTML. '
                       'Change that expression to os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html"). '
                       'Read the resulting file before sending headers. The existing get_count already closes its read connection; '
                       'the missing close is in change_count, after conn.commit(). Do not apply unchanged edits to get_count.')
            if "'/' + self.path" in server_source:
                goal+=(' Fresh source inspection: do_GET opens the project folder plus self.path. For GET / that is a directory, '
                       'which Windows reports as PermissionError. This is a wrong file path, not missing system permissions. '
                       'Both / and /index.html must read the existing index.html file before sending headers. '
                       'Apply this source repair with Edit after Read; do not change OS permissions or speculate about the workspace.')
            if 'http.server.HTTPServer(' in server_source and "protocol_version = 'HTTP/1.1'" in server_source:
                goal+=(' Fresh read-only transport diagnosis: the single-threaded HTTP/1.1 server served the homepage but a second '
                       'independent GET /api/count timed out while the first client remained connected. Use http.server.ThreadingHTTPServer '
                       'in start_server, or correctly close each response so one keep-alive client cannot block Chrome fetches. '
                       'The HTML lives beside server.py, never in the writable SQLite --data-dir. Preserve that distinction.')
            if server_source and not any(isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name=='run'
                                         for node in ast.parse(server_source).body):
                goal+=' Fresh source inspection: run(port, data_dir) was removed by an earlier repair; restore it as a module-level wrapper forwarding to start_server(port, data_dir), and retain start_server.'
            record['response']=run(coder,project,goal,lambda:False,initial_plan=plan,
                initial_feedback=repair_packet(project,diagnosis,plan),allowed_paths=['server.py','test_server.py'])
        else:record['response']=coder.run(project,goal,selected=True)
        receipts=[]
        for path in (BASE/'.jarvis-runtime/codex-code').glob('*/request.json'):
            if json.loads(path.read_text(encoding='utf-8'))['project']!=str(project):continue
            result_path=path.parent/'result.json'
            if result_path.exists():receipts.append((result_path.stat().st_mtime_ns,json.loads(result_path.read_text(encoding='utf-8'))))
        passed=[r for _,r in sorted(receipts,key=lambda row:row[0]) if r.get('functional_behavior_verified')
                and all((project/name).is_file() and hashlib.sha256((project/name).read_bytes()).hexdigest()==digest
                        for name,digest in r['validation']['hashes'].items())]
        assert passed,'No verified native Codex completion'
        if '--repair-fixture' in sys.argv:
            names={node.name for node in ast.parse((project/'server.py').read_text()).body
                   if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}
            required={'init_db','get_count','change_count','make_handler','run'}
            assert required<=names,'Required backend interfaces missing: '+', '.join(sorted(required-names))
            record['independent_persistence']=verify_reinitialization(project)
        final=passed[-1];validation=final['validation'];assert validation['passed']
        browser=next(c for c in validation['checks'] if c['kind']=='browser')
        assert '"backend_requests":' in browser['output']
        record.update(passed=True,checks=validation['checks'],repair_turns=final['repair_turns'],source_sha256=validation['hashes'],
            progress_events=sum(k=='task_status' for k,v in events))
        captures=list(Path(final['turns'][-1]).glob('check-workspace-*/browser-check.png'))
        if captures:
            destination=BASE/'artifacts/codex-fullstack-live.png';shutil.copyfile(captures[-1],destination)
            record['screenshot']='artifacts/codex-fullstack-live.png'
    except KeyboardInterrupt:
        record.update(passed=False,interrupted=True,error='Operator interrupted the owned inference trial; no uncertain actions replayed.')
    except Exception as error:record.update(passed=False,error=str(error))
    path=BASE/'artifacts/codex-validation-live-check.json'
    if path.exists():
        history=path.with_name('codex-validation-live-history.json');rows=json.loads(history.read_text()) if history.exists() else []
        rows.append(json.loads(path.read_text()));history.write_text(json.dumps(rows,indent=2)+'\n')
    path.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2),flush=True)
    return record['passed']


if __name__=='__main__':raise SystemExit(0 if verify() else 1)
