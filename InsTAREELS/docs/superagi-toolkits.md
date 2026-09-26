# SuperAGI toolkit integration

Reviewed [SuperAGI](https://github.com/TransformerOptimus/SuperAGI) at commit
`c3c1982e7bd6a11cfed53c5a193ea502f924b1b6`. The upstream tool tree, selected
reference sources and MIT license are saved as `integrations/superagi-*`.
The runtime adapters in `jarvis/toolkits.py` are independently implemented for
Jarvis; they do not import SuperAGI's database, agent runtime or dependency stack.

37 operations were added to the existing 15-tool registry, giving 52 operations.
19 added operations require no account credentials; 18 account-backed operations
need environment configuration and remain unavailable to planning until configured.
Network access is still needed for public web/GitHub tools. Local reasoning needs
the already configured Jarvis brain. No language model, dependency, launcher,
owned-service list or microphone behavior was changed.

| Toolkit | Added operations |
| --- | --- |
| File | `list_files`, `read_file`, `append_file`, `search_files` |
| Resource / knowledge | `query_resource`, `knowledge_search` |
| Thinking / coding | `think`, `write_spec`, `write_tests`, `write_code`, `improve_code` |
| Web | `web_search`, `scrape_web`, `google_search`, `serp_search`, `searx_search` |
| GitHub | `github_search`, `github_read_file`, `github_pull_request`, `github_pr_files`, `review_pull_request`, `github_add_file`, `github_delete_file` |
| Email | `read_email`, `send_email` |
| Calendar | `calendar_list`, `calendar_details`, `calendar_create`, `calendar_delete` |
| Jira | `jira_projects`, `jira_search`, `jira_create`, `jira_edit` |
| Other services | `apollo_search`, `slack_send`, `twitter_send` |
| Setup inspection | `toolkit_status` |

Existing create/modify/delete file tools and the autonomous coder cover upstream
write-file and saved-code workflows. Coding toolkit operations return drafts or
reviews without executing them; use the existing project coding command to save
checked source. Knowledge/resource search is bounded literal search over local
UTF-8 resources, not SuperAGI's vector database. Email reading returns the latest
five message headers without marking mail read. Scraping extracts static HTML
text and does not run JavaScript. Calendar creation excludes invitations.

Say **“list toolkits”** for readiness and required environment variable names.
The complete inventory is also saved in
`integrations/superagi-jarvis-tool-inventory.json`; regenerate status after configuring.
Credential values are never shown in status or copied into configuration files.
Set the named environment variables before starting Jarvis. OAuth token acquisition
and refresh are not automated; providers need appropriate scopes and account access.

Examples for Jarvis's command input:

```text
list files in Documents
read file notes.txt in Documents
append to file notes.txt in Documents: Remember the meeting.
search github for local voice assistant
extract text from https://example.com
tool write_spec {"value":"A Python calculator"}
tool read_file {"value":"src/main.py","folder":"this folder"}
tool github_pull_request {"value":"owner/repository","content":"{\"number\":12}"}
tool send_email {"value":"recipient@example.com","content":"{\"subject\":\"Meeting\",\"body\":\"See you tomorrow.\"}"}
```

The explicit `tool` syntax accepts only `value`, `folder` and `content`. For tools
requiring structured parameters, `content` is a JSON string. Tool descriptions
and the status inventory identify required service configuration. Natural task
planning now sees every configured operation, without a keyword filter. The
planner chooses useful prerequisite tools by meaning and integrates their
results into the remaining plan; you do not need to name toolkit operations.

## Autonomous planning and chaining

Give Jarvis the goal using **Do task**, `task ...`, or a compound natural request:

- `task find useful public sources about Python asyncio and compare the tradeoffs`
- `read file source.txt in Demo and draft tests for its functions`
- `task review pull request 12 in GitHub repository owner/repository`
- `task check my upcoming calendar meetings and draft a preparation checklist`
- `task research Python asyncio and email a summary to recipient@example.com`

These are examples of goals, not promises that every provider is configured.
The final example needs the email environment variables and a visible approval
of recipient, subject and exact body before sending. Drafting returns text;
it does not execute generated code or silently save it into a project.

With no account credentials the catalog contains 34 operations (15 core + 19
toolkit). With all required configuration present it contains all 52. Initial
planning, adaptive replanning and failure recovery share this catalog. Model
names remain unchanged; planning/replanning uses a 16,384-token context budget
to accommodate the complete catalog and result context.

Toolkit results are independently checked against the expected step result.
API responses, scoped file reads and drafts are verified from returned data,
not from an unrelated desktop screenshot. Verified results are supplied as
untrusted observations to later decisions, replanning and final goal checks.
The runtime keeps up to 12,000 characters per tool response in task memory and
supplies at most 16,000 characters across recent results (up to 10,000 for the
latest and 3,000 for earlier results), with truncation markers. Full transient
result context is cleared on a new task; it is not added to the durable plan
beyond the existing compact 500-character result summaries. After a restart,
tools must observe fresh data before relying on old results.

When downstream arguments require unknown URLs, IDs, source text or repository
SHAs, the planner should perform the prerequisite read first and replan from
its result. No fabricated placeholder targets are dispatched. Compound read,
search and list requests remain one task rather than swallowing the remaining
goal into a folder or query. Initial and revised plans both enforce explicit
external-write intent; dispatch retains credential checks and exact-content
approval. Failed verification stops the chain, and uncertain actions are not
replayed. Tool fingerprints include exact payloads and applicable folder scope.
The existing six-action limit, microphone stop and Quit handling remain.

Validation uses autonomous-plan dispatch tests for all 37 operations with
mocked adapters, a real temporary-file read followed by draft inference with
controlled model responses, and injected failed verification/unrequested-send
checks. `verify_toolkit_planner.py` separately checks actual configured local
model planning and source-driven replanning without executing desktop,
web-tool or account actions. Fresh test results are recorded in the README.

File tools stay inside an explicitly identified folder, reject linked/outside
paths, bound scans and exclude common secret/hidden files from discovery. Appends
save original bytes and a diff, check for concurrent changes and verify the commit.
External sends, publishing, remote file changes and deletion need a visible approval
showing destination and exact content. Checkpoints precede external writes; no write
is automatically retried after a timeout or uncertain response. Direct toolkit tasks
are not automatically resumed. Stop cancels queued work and checks cancellation
before requests and while reading responses. Active network reads use bounded
timeouts; an in-flight remote write cannot be recalled by cancellation.

HTTP adapters reject embedded credentials, private destinations and redirects;
authenticated requests require HTTPS. Responses are limited to 1 MB and returned
context to 12,000 characters. Provider errors do not expose credential-bearing URLs.
Read data remains untrusted and cannot authorize an action or override user goals.

Not every upstream operation is included: image generation needs a separate image
provider/model; Instagram publishing needs its media preparation and account workflow;
email attachments need a separate attachment selection/preview flow. These are not
advertised as working tools. SuperAGI's agent spawning, Docker services, vector stores,
marketplace loader and UI were not imported into Jarvis's desktop runtime.

Provider adapters follow current primary documentation for
[GitHub contents](https://docs.github.com/en/rest/repos/contents),
[Google Calendar](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert),
[Google Search](https://developers.google.com/custom-search/v1/reference/rest/v1/cse/list),
[Jira search](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/),
[Apollo organizations](https://docs.apollo.io/reference/organization-search),
[Slack messages](https://api.slack.com/methods/chat.postMessage),
[X posts](https://docs.x.com/x-api/posts/create-post) and
[SerpAPI](https://serpapi.com/search-api). Account-backed operations were validated
with mocked transports; no real message, event, repository change or account
operation was performed. Public/local tools and local-model drafting have a separate
smoke check in `verify_toolkits.py --live`.

Validation covers 20 toolkit-specific tests plus the existing regression suite:
scoped reads, traversal/size rejection, exact append bytes and backups, injected
failure after commit, denied approval, stopped requests, private destinations,
redirects, response limits, provider payloads, secret-safe errors, local-model
routing, task-state isolation and toolkit evidence in the final goal check.
The live temporary-file/local-model smoke passed with unchanged `qwen3.5:4b`;
launcher checks report ready.

Results on 2026-09-27: 330 regression tests passed; live configured Qwen planning selected research/read tools and used observed source text in a test-drafting replan; launcher reported ready. All 37 dispatch paths are covered with mocked adapters; account sends and remote writes were not performed. Repository reads now retain returned SHA/path/ref metadata alongside text for subsequent approved writes.
