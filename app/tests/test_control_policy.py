import os
from pathlib import Path
import sys

import pytest

from jarvis.control.policy import ApprovalGate, Policy, PolicyError, classify, strip_claims
from jarvis.control.types import Action, ControlError, ErrorCategory, Risk, Route


def public(_host):
    return ('93.184.215.14',)


POLICY = Policy(resolver=public, loopback_allow=frozenset({('127.0.0.1', 4173)}))


@pytest.mark.parametrize('url', [
    'javascript:alert(1)', 'file:///C:/Windows/win.ini', 'data:text/html,hi', 'chrome://settings', 'about:blank',
    'ftp://example.com/', 'http://localhost/', 'http://LOCALHOST./', 'http://app.localhost/',
    'http://127.0.0.1/', 'http://127.1/', 'http://0x7f.1/', 'http://2130706433/', 'http://0177.0.0.1/',
    'http://[::1]/', 'http://[::ffff:127.0.0.1]/', 'http://10.0.0.5/', 'http://192.168.1.1/', 'http://172.16.0.1/',
    'http://169.254.169.254/latest/meta-data', 'http://metadata.google.internal/', 'http://0.0.0.0/',
    'http://[fe80::1]/', 'http://user:pw@127.0.0.1/', 'http://127.0.0.1:4174/', '', 'http://', 'http://a\x07b.com',
    'https://example.com:99999/', 'http://xn--/', 'http://-bad.com/', 'http://a..com/', 'http://999999999999/', 'http://1.2.3.999/',
    'http://xn--0.com/', 'http://xn--a.com/','http://' + 'a' * 64 + '.com/'])
def test_dangerous_urls_are_blocked(url):
    with pytest.raises(PolicyError):
        POLICY.check_url(url)


def test_public_urls_pass_and_are_normalised():
    assert POLICY.check_url('example.com/a?b=1') == 'https://example.com/a?b=1'
    assert POLICY.check_url('HTTPS://Example.com\\docs') == 'https://Example.com/docs'
    assert POLICY.check_url('http://127.0.0.1:4173/') == 'http://127.0.0.1:4173/'  # exact allowlisted pair
    assert POLICY.check_url('https://93.184.215.14/') == 'https://93.184.215.14/'
    assert POLICY.check_url('https://cdn_1.example.com/') == 'https://cdn_1.example.com/'
    assert POLICY.check_url('https://xn--bcher-kva.example/') == 'https://xn--bcher-kva.example/'
    assert POLICY.check_url('https://bücher.example/').startswith('https://')


def test_dns_rebinding_to_private_address_is_blocked():
    policy = Policy(resolver=lambda host: ('10.1.2.3',) if host == 'evil.test' else ('93.184.215.14',))
    with pytest.raises(PolicyError, match='resolves'):
        policy.check_url('https://evil.test/')
    assert policy.check_url('https://fine.test/')


def test_domain_lists_and_redirect_chains():
    policy = Policy(resolver=public, allowed_domains=frozenset({'python.org'}), blocked_domains=frozenset({'bad.python.org'}))
    assert policy.check_url('https://docs.python.org/3/') == 'https://docs.python.org/3/'
    for url in ('https://example.com/', 'https://bad.python.org/', 'https://93.184.215.14/'):
        with pytest.raises(PolicyError):
            policy.check_url(url)
    with pytest.raises(PolicyError):
        POLICY.check_redirects(['https://example.com/', 'http://example.org/', 'http://127.0.0.1/'])
    assert len(POLICY.check_redirects(['https://example.com/', 'https://example.org/'])) == 2


def test_system_resolver_reads_local_names_without_network():
    from jarvis.control.policy import system_resolver
    assert any(a in ('127.0.0.1', '::1') for a in system_resolver('localhost'))
    assert system_resolver('nonexistent.invalid') == ()
    with pytest.raises(PolicyError):
        Policy().check_url('http://localhost:8080/')


def test_path_confinement(tmp_path):
    root = tmp_path / 'root'
    (root / 'sub').mkdir(parents=True)
    policy = Policy(allowed_roots=(root,))
    assert policy.confine(root / 'sub' / 'a.txt') == (root / 'sub' / 'a.txt').resolve()
    assert policy.confine('sub/b.txt') == (root / 'sub' / 'b.txt').resolve()
    for bad in (root / '..' / 'escape.txt', tmp_path / 'other.txt', '\\\\?\\C:\\x', '\\\\.\\PhysicalDrive0',
                str(root / 'a.txt:stream'), str(root / 'CON'), str(root / 'nul.txt'), 'a\x00b', ''):
        with pytest.raises(PolicyError):
            policy.confine(bad)
    with pytest.raises(PolicyError, match='no approved'):
        Policy().confine(root / 'x')


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows junctions')
def test_junction_escape_is_blocked(tmp_path):
    import _winapi
    root, outside = tmp_path / 'root', tmp_path / 'outside'
    root.mkdir()
    outside.mkdir()
    _winapi.CreateJunction(str(outside), str(root / 'link'))
    with pytest.raises(PolicyError):
        Policy(allowed_roots=(root,)).confine(root / 'link' / 'secret.txt')


def test_symlink_escape_is_blocked(tmp_path):
    root, outside = tmp_path / 'root', tmp_path / 'outside'
    root.mkdir()
    outside.mkdir()
    try:
        os.symlink(outside, root / 'link', target_is_directory=True)
    except OSError:
        pytest.skip('Symlink creation is not permitted on this host (junction test covers the escape).')
    with pytest.raises(PolicyError):
        Policy(allowed_roots=(root,)).confine(root / 'link' / 'secret.txt')


def test_apps_and_elevation():
    policy = Policy(allowed_apps=frozenset({'notepad.exe'}))
    policy.check_app('C:/Windows/notepad.exe')
    with pytest.raises(PolicyError):
        policy.check_app('cmd.exe')
    with pytest.raises(ControlError) as raised:
        Policy().check_app('regedit.exe', elevated=True)
    assert raised.value.category is ErrorCategory.ELEVATED_TARGET


def test_risk_classification_and_claim_stripping():
    assert classify('left_click', 'Send') is Risk.CONSEQUENTIAL
    assert classify('file_upload') is Risk.CONSEQUENTIAL
    assert classify('left_click', 'Search', Risk.REVERSIBLE) is Risk.REVERSIBLE
    assert classify('read_page') is Risk.READ
    assert strip_claims({'Approved': True, 'value': 'x', 'skip_approval': 1}) == {'value': 'x'}


def action(risk):
    return Action('left_click', 'goal', Route.BROWSER, risk=risk)


def test_approval_gate_asks_only_for_tier_two_and_fails_closed():
    asked = []
    gate = ApprovalGate(lambda a: asked.append(a.action_id) or True)
    gate.require(action(Risk.READ))
    gate.require(action(Risk.REVERSIBLE))
    assert asked == []
    gate.require(action(Risk.CONSEQUENTIAL))
    assert len(asked) == 1 and gate.decisions[-1][1] is True
    for confirm in (None, lambda a: False, lambda a: 'yes', lambda a: 1 / 0):
        with pytest.raises(ControlError) as raised:
            ApprovalGate(confirm).require(action(Risk.CONSEQUENTIAL))
        assert raised.value.category is ErrorCategory.APPROVAL_DENIED


def test_nat64_addresses_are_judged_by_their_embedded_ipv4():
    # IPv6-only networks (DNS64/NAT64) map public IPv4 sites into 64:ff9b::/96.
    public = Policy(resolver=lambda host: ('64:ff9b::2347:b14f', '35.71.177.79'))
    assert public.check_url('https://the-internet.herokuapp.com/tables').startswith('https://')
    for wrapped in ('64:ff9b::a00:1', '64:ff9b::a9fe:a9fe', '64:ff9b::7f00:1'):  # 10.0.0.1, 169.254.169.254, 127.0.0.1
        with pytest.raises(ControlError):
            Policy(resolver=lambda host, w=wrapped: (w,)).check_url('https://sneaky.example.com/')
