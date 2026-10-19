"""Prompt 31 safe component probes. Authored files; no account or device action."""
import hashlib
from pathlib import Path
from unittest.mock import patch


def test_JRV_31_005_executable_drop_is_data_and_never_runs(tmp_path):
    from jarvis import file_drop
    from tests.test_documents import library
    lib, actions, reports = library()
    path = tmp_path / 'inert-fixture.exe'
    path.write_bytes(b'MZ\x00inert audit bytes; never a runnable executable')
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    questions = []
    def answer(_actions, prompt, cancelled, speak=None):
        questions.append(prompt.question)
        return None  # No user data-use choice: default to nothing.
    with patch('jarvis.whatsapp.ask', answer), \
         patch('subprocess.Popen', side_effect=AssertionError('unexpected executable launch')), \
         patch('os.startfile', side_effect=AssertionError('unexpected shell launch')):
        reply = file_drop.handle(actions, [str(path)])
    assert path.name in reply and questions
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert not lib.session and not Path(actions.memory.vault).exists()
    assert not any('send' in str(event).lower() and event[0] == 'action' for event in reports)


def test_JRV_31_004_pdf_drop_uses_intended_file_after_explicit_choice(tmp_path):
    from jarvis import file_drop
    from tests.test_documents import library, make_pdf
    lib, actions, reports = library()
    path = make_pdf(tmp_path / 'intended-fixture.pdf', ['Authored PDF canary: ORCHID 2718.'])
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    def answer(_actions, prompt, cancelled, speak=None):
        prompt.resolve('ask')
        return prompt.answer
    with patch('jarvis.whatsapp.ask', answer):
        reply = file_drop.handle(actions, [str(path)])
    assert 'Ready' in reply and lib.session
    document = next(iter(lib.session.values()))
    assert Path(document.data['path']).resolve() == path.resolve()
    assert 'ORCHID' in str(document.context('ORCHID'))
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert not Path(actions.memory.vault).exists(), 'drop must not silently mutate the vault'


def test_JRV_31_011_synthetic_speech_cancel_clears_pending_generation():
    from jarvis.speech import Speech
    speech = Speech({'enabled': True, 'engine': 'f5'}, lambda *args: None)
    speech.stream('This authored fixture sentence is long enough to queue speech. More text follows.')
    speech._begin_output('synthetic active speech; no worker or playback')
    before = speech.generation
    assert speech.speaking.is_set()
    speech.cancel()
    assert speech.generation == before + 1
    assert not speech.speaking.is_set() and speech.queue.empty() and speech.streamed is None
    assert not speech.outstanding and speech.process is None


def test_JRV_31_006_exact_35_emotions_remain_available():
    from jarvis.island_buddy import EMOTIONS
    assert len(EMOTIONS) == 35
