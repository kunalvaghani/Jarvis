"""Island cards for browser/PC control: every route and phase renders and animates; progress maps to outcomes."""
from types import SimpleNamespace

import pytest

from jarvis import island_control as control
from jarvis.control.progress import ProgressEvent, Reporting, emit, label, outcome
from jarvis.control.types import Action, ActionResult, ErrorCategory, Route
from jarvis.island import MEDIA_HEIGHT, animate_frame, render_island
from jarvis.media_player import card


@pytest.mark.parametrize('service', sorted(control.SERVICES))
@pytest.mark.parametrize('phase', sorted(control.PHASES))
def test_every_route_and_phase_renders_and_the_tile_moves(service, phase):
    media = card(service, phase, 'Clicking "Search"', 'Browser · example.com', '', 0, 0, '')
    media.update(step=2, steps=4)
    base = render_island(560, MEDIA_HEIGHT, 'WORKING', 0, '', 0, False, '', 1, media)
    first = animate_frame(base, 560, MEDIA_HEIGHT, 'WORKING', 0.3, 0, 1, media)
    second = animate_frame(base, 560, MEDIA_HEIGHT, 'WORKING', 1.1, 0, 1, media)
    assert first.size == base.size
    tile = (54, 54, 108, 108)
    if phase in control.WORKING:
        assert first.crop(tile).tobytes() != second.crop(tile).tobytes()  # Live motion while working.
    header = animate_frame(render_island(614, 44, 'WORKING', 0, '', 0, False, 'Working', 1), 614, 44, 'WORKING',
                           0.5, 0, 1, live=media)
    assert header.size[1] == 44


def test_step_text_and_fraction():
    media = {'service': 'browser', 'phase': 'acting', 'step': 3, 'steps': 4}
    assert control.step_text(media) == 'Step 3 of 4' and control.fraction(media) == 0.5
    assert control.fraction({**media, 'phase': 'done'}) == 0.75
    assert control.fraction({'service': 'browser', 'phase': 'acting'}) is None and control.step_text({'step': 2}) == 'Step 2'


def test_island_progress_sends_deduplicated_cards():
    sent = []
    sink = control.IslandProgress(SimpleNamespace(report=lambda kind, value: sent.append((kind, value))))
    event = ProgressEvent(Route.UIA, 'acting', 'Clicking "Seven"', 'Windows apps · Calculator', '', 1, 3)
    sink(event)
    sink(event)
    sink(ProgressEvent(Route.UIA, 'done', 'Clicking "Seven"', '', 'Checked', 1, 3))
    assert [v['phase'] for _, v in sent] == ['acting', 'done'] and all(k == 'media_card' for k, _ in sent)
    assert sent[0][1]['service'] == 'desktop' and sent[1][1]['subtitle'] == 'Windows apps' and sent[0][1]['steps'] == 3


def test_outcomes_labels_and_a_broken_sink():
    action = Action('left_click', 'click', Route.BROWSER, params={'target': 'Search'})
    assert label(action) == 'Clicking "Search"'
    done = ActionResult(action.action_id, True, Route.BROWSER)
    refused = ActionResult(action.action_id, False, Route.BROWSER, error_category=ErrorCategory.TARGET_NOT_FOUND)
    blocked = ActionResult(action.action_id, False, Route.BROWSER, error_category=ErrorCategory.ELEVATED_TARGET)
    uncertain = ActionResult(action.action_id, False, Route.BROWSER, executed=True, error_category=ErrorCategory.UNCERTAIN)
    assert [outcome(r) for r in (done, refused, blocked, uncertain)] == ['done', 'refused', 'blocked', 'failed']
    emit(lambda event: 1 / 0, ProgressEvent(Route.API, 'acting', 'x'))  # Display failures never surface.


def test_reporting_wrapper_streams_act_and_keeps_the_result():
    events = []

    class Inner:
        route = Route.API

        def act(self, action):
            return ActionResult(action.action_id, True, Route.API, verified=True, evidence='sha256 read-back')

    wrapped = Reporting(Inner(), events.append, 'Apps & files')
    wrapped.plan(2)
    result = wrapped.act(Action('files.create_text', 'create', Route.API, params={'target': 'note.txt'}))
    assert result.ok and [(e.phase, e.step, e.steps) for e in events] == [('acting', 1, 2), ('done', 1, 2)]
    assert events[-1].detail.startswith('Checked: sha256')
