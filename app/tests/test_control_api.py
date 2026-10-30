"""Route 1 executor: typed adapter operations, per-action approval, no retries, confined file writes."""
import hashlib

import pytest

from jarvis.control.policy import ApprovalGate, Policy
from jarvis.control.routes.api import ApiAdapter, ApiExecutor, FileAdapter, Operation, validate
from jarvis.control.types import Action, ControlError, ErrorCategory, Expectation, Risk, Route


def act(executor, name, expectation=None, **params):
    return executor.act(Action(name, name, Route.API, params=params, expectation=expectation, timeout_s=5))


@pytest.fixture
def root(tmp_path):
    folder = tmp_path / 'approved'
    folder.mkdir()
    return folder


def files(root, answers=()):
    asked = []
    answers = list(answers)

    def confirm(action):
        asked.append(action.name)
        return answers.pop(0) if answers else False
    return ApiExecutor([FileAdapter(Policy(allowed_roots=(root,)))], ApprovalGate(confirm)), asked


def test_validate_types_and_names():
    op = Operation('x', params={'path': 'str', 'count?': 'int'})
    assert validate(op, {'path': 'a'}) == {'path': 'a'}
    for bad in ({}, {'path': 1}, {'path': 'a', 'count': True}, {'path': 'a', 'other': 1}):
        with pytest.raises(ControlError) as caught:
            validate(op, bad)
        assert caught.value.category is ErrorCategory.INVALID_ARGUMENTS


def test_create_is_atomic_verified_and_never_overwrites(root):
    executor, asked = files(root)
    made = act(executor, 'files.create_text', path=str(root / 'note.txt'), text='hello\nworld')
    assert made.ok and made.verified and made.executed and made.evidence == 'sha256 read-back'
    assert (root / 'note.txt').read_bytes() == b'hello\nworld' and not asked  # Tier 1: no approval prompt.
    again = act(executor, 'files.create_text', path=str(root / 'note.txt'), text='other')
    assert again.error_category is ErrorCategory.NOT_ACTIONABLE and (root / 'note.txt').read_text() == 'hello\nworld'
    assert not [p for p in root.iterdir() if p.name.startswith('.jarvis-')]  # No temporary files left behind.


def test_replace_needs_approval_every_time_and_the_hash_it_was_read_with(root):
    note = root / 'note.txt'
    note.write_text('v1', encoding='utf-8')
    executor, asked = files(root, answers=[False, True, True])
    first = act(executor, 'files.read_text', path=str(note))
    assert first.ok and first.state['untrusted'] and first.state['text'] == 'v1'
    digest = first.state['sha256']
    denied = act(executor, 'files.replace_text', path=str(note), text='v2', expected_sha256=digest)
    assert denied.error_category is ErrorCategory.APPROVAL_DENIED and not denied.executed and note.read_text() == 'v1'
    done = act(executor, 'files.replace_text', path=str(note), text='v2', expected_sha256=digest)
    assert done.ok and done.verified and note.read_text() == 'v2'
    stale = act(executor, 'files.replace_text', path=str(note), text='v3', expected_sha256=digest)
    assert stale.error_category is ErrorCategory.STALE_REF and note.read_text() == 'v2'
    assert asked == ['files.replace_text'] * 3  # One decision per action; never cached.


def test_paths_outside_the_approved_root_are_refused(root, tmp_path):
    executor, _ = files(root)
    outside = act(executor, 'files.create_text', path=str(tmp_path / 'escape.txt'), text='x')
    assert outside.error_category is ErrorCategory.POLICY_DENIED and not (tmp_path / 'escape.txt').exists()
    dotdot = act(executor, 'files.read_text', path=str(root / '..' / 'escape.txt'))
    assert dotdot.error_category is ErrorCategory.POLICY_DENIED


def test_list_hash_probe_and_expectation(root):
    executor, _ = files(root)
    (root / 'b.txt').write_text('b')
    (root / 'A').mkdir()
    listed = act(executor, 'files.list', path=str(root))
    assert [e['name'] for e in listed.state['entries']] == ['A', 'b.txt']
    assert act(executor, 'files.sha256', path=str(root / 'b.txt')).state['sha256'] == hashlib.sha256(b'b').hexdigest()
    made = act(executor, 'files.create_text', path=str(root / 'c.txt'), text='c',
               expectation=Expectation('probe_equals', {'what': 'files.exists', 'args': {'path': str(root / 'c.txt')},
                                                        'expected': True}))
    assert made.ok and made.verified and 'read back' in made.evidence
    assert act(executor, 'files.read_text', path=str(root / 'missing.txt')).error_category is ErrorCategory.TARGET_NOT_FOUND


class Flaky(ApiAdapter):
    name = 'service'
    operations = {'get': Operation('read'), 'post': Operation('write', Risk.REVERSIBLE), 'pay': Operation('pay', Risk.CONSEQUENTIAL)}

    def __init__(self, reason=None):
        self.reason, self.calls = reason, []

    def unavailable(self):
        return self.reason

    def call(self, operation, params, action):
        self.calls.append(operation)
        raise RuntimeError('connection reset')


def test_failures_after_a_write_started_are_uncertain_and_not_retried():
    adapter = Flaky()
    executor = ApiExecutor([adapter], ApprovalGate(lambda action: True))
    read = act(executor, 'service.get')
    assert read.error_category is ErrorCategory.TOOL_ERROR and not read.executed
    write = act(executor, 'service.post')
    assert write.error_category is ErrorCategory.UNCERTAIN and write.executed
    assert adapter.calls == ['get', 'post']  # Exactly once each.


def test_unavailable_adapters_and_unknown_operations():
    executor = ApiExecutor([Flaky('connect it with Setup.cmd')])
    result = act(executor, 'service.get')
    assert result.error_category is ErrorCategory.UNSUPPORTED and 'Setup.cmd' in result.text
    assert not executor.capable('service.get') and not executor.capable('nothing.here')
    assert act(executor, 'service.delete').error_category is ErrorCategory.UNSUPPORTED
    assert 'unavailable - connect it' in executor.observe().text
    assert executor.health_check().capabilities['adapters'] == {'service': 'connect it with Setup.cmd'}


def test_consequential_operations_ask_even_when_the_caller_claims_tier_0():
    adapter = Flaky()
    executor = ApiExecutor([adapter], ApprovalGate(lambda action: action.risk < Risk.CONSEQUENTIAL))
    result = executor.act(Action('service.pay', 'pay', Route.API, risk=Risk.READ))
    assert result.error_category is ErrorCategory.APPROVAL_DENIED and adapter.calls == []


def test_contracts_describe_risk_and_schema(root):
    executor, _ = files(root)
    contracts = {c.name: c for c in executor.contracts()}
    replace = contracts['files.replace_text']
    assert replace.risk is Risk.CONSEQUENTIAL and replace.permission == 'approval'
    assert sorted(replace.input_schema['required']) == ['expected_sha256', 'path', 'text']
    assert contracts['files.read_text'].permission == 'none'
    with pytest.raises(ControlError):
        executor.register(FileAdapter(Policy(allowed_roots=(root,))))  # Duplicate name.
