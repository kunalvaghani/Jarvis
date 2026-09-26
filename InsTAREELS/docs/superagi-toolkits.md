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
planning sees only relevant configured tools to limit prompt overhead.

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
