"""Local cloud controls; live smoke requires two explicit opt-ins and free gating."""
import argparse
import json
import uuid

from .hybrid_inference import BASE,control,get_service


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['status','offline','enable','auto','coding-status','confirm-gemini-key-project','refresh-metadata','live-smoke'])
    parser.add_argument('--authorize-live-free-request',action='store_true')
    parser.add_argument('--project-id')
    parser.add_argument('--confirm-key-project-and-free-tier',action='store_true')
    args=parser.parse_args()
    if args.action=='confirm-gemini-key-project':
        if not args.confirm_key_project_and_free_tier or not args.project_id:
            raise SystemExit('No configuration changed. Explicit confirmation of the local key project and free-only billing is required.')
        import hashlib
        from .coding_cloud_policy import credential,gemini_settings
        from .skill_memory import atomic
        path=BASE/'config/config.json';config=json.loads(path.read_text(encoding='utf-8'));options=gemini_settings(config.get('gemini'))
        if args.project_id!=options['api_project_id'] or args.project_id!=options['quota_project_id'] or not options['quota_verified'] or not options['billing_disabled_confirmed']:
            raise SystemExit('Configured project/model/free-tier quota must match the explicit project confirmation.')
        key=credential(BASE)
        if not key:raise SystemExit('No GEMINI_API_KEY configured locally; no configuration changed.')
        options.update(key_project_confirmed=True,quota_key_sha256=hashlib.sha256(key.encode()).hexdigest())
        config['gemini']=options;atomic(path,json.dumps(config,indent=2,ensure_ascii=False)+'\n')
        print(json.dumps({'project':args.project_id,'model':options['model'],'key_project_confirmation':'operator_attestation','inference_requests':0}));return
    if args.action=='coding-status':
        service=get_service(BASE)
        if not service:print(json.dumps({'coding':'disabled'}));return
        if service.coding_routes is None:
            from .coding_cloud_routes import CodingRoutes
            service.coding_routes=CodingRoutes(service,json.loads((BASE/'config/config.json').read_text(encoding='utf-8')))
        print(json.dumps(service.coding_routes.status()));return
    if args.action in {'status','offline','enable','auto'}:
        print(control(BASE,args.action));return
    service=get_service(BASE)
    if not service or not service.adapter:
        raise SystemExit('Groq remains unavailable: check enabled configuration, free-account/quota confirmations and local credentials.')
    if args.action=='live-smoke' and (not args.authorize_live_free_request or not service.options['live_tests_enabled']):
        raise SystemExit('No inference sent. Live smoke needs GROQ_LIVE_TESTS_ENABLED=true and --authorize-live-free-request.')
    try:
        service.adapter.refresh()
        if args.action=='refresh-metadata':
            print(json.dumps({'model_available':service.adapter.ready(),'scope':'Model metadata only, no inference.'}));return
        identifier=uuid.uuid4().hex
        message=service.adapter.complete([{'role':'user','content':'Explain why the sky is blue in one sentence.'}],
            output_tokens=32,request_id=identifier)
        with service.guardian.connect() as db:
            row=db.execute('SELECT usage,status FROM calls WHERE id=?',(identifier,)).fetchone()
        print(json.dumps({'answer':message['content'],'usage':json.loads(row['usage']),'reconciliation':row['status']}))
    finally:service.close()


if __name__=='__main__':main()
