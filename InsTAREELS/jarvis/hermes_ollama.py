"""Native Ollama provider transport for Hermes's single Jarvis proposal tool."""
import json
import time
import uuid
import sys


def completion(payload, schema, model, budget, client, chat_fn, rules):
    """Translate real local inference into the OpenAI tool-call wire envelope."""
    messages = [{"role": "system", "content": rules +
        "Return the proposal JSON matching the supplied schema. question is empty unless information is missing; never copy the goal into it. "
        "Use either steps or a clarification. For replan, done=true requires fresh evidence of the whole goal, steps=[], question='', and an evidence-based reason. "
        "Unused browser is chrome; unused content/folder/platform are empty strings. "}]
    for row in payload.get("messages", []):
        # Hermes's generic identity is replaced with Jarvis's bounded planning rules.
        # Preserve its actual user turn and tool correction history.
        if row.get("role") in {"user", "assistant", "tool"}:
            content = row.get("content") or ""
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False)
            if row.get("tool_calls"):
                content += "\nPrevious proposal: " + json.dumps(row["tool_calls"], ensure_ascii=False)
            messages.append({"role": "user" if row["role"] == "tool" else row["role"], "content": content})
    print("Hermes native inference started.", file=sys.stderr, flush=True)
    generated = chat_fn(client, {"model": model, "num_gpu": 0, "num_ctx": 64000,
        "num_predict": 1400, "temperature": .1, "think": False,
        "timeout_seconds": budget, "format_schema": schema}, messages, structured=True)
    proposal = json.loads(generated)
    print("Hermes native inference completed.", file=sys.stderr, flush=True)
    if not isinstance(proposal, dict):
        raise ValueError("Ollama returned an invalid proposal object.")
    return {"id": "jarvis-hermes-" + uuid.uuid4().hex, "object": "chat.completion",
        "created": int(time.time()), "model": model, "choices": [{"index": 0,
            "finish_reason": "tool_calls", "message": {"role": "assistant", "content": None,
                "tool_calls": [{"id": "call_" + uuid.uuid4().hex, "type": "function",
                    "function": {"name": "submit_jarvis_plan", "arguments": json.dumps(proposal)}}]}}]}


def start_provider(schema, model, budget, rules):
    """Own a loopback-only provider for the upstream synchronous/async SDK clients."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading
    from .knowledge_worker import chat, session

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 200000:
                self.send_error(400)
                return
            payload = json.loads(self.rfile.read(size))
            client = session()
            try:
                if self.path == "/api/show":
                    data = client.post("http://127.0.0.1:11434/api/show", json={"model": model}, timeout=5).json()
                elif self.path == "/v1/chat/completions":
                    data = completion(payload, schema, model, budget, client, chat, rules)
                else:
                    self.send_error(404)
                    return
                if payload.get("stream") and self.path == "/v1/chat/completions":
                    calls = [{"index": i, **call} for i, call in enumerate(data["choices"][0]["message"]["tool_calls"])]
                    chunk = {"id": data["id"], "object": "chat.completion.chunk", "created": data["created"], "model": model,
                             "choices": [{"index": 0, "delta": {"role": "assistant", "tool_calls": calls}, "finish_reason": None}]}
                    end = {**chunk, "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]}
                    body = ("data: " + json.dumps(chunk) + "\n\ndata: " + json.dumps(end) + "\n\ndata: [DONE]\n\n").encode("utf-8")
                    content_type = "text/event-stream"
                else:
                    body, content_type = json.dumps(data).encode("utf-8"), "application/json"
                self.send_response(200)
            except Exception as exc:
                body = json.dumps({"error": {"message": "Native Ollama planning failed: " + str(exc), "type": "invalid_request_error"}}).encode("utf-8")
                content_type = "application/json"
                self.send_response(400)
            finally:
                client.close()
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, "http://127.0.0.1:" + str(server.server_port) + "/v1"
