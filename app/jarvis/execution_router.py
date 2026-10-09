"""Ordered preflight fallback; one external action, followed by observations only."""
import time
from contextlib import nullcontext
from .execution_adapters import PROVIDERS, Unsupported


def validate(request, control):
    operation = request['operation']
    if operation == 'fill_text':
        content = request.get('content')
        if (not isinstance(content, str) or len(content) > 10000 or '\x00' in content
                or control.get('password') or control.get('role') != 'Edit'):
            raise ValueError('Choose a non-password text field and exact text up to 10,000 characters.')
    elif operation == 'shortcut':
        from .desktop_actions import shortcut_key
        shortcut_key(request['value'])
    elif operation == 'scroll' and request.get('value') not in {'up', 'down', 'left', 'right'}:
        raise ValueError('Unsupported scroll direction.')
    elif operation not in {'activate', 'open_menu', 'scroll'}:
        raise ValueError('Unsupported execution operation.')


class UncertainAction(ValueError):
    def __init__(self, message, receipt):
        self.receipt = receipt
        super().__init__('Task paused: ' + message + ' No action was replayed; inspect fresh state before continuing.')


def execute(request, element, control, window, guard, observe=None,
            providers=None, clock=time.monotonic, sleep=time.sleep, cue=None):
    """Preparation failures may fall through; dispatch/verification failures never do.

    guard is called before each provider and immediately before dispatch. It must
    establish identity, owner, focus, enabled/visible/read-only and cancellation.
    Read-only postcondition observations are bounded to one second.
    """
    validate(request, control)
    started, attempts = clock(), []
    providers = providers if providers is not None else [provider() for provider in PROVIDERS]
    for provider in providers:
        guard()
        try:
            prepared = provider.prepare(element, control, request, window)
        except Exception as exc:
            if isinstance(exc, ValueError):
                raise  # Invalid parameters/read-only targets are not provider outages.
            attempts.append({'provider': provider.name, 'state': 'not_dispatched',
                             'error_type': type(exc).__name__, 'reason': str(exc)[:180]})
            continue
        guard()
        before = observe() if observe and not prepared.read and not prepared.no_op else None
        guard()
        receipt = {'provider': provider.name, 'operation': request['operation'],
                   'attempts': attempts, 'dispatched': not prepared.no_op, 'verified': False}
        error = None
        if not prepared.no_op:
            # Animation is preparation: re-admit the target after it, before any
            # mutation. Cue failure/focus changes cannot enter a dispatch retry.
            with cue(control) if cue else nullcontext():
                guard()
                try:
                    if prepared.call() is False:
                        error = 'The input method reported failure after dispatch.'
                except Exception as exc:
                    error = type(exc).__name__ + ': ' + str(exc)[:180]
        # Once input was entered, inspect even on exception. Never try the next provider.
        deadline = clock() + 1.0
        while True:
            try:
                if prepared.no_op:
                    receipt['verified'] = bool(prepared.read and prepared.read() == prepared.expected)
                    receipt['evidence'] = ('Requested state is still present; no input issued.' if receipt['verified']
                                           else 'Requested state changed during admission; no input issued.')
                elif prepared.read:
                    after = prepared.read()
                    receipt['verified'] = (after == prepared.expected) if prepared.expected is not None else after != prepared.before
                    receipt['evidence'] = 'Fresh native postcondition matched.' if receipt['verified'] else 'Native postcondition has not matched.'
                elif observe:
                    after = observe()
                    receipt['observed_change'] = after != before
                    receipt['evidence'] = ('Fresh accessible state changed after one dispatch; downstream application outcome is not established.'
                                           if receipt['observed_change'] else 'Input dispatched once; accessible state has not changed.')
            except Exception as exc:
                receipt['observation_error'] = type(exc).__name__
            if receipt['verified'] or prepared.no_op or receipt.get('observed_change') or clock() >= deadline:
                break
            sleep(.05)
        receipt['execution_ms'] = round((clock() - started) * 1000, 3)
        if error and not (receipt['verified'] and prepared.read):
            receipt['dispatch_error'] = error
            raise UncertainAction(error, receipt)
        if error:
            receipt['dispatch_error'] = error
            receipt['evidence'] += ' Dispatch raised, but the requested native postcondition was observed.'
        label = control.get('name') or request.get('value') or 'window'
        operation = request['operation']
        if prepared.no_op and not receipt['verified']:
            message = 'The requested state changed before dispatch; no input issued'
        elif operation == 'fill_text' and receipt['verified']:
            message = 'Filled ' + label + '; exact field value verified'
        else:
            verb = {'fill_text': 'Filled', 'activate': 'Activated', 'open_menu': 'Opened menu', 'shortcut': 'Pressed', 'scroll': 'Scrolled'}[operation]
            message = verb + ' ' + label
            if not receipt['verified']:
                message += '; input sent once, result not verified'
        return {'message': message, **receipt}
    raise ValueError('No compatible executor could prepare this action. No input issued. ' +
                     '; '.join(item['provider'] + ': ' + item['reason'] for item in attempts))
