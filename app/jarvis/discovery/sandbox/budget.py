"""Atomic reservations in the existing Journal. No separate quota or approval service.

Unknown outcomes remain charged. GPU requests must go to the existing GPU
scheduler; this CPU-only foundation cannot grant GPU admission.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math


class BudgetExceeded(ValueError):
    pass


def amount(value):
    if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
        raise ValueError('resource amounts must be finite nonnegative numbers')
    return float(value)


class Budget:
    def __init__(self, journal, *, cpu_s=120.0, disk_bytes=50_000_000):
        self.journal = journal
        self.cpu_s, self.disk_bytes = amount(cpu_s), amount(disk_bytes)
        with journal.tx() as db:
            db.execute('CREATE TABLE IF NOT EXISTS discovery_budget '
                       '(id TEXT PRIMARY KEY, day TEXT NOT NULL, cpu_s REAL NOT NULL, '
                       'disk_bytes REAL NOT NULL, state TEXT NOT NULL)')

    def reserve(self, identity, *, cpu_s, disk_bytes=0, money=0, vram_mb=0):
        cpu, disk, dollars, vram = map(amount, (cpu_s, disk_bytes, money, vram_mb))
        if not isinstance(identity, str) or not 1 <= len(identity) <= 100:
            raise ValueError('bounded reservation id required')
        if dollars or vram:
            raise BudgetExceeded('paid or GPU work requires existing approval/quota/GPU admission; no grant made')
        day = datetime.now(timezone.utc).date().isoformat()
        with self.journal.tx() as db:
            old = db.execute('SELECT cpu_s,disk_bytes FROM discovery_budget WHERE id=?', (identity,)).fetchone()
            if old:
                if (old[0], old[1]) != (cpu, disk):
                    raise ValueError('reservation identity reused with different resource bounds')
                return
            used = db.execute('SELECT COALESCE(SUM(cpu_s),0),COALESCE(SUM(disk_bytes),0) '
                              'FROM discovery_budget WHERE day=?', (day,)).fetchone()
            if used[0] + cpu > self.cpu_s or used[1] + disk > self.disk_bytes:
                raise BudgetExceeded('local daily resource reservation limit reached')
            db.execute('INSERT INTO discovery_budget VALUES (?,?,?,?,?)', (identity, day, cpu, disk, 'reserved'))

    def settle(self, identity, *, cpu_s=None, disk_bytes=None, uncertain=False):
        with self.journal.tx() as db:
            row = db.execute('SELECT cpu_s,disk_bytes,state FROM discovery_budget WHERE id=?', (identity,)).fetchone()
            if row is None:
                raise ValueError('unknown resource reservation')
            if row[2] != 'reserved':
                return
            if uncertain:
                db.execute("UPDATE discovery_budget SET state='uncertain' WHERE id=?", (identity,))
                return
            if cpu_s is None or disk_bytes is None:
                raise ValueError('actual resource measurements required')
            cpu, disk = amount(cpu_s), amount(disk_bytes)
            db.execute("UPDATE discovery_budget SET cpu_s=?,disk_bytes=?,state='done' WHERE id=?", (cpu, disk, identity))
