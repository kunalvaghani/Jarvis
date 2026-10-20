"""Regression tests for spoken commands that were routed to chat or to the wrong browser (2026-10-20).

The failing phrases come from the user's own conversation log: filler lead-ins ("so I will", "shall we"),
"Jarvis" misheard as "there is", third-person verbs ("opens"), and corrections ("it's obviously X on Spotify").
Nothing here launches a browser, Spotify or PowerShell.
"""
from unittest.mock import patch

import pytest

from jarvis.actions import Actions
from jarvis.commands import Command
from jarvis.conversation_intent import quick_kind
from jarvis.engine import Engine


def parse(text):
    emitted = []
    engine = Engine(emitted.append, lambda *args: None)
    engine.activate()
    engine.feed(text, final=True)
    return emitted


@pytest.mark.parametrize('text,expected', [
    ('so i will select the second video', Command('select_context', '2:video', 'select')),
    ('shall we select the second video', Command('select_context', '2:video', 'select')),
    ('can you click the first video', Command('select_context', '1:video', 'select')),
    ('there is play finding her on spotify', Command('play_media', 'finding her', 'spotify')),
    ("there's play finding her on spotify", Command('play_media', 'finding her', 'spotify')),
    ("it's obviously finding her on spotify", Command('play_media', 'finding her', 'spotify')),
    ('i said finding her on spotify', Command('play_media', 'finding her', 'spotify')),
    ('opens spotify and play adhd', Command('play_media', 'adhd', 'spotify')),
    ('okay so play despacito on youtube', Command('play_media', 'despacito', 'youtube')),
])
def test_spoken_variations_reach_the_action_not_chat(text, expected):
    assert parse(text) == [expected]


@pytest.mark.parametrize('text', [
    'there is a problem with my code', 'so i will be late today', "it's obviously raining", "i'll be back soon",
    "it's a nice song on spotify", 'next week i have exams', 'i will call you later', "there's nothing to do",
    'thank you very much', 'okay cool', 'just kidding',
])
def test_statements_are_never_promoted_to_actions(text):
    commands = parse(text)
    assert all(command.kind in {'task', 'ask'} for command in commands), commands
    assert quick_kind(text) != 'task'


@pytest.mark.parametrize('spoken,site', [('youtube', 'youtube'), ('google', 'google'), ('gmail', 'gmail'),
                                         ('github', 'github'), ('google drive', 'drive.google.com'),
                                         ('chatgpt', 'chatgpt')])
def test_open_website_uses_chrome_not_the_windows_default_browser(spoken, site):
    routed = []
    real = Actions._execute

    def intercept(self, command, cancelled=lambda: False):
        if command.kind == 'browse':
            routed.append(command)
            return 'opened'
        return real(self, command, cancelled)

    actions = Actions.__new__(Actions)
    actions.apps = {}
    with patch.object(Actions, '_execute', intercept), \
            patch('jarvis.windows_commands.execute', side_effect=AssertionError('default-browser launch')):
        assert actions._execute(Command('open', spoken)) == 'opened'
    assert routed == [Command('browse', site, 'chrome')]
