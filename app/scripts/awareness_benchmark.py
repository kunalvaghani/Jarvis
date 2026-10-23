"""Repeatable Cognitive Awareness Engine benchmark (no models, no network, owned temporary state).

Measures idle/active/flood CPU, event processing and event-to-notification latency, RSS overhead and
durable task admission latency with and without the awareness worker tailing the queue. Results are
for this machine and moment; they are not a performance guarantee.

    python scripts/awareness_benchmark.py [output.json] [--seconds 20]
"""
import json
import os
import statistics
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psutil  # noqa: E402

from jarvis.awareness import AwarenessEngine  # noqa: E402
from jarvis.commands import Command  # noqa: E402
from jarvis.task_ingress import TaskIngress  # noqa: E402

SENSORS = {'system': True, 'tasks': True, 'jarvis': True, 'user_presence': True, 'foreground_app': True,
           'files': False, 'external': True}


def percentile(values, q):
    values = sorted(values)
    return round(values[min(len(values) - 1, int(q * len(values)))], 4) if values else None


def host(base, events):
    actions = SimpleNamespace(base=base, config={'task_queue': {'reserve_ram_mb': 1024}}, cognition=None, ingress=None,
                              report=lambda kind, message: events.append((time.perf_counter(), kind, message)),
                              generation=0, closed=threading.Event(), queue_lock=threading.RLock(), pending_tasks=[],
                              thread=threading.Thread())
    actions.ingress = TaskIngress(actions, base / 'queue.sqlite3', {})
    actions.ingress.scheduler.observe = lambda: {'ram_available_mb': 32000, 'cpu_percent': 0, 'desktop': True, 'battery_low': False}
    return actions


def admission(actions, count=200):
    timings = []
    for index in range(count):
        started = time.perf_counter()
        actions.ingress.submit(Command('jarvis_status', 'uptime'), idempotency_key='bench:' + str(time.time_ns()) + str(index))
        timings.append((time.perf_counter() - started) * 1000)
        with actions.ingress.store.transaction():
            identity = actions.ingress.store.rows(limit=1)[-1]['id']
            actions.ingress.store.transition(identity, 'CANCELLED', 'benchmark cleanup')
    return {'n': count, 'median_ms': round(statistics.median(timings), 4), 'p95_ms': percentile(timings, .95)}


def cpu_seconds(process):
    times = process.cpu_times()
    return times.user + times.system


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    seconds = float(sys.argv[sys.argv.index('--seconds') + 1]) if '--seconds' in sys.argv else 20.
    out = Path(args[0]) if args else Path(__file__).resolve().parents[1] / 'artifacts' / 'cognitive-awareness' / 'benchmark.json'
    process = psutil.Process(os.getpid())
    result = {'measured_at': time.strftime('%Y-%m-%d %H:%M:%S %z'), 'python': sys.version.split()[0],
              'cpu_count': psutil.cpu_count(), 'ram_total_gb': round(psutil.virtual_memory().total / 1073741824, 1),
              'seconds_per_mode': seconds, 'models_loaded_by_layer': 0, 'network_requests_by_layer': 0,
              'note': 'Owned temporary state; real psutil/GetLastInputInfo/nvidia-smi sampling; model probe replaced by a fixture.'}
    with tempfile.TemporaryDirectory() as folder:
        base = Path(folder)
        events = []
        (base / 'baseline').mkdir()
        actions = host(base / 'baseline', events)
        result['admission_without_awareness'] = admission(actions)
        actions.ingress.close(); actions.ingress.store.db.close()

        (base / 'aware').mkdir()
        events = []
        rss_before = process.memory_info().rss
        actions = host(base / 'aware', events)
        engine = AwarenessEngine(actions, {'enabled': True, 'sensors': SENSORS, 'quiet_hours': False, 'task_poll_seconds': 1,
                                           'system_sample_seconds': 5, 'gpu_sample_seconds': 30, 'predict_seconds': 10,
                                           'self_model_seconds': 300},
                                 store_path=base / 'aware' / 'awareness.sqlite3', probe_models=lambda: ['fixture-model'])
        actions.awareness = engine
        engine.start()
        time.sleep(2)

        start_cpu, start = cpu_seconds(process), time.perf_counter()
        time.sleep(seconds)
        idle_cpu = cpu_seconds(process) - start_cpu
        result['idle'] = {'process_cpu_percent_one_core': round(100 * idle_cpu / (time.perf_counter() - start), 3),
                          'engine_thread_cpu_percent': engine.cpu_percent, 'processed': engine.counters['processed']}

        result['admission_with_awareness_running'] = admission(actions)

        # Active: a working user — focus changes, queue activity and occasional failures.
        start_cpu, start = cpu_seconds(process), time.perf_counter()
        sent, index = 0, 0
        titles = ['main.py - Jarvis - Visual Studio Code', 'Chrome - docs', 'Terminal', 'Blender']
        while time.perf_counter() - start < seconds:
            engine.observe_window(titles[index % len(titles)], ['Code.exe', 'chrome.exe', 'WindowsTerminal.exe', 'blender.exe'][index % 4])
            scheduler = actions.ingress.scheduler
            scheduler.put_nowait((0, Command('task', 'step ' + str(index)), threading.Event()))
            scheduler.get(timeout=0)
            scheduler.outcome('FAILED' if index % 25 == 0 else 'COMPLETED', 'benchmark')
            scheduler.task_done()
            sent += 2
            index += 1
            time.sleep(.1)
        time.sleep(engine.intervals['tasks'] + 1)
        active_cpu = cpu_seconds(process) - start_cpu
        elapsed = time.perf_counter() - start
        latency = [1000 * v for v in engine.latency]
        result['active'] = {'events_offered': sent, 'events_per_second': round(sent / elapsed, 1),
                            'process_cpu_percent_one_core_including_generator': round(100 * active_cpu / elapsed, 3),
                            'engine_thread_cpu_percent': engine.cpu_percent, 'slowdown': engine.slowdown,
                            'processing_latency_ms_p50': percentile(latency, .5), 'processing_latency_ms_p95': percentile(latency, .95),
                            'counters': dict(engine.counters),
                            'cognitive_tasks_admitted': sum(str(r['idem']).startswith('cognitive:') for r in actions.ingress.store.rows())}

        # Event-to-decision: a fresh failure reported straight into the inbox, until the policy has acted
        # (notification, queued investigation or deliberate silence). Includes the worker wake-up.
        marks, choices = [], []
        for trial in range(5):
            before = len(engine.recent)
            started = time.perf_counter()
            engine.observe('connector.trial' + str(trial) + '.failed', 'benchmark', 'jarvis',
                           {'detail': 'trial failure', 'signature': str(trial), 'service': 'svc' + str(trial)}, sensor='jarvis')
            while time.perf_counter() < started + 5 and len(engine.recent) == before:
                time.sleep(.0005)
            marks.append((time.perf_counter() - started) * 1000)
            choices.append(engine.recent[-1]['choice'] if len(engine.recent) > before else 'timeout')
        result['event_to_decision_ms'] = {'trials': len(marks), 'median': round(statistics.median(marks), 3),
                                          'max': round(max(marks), 3), 'choices': choices}

        # Flood: low-value telemetry and important events from many threads at once.
        calls = []
        def producer(offset):
            for n in range(12500):
                t = time.perf_counter()
                engine.observe('system.bench.sample', 'bench', 'system', {'n': n}, sensor='system', low_value=True)
                if n % 25 == 0:
                    engine.observe('service.bench' + str(offset) + '.changed', 'bench', 'jarvis', {'n': n, 'signature': str(n)}, sensor='jarvis')
                calls.append((time.perf_counter() - t) * 1000)
        start_cpu, start = cpu_seconds(process), time.perf_counter()
        threads = [threading.Thread(target=producer, args=(i,)) for i in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        offered = time.perf_counter() - start
        while engine.inbox or engine.telemetry:
            time.sleep(.01)
        drained = time.perf_counter() - start
        result['flood'] = {'observe_calls': len(calls), 'observe_ms_p50': percentile(calls, .5), 'observe_ms_p99': percentile(calls, .99),
                           'offer_seconds': round(offered, 3), 'drain_seconds': round(drained, 3),
                           'process_cpu_percent_one_core': round(100 * (cpu_seconds(process) - start_cpu) / drained, 1),
                           'dropped': engine.counters['dropped'], 'coalesced': engine.counters['coalesced'],
                           'inbox_capacity': engine.capacity}
        rss_after = process.memory_info().rss
        result['rss_mb'] = {'before_engine': round(rss_before / 1048576, 2), 'after_all_modes': round(rss_after / 1048576, 2),
                            'delta': round((rss_after - rss_before) / 1048576, 2),
                            'note': 'Sampled RSS of the whole benchmark process (includes the queue), not peak memory.'}
        result['engine_snapshot'] = {k: v for k, v in engine.snapshot().items() if k in {'status', 'latency_p50_ms', 'cpu_percent', 'slowdown', 'error'}}
        result['model_calls'] = engine.counters['model_calls']
        engine.close()
        actions.ingress.close(); actions.ingress.store.db.close()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
