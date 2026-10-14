"""Local cloud controls; live smoke requires two explicit opt-ins and free gating."""
import argparse
import json
import uuid

from .hybrid_inference import BASE,control,get_service


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['status','offline','enable','auto','refresh-metadata','live-smoke'])
    parser.add_argument('--authorize-live-free-request',action='store_true')
    args=parser.parse_args()
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
