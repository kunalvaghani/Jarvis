"""Best-effort UI metadata; display failures must never replay or stop an action."""
def status(report, phase, target='', active=True, **metadata):
    try:
        report('task_status', {'phase': str(phase)[:80], 'target': str(target)[:400], 'active': bool(active),
                              **{k: v for k,v in metadata.items() if k in {'preview','characters','outcome','file'}}})
    except Exception:
        pass
