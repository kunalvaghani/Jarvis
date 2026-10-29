"""Summarize actual local campaign receipts without promoting any run to PASS."""
from datetime import datetime,timezone
import hashlib
import json
import re
import sqlite3
from pathlib import Path
import sys

BASE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(BASE))


def main():
    from jarvis.workload_state import latest_checkpoint
    runs=[]
    for root in sorted((BASE/'.jarvis-runtime/autonomous-repair').glob('*')):
        source=root/'campaign.json'
        if not source.is_file():continue
        campaign=json.loads(source.read_text(encoding='utf-8'))
        workloads=[]
        for directory in (root/'.jarvis-runtime/native-workloads').glob('*'):
            if not (directory/'receipt.json').exists() and not (directory/'checkpoints').exists():continue
            receipt=latest_checkpoint(directory)
            metadata=[json.loads(p.read_text(encoding='utf-8')) for p in directory.glob('model-responses/*/metadata.json')]
            validation=receipt.get('validation') or {}
            workloads.append({k:receipt.get(k) for k in ('status','seconds','planning_seconds','workload_count','error','max_workers','changed')} | {
                'id':directory.name,'evidence':directory.relative_to(BASE).as_posix(),
                'validation':{k:validation.get(k) for k in ('passed','runtime_verified','errors')},
                'executable_checks':[{k:c.get(k) for k in ('kind','path','exit_code','output')} for c in validation.get('checks',[])],
                'planner_calls_retained':len(metadata),'responses':metadata})
        native=[]
        for directory in (root/'.jarvis-runtime/native-code').glob('*'):
            tools=directory/'tools.jsonl'
            rows=[json.loads(s) for s in tools.read_text(encoding='utf-8').splitlines()] if tools.exists() else []
            files=directory/'file-events.jsonl'
            writes=[json.loads(s) for s in files.read_text(encoding='utf-8').splitlines()] if files.exists() else []
            native_metadata=[json.loads(p.read_text(encoding='utf-8')) for p in directory.glob('model-responses/*/metadata.json')]
            result=json.loads((directory/'result.json').read_text(encoding='utf-8')) if (directory/'result.json').exists() else {}
            validation=json.loads((directory/'validation.json').read_text(encoding='utf-8')) if (directory/'validation.json').exists() else {}
            cloud_path=directory/'cloud-route-state.json'
            cloud=json.loads(cloud_path.read_text(encoding='utf-8')) if cloud_path.exists() else {}
            dispatched=[row for row in cloud.get('attempts',[]) if row.get('sent') is True]
            native.append({'cloud_inference':{'attempted_requests':len(dispatched),
                'reported_tokens':sum(row.get('usage',{}).get('total_tokens',0) for row in dispatched),
                'uncertain_usage_requests':sum(not row.get('usage',{}).get('exact_usage_available') for row in dispatched),
                'providers':sorted({row['provider'] for row in dispatched}),
                'independent_application_acceptance':'NOT_ESTABLISHED_BY_PROVIDER_RESPONSE'},'id':directory.name,'tool_proposals':len(rows),'rejected_tools':sum(isinstance(r.get('result'),dict) and 'error' in r['result'] for r in rows),
                'confirmed_file_saves':sum(r.get('stage')=='applied' for r in writes),
                'model_calls_retained':len(native_metadata),
                'error':result.get('error'),'validation':{k:validation.get(k) for k in ('passed','runtime_verified')},
                'executable_checks':[{k:c.get(k) for k in ('kind','path','exit_code')} for c in validation.get('checks',[])],
                'served_models':sorted({m['served_model'] for m in native_metadata if m.get('served_model')}),
                'requested_models':sorted({m['model'] for m in native_metadata if m.get('model')})})
        history=[json.loads(p.read_text(encoding='utf-8')) for p in sorted((root/'campaign-history').glob('*.json'))]
        cancellation=root/'supervisor-cancellation.json'
        research_observation=root/'research-observation.json'
        interruption=root/'interrupted-observation.json'
        independent=[]
        for path in [*root.glob('independent-acceptance-*.json'),*root.glob('independent-cli-acceptance-*.json')]:
            value=json.loads(path.read_text(encoding='utf-8'))
            project=Path(value.get('project',''))
            current={p.relative_to(project).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in project.rglob('*') if p.is_file() and '__pycache__' not in p.parts} if project.is_dir() else {}
            expected=value.get('artifact_hashes')
            if value.get('source_after') is not None:
                from jarvis.codex_workload import fingerprint
                try:current=fingerprint(Path(value['project']))
                except (OSError,ValueError):current={}
                expected=value['source_after']
            independent.append({**value,'source_current':bool(current) and current==expected})
        durable={}
        queue=root/'.jarvis-runtime/task-queue.sqlite3'
        if queue.is_file():
            with sqlite3.connect(queue.resolve().as_uri()+'?mode=ro',uri=True,timeout=2) as connection:
                durable=dict(connection.execute('SELECT id,state FROM tasks'))
        runs.append({k:campaign.get(k) for k in ('date','finished_at','record_to_shutdown_seconds','case','request','model','result','reason','seconds','resume','mode','scope','live_changes','jarvis_source_sha256','jarvis_source_changed_during_trial','configuration_sha256','gpu_policy','coding_policy','configuration_changed_during_trial')} | {
            'run':root.name,'task_ids':[r['id'] for r in campaign.get('tasks',[])],
            'task_states':{r['id']:r['state'] for r in campaign.get('tasks',[])},
            'durable_task_states':durable,
            'task_capture_stage':campaign.get('task_capture_stage','Campaign snapshot; older trials can precede shutdown. Compare fresh durable_task_states.'),
            'existing_files_unchanged':all(campaign.get('source_after',{}).get(p)==h for p,h in campaign['source_before'].items()) if 'source_before' in campaign and 'source_after' in campaign else None,
            'previous_campaigns':[{k:c.get(k) for k in ('date','result','reason','seconds')} for c in history],
            'supervised_cancellation':json.loads(cancellation.read_text(encoding='utf-8')) if cancellation.exists() else None,
            'research_observation':json.loads(research_observation.read_text(encoding='utf-8')) if research_observation.exists() else None,
            'interruption_observation':json.loads(interruption.read_text(encoding='utf-8')) if interruption.exists() else None,
            'independent_acceptance':independent,
            'reuse_trials':[json.loads(p.read_text(encoding='utf-8')) for p in root.glob('reuse-trials/*/campaign.json')],
            'project_ids':[p['id'] for p in campaign.get('projects',[])],
            'workloads':workloads,'native_runs':native,
            'generated_source_files':[str(p) for p in Path(campaign.get('workspace_parent',str(root/'projects'))).rglob('*') if p.is_file() and p.suffix.lower() in {'.py','.js','.html','.css','.ts','.tsx','.jsx'}]})
    original=BASE/'.jarvis-runtime/native-workloads/1b0d48672c274ba2a3a5799a7a1096c7'
    report={'date':datetime.now(timezone.utc).isoformat(),'release_acceptance':'OPEN',
        'note':'Actual production intake/local Qwen trials; no supervisor-authored target source. Pending runs retain NOT_RUN until terminal capture. Regression fixtures are not acceptance.',
        'original_workload_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in original.glob('*') if p.is_file()},
        'runs':runs,'unmeasured':['peak_vram','cpu_ram_overhead','reuse_benefit','research_source_editing_overlap','representative_success_rates']}
    regression={}
    for name in ('repair-full-remainder','repair-full-failure-modules','repair-consecutive-recovery-final',
                 'repair-compact-prompt-final','repair-faults-final','repair-tool-contract-final',
                 'repair-parent-contract-final2','repair-safe-resume-final','repair-final-source-regression',
                 'repair-active-diagnostics-final2','repair-parent-preservation-final','repair-final-boundaries',
                 'repair-final-inspection-boundary','repair-final-context-boundary','repair-final-evidence-scope','repair-focused-edit-final2',
                 'repair-authoritative-goal-final','repair-readonly-transport-final','repair-campaign-contract-final',
                 'repair-preview-slice-final','repair-compact-diagnostics-final','repair-web-choice-final',
                 'repair-supported-ownership-final','repair-origin-handoff-final','repair-react-framework-final',
                 'repair-react-manifest-scope-final','repair-fullstack-check-schema-final',
                 'repair-existing-source-transition-final2','repair-preserved-export-feedback-final',
                 'repair-frozen-test-interfaces-final','repair-frozen-test-calls-final',
                 'repair-explicit-refinement-final2','repair-bounded-source-regeneration-final2',
                 'repair-research-source-context-final','repair-research-source-reader-final2',
                 'repair-planner-feedback-source-final2','repair-research-budget-final','repair-domain-source-budgets-final2',
                 'repair-verified-source-integrity-final','repair-memory-provenance-final','repair-owned-memory-reuse-final',
                 'repair-context-policy-final','repair-stack-plan-normalization-host-final',
                 'repair-plan-correction-final','repair-nested-package-final',
                 'repair-react-entry-final','repair-gui-test-guidance-final',
                 'repair-gui-original-callbacks-final','repair-application-entry-final',
                 'repair-application-entry-cases-final','repair-stack-family-final','repair-stack-family-cases-final',
                 'repair-explicit-reuse-source-final','repair-explicit-reuse-source-cases-final',
                 'repair-frozen-expectations-final','repair-stage-feedback-cases-final',
                 'repair-batch-observation-progress-final2','repair-noop-boundary-final3',
                 'repair-snapshot-bytes-final2','repair-patch-newlines-final','repair-complete-regeneration-final',
                 'repair-complete-regeneration-prompt','repair-cli-focus-final',
                 'repair-cli-focus-cases-final','repair-incidental-entry-final2',
                 'repair-stagnation-final','repair-exact-target-final','repair-exact-target-case-final',
                 'repair-immediate-focus-final','repair-progress-expectations-final','repair-failed-test-read-final',
                 'repair-traceback-contract-final','repair-traceback-contract-final2','repair-traceback-deep-integration',
                 'repair-gui-test-loop-final','repair-gui-test-loop-target','repair-gui-test-loop-target2',
                 'repair-gui-api-signature-target','repair-gui-api-signature-final',
                 'repair-gui-modules-target','repair-gui-module-mock-target','repair-gui-module-mock-final',
                 'repair-gui-module-import-final','repair-gui-instance-api-target','repair-gui-instance-api-final',
                 'repair-frozen-state-focus-target','repair-frozen-state-focus-final',
                 'repair-preserved-input-target','repair-preserved-input-final','repair-preserved-input-hashes-final',
                 'repair-preserved-input-hashes-final2','repair-preserved-source-boundary-final',
                 'repair-preserved-source-boundary-final2','repair-preserved-source-schema-case',
                 'repair-diagnostic-windows-target','repair-diagnostic-windows-target2','repair-diagnostic-windows-final',
                 'repair-primary-failure-target','repair-primary-failure-final',
                 'repair-iterative-until-target2','repair-iterative-until-final',
                 'repair-iterative-gates-final','repair-iterative-island-recheck',
                 'repair-source-coverage-target','repair-source-coverage-target2',
                 'repair-source-coverage-target3','repair-source-coverage-final',
                 'repair-context-replacement-target','repair-context-replacement-target2',
                 'repair-context-replacement-final','repair-context-replacement-final2',
                 'repair-replacement-idle-target','repair-replacement-idle-final',
                 'repair-primary-trace-target','repair-primary-trace-final',
                 'repair-receiver-protocol-target','repair-receiver-protocol-final',
                 'repair-failure-history-target','repair-history-cycle-target','repair-history-cycle-final',
                 'repair-bounded-plan-target','repair-bounded-plan-final',
                 'repair-stdlib-frame-target','repair-stdlib-frame-final',
                 'repair-portable-plan-string-target','repair-portable-plan-string-final',
                 'repair-generation-grammar-target','repair-generation-grammar-final',
                 'repair-generation-grammar-target2','repair-generation-grammar-target3',
                 'repair-generation-grammar-final2','repair-generation-grammar-final3',
                 'repair-isolated-cause-target','repair-isolated-cause-final',
                 'repair-readonly-plan-data-target','repair-readonly-plan-data-final',
                 'repair-canonical-diagnosis-target','repair-canonical-diagnosis-final',
                 'repair-presave-escalation-target','repair-presave-escalation-target2',
                 'repair-presave-escalation-target3','repair-presave-escalation-idle-boundary',
                 'repair-presave-escalation-final',
                 'repair-runtime-operands-target','repair-runtime-operands-target2',
                 'repair-runtime-operands-final','repair-runtime-operands-target3',
                 'repair-runtime-operands-final2',
                 'repair-receiver-keys-native','repair-receiver-keys-nearby',
                 'repair-single-owner-regression','repair-exact-statement-target',
                 'repair-exact-statement-regression','webmcp-contracts-final',
                 'webmcp-nearby-regression','webmcp-offer-integrity-final',
                 'repair-history-handoff-target4','repair-history-handoff-final-bindings',
                 'repair-history-handoff-regression','repair-candidate-preservation-target',
                 'repair-candidate-preservation-regression','repair-typed-diagnosis-focused',
                 'repair-typed-diagnosis-regression','repair-typed-diagnosis-regression-final',
                 'repair-bounded-stage-target','repair-bounded-stage-regression',
                 'repair-frozen-metadata-target','repair-frozen-metadata-regression',
                 'repair-canonical-handoff-target','repair-canonical-handoff-regression',
                 'repair-member-facts-target','repair-member-facts-regression',
                 'repair-grounded-edit-target','repair-grounded-edit-regression',
                 'repair-atomic-progress-target','repair-atomic-progress-target-final',
                 'repair-atomic-progress-regression','repair-first-write-baseline-target',
                 'repair-first-write-baseline-regression','repair-first-write-baseline-target-final',
                 'repair-first-write-baseline-regression-final','repair-first-write-baseline-regression-final2',
                 'repair-first-write-history-target','repair-strict-progress-target',
                 'repair-strict-progress-regression','repair-strict-progress-audit',
                 'repair-independent-feedback-target','repair-independent-feedback-target-final',
                 'repair-independent-feedback-regression','repair-independent-feedback-audit',
                 'repair-diagnostic-feedback-target','repair-diagnostic-feedback-target-final',
                 'repair-diagnostic-feedback-regression','repair-diagnostic-feedback-audit',
                 'repair-patch-preemption-before-fix-final','repair-patch-preemption-target-final2',
                 'repair-patch-preemption-regression','repair-patch-preemption-audit',
                 'repair-protocol-intent-target','repair-protocol-contract-target-final',
                 'repair-protocol-intent-regression','repair-protocol-intent-audit',
                 'repair-same-source-recurrence-target','repair-same-source-recurrence-target-final',
                 'repair-same-source-recurrence-regression','repair-same-source-recurrence-regression-final',
                 'repair-same-source-recurrence-audit','repair-bound-interface-target',
                 'repair-bound-interface-regression','repair-bound-interface-audit',
                 'repair-bounded-corrections-target-final2','repair-bounded-corrections-regression-final',
                 'repair-bounded-corrections-audit','repair-binding-rendering-target-final',
                 'repair-binding-rendering-regression-final','repair-binding-rendering-audit-final',
                 'repair-candidate-feedback-target','repair-candidate-feedback-regression','repair-candidate-feedback-audit',
                 'repair-owned-contract-target','repair-owned-contract-regression','repair-owned-contract-audit',
                 'repair-owned-feedback-target','repair-owned-feedback-regression','repair-owned-feedback-audit',
                 'repair-owned-methods-target','repair-owned-methods-regression','repair-owned-methods-audit',
                 'repair-diagnostic-evidence-target','repair-diagnostic-evidence-target-final',
                 'repair-diagnostic-evidence-regression','repair-diagnostic-evidence-audit',
                 'repair-key-contract-target','repair-key-contract-target-final',
                 'repair-key-contract-regression','repair-key-contract-audit',
                 'repair-key-producer-target-final','repair-key-producer-regression','repair-key-producer-regression-final',
                 'repair-key-producer-audit','repair-key-producer-audit-final',
                 'repair-normal-feedback-target-final','repair-normal-feedback-regression','repair-normal-feedback-audit',
                 'repair-noop-contract-target-corrected','repair-noop-contract-regression','repair-noop-contract-regression-final',
                 'repair-noop-contract-legacy-guard','repair-noop-contract-audit',
                 'repair-execution-contract-target','repair-execution-contract-target-final','repair-execution-contract-eligibility-final',
                 'repair-execution-contract-regression','repair-execution-contract-regression-final','repair-execution-contract-regression-verified',
                 'repair-execution-contract-audit','repair-execution-contract-audit-final','repair-execution-contract-audit-verified',
                 'repair-function-definition-target','repair-function-definition-regression','repair-function-definition-audit',
                 'repair-function-statements-target','repair-function-statements-regression','repair-function-statements-audit',
                 'repair-structured-python-target','repair-structured-python-regression','repair-structured-python-audit',
                 'repair-callback-contract-target','repair-callback-contract-regression','repair-callback-contract-audit',
                 'cloud-coding-final-regression','cloud-coding-final-audit','repair-regex-focused',
                 'repair-regex-audit','cloud-feedback-zero-token-final','cloud-feedback-native-regression'):
        path=BASE/'.jarvis-runtime'/(name+'.log')
        if path.exists():
            lines=[s for s in path.read_text(encoding='utf-8',errors='replace').splitlines() if re.search(r'\d+ passed',s)]
            if lines:regression[name]=lines[-1].strip('= ')
            else:
                content=path.read_text(encoding='utf-8',errors='replace')
                summary=re.search(r'Ran (\d+) tests? in ([\d.]+)s\s+((?:OK|FAILED)[^\r\n]*)',content)
                if summary:regression[name]={'tests':int(summary[1]),'seconds':float(summary[2]),'result':summary[3]}
    path=BASE/'.jarvis-runtime/repair-full-regression.log'
    if path.exists():
        progress=''.join(re.match(r'^([.sFxE]+)',s)[1] for s in path.read_text().splitlines() if re.match(r'^[.sFxE]+ +\[',s))
        regression['interrupted_initial_recorded_outcomes']={symbol:progress.count(symbol) for symbol in ('.','s','F','E')}
        regression['clean_single_full_suite_pass']=False
    report['regression_evidence']=regression
    readiness=BASE/'.jarvis-runtime/repair-regex-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-callback-contract-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-structured-python-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-function-statements-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-diagnostic-evidence-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-owned-feedback-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-owned-contract-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-candidate-feedback-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-binding-rendering-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-bounded-corrections-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-bound-interface-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-same-source-recurrence-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-protocol-intent-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-patch-preemption-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-diagnostic-feedback-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-independent-feedback-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-strict-progress-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-first-write-baseline-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-atomic-progress-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-grounded-edit-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-member-facts-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-canonical-handoff-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-frozen-metadata-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-typed-diagnosis-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-candidate-preservation-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-history-handoff-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-exact-statement-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-single-owner-launcher.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-runtime-operands-launcher-check.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-presave-escalation-launcher-check.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-canonical-diagnosis-launcher-check.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-isolated-cause-launcher-check.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-generation-grammar-launcher-check.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-stdlib-frame-launcher-check.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-bounded-plan-launcher-check.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-history-cycle-launcher-check.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-receiver-protocol-launcher-check.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-primary-trace-launcher-check.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-replacement-idle-launcher-check.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-context-replacement-launcher-final2.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-context-replacement-launcher-check.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-source-coverage-launcher-check.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-iterative-gates-launcher-final.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-primary-failure-launcher-check.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-diagnostic-windows-launcher-check.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-frozen-state-focus-launcher-check.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-gui-instance-api-launcher-check.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-gui-module-mock-launcher-final.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-gui-api-signature-launcher-check.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-gui-test-loop-launcher-check.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-traceback-launcher-check-final.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-final-host-readiness.log'
    if not readiness.exists():readiness=BASE/'.jarvis-runtime/repair-final-readiness.log'
    if readiness.exists():
        lines=readiness.read_text(encoding='utf-8',errors='replace').splitlines()
        if lines:
            value=json.loads(lines[-1])
            report['configured_readiness']={k:value.get(k) for k in ('status','missing','incomplete','scope')}
            report['configured_readiness']['evidence']=readiness.relative_to(BASE).as_posix()
    destination=BASE/'artifacts/autonomous-repair';destination.mkdir(parents=True,exist_ok=True)
    (destination/'campaign-summary.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'runs':len(runs),'release_acceptance':'OPEN','report':str(destination/'campaign-summary.json')}))


if __name__=='__main__':main()
