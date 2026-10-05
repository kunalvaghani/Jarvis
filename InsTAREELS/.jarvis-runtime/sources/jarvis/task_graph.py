# Copyright (c) Microsoft Corporation.
# Adapted from microsoft/JARVIS hugginggpt/server/awesome_chat.py (MIT).
# See integrations/MICROSOFT-JARVIS-LICENSE for the permission notice.
"""Validate task dependencies before any desktop action; never schedule replays."""
import re

MAX_PLAN_STEPS = 40
MAX_TASK_GOAL_CHARS = 6000


def action_budget(options):
    value = options.get('max_task_actions', 20)
    if type(value) is not int or not 1 <= value <= MAX_PLAN_STEPS:
        raise ValueError('max_task_actions must be an integer between 1 and 40.')
    return value


def resource_dependencies(step):
    """Adapt HuggingGPT's GENERATED reference detection to our flat tool fields."""
    dependencies = []
    for value in step.values():
        if isinstance(value, str):
            for match in re.finditer(r"<GENERATED>-(\d+)", value):
                dependency = int(match[1])
                if dependency not in dependencies:
                    dependencies.append(dependency)
    return dependencies


def validate_dependencies(steps, completed=()):
    """Accept explicit id/dep metadata only when prerequisites precede the task.

    Existing plans without metadata keep their sequential order. Dependencies
    from a previous plan count only when their completion was verified.
    """
    seen = {item["id"] for item in completed if item.get("verified") is True
            and type(item.get("id")) is int and item["id"] >= 0}
    for step in steps:
        references = resource_dependencies(step)
        if references or any(isinstance(v, str) and "<GENERATED>" in v for v in step.values()):
            raise ValueError("Generated resource placeholders are not desktop targets. Use freshly observed exact values.")
        if "id" not in step and "dep" not in step:
            continue
        identifier = step.get("id")
        dependencies = step.get("dep", [-1])
        if type(identifier) is not int or identifier < 0 or identifier in seen:
            raise ValueError("Task IDs must be unique non-negative integers.")
        if not isinstance(dependencies, list) or any(type(dep) is not int for dep in dependencies):
            raise ValueError("Task dependencies must be an integer list.")
        if -1 in dependencies and dependencies != [-1]:
            raise ValueError("The no-dependency sentinel cannot be combined with task IDs.")
        if any(dep not in seen for dep in dependencies if dep != -1):
            raise ValueError("A task prerequisite is missing, unverified, or ordered after its dependent task.")
        seen.add(identifier)
    return steps
