# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates.
# Copyright (c) 2025-2026 DeerFlow Authors.
# MIT; permission notice: integrations/deerflow/LICENSE.
# Extracted pure helpers at a5e71751d7a9f8f4a71ca458da3984fc1284d098.
import re

_BLOCKED_TAG_NAMES: frozenset[str] = frozenset(
    {
        # Framework-injected structured/authority blocks. The lead-agent system
        # prompt's "System-Context Confidentiality" section (agents/lead_agent/
        # prompt.py) declares *every* such tag trusted internal data — it names a
        # few then says "and all other structured tags". So the denylist must
        # cover the framework's authority blocks as a class, not a hand-picked
        # subset: any one of them, forged in untrusted input, mimics trusted
        # framework context. Enumerated from the block tags the framework actually
        # emits into model input (system prompt + hidden-context/reminder
        # middlewares) and pinned against drift by
        # test_input_sanitization_middleware.py::test_denylist_covers_framework_authority_blocks.
        # Both spellings of the reminder block are covered: "system-reminder"
        # (dynamic-context) and "system_reminder" (todo/terminal middlewares).
        #
        # Subagents share this denylist: build_subagent_runtime_middlewares reuses
        # the same _build_runtime_middlewares base, so both sanitization paths guard
        # subagent model input too. The subagent system-prompt blocks
        # (file_editing_workflow / guidelines / output_format / working_directory)
        # are therefore authority blocks of the same class as the lead-agent ones.
        "system-reminder",
        "system_reminder",
        "memory",
        "current_date",
        "think",
        "analysis",
        "role",
        "soul",
        "self_update",
        "thinking_style",
        "clarification_system",
        "critical_reminders",
        "response_style",
        "citations",
        "current_uploads",
        "subagent_system",
        "skill_system",
        "skill_index",
        "available_skills",
        "disabled_skills",
        "memory_tool_system",
        "todo_list_system",
        "durable_context_data",
        "slash_skill_activation",
        "mcp_routing_hints",
        "available-deferred-tools",
        "goal_continuation",
        "active_goal",
        "background_task_event",
        "file_editing_workflow",
        "guidelines",
        "output_format",
        "working_directory",
        # Subagent system-prompt block (general_purpose.py): declares the task
        # tool off-limits. Forging this in untrusted input could trick the
        # model into believing it has (or lacks) tool restrictions it does not.
        "tool_restrictions",
        # Subagent report-contract blocks (subagents/report_contract.py, RFC
        # #4651 PR3): injected by the executor into every subagent system
        # prompt (the criteria pointer note carries no criterion values —
        # those stay in the untrusted task message). Forging them in
        # untrusted input could impersonate the verification contract (e.g.
        # pre-declaring acceptance criteria as met).
        "report_contract",
        "acceptance_criteria",
        # Project context blocks (projects/context.py, Projects Phase 2):
        # rendered request-scoped into model input carrying user-managed
        # project identity/instructions and the bounded shelf index. Forging
        # either in untrusted input mimics the run's pinned project
        # configuration or fabricates shelf entries/tool-callable IDs.
        "project",
        "documents",
        # Common prompt-injection tag patterns
        "system",
        "instruction",
        "important",
        "override",
        "ignore",
        "prompt",
    }
)

_BLOCKED_TAG_PATTERN = re.compile(
    r"<\s*/?\s*(?:" + "|".join(re.escape(t) for t in sorted(_BLOCKED_TAG_NAMES)) + r")\b[^>]*>?",
    re.IGNORECASE,
)

_USER_INPUT_BEGIN = "--- BEGIN USER INPUT ---"

_USER_INPUT_END = "--- END USER INPUT ---"

_NEUTRALIZED_BEGIN = "[BEGIN USER INPUT]"

_NEUTRALIZED_END = "[END USER INPUT]"

_BOUNDARY_TOKEN_RE = re.compile(
    re.escape(_USER_INPUT_BEGIN) + r"|" + re.escape(_USER_INPUT_END),
)

def _escape_tag_match(match: re.Match) -> str:
    """Escape < and > in a blocked-tag match so it renders as literal text."""
    return match.group(0).replace("<", "&lt;").replace(">", "&gt;")

def _neutralize_boundary_tokens(text: str) -> str:
    """Replace real BEGIN/END USER INPUT markers with look-alike inert forms."""
    return _BOUNDARY_TOKEN_RE.sub(
        lambda m: _NEUTRALIZED_BEGIN if m.group(0) == _USER_INPUT_BEGIN else _NEUTRALIZED_END,
        text,
    )

def neutralize_untrusted_tags(text: str) -> str:
    """Neutralize framework/injection control tokens in untrusted text.

    Shared primitive for any content that originates outside the trust boundary
    and is about to enter the model context as *data* — currently the genuine
    user message (via :func:`frame_untrusted_text`) and remote tool results
    (web_fetch / web_search and friends, via
    :class:`ToolResultSanitizationMiddleware`).

    Applies exactly the two structural defenses, and nothing else:

    * blocked framework/injection tags (e.g. ``<system-reminder>``) are
      HTML-escaped to ``&lt;system-reminder&gt;`` so they lose their structural
      meaning while staying human-readable;
    * the plain-text ``--- BEGIN/END USER INPUT ---`` boundary markers are
      neutralized so untrusted content cannot forge or break out of the
      user-input boundary.

    It intentionally does **not** wrap the text in boundary markers: that
    framing is specific to the user message. Empty/whitespace-only text is
    returned unchanged so callers do not emit marker noise.
    """
    if not text.strip():
        return text
    text = _BLOCKED_TAG_PATTERN.sub(_escape_tag_match, text)
    return _neutralize_boundary_tokens(text)

RECEIPT_ID_PREFIX = "r"

_MAX_RECEIPT_ID_DIGITS = 10

def receipt_id(position: int) -> str:
    """Display id for the ``position``-th receipt (1-based): ``r1``..``rN``."""
    return f"{RECEIPT_ID_PREFIX}{position}"

CITATION_RE = re.compile(rf"\[{RECEIPT_ID_PREFIX}(\d+)(?:\s+([A-Za-z_][\w.-]*))?\]")

def format_citation(rid: str, tool_name: str | None = None) -> str:
    """Canonical model-facing citation (``[r2]`` bare, ``[r2 write_file]`` anchored)."""
    return f"[{rid} {tool_name}]" if tool_name else f"[{rid}]"

def parse_citations(text: str) -> list[tuple[str, str | None]]:
    """Pull ``(id, anchor)`` pairs out of report prose, deduped first-seen."""
    seen: set[tuple[str, str | None]] = set()
    citations: list[tuple[str, str | None]] = []
    for match in CITATION_RE.finditer(text):
        digits = match.group(1)
        # Model output is untrusted.  Bound the decimal string before int()
        # so an enormous citation id cannot trip Python's conversion limit and
        # turn an otherwise successful task into a verification exception.
        if len(digits) > _MAX_RECEIPT_ID_DIGITS:
            continue
        rid = receipt_id(int(digits))
        citation = (rid, match.group(2))
        if citation in seen:
            continue
        seen.add(citation)
        citations.append(citation)
    return citations
