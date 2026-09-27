"""SuperAGI-inspired toolkit adapters for Jarvis's existing bounded runtime.

Independent implementation; upstream reference/license in integrations/superagi-*.
Tool content and HTTP responses are untrusted data, never executable instructions.
"""
import base64
from email.message import EmailMessage
from html.parser import HTMLParser
import imaplib
import ipaddress
import json
import os
from pathlib import Path
import re
import smtplib
import socket
import ssl
import tempfile
from urllib.parse import quote, urlsplit

import requests
from .agent_tools import TOOLS as AGENT_TOOLS

# name: (toolkit, description, required environment variables, external write)
TOOLS = {
    "think": ("thinking", "Explain a problem using the existing local model; value task, content untrusted context.", (), False),
    "write_spec": ("coding", "Draft a software specification with the existing local model; value goal.", (), False),
    "write_tests": ("coding", "Draft tests for supplied source; value goal, content source. Returns text without execution.", (), False),
    "write_code": ("coding", "Draft code with the existing local model; value goal, content optional context. Use coding tasks to save validated files.", (), False),
    "improve_code": ("coding", "Propose source improvements; value goal, content source. Does not write or execute files.", (), False),
    "review_pull_request": ("github", "Review a public PR with the existing local model; value owner/repo, content JSON {number}.", (), False),
    "knowledge_search": ("knowledge", "Search local UTF-8 knowledge resources; value literal query, folder scope.", (), False),
    "list_files": ("files", "List up to 100 files in folder; value is '.', folder identifies scope.", (), False),
    "read_file": ("files", "Read a small UTF-8 file; value is relative path, folder identifies scope.", (), False),
    "append_file": ("files", "Append exact content to an existing UTF-8 file; value path and folder required.", (), False),
    "search_files": ("files", "Search filenames and text in folder; value is literal query.", (), False),
    "query_resource": ("resource", "Find literal content matches in scoped text resources; value query, folder scope.", (), False),
    "web_search": ("duckduckgo", "Return public web search snippets for value query.", (), False),
    "scrape_web": ("webscraper", "Extract public page text without JavaScript or navigation clutter; value URL, optional content JSON {query} selects a literal excerpt.", (), False),
    "github_search": ("github", "Search public GitHub repositories with value query.", (), False),
    "github_read_file": ("github", "Read repository file and current SHA; value owner/repo, content JSON {path,ref}. Result includes text and metadata for later approved updates/deletion.", (), False),
    "github_pull_request": ("github", "Read PR details; value owner/repo, content JSON {number}.", (), False),
    "github_pr_files": ("github", "Read PR file patches; value owner/repo, content JSON {number}.", (), False),
    "github_add_file": ("github", "Create/update repository UTF-8 file after approval; content JSON {path,message,text,branch,sha optional}.", ("JARVIS_GITHUB_TOKEN",), True),
    "github_delete_file": ("github", "Delete repository file after approval; content JSON {path,message,sha,branch}.", ("JARVIS_GITHUB_TOKEN",), True),
    "google_search": ("google_search", "Search via Google Custom Search; value query.", ("JARVIS_GOOGLE_SEARCH_KEY", "JARVIS_GOOGLE_SEARCH_CX"), False),
    "serp_search": ("serp", "Search via SerpAPI; value query.", ("JARVIS_SERPAPI_KEY",), False),
    "searx_search": ("searx", "Search a configured SearX public endpoint; value query.", ("JARVIS_SEARX_URL",), False),
    "apollo_search": ("apollo", "Search Apollo organizations; value company query.", ("JARVIS_APOLLO_KEY",), False),
    "read_email": ("email", "Read latest five INBOX subject/from headers via IMAP; no messages marked read.", ("JARVIS_IMAP_HOST", "JARVIS_EMAIL_USER", "JARVIS_EMAIL_PASSWORD"), False),
    "send_email": ("email", "Send exact email after approval; value recipient, content JSON {subject,body}.", ("JARVIS_SMTP_HOST", "JARVIS_EMAIL_USER", "JARVIS_EMAIL_PASSWORD"), True),
    "slack_send": ("slack", "Send exact Slack message after approval; value channel, content exact text.", ("JARVIS_SLACK_TOKEN",), True),
    "twitter_send": ("twitter", "Publish exact tweet after approval; content exact text. Requires user-context OAuth token.", ("JARVIS_TWITTER_TOKEN",), True),
    "calendar_list": ("calendar", "List next calendar events; value calendar ID or primary.", ("JARVIS_GOOGLE_ACCESS_TOKEN",), False),
    "calendar_details": ("calendar", "Read calendar event; value calendar ID, content JSON {event_id}.", ("JARVIS_GOOGLE_ACCESS_TOKEN",), False),
    "calendar_create": ("calendar", "Create event after approval; value calendar ID, content JSON {summary,start,end,description optional}.", ("JARVIS_GOOGLE_ACCESS_TOKEN",), True),
    "calendar_delete": ("calendar", "Delete event after approval; value calendar ID, content JSON {event_id}.", ("JARVIS_GOOGLE_ACCESS_TOKEN",), True),
    "jira_projects": ("jira", "List Jira projects.", ("JARVIS_JIRA_URL", "JARVIS_JIRA_USER", "JARVIS_JIRA_TOKEN"), False),
    "jira_search": ("jira", "Search Jira issues; value JQL.", ("JARVIS_JIRA_URL", "JARVIS_JIRA_USER", "JARVIS_JIRA_TOKEN"), False),
    "jira_create": ("jira", "Create Jira issue after approval; content JSON {fields}.", ("JARVIS_JIRA_URL", "JARVIS_JIRA_USER", "JARVIS_JIRA_TOKEN"), True),
    "jira_edit": ("jira", "Edit Jira issue after approval; value issue key, content JSON {fields}.", ("JARVIS_JIRA_URL", "JARVIS_JIRA_USER", "JARVIS_JIRA_TOKEN"), True),
    "toolkit_status": ("toolkits", "List tools and missing configuration; never displays credentials.", (), False),
}
TOOLS.update(AGENT_TOOLS)


def status():
    return [{"tool": name, "toolkit": data[0], "configured": all(os.environ.get(key) for key in data[2]),
             "required_environment": list(data[2]), "approval": "user" if data[3] else "none"}
            for name, data in TOOLS.items()]


def available(name):
    """Expose every configured operation; the planner chooses by task meaning."""
    return all(os.environ.get(key) for key in TOOLS[name][2])


def arguments(step):
    content = step.get("content", "")
    if not content:
        return {}
    try:
        value = json.loads(content)
    except ValueError as exc:
        raise ValueError("This tool needs JSON parameters in content.") from exc
    if not isinstance(value, dict):
        raise ValueError("Tool parameters must be a JSON object.")
    return value


def validate_step(step):
    if step["action"] not in TOOLS:
        return
    if not isinstance(step.get("value"), str) or not step["value"] or not isinstance(step.get("content", ""), str):
        raise ValueError("Tool value and content must be text; value cannot be empty.")
    if len(step.get("content", "")) > 10000:
        raise ValueError("Tool content exceeds 10,000 characters.")
    if step['action'] in AGENT_TOOLS and step['action'] not in {'tool_search', 'mcp_status', 'mcp_list_tools', 'mcp_call'}:
        if not isinstance(step.get('folder'), str) or not step['folder'].strip():
            raise ValueError('Agent observations need an explicit project folder.')
    if step["action"] in {"list_files", "read_file", "append_file", "search_files", "query_resource", "knowledge_search"}:
        if not isinstance(step.get("folder"), str) or not step["folder"].strip():
            raise ValueError("Toolkit file operations need an explicit folder.")


def scoped_path(root, name):
    relative = Path(name)
    if relative.is_absolute() or relative.drive or any(part.startswith(".") for part in relative.parts if part != "."):
        raise ValueError("Use a relative visible path within the selected folder.")
    target = root / relative
    if not target.resolve().is_relative_to(root) or any(path.is_symlink() for path in [target, *target.parents] if path.is_relative_to(root)):
        raise ValueError("Linked paths and paths outside the selected folder are unsupported.")
    return target


def read_text(path):
    if not path.is_file() or path.stat().st_size > 20000:
        raise ValueError("Choose a UTF-8 text file up to 20,000 bytes.")
    with path.open("rb") as source:
        raw = source.read(20001)
    if len(raw) > 20000:
        raise ValueError("File grew beyond the read limit.")
    return raw.decode("utf-8")


def file_tool(actions, step, cancelled):
    root = Path(actions._task_folder(step["folder"], cancelled)).resolve(strict=True)
    name, value = step["action"], step["value"]
    if name in {"read_file", "append_file"}:
        path = scoped_path(root, value)
        current = read_text(path)
        if name == "read_file":
            return current
        content = current + step.get("content", "")
        if not step.get("content") or len(content.encode("utf-8")) > 20000:
            raise ValueError("Append requires nonempty content and a final file up to 20,000 bytes.")
        original = current.encode("utf-8")
        from .code_context import save_change_review
        from .task_state import TaskState
        state = getattr(actions, "task_state", None)
        if isinstance(state, TaskState):
            review = save_change_review(root, [(path, original, content)], state.path.parent)
            state.checkpoint("coding_review", target=review, evidence="append backup and diff saved")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile("wb", dir=path.parent, prefix=".jarvis-append-", delete=False) as output:
                temporary = Path(output.name)
                output.write(content.encode("utf-8"))
            if cancelled() or path.read_bytes() != original:
                raise ValueError("Append cancelled or file changed; nothing committed.")
            if isinstance(state, TaskState):
                state.checkpoint("action_attempted", action=name, target=path, evidence="append commit beginning")
            os.replace(temporary, path)
            temporary = None
            if path.read_bytes() != content.encode("utf-8"):
                raise ValueError("Append result uncertain; inspect the file before continuing.")
            if isinstance(state, TaskState):
                state.checkpoint("observed_file", target=path, evidence="appended bytes read back")
            return "Appended and verified " + str(path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    results, inspected = [], 0
    for directory, folders, files in os.walk(root, followlinks=False):
        if cancelled():
            raise ValueError("Tool cancelled.")
        folders[:] = sorted(name for name in folders if not name.startswith(".") and name not in {"node_modules", "venv", "__pycache__"}
                            and not (Path(directory)/name).is_symlink())[:30]
        for filename in sorted(files):
            inspected += 1
            if inspected > 500:
                return "\n".join(results) + "\n[Scan limited to 500 files]"
            if filename.startswith(".") or re.search(r"secret|credential|password|private_key|access_token", filename, re.I):
                continue
            path = Path(directory)/filename
            if path.is_symlink():
                continue
            relative = path.relative_to(root).as_posix()
            if name == "list_files":
                results.append(relative)
            elif value.casefold() in relative.casefold():
                results.append(relative)
            else:
                try:
                    for index, line in enumerate(read_text(path).splitlines(), 1):
                        if value.casefold() in line.casefold():
                            results.append(f"{relative}:{index}: {line[:240]}")
                except (OSError, UnicodeError, ValueError):
                    pass
            if len(results) >= 100:
                return "\n".join(results[:100]) + "\n[Results truncated]"
    return "\n".join(results) or "No matching files or text."


def public_url(url):
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("Use a public HTTP(S) URL without embedded credentials.")
    addresses = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError("Private, loopback and reserved network destinations are unsupported.")
    return url


class PageText(HTMLParser):
    BLOCKS = {'p', 'div', 'li', 'dt', 'dd', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'pre', 'tr', 'section', 'br'}
    def __init__(self):
        super().__init__()
        self.stack = []
        self.parts = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        hidden = (bool(self.stack and self.stack[-1][1])
                  or tag in {'script', 'style', 'noscript', 'nav', 'aside', 'footer', 'head'}
                  or attrs.get('role') == 'navigation' or attrs.get('aria-hidden') == 'true'
                  or 'hidden' in attrs)
        if not hidden and tag in self.BLOCKS:
            self.parts.append('\n')
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append((tag, hidden))
    def handle_endtag(self, tag):
        if not (self.stack and self.stack[-1][1]) and tag in self.BLOCKS:
            self.parts.append('\n')
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break
    def handle_data(self, data):
        if not (self.stack and self.stack[-1][1]):
            self.parts.append(data)


def api(client, method, url, cancelled, **kwargs):
    public_url(url)
    if urlsplit(url).scheme != "https" and (kwargs.get("auth") or "Authorization" in kwargs.get("headers", {})):
        raise ValueError("Authenticated services require HTTPS.")
    if cancelled():
        raise ValueError("Tool cancelled before request.")
    # Redirects must never forward credentials or bypass destination checks.
    with client.request(method, url, timeout=(5, 20), allow_redirects=False, stream=True, **kwargs) as response:
        if 300 <= response.status_code < 400:
            raise ValueError("Redirect refused; provide the final public service URL.")
        if not 200 <= response.status_code < 300:
            raise ValueError(f"Service returned HTTP {response.status_code}; external writes must not be retried automatically.")
        chunks, size = [], 0
        for chunk in response.iter_content(16384):
            if cancelled():
                raise ValueError("Tool cancelled during response; inspect any external write before repeating.")
            size += len(chunk)
            if size > 1000000:
                raise ValueError("Service response exceeds 1 MB.")
            chunks.append(chunk)
        raw = b"".join(chunks).decode("utf-8", errors="replace")
    return raw


def execute(actions, step, cancelled):
    name = step["action"]
    validate_step(step)
    if name not in TOOLS:
        raise ValueError("Unknown toolkit tool.")
    data = TOOLS[name]
    missing = [key for key in data[2] if not os.environ.get(key)]
    if missing:
        raise ValueError("Configure environment variables for " + name + ": " + ", ".join(missing))
    if cancelled():
        raise ValueError("Tool cancelled.")
    if name in AGENT_TOOLS:
        from .agent_tools import execute as agent_execute
        return agent_execute(actions, step, cancelled)
    if name == "toolkit_status":
        return json.dumps(status(), indent=2)
    if data[0] in {"files", "resource", "knowledge"}:
        return file_tool(actions, step, cancelled)
    if name in {"think", "write_spec", "write_tests", "write_code", "improve_code"}:
        return actions.brain.client.request("tool_text", cancelled, tool=name,
            goal=step["value"], context=step.get("content", ""))["text"]
    if name == "review_pull_request":
        patches = execute(actions, {**step, "action": "github_pr_files"}, cancelled)
        return actions.brain.client.request("tool_text", cancelled, tool=name,
            goal="Review pull request " + step["value"], context=patches[:10000])["text"]
    if name == "web_search":
        from .knowledge_worker import search
        return json.dumps(search(step["value"]), ensure_ascii=False)
    if data[3]:
        actions._approve(name, json.dumps({key: step.get(key, "") for key in ("action", "value", "content")}, ensure_ascii=False), cancelled)
    from .task_state import TaskState
    state = getattr(actions, "task_state", None)
    # Record uncertainty BEFORE any network write. Never retry these operations.
    if data[3] and isinstance(state, TaskState):
        state.checkpoint("action_attempted", action=name, target=step["value"], evidence="approved external request beginning")
    client = requests.Session()
    client.trust_env = False
    try:
        result = remote_tool(client, step, cancelled)
        if data[3] and isinstance(state, TaskState):
            state.checkpoint("observed", action=name, target=step["value"], evidence="service acknowledged request")
        for key, secret in os.environ.items():
            if key.startswith("JARVIS_") and any(word in key for word in ("TOKEN", "PASSWORD", "KEY")) and len(secret) >= 8:
                result = result.replace(secret, "[credential redacted]")
        return result[:12000] + ("\n[Tool response truncated]" if len(result) > 12000 else "")
    except (requests.RequestException, smtplib.SMTPException, imaplib.IMAP4.error, OSError) as exc:
        # Provider exceptions can contain URLs with API keys or authentication text.
        raise ValueError("Service request failed; inspect external state before repeating any write.") from None
    finally:
        client.close()


def remote_tool(client, step, cancelled):
    name, value, content = step["action"], step["value"], step.get("content", "")
    env = os.environ
    call = lambda method, url, **kwargs: api(client, method, url, cancelled, **kwargs)
    if name == "scrape_web":
        text = call("GET", value)
        parser = PageText()
        parser.feed(text)
        # Inline spans often split names such as json.loads across text nodes.
        # Preserve their adjacency; only block elements introduce boundaries.
        plain = re.sub(r'[ \t]+', ' ', ''.join(parser.parts)).strip()
        plain = re.sub(r'\n\s*\n+', '\n', plain)
        params = arguments(step)
        query = params.get('query', urlsplit(value).fragment)
        if not isinstance(query, str) or len(query) > 200:
            raise ValueError('Scrape query must be literal text up to two hundred characters.')
        start = 0
        if query:
            index = plain.casefold().find(query.casefold())
            if index < 0:
                return 'Untrusted page text from ' + value + ':\nNo literal match for ' + query
            start = max(0, index - 800)
        excerpt = plain[start:start + 10000]
        return ('Untrusted page text from ' + value + ':\n' + ('[Earlier page text omitted]\n' if start else '')
                + excerpt + ('\n[Page text truncated]' if start + len(excerpt) < len(plain) else ''))
    if name.startswith("github_"):
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "Jarvis-toolkit"}
        if env.get("JARVIS_GITHUB_TOKEN"):
            headers["Authorization"] = "Bearer " + env["JARVIS_GITHUB_TOKEN"]
        if name == "github_search":
            return call("GET", "https://api.github.com/search/repositories", headers=headers, params={"q": value, "per_page": 5})
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", value):
            raise ValueError("Use owner/repository as value.")
        args = arguments(step)
        base = "https://api.github.com/repos/" + value
        if name in {"github_pull_request", "github_pr_files"}:
            number = int(args["number"])
            if number <= 0:
                raise ValueError("PR number must be positive.")
            return call("GET", base+f"/pulls/{number}"+("/files" if name == "github_pr_files" else ""), headers=headers, params={"per_page": 20})
        path = args["path"]
        if not isinstance(path, str) or path.startswith("/") or ".." in path.split("/"):
            raise ValueError("Use a repository-relative path.")
        url = base + "/contents/" + quote(path, safe="/")
        if name == "github_read_file":
            raw = json.loads(call("GET", url, headers=headers, params={"ref": args.get("ref", "HEAD")}))
            if raw.get("size", 0) > 20000 or raw.get("encoding") != "base64":
                raise ValueError("Choose a small text repository file.")
            text = base64.b64decode(raw["content"]).decode("utf-8")
            if isinstance(raw.get("sha"), str) and raw["sha"]:
                return json.dumps({"repository": value, "path": path, "ref": args.get("ref", "HEAD"),
                                   "sha": raw["sha"], "text": text}, ensure_ascii=False)
            return text
        body = {key: args[key] for key in ("message", "sha", "branch") if key in args}
        if not body.get("message"):
            raise ValueError("A commit message is required.")
        if name == "github_add_file":
            body["content"] = base64.b64encode(args["text"].encode()).decode()
        elif not body.get("sha"):
            raise ValueError("Deletion requires the current file SHA.")
        return call("PUT" if name == "github_add_file" else "DELETE", url, headers=headers, json=body)
    if name == "google_search":
        return call("GET", "https://www.googleapis.com/customsearch/v1", params={"key": env["JARVIS_GOOGLE_SEARCH_KEY"], "cx": env["JARVIS_GOOGLE_SEARCH_CX"], "q": value, "num": 5})
    if name == "serp_search":
        return call("GET", "https://serpapi.com/search.json", params={"api_key": env["JARVIS_SERPAPI_KEY"], "q": value, "num": 5})
    if name == "searx_search":
        return call("GET", env["JARVIS_SEARX_URL"].rstrip("/")+"/search", params={"q": value, "format": "json"})
    if name == "apollo_search":
        return call("POST", "https://api.apollo.io/api/v1/mixed_companies/search", headers={"X-Api-Key": env["JARVIS_APOLLO_KEY"]}, json={"q_organization_name": value, "per_page": 5})
    if name == "slack_send":
        raw = call("POST", "https://slack.com/api/chat.postMessage", headers={"Authorization": "Bearer "+env["JARVIS_SLACK_TOKEN"]}, json={"channel": value, "text": content})
        if json.loads(raw).get("ok") is not True:
            raise ValueError("Slack did not acknowledge the message; inspect before retrying.")
        return raw
    if name == "twitter_send":
        if not 1 <= len(content) <= 280:
            raise ValueError("Tweet text must have 1 to 280 characters.")
        return call("POST", "https://api.twitter.com/2/tweets", headers={"Authorization": "Bearer "+env["JARVIS_TWITTER_TOKEN"]}, json={"text": content})
    if name.startswith("calendar_"):
        headers = {"Authorization": "Bearer "+env["JARVIS_GOOGLE_ACCESS_TOKEN"]}
        base = "https://www.googleapis.com/calendar/v3/calendars/"+quote(value or "primary", safe="")+"/events"
        if name == "calendar_list":
            from datetime import datetime, timezone
            return call("GET", base, headers=headers, params={"maxResults": 10, "singleEvents": "true", "orderBy": "startTime", "timeMin": datetime.now(timezone.utc).isoformat()})
        args = arguments(step)
        if name == "calendar_create":
            if not all(key in args for key in ("summary", "start", "end")) or "attendees" in args:
                raise ValueError("Supply summary/start/end; invitation sending is unsupported.")
            return call("POST", base, headers=headers, json={key: args[key] for key in ("summary", "start", "end", "description") if key in args})
        return call("DELETE" if name == "calendar_delete" else "GET", base+"/"+quote(args["event_id"], safe=""), headers=headers)
    if name.startswith("jira_"):
        base = env["JARVIS_JIRA_URL"].rstrip("/")+"/rest/api/3"
        auth = (env["JARVIS_JIRA_USER"], env["JARVIS_JIRA_TOKEN"])
        if name == "jira_projects":
            return call("GET", base+"/project/search", auth=auth, params={"maxResults": 10})
        if name == "jira_search":
            return call("GET", base+"/search/jql", auth=auth, params={"jql": value, "maxResults": 10})
        args = arguments(step)
        if not isinstance(args.get("fields"), dict):
            raise ValueError("Supply Jira fields object.")
        return call("POST" if name == "jira_create" else "PUT", base+"/issue"+("/"+quote(value, safe="") if name == "jira_edit" else ""), auth=auth, json={"fields": args["fields"]})
    if name == "read_email":
        public_url("https://"+env["JARVIS_IMAP_HOST"])
        with imaplib.IMAP4_SSL(env["JARVIS_IMAP_HOST"], timeout=20, ssl_context=ssl.create_default_context()) as mailbox:
            mailbox.login(env["JARVIS_EMAIL_USER"], env["JARVIS_EMAIL_PASSWORD"])
            mailbox.select("INBOX", readonly=True)
            ok, ids = mailbox.search(None, "ALL")
            if ok != "OK":
                raise ValueError("Mailbox search failed.")
            rows = []
            for uid in ids[0].split()[-5:]:
                if cancelled():
                    raise ValueError("Email read cancelled.")
                ok, data = mailbox.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])")
                if ok == "OK":
                    rows.extend(item[1][:2000].decode(errors="replace") for item in data if isinstance(item, tuple))
            return "\n".join(rows) or "No email headers."
    if name == "send_email":
        args = arguments(step)
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = env["JARVIS_EMAIL_USER"], value, args["subject"]
        message.set_content(args["body"])
        public_url("https://"+env["JARVIS_SMTP_HOST"])
        with smtplib.SMTP_SSL(env["JARVIS_SMTP_HOST"], 465, timeout=20, context=ssl.create_default_context()) as smtp:
            smtp.login(env["JARVIS_EMAIL_USER"], env["JARVIS_EMAIL_PASSWORD"])
            if smtp.send_message(message):
                raise ValueError("Some recipients were refused; inspect delivery before retrying.")
        return "SMTP server accepted email to " + value
    raise ValueError("Unsupported remote tool.")
