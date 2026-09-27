"""Live transfer task through the ordinary Jarvis coding generator."""
from datetime import datetime, timezone
import argparse
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import sys

from jarvis.brain import BrainClient
from jarvis.coder import generate_checked
from jarvis.coding_lessons import record
from train_coding import BASE, check, failure_category, inspect_source

CONTRACT=('Create main.py as a complete standard-library Python JSON CLI invoice calculator. '
          'Read one JSON object from stdin with items (list of objects containing price and qty), '
          'discount_pct and tax_pct. All values are nonnegative, qty is an integer and percentages are 0..100. '
          'Output only one JSON object with numeric subtotal, discount, net, tax and total. '
          'Round subtotal=sum(price*qty) to two decimal places using decimal ROUND_HALF_UP. '
          'Round discount=subtotal*discount_pct/100 to two places HALF_UP; net=subtotal-discount. '
          'Round tax=net*tax_pct/100 HALF_UP; total=net+tax. Empty/zero-quantity items contribute zero. '
          'Retain every item including duplicates. Use Decimal from string representations for cents. '
          'No files, network, processes, eval, installation or extra stdout labels.')


def cases():
    samples=[([],0,0),([{'price':10,'qty':2}],0,5),
             ([{'price':12.5,'qty':2},{'price':3,'qty':4}],10,5),
             ([{'price':0.1,'qty':3},{'price':0.2,'qty':1}],0,10),
             ([{'price':20,'qty':4}],100,20),([{'price':100,'qty':1}],20,0),
             ([{'price':10,'qty':0}],10,20),
             ([{'price':7.25,'qty':1},{'price':7.25,'qty':3}],0,7.5),
             ([{'price':0.05,'qty':1}],10,0),([{'price':1000,'qty':100}],5,18)]
    output=[]
    def cents(value):return value.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
    for items,discount_pct,tax_pct in samples:
        subtotal=cents(sum((Decimal(str(i['price']))*i['qty'] for i in items),Decimal(0)))
        discount=cents(subtotal*Decimal(str(discount_pct))/100);net=subtotal-discount
        tax=cents(net*Decimal(str(tax_pct))/100)
        expected=dict(subtotal=subtotal,discount=discount,net=net,tax=tax,total=net+tax)
        output.append({'input':dict(items=items,discount_pct=discount_pct,tax_pct=tax_pct),
                       'expected':{k:float(v) for k,v in expected.items()}})
    return output


def invoice_equal(actual,expected):
    return (isinstance(actual,dict) and actual.keys()==expected.keys() and
            all(type(actual[k]) in {int,float} and abs(actual[k]-expected[k])<=1e-8
                for k in expected))


class ObservedClient:
    def __init__(self,brain):self.brain=brain;self.base=BASE;self.events=[]
    def request(self,*args,**kwargs):
        event={'operation':args[0],'lesson_kinds':[r['kind'] for r in kwargs.get('coding_lessons',[])],
               'validation_error':kwargs.get('validation_error','')}
        self.events.append(event)
        result=self.brain.request(*args,**kwargs);event['model_used']=result.get('model_used')
        return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint',help='Test an actual trained Qwen checkpoint through the ordinary coding route')
    args=parser.parse_args()
    root=BASE/'artifacts'/('coding-transfer-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    root.mkdir(exist_ok=False);samples=cases()
    (root/'README.md').write_text('# Invoice calculator transfer task\n\n'+CONTRACT+'\n\nRun `python main.py`. Two examples were provided; eight follow-up cases were withheld.\n',encoding='utf-8')
    report={'at':datetime.now(timezone.utc).isoformat(),'task':'invoice calculator',
            'visible_examples':2,'withheld_cases':8,'learning':'ordinary generator with experience recall; no execution-feedback repair'}
    options=json.loads((BASE/'config.json').read_text(encoding='utf-8'))['brain']
    if args.checkpoint:
        options['trained_coder_checkpoint']=args.checkpoint
        report.update(learning='actual trained Qwen checkpoint; no execution-feedback repair',checkpoint=args.checkpoint)
    brain=BrainClient(BASE,options)
    client=ObservedClient(brain)
    try:
        source=generate_checked(client,lambda:False,Path('main.py'),goal=CONTRACT,project='invoice-transfer',
            path='main.py',reason='Implement the invoice calculator',current='',
            plan=[{'path':'main.py','reason':'Implement the invoice calculator'}],files=[],
            references={'visible_examples':json.dumps(samples[:2])})
        kind,error=inspect_source(source)
        if kind:report.update(status='not_executed',kind=kind,error=error)
        else:
            with (root/'main.py').open('x',encoding='utf-8') as file:file.write(source)
            before=hashlib.sha256((root/'main.py').read_bytes()).hexdigest()
            rows=check(root,samples,compare=invoice_equal);unchanged=before==hashlib.sha256((root/'main.py').read_bytes()).hexdigest()
            passed=sum(row['passed'] for row in rows)
            kind='logic' if passed==10 else failure_category([r for r in rows if not r['passed']])
            if not unchanged:kind='policy';passed=0
            if not args.checkpoint:
                record(BASE,'101-invoice-transfer',kind,passed,10,1)
            report.update(status='executed',cases=rows,source_sha256=before,source_unchanged=unchanged,
                          summary={'passed':passed,'total':10})
    except Exception as exc:report.update(status='generation_failed',error=str(exc)[:1000])
    finally:brain.close()
    report['inference_events']=client.events
    (root/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(str(root/'results.json'),flush=True)
    print(json.dumps({k:report[k] for k in ('status','summary') if k in report}),flush=True)
    return 0 if report.get('summary',{}).get('passed')==10 else 1

if __name__=='__main__':sys.exit(main())
