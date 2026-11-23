"""Standard-library-only native transport; usable in the existing brain worker.

No solver imports, planning, approval grants, filesystem access or execution.
"""
import json
import re

TOPICS=('mechanics','pendulum','study','dilation','vehicle')


def parameters(topics=TOPICS):
    properties={
        'operation':{'type':'string','enum':['help','run'],
            'description':'help reads the command menu or one input schema; run executes one supported Lab command.'},
        'expected':{'type':'string','minLength':1,'maxLength':500,
            'description':'Required: a short sentence describing the observable result of this one tool call.'},
        'command':{'type':'string','maxLength':1000,
            'description':'Required for run: an exact lab command from help. Commands such as lab status or lab assets inspect "UID" take no request field. Only input-file commands use a quoted "{request}" placeholder.'},
        'request':{'type':'object','additionalProperties':True,
            'description':'Omit this field entirely for status/search/inspect commands (not even {}). Supply it only when command contains the quoted "{request}" placeholder, using the input schema from help. Values remain unverified assumptions.'}}
    if topics:
        properties['topic']={'type':'string','enum':list(topics),
            'description':'For help, select one input schema; omit for the command menu.'}
    return {'type':'object','additionalProperties':False,'required':['operation','expected'],'properties':properties}


def lower(arguments,topics=TOPICS):
    if not isinstance(arguments,dict) or set(arguments)-{'operation','expected','topic','command','request'}:
        raise ValueError('Lab arguments must use operation, expected, command and request (object); topic is for help. Legacy value/content/folder fields are invalid.')
    operation=arguments.get('operation');expected=arguments.get('expected')
    if operation not in ('help','run'):
        raise ValueError('Lab operation must be the literal string help or run; command names and schema topics are separate fields.')
    if not isinstance(expected,str) or not 1<=len(expected.strip())<=500:
        raise ValueError('Lab expected is required: one nonempty sentence, at most 500 characters, describing this tool call result.')
    topic=arguments.get('topic')
    if 'topic' in arguments and topic not in topics:
        raise ValueError('Select a schema topic advertised by this session')
    if operation=='help':
        if set(arguments)-{'operation','expected','topic'}:raise ValueError('Help accepts only a topic and expected result')
        value='help'+(' '+topic if topic else '');content=''
    else:
        value=arguments.get('command')
        if (not isinstance(value,str) or not 1<=len(value)<=1000 or not re.match(r'^lab\s+',value,re.I)
                or '\r' in value or '\n' in value):raise ValueError('Run requires one bounded lab command from help')
        has_request='request' in arguments
        if has_request:
            if not isinstance(arguments['request'],dict):raise ValueError('request must be a JSON object')
            try:content=json.dumps(arguments['request'],allow_nan=False,separators=(',',':'))
            except (ValueError,TypeError,RecursionError):raise ValueError('request must be bounded finite JSON') from None
            if len(content.encode('utf-8'))>10000:raise ValueError('request exceeds10000 UTF-8 bytes')
        else:content=''
        if has_request and '{request}' not in value:
            raise ValueError('This command has no input-file placeholder. Omit the request field entirely, including an empty {}. '
                'Keep the command literal and its quoted search/inspect argument; do not replace that argument with a request object. No action was dispatched.')
        if not has_request and '{request}' in value:
            raise ValueError('This input-file command requires a request JSON object matching its help schema. No action was dispatched.')
        if value.count('{request}')>1 or (has_request and '"{request}"' not in value):
            raise ValueError('Use exactly one quoted "{request}" placeholder for the request JSON object. No action was dispatched.')
    return {'action':'discovery_call','value':value,'content':content,'expected':expected,
            'folder':'','browser':'chrome','find':'','platform':''}


def read_only(step):
    """Recognize bounded metadata reads; acquisition and simulations stay conservative.

    Source inspection establishes identity/license information. Requiring an LLM
    to certify that information *before reading it* prevents disambiguation.
    The existing source adapter still enforces fixed origins, bounds, source
    validation, feature flags and parent-goal identity checks after admission.
    """
    value=step.get('value')
    return (step.get('action')=='discovery_call' and step.get('content','')=='' and isinstance(value,str)
            and (value=='lab status' or re.fullmatch(r'help(?: (?:mechanics|pendulum|study|dilation|vehicle))?',value) is not None
                 or re.fullmatch(r'lab assets inspect "[a-f0-9]{32}"',value) is not None
                 or re.fullmatch(r'lab assets search "[^"\r\n]{4,240}"',value) is not None))


def arguments(step,topics=TOPICS):
    """Rehydrate verified history using the same schema as current native calls."""
    value=step.get('value','');content=step.get('content','')
    result={'expected':step.get('expected') or 'Read the retained Lab result'}
    if value=='help' or value.startswith('help '):
        result['operation']='help'
        if value!='help':result['topic']=value[5:]
    else:
        result.update(operation='run',command=value)
        if content:result['request']=json.loads(content)
    lower(result,topics)  # Never teach a history call the current executor would reject.
    return result
