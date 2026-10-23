"""Routine choices never mint approval receipts or authorize tool side effects."""
import json
import time
import uuid


class DecisionManager:
    def __init__(self, store, timeout=20, clock=time.time):
        if not 1 <= float(timeout) <= 300:
            raise ValueError('Decision timeout must be between 1 and 300 seconds')
        self.store, self.timeout, self.clock = store, float(timeout), clock

    def create(self, task, question, options, recommended=0, confidence=0., reversible=False, sensitive=True):
        if not options or not 0 <= recommended < len(options):
            raise ValueError('Invalid decision options')
        identity = uuid.uuid4().hex
        data = {'id': identity, 'question': question, 'options': options, 'recommended': recommended,
                'confidence': float(confidence), 'reversible': bool(reversible), 'sensitive': bool(sensitive),
                'presented_at': None, 'choice': None, 'status': 'PENDING', 'automatic': False}
        with self.store.transaction():
            self.store.db.execute('INSERT INTO decisions VALUES(?,?,?)', (identity, task or '', json.dumps(data)))
        return identity

    def rows(self):
        with self.store.lock:
            return [json.loads(row[0]) for row in self.store.db.execute('SELECT data FROM decisions ORDER BY rowid')]

    def _update(self, identity, operation):
        with self.store.transaction():
            row = self.store.db.execute('SELECT data FROM decisions WHERE id=?', (identity,)).fetchone()
            if not row:
                raise ValueError('Unknown decision')
            data = json.loads(row[0])
            changed = operation(data)
            self.store.db.execute('UPDATE decisions SET data=? WHERE id=?', (json.dumps(data), identity))
            self.store.setting('decision_history', self.rows())
            return changed, data

    def presented(self, identity):
        def present(data):
            if data['presented_at'] is None and data['status'] == 'PENDING':
                data['presented_at'] = self.clock()
        return self._update(identity, present)[1]

    def choose(self, identity, choice):
        def select(data):
            if data['status'] != 'PENDING':
                return False
            if data['presented_at'] is None:
                return False
            if not 0 <= choice < len(data['options']):
                raise ValueError('Unknown option')
            # Resolve timeout atomically before accepting a late response.
            if self.clock() >= data['presented_at']+self.timeout:
                self._expire(data)
                return False
            data.update(choice=choice, status='SELECTED', justification='User selected')
            return True
        return self._update(identity, select)

    def _expire(self, data):
        if data['sensitive']:
            data.update(status='WAITING_APPROVAL', justification='Silence never authorizes sensitive actions')
        elif data['reversible'] and data['confidence'] >= .85:
            data.update(choice=data['recommended'], status='SELECTED', automatic=True,
                        justification='High-confidence reversible routine preference; deadline elapsed')
        else:
            data.update(status='DEFERRED', justification='Insufficient confidence or reversibility')

    def tick(self):
        resolved = []
        for data in self.rows():
            if data['status'] == 'PENDING' and data['presented_at'] is not None and self.clock() >= data['presented_at']+self.timeout:
                def expire(value):
                    if value['status'] == 'PENDING':
                        self._expire(value)
                        return True
                    return False
                changed, value = self._update(data['id'], expire)
                if changed:
                    resolved.append(value)
        return resolved
