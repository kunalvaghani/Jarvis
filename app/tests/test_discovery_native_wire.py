"""Transport contracts, without model calls or solver proof consumption."""
import json
import pytest
from jarvis.discovery.native_wire import lower, parameters, read_only, arguments


def test_help_and_structured_request_lower_to_existing_transport():
    help_step=lower({'operation':'help','topic':'mechanics','expected':'Read schema'})
    assert read_only(help_step) and help_step['value']=='help mechanics'
    step=lower({'operation':'run','command':'lab simulate mechanics "{request}"',
                'request':{'units':'SI'},'expected':'Conditional result'})
    assert json.loads(step['content'])=={'units':'SI'} and not read_only(step)
    assert 'request' in parameters()['properties']
    assert lower(arguments(help_step))==help_step
    assert lower(arguments(step))==step


def test_fresh_native_history_uses_current_schema_and_retains_full_help():
    from unittest.mock import Mock
    from jarvis.native_tools import plan
    rows=[{'action':'discovery_call','description':'Lab','lab_workflow':True,'parameters':parameters()}]
    done={'message':{'tool_calls':[{'function':{'name':'jarvis_finish','arguments':{'reason':'Inspected'}}}]}}
    client=Mock(post=Mock(return_value=Mock(status_code=200,raise_for_status=Mock(),json=Mock(return_value=done))))
    step={**lower({'operation':'help','topic':'mechanics','expected':'Read schema'}),
          'verified':True,'result':'schema '*700+'LAST_SCHEMA_FIELD'}
    plan(client,'qwen3.5:9b','Plan.',{'goal':'Inspect supported schema','tools':rows,'completed':[step]}, {})
    messages=client.post.call_args.kwargs['json']['messages']
    call=messages[1]['tool_calls'][0]['function']
    assert call['arguments']=={'operation':'help','topic':'mechanics','expected':'Read schema'}
    assert 'LAST_SCHEMA_FIELD' in messages[2]['content']


@pytest.mark.parametrize('fields',[
    {'operation':'run','command':'primitive-mechanics'},
    {'operation':'run','command':'lab simulate mechanics "{request}"'},
    {'operation':'run','command':'lab simulate mechanics {request}','request':{}},
    {'operation':'run','command':'lab status','request':{}},
    {'operation':'run','command':'lab simulate mechanics "{request}"','request':{'x':float('nan')}},
    {'operation':'run','command':'lab simulate mechanics "{request}"','request':{'x':'x'*10001}},
    {'operation':'help','request':{}},
    {'operation':'help','approved':True},
    {'operation':'help','topic':'dilation'},
])
def test_invalid_or_disabled_native_requests_are_rejected(fields):
    with pytest.raises(ValueError):lower({'expected':'Inspect or run',**fields},('mechanics',))


@pytest.mark.parametrize('step',[
    {'action':'discovery_call','value':'help','content':'{}'},
    {'action':'discovery_call','value':None},
    {'action':'discovery_call','value':'help mechanics\nlab status'},
    {'action':'discovery_call','value':'lab simulate mechanics "x"'},
])
def test_only_empty_body_help_or_status_is_read_only(step):
    assert not read_only(step)


def test_bounded_metadata_inspection_is_a_prerequisite_read_not_identity_certification():
    from jarvis.brain import navigation_step
    for command in ('lab assets inspect "'+'b'*32+'"','lab assets search "a generic vehicle 2030"'):
        step=lower({'operation':'run','command':command,'expected':'Read untrusted source metadata'})
        assert read_only(step) and navigation_step(step,{})
        assert not read_only({**step,'content':'{}'})
    for command in ('lab assets download "'+'b'*32+'"','lab assets inspect "https://example.com"',
                    'lab compare vehicle "input.json"','lab assets search "valid query"\nlab status'):
        assert not read_only({'action':'discovery_call','value':command})


def test_native_correction_explains_request_omission_without_rewriting_or_dispatch():
    from unittest.mock import Mock
    from jarvis.native_tools import plan
    rows=[{'action':'discovery_call','description':'Lab','lab_workflow':True,'parameters':parameters()}]
    command='lab assets inspect "'+'a'*32+'"'
    bad={'operation':'run','command':command,'request':{},'expected':'Read metadata'}
    good={key:value for key,value in bad.items() if key!='request'}
    def reply(arguments):
        return Mock(status_code=200,raise_for_status=Mock(),json=Mock(return_value={
            'done_reason':'stop','message':{'tool_calls':[{'function':{
                'name':'discovery_call','arguments':arguments}}]}}))
    client=Mock(post=Mock(side_effect=[reply(bad),reply(good)]))
    result=plan(client,'qwen3.5:9b','Plan.',{'goal':'Inspect an asset','tools':rows},{})
    assert client.post.call_count==2
    feedback=client.post.call_args_list[1].kwargs['json']['messages'][-1]['content']
    assert 'Omit the request field entirely' in feedback
    assert result['steps'][0]['value']==command
    assert result['steps'][0]['content']==''


def test_repeated_invalid_native_request_remains_bounded_and_never_becomes_an_action():
    from unittest.mock import Mock
    from jarvis.native_tools import plan
    rows=[{'action':'discovery_call','description':'Lab','lab_workflow':True,'parameters':parameters()}]
    response={'done_reason':'stop','message':{'tool_calls':[{'function':{'name':'discovery_call',
        'arguments':{'operation':'run','command':'lab status','request':{},'expected':'Read status'}}}]}}
    client=Mock(post=Mock(return_value=Mock(status_code=200,raise_for_status=Mock(),json=Mock(return_value=response))))
    with pytest.raises(ValueError,match='Omit the request field entirely'):
        plan(client,'qwen3.5:9b','Plan.',{'goal':'Inspect status','tools':rows},{})
    assert client.post.call_count==3  # Existing inference-only retry cap; no action dispatch.
