"""Local operational metadata; never includes speech, prompts, answers or URLs."""
import time


ANSWER_PHASES = {'Preparing answer', 'Loading model / preparing prompt', 'Generating answer',
    'Generating screen answer', 'Verifying online', 'Generating verified answer',
    'Thinking', 'Finishing answer', 'Cancelled · incomplete'}


class RuntimeHealth:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.audio_phase = 'off'
        self.answer_phase = 'idle'
        self.answer_started = None
        self.last_answer_seconds = None
        self.final_segments = 0

    def observe(self, kind, value):
        if kind == 'state' and isinstance(value, str):
            if value == 'Loading Whisper on GPU…': self.audio_phase = 'loading_model'
            elif value.startswith(('Listening for Jarvis', 'Awake')): self.audio_phase = 'listening'
        elif kind == 'backend': self.audio_phase = 'listening'
        elif kind == 'fatal': self.audio_phase = 'failed'
        elif kind == 'listener_stopped': self.audio_phase = 'off'
        elif kind == 'final': self.final_segments += 1
        elif kind == 'thinking':
            self.answer_started = self.clock()
            self.answer_phase = 'preparing'
        elif kind == 'answer_stream' and isinstance(value, dict):
            phase = value.get('phase')
            if isinstance(phase, str) and phase in ANSWER_PHASES:
                self.answer_phase = phase
                if phase == 'Cancelled · incomplete':
                    if self.answer_started is not None:
                        self.last_answer_seconds = round(self.clock()-self.answer_started, 3)
                    self.answer_started = None
                elif self.answer_started is None:
                    self.answer_started = self.clock()
        elif kind in {'answer', 'answer_error'}:
            if self.answer_started is not None:
                self.last_answer_seconds = round(self.clock() - self.answer_started, 3)
            self.answer_started = None
            self.answer_phase = 'completed' if kind == 'answer' else 'failed'

    def snapshot(self, app):
        listener = getattr(app, 'listener', None)
        alive = lambda worker: bool(worker and getattr(worker, 'thread', None) and worker.thread.is_alive())
        last_audio = getattr(listener, 'last_audio', None)
        result={'audio': {'requested': bool(app.listening_requested), 'phase': self.audio_phase,
                    'capture_alive': alive(listener),
                    'decoder_alive': bool(listener and getattr(listener, 'decoder', None) and listener.decoder.is_alive()),
                    'last_block_age_seconds': round(max(0, self.clock()-last_audio), 3) if last_audio is not None else None,
                    'final_segments': self.final_segments},
                'answer': {'phase': self.answer_phase,
                    'active_seconds': round(self.clock()-self.answer_started, 3) if self.answer_started is not None else None,
                    'last_duration_seconds': self.last_answer_seconds},
                'workers': {name: alive(worker) for name, worker in
                    [('actions', app.actions), ('questions', app.actions.knowledge), ('speech', app.speech)]}}
        config=getattr(app,'config',{})
        if isinstance(config,dict) and config.get('gpu_scheduler',{}).get('enabled'):
            from .gpu_scheduler import status
            result['gpu']=status()
        return result
