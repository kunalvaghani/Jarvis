"""Independent, cancellable question worker; never dispatches desktop actions."""
import json
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
from .question_client import QuestionClient
from .quick_answers import QuickAnswers


SCREEN_QUERY = re.compile(
    r"\b(?:screen|screenshot|this page|this window|what(?:'s| is) this|what do you see|"
    r"what am i looking at|on display|yahan|yeh kya|screen pe|screen par|"
    r"(?:this|that) (?:error|message|image|picture|button|app|website|page))\b|"
    r"(?:स्क्रीन|यहाँ|यह क्या|ये क्या|इस पेज|इस विंडो)", re.I)


def wants_screen(question):
    return bool(SCREEN_QUERY.search(question))


class Knowledge:
    def __init__(self, options, report):
        self.options, self.report = options, report
        self.queue = queue.Queue(maxsize=4)
        self.generation = 0
        self.history = []
        self.context_seed = []
        self.context_lock = threading.RLock()
        self.conversations = None
        self.session_id = None
        self.pending_memory = None
        self.context_budget = 24000
        self.memory_choice_seconds = 300
        self.memory_error_after = 0
        self.context_selector = None
        self.context_jobs = {}
        self.closed = threading.Event()
        self.screen_handle = lambda: 0
        self.client = QuestionClient(Path(__file__).resolve().parent.parent, report)
        self.quick = QuickAnswers()
        self.on_request = None
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def cancel(self):
        with self.context_lock:
            self.generation += 1
            pending, self.pending_memory = self.pending_memory, None
            if pending:
                self._saved('finish', pending['turn'], status='cancelled')

    def forget(self):
        self.cancel()
        with self.context_lock:
            self.history = []
            self.context_seed = []
            self.session_id = self._saved('start_session')

    def attach_conversations(self, path, options=None):
        from .conversation_memory import ConversationMemory
        options = options or {}
        self.context_budget = int(options.get('context_characters', 24000))
        self.memory_choice_seconds = int(options.get('choice_seconds', 300))
        if not options.get('enabled', False):
            return
        try:
            self.conversations = ConversationMemory(Path(path))
            self.session_id = self.conversations.start_session()
        except Exception as exc:
            self.conversations = None
            self.report('repair', 'Conversation storage unavailable; session context remains in RAM: '+type(exc).__name__)

    def attach_selector(self, options):
        from .context_selector import ContextSelector
        self.context_selector = ContextSelector(options, self.report)

    def _context(self, question, history, session, choose=None, cancelled=lambda: False, app_context=None):
        from .conversation_memory import current_context, messages, FOLLOWUP
        context, found = current_context(history, question, self.context_budget)
        if found:
            return {'history': context, 'source': 'current_session', 'matches': []}
        current=(app_context or {}).get('current') or {}
        app_followup=bool(current.get('status')=='open' and FOLLOWUP.search(question))
        lookup=question+' '+current.get('title','') if app_followup else question
        matches = self._saved('matches', lookup, session) or []
        if not matches and getattr(self, 'memory', None) is not None:
            from .conversation_memory import terms
            import hashlib
            keywords = terms(lookup)
            for row in self.memory.recall(lookup):
                observation = row.get('observation', '')
                if re.search(r'\| Jarvis (?:question|request):', observation):
                    continue  # The legacy submit log is not an answer or prior context.
                matched = keywords & terms(observation)
                if not matched:
                    continue
                identity = 'legacy-'+hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest()[:16]
                matches.append({'id':identity,'session':identity,'created':row.get('date_utc','Historical note'),
                    'question':row.get('source','Recorded observation'), 'answer':observation,
                    'score':len(matched),'keywords':sorted(matched),'legacy':True})
            matches = matches[:8]
        if cancelled():
            return None
        selected = matches[0] if len(matches) == 1 else None
        scores = sorted((row['score'] for row in matches), reverse=True)
        if len(matches) > 1 and choose and scores[0] >= 2 and scores[0] > scores[1]:
            goal = {'request':question,'active_app':{'title':current.get('title',''),'status':'open'}} if app_followup else question
            identity = choose(goal, matches, cancelled)
            proposed = next((row for row in matches if row['id'] == identity), None)
            if proposed and proposed['score'] >= 2 and all(
                    proposed['score'] > row['score'] for row in matches if row is not proposed):
                selected = proposed
        if selected:
            return {'history': self._memory_history(selected),
                    'source': 'saved_memory', 'matches': [], 'selected_id': selected['id']}
        return {'history': [], 'source': 'none', 'matches': matches}

    def _memory_history(self, selected):
        from .conversation_memory import messages
        if selected.get('legacy'):
            return messages([selected], self.context_budget)
        rows = self._saved('turns', selected['session']) or []
        anchor = next((i for i,row in enumerate(rows) if row['id']==selected['id']), 0)
        return messages(rows[max(0,anchor-3):anchor+4], self.context_budget)

    def prepare_context(self, question):
        if self.context_selector is None or not self.context_selector.options['enabled']:
            return None
        with self.context_lock:
            provider=getattr(self,'app_snapshot_provider',None)
            app_context=provider() if provider else None
            current=(app_context or {}).get('current') or {}
            app_revision=tuple(current.get(key) for key in ('handle','pid','process_started','title','status'))
            revision = (self.session_id, len(self.history), self.generation, app_revision)
            entry = self.context_jobs.get(question)
            if entry and entry['revision'] == revision:
                return entry['future']
            history = list(self.context_seed+self.history)
            session, generation = self.session_id, self.generation
            future = self.context_selector.prepare(lambda choose, stopped:
                self._context(question, history, session, choose, stopped, app_context),
                lambda: self.closed.is_set() or generation != self.generation)
            self.context_jobs[question] = {'revision': revision, 'future': future}
            while len(self.context_jobs) > 8:
                self.context_jobs.pop(next(iter(self.context_jobs)))
            return future

    def planning_context(self, goal):
        """Planner never waits for a selector; consume only already-ready output."""
        future = self.prepare_context(goal)
        if not future or not future.done():
            return None
        result = future.result()
        if not result:
            return None
        if result['matches']:
            return {'status': 'ambiguous', 'note': 'Multiple historical sessions match. Do not infer targets or replay actions; ask if needed.',
                    'options': [{'question': row['question'][:200], 'keywords': row['keywords']} for row in result['matches']]}
        return {'status': 'selected', 'source': result['source'], 'messages': result['history']} if result['history'] else None

    def _saved(self, operation, *args, **kwargs):
        if self.conversations is None:
            return None
        try:
            return getattr(self.conversations, operation)(*args, **kwargs)
        except Exception as exc:
            if time.monotonic() >= self.memory_error_after:
                self.memory_error_after = time.monotonic()+30
                self.report('repair', 'Conversation storage needs review; RAM context retained: '+type(exc).__name__)
            return None

    def record_pair(self, question, answer, turn=None):
        with self.context_lock:
            turn = turn or self._saved('begin', self.session_id, question)
            if turn:
                self._saved('finish', turn, answer)
            self.history.extend([{'role': 'user', 'content': question}, {'role': 'assistant', 'content': answer}])

    def choice_snapshot(self):
        with self.context_lock:
            pending = self.pending_memory
            if not pending or pending['generation'] != self.generation:
                return None
            if time.monotonic() > pending['expires']:
                self.pending_memory = None
                self._saved('finish', pending['turn'], status='expired')
                return None
            return {key: pending[key] for key in ('token', 'kind', 'expires', 'question', 'options')}

    def choose_memory(self, token, index):
        with self.context_lock:
            card = self.choice_snapshot()
            if not card or token != card['token'] or not 0 <= index < len(card['options']):
                raise ValueError('Those memory choices changed or expired. Repeat your question.')
            pending = self.pending_memory
            selected = pending['matches'][index]
            history = self._memory_history(selected)
            if not history:
                raise ValueError('That saved conversation is unavailable. Choose again or repeat your question.')
            job = pending['job'] + (history,)
            try:
                self.queue.put_nowait(job)
            except queue.Full:
                raise ValueError('Question queue is busy; your memory choices are still available.')
            self.pending_memory = None  # A repeated click cannot generate a second answer.
            self.report('question', '')
            self.report('memory_selected', card['options'][index]['label'])

    def memory_reply(self, command):
        from .clarification import choice_index, short_reply
        card = self.choice_snapshot()
        if not card or command.kind not in {'ask', 'task', 'choose_control', 'select_context', 'click_control'}:
            return False
        index = choice_index(command.value, [row['label'] for row in card['options']])
        if command.kind == 'select_context' and command.value.endswith(':option'):
            number = command.value.split(':')[0]
            index = int(number)-1 if number.isdigit() else None
        if index is None:
            if short_reply(command) and command.kind in {'choose_control', 'select_context'}:
                self.report('question', 'Choose a listed memory name or option number.')
                return True
            return False
        self.choose_memory(card['token'], index)
        return True

    def close(self):
        self.cancel()
        self.closed.set()
        if self.context_selector:
            self.context_selector.close()
        if self.thread.is_alive():
            self.thread.join(timeout=3)
        if not self.thread.is_alive():
            self.client.close()

    def submit(self, question, web=False, screen=False):
        if self.on_request is not None:
            self.on_request('ask', question)
        try:
            memory = getattr(self, "memory", None)
            if memory is not None:
                memory.record("Jarvis question", question)
            handle = self.screen_handle() if screen or wants_screen(question) else 0
            with self.context_lock:
                pending, self.pending_memory = self.pending_memory, None
                if pending:
                    self._saved('finish', pending['turn'], status='superseded')
                turn = self._saved('begin', self.session_id, question)
            self.prepare_context(question)
            self.queue.put_nowait((self.generation, question, web, bool(screen or wants_screen(question)), handle, turn))
        except queue.Full:
            if turn:
                self._saved('finish', turn, status='rejected')
            self.report("warning", "Question queue full. Wait for an answer or press Stop all tasks.")

    def _run(self):
        while not self.closed.is_set():
            try:
                job = self.queue.get(timeout=.2)
                generation, question, web, use_screen, handle, turn = job[:6]
            except queue.Empty:
                continue
            process = None
            direct = None
            capture_hidden = False
            completed = False
            cancelled = lambda: self.closed.is_set() or generation != self.generation
            try:
                if cancelled():
                    continue
                future = self.prepare_context(question)
                prepared = None
                if future and len(job) <= 6:
                    try:
                        prepared = future.result(timeout=3)
                    except TimeoutError:
                        pass
                    if cancelled():
                        continue
                with self.context_lock:
                    selected = job[6] if len(job) > 6 else None
                    app_provider=getattr(self,'app_snapshot_provider',None)
                    resolved = prepared or self._context(question, self.context_seed+self.history, self.session_id,
                        app_context=app_provider() if app_provider else None)
                    context = resolved['history']
                    current_found = resolved['source'] == 'current_session'
                    if selected is not None:
                        context, current_found = selected, False
                        self.context_seed = selected
                    elif not current_found and not use_screen:
                        matches = resolved['matches']
                        if len(matches) > 1:
                            import uuid
                            options = [{'label': row['created'][:16].replace('T',' ')+' UTC · '+row['question'][:100],
                                        'context': 'Matched: '+', '.join(row['keywords'])+'\nQ: '+row['question'][:200]+
                                            '\nA: '+row['answer'][:260], 'image': ''} for row in matches]
                            self.pending_memory = {'token': uuid.uuid4().hex, 'kind': 'memory',
                                'generation': generation, 'expires': time.monotonic()+self.memory_choice_seconds,
                                'question': 'Which saved conversation should I use for: '+question.rstrip(' ?')+'?',
                                'options': options, 'matches': matches, 'job': job[:6], 'turn': turn}
                            self.report('question', self.pending_memory['question'])
                            continue
                        if context:
                            self.context_seed = context
                realtime = getattr(self, 'realtime', None)
                realtime_context = realtime.context(question, cancelled) if realtime and not use_screen else None
                direct = None if web or use_screen or realtime_context else self.quick.answer(question)
                if context:
                    direct = None  # A follow-up must use its chosen conversation context.
                if direct is not None:
                    result = {"answer": direct}
                else:
                    self.report("thinking", f"Thinking locally: {question}")
                    if self.options.get('stream', True):
                        self.report('answer_stream', {'phase': 'Preparing answer', 'text': ''})
                screen = None
                if use_screen:
                    self.report("screen_capture", "")
                    capture_hidden = True
                    time.sleep(.3)  # Let the overlay disappear before taking the screenshot.
                    if cancelled():
                        continue
                    process = subprocess.Popen([sys.executable, "-m", "jarvis.screen_worker"],
                        cwd=Path(__file__).resolve().parent.parent, stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8",
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    import os
                    payload = json.dumps({"handle": handle, "owner_pid": os.getpid()})
                    deadline = time.monotonic() + 20
                    first = True
                    while True:
                        if cancelled():
                            break
                        if time.monotonic() >= deadline:
                            raise TimeoutError("Screen capture timed out.")
                        try:
                            output, error = process.communicate(input=payload if first else None, timeout=.2)
                            break
                        except subprocess.TimeoutExpired:
                            first = False
                    if cancelled():
                        continue
                    if process.returncode:
                        raise RuntimeError(error[-500:] or "Screen capture failed.")
                    screen = json.loads(output)
                    if screen.get("error"):
                        raise ValueError(screen["error"])
                    self.report("screen_capture_done", "")
                    capture_hidden = False
                    self.report("screen", f"Reading visible window: {screen['title']}")
                if direct is None:
                    app_context=None
                    app_provider=getattr(self,'live_app_provider',None)
                    if app_provider and re.search(r'\b(app|window|buttons?|controls?|opened|closed|it|that|this)\b',question,re.I):
                        app_context=app_provider(cancelled)
                    result = self.client.request({"question": question, "web": web, "options": self.options,
                                                  "realtime_context": realtime_context,
                                                  "live_app_context": app_context,
                                                  "history": context, "screen": screen,
                                                  "conversation_context": bool(context),
                                                  "memory_retrieval_done": True,
                                                  "context_source": 'current_session' if current_found else 'selected_memory' if context else 'none',
                                                  "stream_answer": self.options.get('stream', True)}, cancelled)
                if cancelled():
                    continue
                answer = result["answer"]
                if cancelled():
                    continue
                with self.context_lock:
                    if cancelled():
                        continue
                    self.record_pair(question, answer, turn)
                    self.report("answer", answer)
                    completed = True
            except Exception as exc:
                if not cancelled():
                    if turn:
                        self._saved('finish', turn, status='failed')
                    self.report("answer_error", f"Could not finish answer: {exc}")
            finally:
                if cancelled() and turn and not completed:
                    self._saved('finish', turn, status='cancelled')
                if cancelled() and direct is None:
                    self.report('answer_stream', {'phase': 'Cancelled · incomplete', 'active': False})
                if capture_hidden:
                    self.report("screen_capture_done", "")
                if process and process.poll() is None:
                    process.kill()
                    process.communicate()
                self.queue.task_done()
        self.client.close()
