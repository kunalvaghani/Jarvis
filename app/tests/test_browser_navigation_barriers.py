"""Security challenges must never become verified source-navigation evidence."""
from unittest.mock import Mock
import pytest
from jarvis.control.policy import Policy
from jarvis.control.types import Action, ErrorCategory, Route
from jarvis.control.web.agent_browser_backend import AgentBrowserExecutor, navigation_barrier


@pytest.mark.parametrize('url', [
    'https://www.google.com/sorry/index?continue=search',
    'https://google.co.in/sorry/',
    'https://challenges.cloudflare.com/turnstile/',
    'https://example.org/cdn-cgi/challenge-platform/foo',
])
def test_interstitial_is_barrier(url):
    assert navigation_barrier(url)


@pytest.mark.parametrize('url', [
    'https://www.google.com/search?q=captcha',
    'https://example.org/articles/how-captcha-works',
    'https://www.google.com.example.org/sorry/index',
    'https://example.org/sorry/',
])
def test_ordinary_content_and_lookalikes_unaffected(url):
    assert not navigation_barrier(url)


def test_navigation_to_challenge_is_failed_not_verified_and_no_interaction():
    run=Mock();run.profile='owned-test';run.auto_connect=False
    executor=AgentBrowserExecutor(Policy(),run)
    executor._own_tab=Mock(return_value=False)
    executor._call=Mock()
    executor._final_url=Mock(return_value='https://www.google.com/sorry/index')
    executor._visible_tabs=Mock(return_value=[])
    result=executor.act(Action('navigate','test',Route.BROWSER,params={'url':'https://www.google.com/search?q=mechanism'}))
    assert not result.ok
    assert not result.verified
    assert result.executed
    assert result.error_category==ErrorCategory.VERIFICATION_FAILED
    assert [call.args[0][0] for call in executor._call.call_args_list]==['open']
