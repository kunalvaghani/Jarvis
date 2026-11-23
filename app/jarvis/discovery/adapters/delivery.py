"""Exactly-once export admission, known-ID reconciliation, existing Google Files transport."""
import json,re
from ..model.delivery import sha,verify_back

def files(base):
    from ...google_files import Files
    return Files(base)

class Ledger:
    def __init__(self,journal):
        self.j=journal
        with journal.tx() as db:db.execute('CREATE TABLE IF NOT EXISTS discovery_deliveries '
            '(id TEXT PRIMARY KEY,payload_ref TEXT NOT NULL,state TEXT NOT NULL,remote_id TEXT,result_ref TEXT)')

    def stage(self,payload):
        key='delivery-'+sha(payload);ref=self.j.put(payload,data_type='Report')
        with self.j.tx() as db:db.execute('INSERT OR IGNORE INTO discovery_deliveries VALUES (?,?,?,NULL,NULL)',(key,ref,'PREPARED'))
        return key

    def row(self,key):
        rows=self.j.rows('SELECT * FROM discovery_deliveries WHERE id=?',(key,))
        if not rows:raise ValueError('unknown delivery')
        return rows[0]

    def payload(self,key):return json.loads(self.j.get(self.row(key)['payload_ref']))

    def create(self,key,base,cancelled):
        row=self.row(key);payload=self.payload(key)
        if row['remote_id']:return {'delivery_id':key,'remote_id':row['remote_id'],'state':row['state']}
        if row['state']!='PREPARED':raise ValueError('delivery uncertain without ID; inspect Drive, never repeat creation')
        if cancelled():raise ValueError('delivery cancelled before client access')
        client=files(base)
        try:
            with self.j.tx() as db:
                changed=db.execute("UPDATE discovery_deliveries SET state='SENT' WHERE id=? AND state='PREPARED' AND remote_id IS NULL",(key,)).rowcount
                if changed!=1:raise ValueError('another delivery owns this admission; do not repeat')
            if cancelled():
                with self.j.tx() as db:db.execute("UPDATE discovery_deliveries SET state='PREPARED' WHERE id=? AND state='SENT'",(key,))
                raise ValueError('cancelled before external request')
            try:
                made=client.create_doc(payload['title'],payload['text'],payload['parent_id']) if payload['kind']=='report' else client.create_sheet(payload['title'],payload['rows'],payload['parent_id'])
                identity=made.get('id')
                if not isinstance(identity,str) or not re.fullmatch(r'[A-Za-z0-9_-]{10,100}',identity):raise ValueError('missing remote ID')
            except Exception:
                with self.j.tx() as db:db.execute("UPDATE discovery_deliveries SET state='UNCERTAIN' WHERE id=?",(key,))
                raise ValueError('Google creation outcome uncertain; inspect Drive; no retry or duplicate creation') from None
            with self.j.tx() as db:db.execute("UPDATE discovery_deliveries SET remote_id=?,state='CREATED' WHERE id=?",(identity,key))
            return {'delivery_id':key,'remote_id':identity,'state':'CREATED'}
        finally:client.close()

    def inspect(self,key,base,cancelled):
        row=self.row(key);payload=self.payload(key)
        if not row['remote_id']:raise ValueError('no known remote ID; inspect Drive manually, never recreate')
        if cancelled():raise ValueError('delivery readback cancelled')
        client=files(base)
        try:back=client.text_of(row['remote_id']) if payload['kind']=='report' else client.cells_of(row['remote_id'])
        except Exception:raise ValueError('known-ID readback failed; use lab export inspect; no write was repeated') from None
        finally:client.close()
        verify_back(payload,back)
        result={'delivery_id':key,'remote_id':row['remote_id'],'kind':payload['kind'],'readback_sha256':sha(back),
                'verified':True,'evidence_status':'MODEL_CONSISTENT','physical_validation':False}
        ref=self.j.put(result,data_type='Report')
        with self.j.tx() as db:db.execute("UPDATE discovery_deliveries SET state='VERIFIED',result_ref=? WHERE id=?",(ref,key))
        return result
