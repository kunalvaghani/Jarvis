"""Promotion of qualified evolution candidates: proposal, approval, staged deploy, rollback.

A candidate that passed the sealed retention gate is only a *proposal*. Deploying it needs:
an explicit Dynamic Island approval card (``Actions._approve``), an unchanged evaluator seal,
a production tree still at the candidate's source commit with the surface at its approved
baseline values, a known-good release snapshot, and staged health checks (import readback,
target-domain tests, privacy/security tests). Any failed check restores the snapshot
automatically. Rollback is independent of Jarvis running:

    python -m jarvis.evolution_promotion releases
    python -m jarvis.evolution_promotion rollback <release_id>
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

from .evolution_archive import EvolutionArchive
from .evolution_surfaces import SURFACES, extract, render, verify_bounded

TOOLS = {
    'evolution_status': ('evolution', 'Read the self-evolution archive (read-only): experiments, candidate lineage, '
                         'qualified improvement proposals with held-out evidence, and deployed releases.', (), False),
    'evolution_promote': ('evolution', 'Deploy one qualified self-evolution proposal (value=candidate id) after an '
                          'explicit approval card; snapshot, staged health checks and automatic rollback. Never automatic.',
                          (), True),
    'evolution_rollback': ('evolution', 'Restore the known-good snapshot of a deployed self-evolution release '
                           '(value=release id) after explicit approval.', (), True),
}
HEALTH_DOMAINS = ('privacy_cloud',)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _normalize(data):
    return data.replace(b'\r\n', b'\n')


class PromotionError(ValueError):
    pass


class EvolutionPromotion:
    def __init__(self, base, archive=None, gate=None, python=None):
        self.base = Path(base).resolve()
        self.root = self.base / '.jarvis-runtime' / 'evolution'
        self.archive = archive or EvolutionArchive(self.root / 'archive.sqlite3')
        self.releases = self.root / 'releases'
        self.python = python or sys.executable
        self._gate = gate

    @property
    def gate(self):
        if self._gate is None:
            from .autoresearch import _gate_class
            self._gate = _gate_class()(self.base, self.base / 'evolution_eval')
        return self._gate

    # ---- proposals ---------------------------------------------------------------------------------------------------
    def proposals(self):
        return self.archive.candidates(statuses=['qualified', 'proposed'])

    def describe(self, row):
        target = (row.get('gate') or {}).get('checks', {}).get('target', {})
        domains = (row.get('gate') or {}).get('checks', {}).get('domains', [])
        spec = SURFACES[row['surface']]
        before = (row.get('mutation') or {}).get('from', {})
        changes = ', '.join(f'{k}: {before.get(k)!r} -> {v!r}' for k, v in row['values'].items() if before.get(k) != v)
        return '\n'.join([
            'Apply a tested self-improvement to Jarvis?', '',
            'Change: ' + spec['file'] + ' ' + spec['symbol'] + ' (' + changes[:300] + ')',
            'Hypothesis: ' + (row.get('hypothesis') or '')[:300],
            'Held-out result: ' + str(target.get('benchmark')) + ' relative change ' + str(target.get('relative_delta')) +
            ', 95% CI ' + str(target.get('ci95')) + ' over ' + str(target.get('examples')) + ' cases x ' +
            str(target.get('repeats')) + ' repeats',
            'Domain suites: ' + str(sum(d['passed'] for d in domains)) + '/' + str(len(domains)) + ' passed',
            'A snapshot is kept; health checks run after the change and failures restore it automatically.',
            'Takes effect after Jarvis restarts. Deny keeps the current behaviour.'])

    # ---- deploy ------------------------------------------------------------------------------------------------------
    def deploy(self, identifier, approve, cancelled=lambda: False):
        row = self.archive.get(identifier)
        if row is None or row['status'] not in {'qualified', 'proposed'}:
            raise PromotionError('Only a qualified proposal can be deployed.')
        report = row.get('gate') or {}
        if report.get('decision') != 'qualified':
            raise PromotionError('The stored gate report does not qualify this candidate.')
        if self.gate.seal() != report.get('seal'):
            raise PromotionError('The evaluator changed since this candidate was evaluated; re-evaluate first.')
        spec = SURFACES[row['surface']]
        target = self.base / spec['file']
        head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=self.base, capture_output=True, text=True, timeout=30).stdout.strip()
        if head != row['source_commit']:
            raise PromotionError('Production moved from the evaluated source commit; re-run the experiment on this release.')
        original = target.read_bytes()
        source = original.decode('utf-8')
        seeds = [r for r in self.archive.candidates(row['surface'], ['seed']) if r['source_commit'] == row['source_commit']]
        if not seeds or extract(source, row['surface']) != seeds[0]['values']:
            raise PromotionError('The production surface is not at its approved baseline values; refusing a stale patch.')
        changed = render(source, row['surface'], row['values'])
        verify_bounded(source, changed, row['surface'])
        self.archive.update(identifier, status='proposed')
        approve('evolution_promotion', self.describe(row), cancelled)  # raises unless explicitly approved
        if cancelled():
            raise PromotionError('Deployment cancelled after approval.')
        if target.read_bytes() != original:
            raise PromotionError('The target changed during approval; nothing was written.')
        release = 'rel_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '_' + uuid.uuid4().hex[:6]
        folder = self.releases / release
        folder.mkdir(parents=True)
        (folder / 'original.bin').write_bytes(original)
        deployed = changed.encode('utf-8')
        meta = {'release': release, 'candidate': identifier, 'surface': row['surface'], 'file': spec['file'],
                'known_good_commit': head, 'original_sha256': _sha(original), 'deployed_sha256': _sha(deployed),
                'values': row['values'], 'created_at': _now(), 'status': 'deploying', 'health': []}
        self._meta(folder, meta)
        self._replace(target, deployed)
        health = self.health_checks(row)
        meta['health'] = health
        if not all(check['passed'] for check in health):
            self._replace(target, original)
            meta.update(status='rolled_back_automatically', rolled_back_at=_now())
            self._meta(folder, meta)
            self.archive.update(identifier, status='deploy_failed', failure_reason='staged health check failed')
            return meta
        meta['status'] = 'deployed'
        self._meta(folder, meta)
        self.archive.update(identifier, status='deployed')
        return meta

    def health_checks(self, row):
        spec = SURFACES[row['surface']]
        module = spec['file'][:-3].replace('/', '.')
        probe = (f'import json, {module} as m; v=json.loads({json.dumps(json.dumps(row["values"]))}); '
                 f'assert m.{spec["symbol"]} == v, m.{spec["symbol"]}; print("ok")')
        run = subprocess.run([self.python, '-c', probe], cwd=self.base, capture_output=True, text=True, timeout=120)
        checks = [{'check': 'import_readback', 'passed': run.returncode == 0 and run.stdout.strip() == 'ok',
                   'detail': (run.stderr or run.stdout)[-300:]}]
        domain = spec['domain'] if spec['domain'] in self.gate.policy['domains'] else 'voice_routing'
        for name in dict.fromkeys((domain, *HEALTH_DOMAINS)):
            outcome = self.gate.domain_tests(self.base, name)
            checks.append({'check': 'domain:' + name, 'passed': outcome['passed'], 'detail': outcome['summary']})
        return checks

    # ---- rollback ----------------------------------------------------------------------------------------------------
    def list_releases(self):
        if not self.releases.is_dir():
            return []
        return [json.loads((f / 'meta.json').read_text(encoding='utf-8')) for f in sorted(self.releases.iterdir())
                if (f / 'meta.json').is_file()]

    def rollback(self, release, approve=None, cancelled=lambda: False):
        folder = self.releases / release
        if not (folder / 'meta.json').is_file() or Path(release).name != release:
            raise PromotionError('Unknown release.')
        meta = json.loads((folder / 'meta.json').read_text(encoding='utf-8'))
        if meta['status'] != 'deployed':
            raise PromotionError('Only a deployed release can be rolled back (status ' + meta['status'] + ').')
        target = self.base / meta['file']
        current = target.read_bytes()
        if _sha(current) != meta['deployed_sha256']:
            raise PromotionError('The file changed after deployment; automatic overwrite refused. Restore manually from '
                                 + str(folder / 'original.bin') + ' or git commit ' + meta['known_good_commit'])
        if approve is not None:
            approve('evolution_rollback', f"Restore {meta['file']} to its snapshot from {meta['created_at']}?", cancelled)
        original = (folder / 'original.bin').read_bytes()
        if _sha(original) != meta['original_sha256']:
            raise PromotionError('Snapshot integrity check failed.')
        self._replace(target, original)
        meta.update(status='rolled_back', rolled_back_at=_now())
        self._meta(folder, meta)
        if self.archive.get(meta['candidate']):
            self.archive.update(meta['candidate'], status='rolled_back')
        return meta

    @staticmethod
    def _replace(target, data):
        temporary = target.with_name(target.name + '.' + uuid.uuid4().hex + '.tmp')
        temporary.write_bytes(data)
        temporary.replace(target)

    @staticmethod
    def _meta(folder, meta):
        temporary = folder / 'meta.json.tmp'
        temporary.write_text(json.dumps(meta, indent=1), encoding='utf-8')
        temporary.replace(folder / 'meta.json')


def status(base):
    promotion = EvolutionPromotion(base)
    rows = promotion.archive.candidates()
    return {'archive': promotion.archive.summary(),
            'proposals': [{'id': r['id'], 'surface': r['surface'], 'values': r['values'], 'hypothesis': r['hypothesis'],
                           'heldout': (r.get('fitness') or {}).get('heldout_relative_delta'),
                           'ci95': (r.get('fitness') or {}).get('heldout_ci95')} for r in promotion.proposals()],
            'recent': [{'id': r['id'], 'surface': r['surface'], 'status': r['status'], 'parent': r['parent_id'],
                        'reason': r['failure_reason']} for r in rows[-10:]],
            'releases': [{k: m[k] for k in ('release', 'candidate', 'file', 'status', 'created_at')} for m in promotion.list_releases()]}


def execute(actions, step, cancelled):
    """ToolRegistry entry point; deploy and rollback always ask through the approval card."""
    promotion = EvolutionPromotion(actions.base)
    if step['action'] == 'evolution_status':
        return json.dumps(status(actions.base), indent=1, default=str)
    if step['action'] == 'evolution_promote':
        return json.dumps(promotion.deploy(str(step.get('value', '')).strip(), actions._approve, cancelled), indent=1)
    if step['action'] == 'evolution_rollback':
        return json.dumps(promotion.rollback(str(step.get('value', '')).strip(), actions._approve, cancelled), indent=1)
    raise ValueError('Unknown evolution tool.')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Inspect or roll back self-evolution releases without running Jarvis.')
    parser.add_argument('command', choices=['releases', 'rollback', 'status'])
    parser.add_argument('release', nargs='?')
    args = parser.parse_args(argv)
    base = Path(__file__).resolve().parents[1]
    promotion = EvolutionPromotion(base)
    if args.command == 'releases':
        print(json.dumps(promotion.list_releases(), indent=1))
    elif args.command == 'status':
        print(json.dumps(status(base), indent=1, default=str))
    else:
        if not args.release:
            parser.error('rollback needs a release id')
        print(json.dumps(promotion.rollback(args.release), indent=1))  # running this command is the explicit approval


if __name__ == '__main__':
    main()
