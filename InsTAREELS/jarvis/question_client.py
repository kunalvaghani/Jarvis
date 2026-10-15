"""Reusable, cancellable question-only process; no desktop actions or answer cache."""
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import uuid


def bounded_request(value):
    """Snapshot JSON data after a bounded traversal, before any worker side effect."""
    pending, nodes, characters = [(value, 0)], 0, 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        if depth > 12 or nodes > 4096:
            raise ValueError('Question request exceeds structural limits.')
        if isinstance(item, str):
            characters += len(item)
        elif isinstance(item, dict):
            if len(item) > 4096 or any(not isinstance(key, str) for key in item):
                raise ValueError('Invalid question request object.')
            pending.extend((key, depth+1) for key in item)
            pending.extend((child, depth+1) for child in item.values())
        elif isinstance(item, (list, tuple)):
            if len(item) > 4096:
                raise ValueError('Question request exceeds structural limits.')
            pending.extend((child, depth+1) for child in item)
        elif item is not None and type(item) not in (bool, int, float):
            raise ValueError('Question request must contain JSON data only.')
        if characters > 256000:
            raise ValueError('Question request exceeds context budget.')
    try:
        return json.loads(json.dumps(value, allow_nan=False))
    except (ValueError, OverflowError):
        raise ValueError('Invalid question request data.') from None


class QuestionClient:
    def __init__(self, base, report, timeout=None):
        self.base, self.report, self.timeout = Path(base), report, timeout
        self.process = self.responses = self.log = None
        self.admission = threading.Lock()
        self.last_request = None

    def snapshot(self):
        """Metadata only: prompts, model output and exception text stay out."""
        return dict(self.last_request) if self.last_request else None

    def close(self):
        process, self.process = self.process, None
        if process:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            process.stdin.close()
            process.stdout.close()
        if self.log:
            self.log.close()
            self.log = None

    def _start(self):
        if self.process is not None and self.process.poll() is None:
            return
        self.close()
        log_path = self.base / ".jarvis-runtime/logs/question-worker.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log = log_path.open("a", encoding="utf-8")
        self.process = subprocess.Popen([sys.executable, "-u", "-m", "jarvis.knowledge_worker", "--serve"],
            cwd=self.base, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
            encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        responses = self.responses = queue.Queue(maxsize=64)
        process = self.process
        def publish(value):
            while self.process is process:
                try:
                    responses.put(value, timeout=.1)
                    return True
                except queue.Full:
                    continue
            return False
        def read():
            try:
                for line in process.stdout:
                    if len(line) > 1_000_000:
                        process.kill()
                        break
                    if not publish(line):
                        break
            except (OSError, ValueError):
                pass
            finally:
                publish(None)
        threading.Thread(target=read, daemon=True).start()

    def request(self, request, cancelled):
        request = bounded_request(request)
        from .inference_limits import question_limits
        if not isinstance(request, dict) or not isinstance(request.get('question'), str):
            raise ValueError('Invalid question request.')
        options = request.get('options', {})
        if not isinstance(options, dict):
            raise ValueError('Invalid question options.')
        _, total = question_limits(options)  # Validate before spawning or sending.
        if not self.admission.acquire(blocking=False):
            deadline = time.monotonic() + total
            while not self.admission.acquire(timeout=.05):
                if cancelled():
                    raise ValueError('Question cancelled while waiting for worker.')
                if time.monotonic() >= deadline:
                    raise TimeoutError('Question worker admission timed out.')
        try:
            self.last_request = {'trace_id': uuid.uuid4().hex, 'status': 'running'}
            try:
                result = self._request(request, cancelled)
            except Exception as exc:
                self.last_request = {**self.last_request, 'status': 'cancelled' if cancelled() else 'failed',
                                     'error_type': type(exc).__name__}
                raise
            self.last_request = {**self.last_request, 'status': 'complete'}
            return result
        finally:
            self.admission.release()

    def _request(self, request, cancelled):
        import re
        # Stable across the existing worker-recovery attempt. An uncertain cloud
        # reservation is never dispatched twice after worker death.
        from .hybrid_inference import configured, standalone_public
        fresh_public = standalone_public(self.base, request)
        try:
            if configured(self.base)['enabled']:
                import uuid
                request = {**request, '_cloud_request_id': uuid.uuid4().hex}
        except (OSError, ValueError):
            pass
        style = getattr(self, "answer_style", None)
        if style:
            request = {**request, "answer_style": list(style)}  # "Keep it short", "be serious" for this session.
        memory = getattr(self, "memory", None)
        if memory is not None:
            profile = memory.profile_text()
            if profile:
                request = {**request, "user_profile": profile}
            observations = [] if fresh_public or request.get('conversation_context') or request.get('memory_retrieval_done') else memory.recall(request.get("question", ""))
            if observations:
                request = {**request, "memory_context": observations}
            situation = getattr(memory, "situation", None)
            if callable(situation) and not request.get('_natural_chat'):
                try:
                    block = situation(request.get("question", ""))
                except Exception:
                    block = ""
                if block:
                    request = {**request, "situation": block}
            curator = getattr(memory, "curator", None)
            if curator is not None and getattr(curator, "enabled", False) and not request.get('_natural_chat'):
                block = curator.context(request.get("question", ""))
                if block:
                    request = {**request, "memory_facts": block}
            if not request.get('_natural_chat') and not fresh_public and hasattr(memory, "task_context"):
                catalogue = memory.task_context(request.get("question", ""))
                if any(catalogue.get(key) for key in ("projects", "apps", "tools")):
                    request = {**request, "catalog_context": catalogue}
        if re.search(r'\b(?:my (?:pc|computer|projects?|files?|folders?)|downloads|documents|project.*(?:path|location)|where.*(?:project|folder|file))\b',request.get('question',''),re.I):
            from .pc_context import context
            try:
                request={**request,'pc_context':context(self.base,request['question'])}
            except (OSError,ValueError):
                pass
        for attempt in range(2):
            streamed = False
            if cancelled():
                raise ValueError("Question cancelled.")
            try:
                request = bounded_request(request)
                self._start()
                self.process.stdin.write(json.dumps(request) + "\n")
                self.process.stdin.flush()
                from .inference_limits import question_limits
                idle, total = question_limits(request.get('options', {}))
                # Allow startup and transport outside HTTP. Explicit test/caller overrides win.
                silence = idle + 30 if self.timeout is None else self.timeout
                started = last_activity = time.monotonic()
                streamed = False
                while True:
                    if cancelled():
                        raise ValueError("Question cancelled.")
                    now = time.monotonic()
                    if now-started >= total:
                        raise TimeoutError('Ollama reached the maximum answer duration; partial output is incomplete.')
                    if now-last_activity >= silence:
                        raise TimeoutError('Ollama stopped producing output or is still loading; partial output is incomplete.')
                    try:
                        line = self.responses.get(timeout=.1)
                    except queue.Empty:
                        continue
                    if line is None:
                        raise BrokenPipeError("Question worker stopped.")
                    if not isinstance(line, str) or len(line) > 1_000_000:
                        raise ValueError('Question worker response exceeds protocol limits.')
                    result = json.loads(line)
                    if not isinstance(result, dict):
                        raise ValueError('Invalid question worker response.')
                    if 'answer_progress' in result:
                        event = result['answer_progress']
                        if (not request.get('stream_answer') or not isinstance(event, dict)
                                or not isinstance(event.get('phase'), str) or len(event['phase']) > 100
                                or ('text' in event and (not isinstance(event['text'], str) or len(event['text']) > 100000))):
                            raise ValueError('Invalid answer stream progress.')
                        if cancelled():
                            raise ValueError('Question cancelled.')
                        last_activity = time.monotonic()
                        streamed = True
                        self.report('answer_stream', event)
                        continue
                    if result.get("error"):
                        # Model/transport exceptions may contain prompts or credentials.
                        raise ValueError('Question inference failed; no complete answer was returned.')
                    if not isinstance(result.get("answer"), str) or not result["answer"].strip() or len(result['answer']) > 100000:
                        raise ValueError("Question worker returned no answer.")
                    return result
            except Exception as exc:
                self.close()
                # Only a stopped worker permits one read-only inference retry.
                if not isinstance(exc, (BrokenPipeError, OSError)) or isinstance(exc, TimeoutError) or attempt or cancelled() or streamed:
                    raise
                from .recovery import record
                message = "Question worker stopped; retrying read-only inference after backoff."
                record(self.base, message)
                self.report("repair", message)
                deadline = time.monotonic() + .5
                while time.monotonic() < deadline:
                    if cancelled():
                        raise ValueError("Question cancelled during recovery.")
                    time.sleep(.05)
