"""BaseConnector contract: schemas Jarvis accepts, strict validation, access policy, bounded results."""
from typing import Annotated, Optional

import pytest

from jarvis import mcp_contract
from jarvis_connector import BaseConnector, Param, SchemaError, ToolError, UnknownTool, tool


class Sample(BaseConnector):
    name = 'sample'
    max_result_chars = 200

    @tool()
    def echo(self, text: Annotated[str, Param(min_length=1, max_length=20)],
             times: Annotated[int, Param(minimum=1, maximum=3)] = 1,
             mode: Annotated[str, Param(enum=('plain', 'loud'))] = 'plain',
             tags: Annotated[list[str], Param(max_items=2)] = ()) -> str:
        """Echo text."""
        return (text.upper() if mode == 'loud' else text) * times

    @tool()
    def crash(self) -> str:
        """Fail unexpectedly."""
        raise RuntimeError('C:\\secret\\path leaked?')

    @tool()
    def huge(self) -> str:
        """Return too much."""
        return 'x' * 500

    @tool()
    def wrong_type(self) -> int:
        """Return the wrong type."""
        return 'not an int'

    @tool(access='write', destructive=True)
    def wipe(self, target: str) -> bool:
        """Pretend to delete something."""
        return True


def test_schemas_stay_inside_the_jarvis_bridge_subset():
    connector = Sample(allow_write=True)
    for row in connector.describe():
        # Jarvis refuses unsupported keywords; a valid call must pass its validator unchanged.
        mcp_contract.validate_schema_value(row['inputSchema'], {'text': 'hi'} if row['name'] == 'echo'
                                           else {'target': 'x'} if row['name'] == 'wipe' else {})
        assert row['outputSchema']['required'] == ['result']
    echo = next(r for r in connector.describe() if r['name'] == 'echo')['inputSchema']
    with pytest.raises(mcp_contract.ContractError):
        mcp_contract.validate_schema_value(echo, {'text': 'hi', 'times': 9})


def test_successful_result_satisfies_jarvis_result_contract():
    connector = Sample()
    result = connector.call('echo', {'text': 'hi', 'times': 2, 'mode': 'loud'})
    schema = next(r for r in connector.describe() if r['name'] == 'echo')['outputSchema']
    mcp_contract.validate_result(result, schema)
    assert result['structuredContent'] == {'result': 'HIHI'} and result['isError'] is False


@pytest.mark.parametrize('arguments', [
    {}, {'text': ''}, {'text': 'x' * 21}, {'text': 'hi', 'times': True}, {'text': 'hi', 'times': 1.0},
    {'text': 'hi', 'times': 4}, {'text': 'hi', 'mode': 'quiet'}, {'text': 'hi', 'extra': 1},
    {'text': 'hi', 'tags': ['a', 'b', 'c']}, {'text': 'hi', 'tags': [1]}, {'text': 5}])
def test_invalid_arguments_are_rejected_without_coercion(arguments):
    with pytest.raises(ToolError):
        Sample().invoke('echo', arguments)


def test_write_tools_are_hidden_and_uncallable_without_allow_write():
    assert 'wipe' not in {row['name'] for row in Sample().describe()}
    with pytest.raises(UnknownTool):
        Sample().call('wipe', {'target': 'x'})
    row = next(r for r in Sample(allow_write=True).describe() if r['name'] == 'wipe')
    assert row['annotations']['readOnlyHint'] is False and row['annotations']['destructiveHint'] is True


def test_unknown_tool_raises_unknown_tool():
    with pytest.raises(UnknownTool):
        Sample().call('nope', {})


def test_unexpected_exception_is_a_generic_error_without_details(capsys):
    result = Sample().call('crash', {})
    assert result['isError'] is True
    assert 'secret' not in result['content'][0]['text']
    assert 'RuntimeError' in capsys.readouterr().err  # the traceback goes to the log only


def test_oversized_and_mistyped_results_fail_instead_of_being_cut():
    assert 'too large' in Sample().call('huge', {})['content'][0]['text']
    assert Sample().call('wrong_type', {})['isError'] is True


def test_child_can_override_and_extend_tools():
    class Child(Sample):
        name = 'child'

        @tool()
        def echo(self, text: str) -> str:
            """Child echo."""
            return 'child:' + text

        def huge(self):  # overriding without @tool removes the tool
            return ''

    names = {row['name'] for row in Child().describe()}
    assert 'huge' not in names and {'echo', 'crash'} <= names
    assert Child().invoke('echo', {'text': 'a'}) == 'child:a'
    assert Sample().invoke('echo', {'text': 'a'}) == 'a'


def _bad(**namespace):
    return type('Bad', (BaseConnector,), {'name': 'bad', **namespace})


def test_unsafe_signatures_fail_at_class_definition():
    def no_doc(self) -> str:
        return ''

    def no_hint(self, x) -> str:
        """Doc."""

    def optional(self, x: Optional[str] = 'a') -> str:
        """Doc."""

    def none_default(self, x: str = None) -> str:
        """Doc."""

    def no_return(self):
        """Doc."""

    def varargs(self, *values: str) -> str:
        """Doc."""

    def valid(self) -> str:
        """Doc."""

    for function in (no_doc, no_hint, optional, none_default, no_return, varargs):
        with pytest.raises(SchemaError):
            _bad(tool_method=tool()(function))
    with pytest.raises(SchemaError):
        _bad(tool_method=tool('bad name!')(valid))
    _bad(tool_method=tool()(valid))  # the control case defines fine


def test_name_is_required():
    class Nameless(BaseConnector):
        pass

    with pytest.raises(TypeError):
        Nameless()
