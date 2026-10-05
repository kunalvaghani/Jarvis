"""Bounded planning deadlines shared by HTTP inference and its owned worker."""
import math


def planning_read_timeout(options):
    value = options.get('timeout_seconds', 120)
    if isinstance(value, bool):
        raise ValueError('Inference timeout must be a finite number of seconds.')
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError('Inference timeout must be a finite number of seconds.') from None
    if not math.isfinite(value):
        raise ValueError('Inference timeout must be a finite number of seconds.')
    return min(600, max(5, value))


def planning_worker_timeout(options):
    # Allow startup, availability checks and response transport outside HTTP.
    return max(150, planning_read_timeout(options) + 30)


def question_limits(options):
    """Bound silence separately from the total time of an active answer stream."""
    idle = planning_read_timeout({'timeout_seconds': options.get('timeout_seconds', 300)})
    total = options.get('max_answer_seconds', 1800)
    if isinstance(total, bool):
        raise ValueError('Maximum answer time must be a finite number of seconds.')
    try:
        total = float(total)
    except (TypeError, ValueError):
        raise ValueError('Maximum answer time must be a finite number of seconds.') from None
    if not math.isfinite(total):
        raise ValueError('Maximum answer time must be a finite number of seconds.')
    return idle, min(3600, max(idle + 30, total))


def coding_limits(options):
    """Legacy coding timeout bounds silence; active generation has its own hard cap."""
    value = options.get('coding_timeout_seconds', 900)
    planning_read_timeout({'timeout_seconds': value})  # Shared finite-number validation.
    idle = min(900, max(5, float(value)))
    total = options.get('max_coding_seconds', 1800)
    if isinstance(total, bool):
        raise ValueError('Maximum coding time must be a finite number of seconds.')
    try:
        total = float(total)
    except (TypeError, ValueError):
        raise ValueError('Maximum coding time must be a finite number of seconds.') from None
    if not math.isfinite(total):
        raise ValueError('Maximum coding time must be a finite number of seconds.')
    return idle, min(3600, max(idle + 30, total))


def planning_limits(options):
    """Long full plans may stream for longer than a single silent HTTP budget."""
    idle = planning_read_timeout(options)
    total = options.get('max_planning_seconds', 900)
    if isinstance(total, bool):
        raise ValueError('Maximum planning time must be a finite number of seconds.')
    try:
        total = float(total)
    except (TypeError, ValueError):
        raise ValueError('Maximum planning time must be a finite number of seconds.') from None
    if not math.isfinite(total):
        raise ValueError('Maximum planning time must be a finite number of seconds.')
    return idle, min(3600, max(idle + 30, total))
