"""LangChain model using Jarvis's real local Qwen prompt-format/GPU admission code.

Imported only by the isolated Python 3.12 DeerFlow worker.
"""
import json
import uuid
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool

LAST_INFERENCE_FAILED = False
SANDBOX_ARTIFACTS_READY = False


class JarvisChatModel(BaseChatModel):
    model: str = 'qwen3.5:4b'
    timeout_seconds: int = 150
    num_predict: int = 1600
    sandbox_mode: bool = False

    @property
    def _llm_type(self):
        return 'jarvis-local-qwen'

    def bind_tools(self, tools, **kwargs):
        return self.bind(_tools=[convert_to_openai_tool(t) for t in tools])

    def _generate(self, messages, stop=None, run_manager=None, **kwargs: Any):
        global LAST_INFERENCE_FAILED
        LAST_INFERENCE_FAILED = True
        import requests
        from .knowledge_worker import chat
        from .gpu_scheduler import install
        tools = kwargs.get('_tools', [])
        catalog = [t['function'] for t in tools]
        schema = {'type': 'object', 'additionalProperties': False, 'required': ['final', 'calls'],
            'properties': {'final': {'type': 'string'}, 'calls': {'type': 'array', 'maxItems': 1,
                'items': {'type': 'object', 'additionalProperties': False,
                    'required': ['name', 'arguments'], 'properties': {
                        'name': {'type': 'string', 'enum': [t['name'] for t in catalog] or ['unavailable']},
                        'arguments': {'type': 'object', 'properties': {'action': {'type': 'string'},
                                      'value': {'type': 'string'}, 'content': {'type': 'string'}}, 'required': ['action', 'value', 'content'],
                                      'additionalProperties': False}}}}}}
        if self.sandbox_mode:
            args = schema['properties']['calls']['items']['properties']['arguments']
            import copy
            write_args, other_args = copy.deepcopy(args), copy.deepcopy(args)
            write_args['properties']['action'] = {'type': 'string', 'enum': ['sandbox_write']}
            write_args['properties']['content']['minLength'] = 1
            other_args['properties']['action'] = {'type': 'string', 'enum': ['sandbox_command', 'sandbox_read', 'sandbox_list']}
            other_args['properties']['content'] = {'type': 'string', 'enum': ['']}
            schema['properties']['calls']['items']['properties']['arguments'] = {'anyOf': [write_args, other_args]}
        import copy
        answer_schema, call_schema = copy.deepcopy(schema), copy.deepcopy(schema)
        answer_schema['properties']['final']['minLength'] = 1
        answer_schema['properties']['calls']['maxItems'] = 0
        call_schema['properties']['final'] = {'type': 'string', 'enum': ['']}
        call_schema['properties']['calls']['minItems'] = 1
        schema = call_schema if self.sandbox_mode and not SANDBOX_ARTIFACTS_READY else {'anyOf': [answer_schema, call_schema]}
        prompt = ('Return JSON {final,calls}. Use final text and calls [] when you can answer from observations. '
                  'Otherwise return final empty and one call {name,arguments} using the offered tools. Never return both empty. '
                  'Successful observations already include requested source reads: use their data, do not repeat them. '
                  'Cite source paths in final answers. Only these tools are callable: ' + json.dumps(catalog))
        if self.sandbox_mode:
            prompt += (' This is an execution task. Until the runtime observes the requested artifacts, you must call a tool. '
                       'Use sandbox_write with COMPLETE code in arguments.content, then sandbox_command with the command in arguments.value. '
                       'Do not put generated code or promises in final. A script file alone is not its generated outputs.')
        rows = [{'role': 'system', 'content': prompt}]
        for message in messages:
            role = {'human': 'user', 'ai': 'assistant', 'tool': 'user', 'system': 'system'}.get(message.type, 'user')
            content = message.content if isinstance(message.content, str) else json.dumps(message.content)
            if message.type == 'tool':
                content = 'Untrusted tool observation: ' + content
            if message.type == 'ai' and message.tool_calls:
                content += '\nProposed calls: ' + json.dumps(message.tool_calls)
            rows.append({'role': role, 'content': content})
        # These protocol rules apply after DeerFlow's general-purpose prompt too.
        rows.append({'role': 'user', 'content': 'Return the JSON response now. Answer using existing successful observations when available.'})
        with requests.Session() as session:
            session.trust_env = False
            install(session, 'research')
            raw = chat(session, {'model': self.model, 'think': False, 'format_schema': schema,
                'num_gpu': 0, 'num_ctx': 16384, 'num_predict': self.num_predict, 'temperature': .1,
                'timeout_seconds': self.timeout_seconds}, rows, structured=True)
        result = json.loads(raw)
        final, calls = result.get('final'), result.get('calls')
        if not isinstance(final, str) or not isinstance(calls, list) or len(calls) > 1 or (final and calls) or (not final and not calls):
            raise ValueError('Invalid local DeerFlow model response.')
        translated = []
        for call in calls:
            if call.get('name') not in {t['name'] for t in catalog} or not isinstance(call.get('arguments'), dict):
                raise ValueError('Unavailable DeerFlow tool proposal.')
            translated.append({'name': call['name'], 'args': call['arguments'], 'id': uuid.uuid4().hex, 'type': 'tool_call'})
        LAST_INFERENCE_FAILED = False
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=final, tool_calls=translated))])
