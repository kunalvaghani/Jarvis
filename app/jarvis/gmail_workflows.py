"""API-first Gmail command workflows: read, speak, draft, send, trash and labels.

Every mailbox write is approved once, verified by readback and never replayed."""
from email.utils import parseaddr
import json
import re

from .clarification import TaskClarification
from .tools import ToolRegistry


class GmailResult(str):
    """Trusted completion type; displayed mail text cannot set task status."""


UnreadSearchResult = GmailResult  # Preserve the existing unread workflow contract.

# Leading verb -> operations that verb may legitimately produce.
VERBS = {**dict.fromkeys(('draft','compose','write','create','make'),'draft'),
         **dict.fromkeys(('update','edit','change','replace'),'update'),
         **dict.fromkeys(('read','show','find','search','list','check'),'read'),
         **dict.fromkeys(('speak','say','tell'),'speak'), 'send':'send',
         **dict.fromkeys(('delete','remove','trash','discard'),'delete'),
         **dict.fromkeys(('restore','recover','undelete'),'restore'),
         **dict.fromkeys(('mark','star','unstar'),'mark'), 'archive':'archive',
         **dict.fromkeys(('label','tag','move','put','group','organize','organise','sort'),'label')}
ALLOWED = {'draft':{'draft'}, 'update':{'update_draft'},
           'read':{'list','list_drafts','read','read_draft','list_labels','group','speak'},
           'speak':{'speak'}, 'send':{'send','send_draft'}, 'delete':{'trash','delete_draft'},
           'restore':{'restore'}, 'mark':{'mark'}, 'archive':{'archive'},
           'label':{'label','group','trash','archive'}}
OPERATIONS = set().union(*ALLOWED.values())
MESSAGE_WRITES = {'trash','restore','label','mark','archive'}
MARKS = {'read':([],['UNREAD']), 'unread':(['UNREAD'],[]), 'starred':(['STARRED'],[]),
         'unstarred':([],['STARRED']), 'important':(['IMPORTANT'],[]), 'not important':([],['IMPORTANT'])}
UNSUPPORTED = ('Gmail can read, speak, draft, send, delete to Trash, restore, label, archive, mark and group emails. '
               'Replying and forwarding are not supported yet; I can send a new email or save a draft instead.')


def gmail_request(goal):
    """Route email operations by their object, never by words inside code/text."""
    return bool(re.match(
        r'^(?:please\s+)?(?:draft|compose|write|create|make|read(?:\s+(?:aloud|out))?|show|find|search|list|check|speak|say|tell|'
        r'update|edit|change|replace|send|delete|remove|trash|discard|restore|recover|undelete|reply(?:\s+to)?|forward|mark|archive|'
        r'star|unstar|label|tag|move|put|group|organi[sz]e|sort)\s+'
        r'(?:(?:me|for|an?|the|my|all|new|latest|last|recent|newest|unread|every|this|that|these|those|'
        r'first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th)\s+)*'
        r'(?:gmail|e-?mails?|mails?|inbox|(?:gmail\s+|email\s+)?drafts?|(?:gmail|email)\s+labels)\b(?!\.[A-Za-z0-9]|[/\\])',
        str(goal).strip(),re.I))


def spoken_addresses(goal):
    """Speech recognition writes 'name at gmail dot com'; restore the literal address."""
    def join(match):
        return match[1]+'@'+re.sub(r'\s+dot\s+','.',match[2],flags=re.I)
    return re.sub(r'\b([A-Za-z0-9._%+-]+)\s+at\s+([A-Za-z0-9-]+(?:\s+dot\s+[A-Za-z]{2,})+)\b',join,str(goal),flags=re.I)


def literal(value):
    value=value.strip()
    quoted=re.fullmatch(r'["\'‘“](.*)["\'’”][.!?]*',value,re.S)
    return quoted[1].strip() if quoted else value.strip('"\'‘’“”').strip()


def quoted_subject(goal):
    found=re.search(r'\bsubject\s+["\'‘“](.+?)["\'’”](?=\s|[.,;!?]|$)',goal,re.I)
    return found[1] if found else ''


def explicit_request(goal):
    """Exact common phrases avoid inference; unsupported tails are never dropped."""
    clean=re.sub(r'^(?:please\s+)+','',goal.strip(),flags=re.I)
    base={'query':'','target':'','reference':'','subject':'','body':'','to':'','label':'','fields':[],'question':''}
    if re.fullmatch(r'(?:list|show|check|find)(?: me)? (?:my |the |recent |latest )?(?:gmail |e-?mail )?drafts[.!?]*',clean,re.I):
        return {**base,'operation':'list_drafts'}
    if re.fullmatch(r'(?:show|list|check|find)(?: me)? (?:my |the |recent |latest |unread )?(?:gmail |e-?mail )?(?:e-?mails?|inbox)[.!?]*',clean,re.I):
        return {**base,'operation':'list','query':'is:unread' if 'unread' in clean.casefold() else 'in:inbox'}
    if re.fullmatch(r'read (?:my |the )?(?:latest|last|newest) (?:gmail )?e-?mail[.!?]*',clean,re.I):
        return {**base,'operation':'read','query':'in:inbox','reference':'latest'}
    match=re.fullmatch(r'read (?:the )?(first|second|third|fourth|fifth|[1-5](?:st|nd|rd|th)?) (?:gmail )?e-?mail[.!?]*',clean,re.I)
    if match:return {**base,'operation':'read','reference':match[1].casefold()}
    match=re.fullmatch(r'read (?:the |my )?(?:gmail |email )?(draft|email|e-mail) (?:with )?subject\s+(.+)',clean,re.I)
    if match:return {**base,'operation':'read_draft' if match[1].casefold()=='draft' else 'read','target':literal(match[2])}
    match=re.fullmatch(r'(?:draft|compose|write|create|make)\s+(?:(?:an?|new)\s+)?(?:gmail\s+)?(?:e-?mail|draft)'
                      r'(?:\s+to\s+([^\s,]+))?\s+with\s+subject\s+(["\'‘“].*?["\'’”]|[^"\'‘“].+?)\s+and\s+body\s+(.+?)'
                      r'(?:[,.;]?\s+leave\s+(?:the\s+)?(?:recipient|to)(?:\s+field)?\s+blank[.!?]*)?',clean,re.I|re.S)
    if match:
        # Only literal quoted body text has unambiguous boundaries. A trailing
        # recipient or another instruction goes to the text interpreter rather
        # than being silently included in the body or dropped.
        if not re.fullmatch(r'["\'‘“].*["\'’”][.!?]*',match[3].strip(),re.S):return None
        recipient=match[1] or ''
        if recipient and re.search(r'leave\s+(?:the\s+)?(?:recipient|to).*blank',clean,re.I):
            raise TaskClarification('You supplied a recipient and also asked to leave it blank. Which should I use?', 'gmail')
        return {**base,'operation':'draft','subject':literal(match[2]),'body':literal(match[3]),'to':recipient,'fields':['subject','body','to']}
    match=re.fullmatch(r'(?:update|edit|change) (?:the |my )?(?:gmail |email )?draft (?:with )?subject\s+(.+?)'
                      r'\s+(?:to have|with|and set|set|change) (?:the )?(body|subject)\s+(?:to\s+)?(.+)',clean,re.I|re.S)
    if match:return {**base,'operation':'update_draft','target':literal(match[1]),match[2].casefold():literal(match[3]),'fields':[match[2].casefold()]}
    return action_request(clean,base)


def action_request(clean,base):
    """Literal speak/send/delete/label phrases; anything looser goes to the interpreter."""
    ref=r'(?:the |my )?(latest|last|newest|first|second|third|fourth|fifth|[1-5](?:st|nd|rd|th)?)'
    mail=r'(?:gmail )?e-?mail'
    subject=r' (?:with )?subject\s+'
    sender=r'(?:all )?(?:my |the )?(?:gmail )?e-?mails from (\S+@\S+?)'
    into=r'\s+(?:as|to|into|in|under|with)(?: the)?(?: label| folder)?\s+'
    def reference(word):
        word=word.casefold()
        return 'latest' if word in {'latest','last','newest'} else word
    def selected(match,operation,**extra):
        return {**base,'operation':operation,'reference':reference(match[1]),'query':'in:inbox',**extra}
    # Speak / read aloud.
    match=(re.fullmatch(r'(?:speak|say|read (?:aloud|out)|tell me)(?: me)? '+ref+' '+mail+r'(?: aloud| out loud)?[.!?]*',clean,re.I)
           or re.fullmatch(r'read '+ref+' '+mail+r' (?:aloud|out loud)[.!?]*',clean,re.I))
    if match:return selected(match,'speak')
    match=re.fullmatch(r'(?:speak|read (?:aloud|out)) (?:the |my )?'+mail+subject+r'(.+)',clean,re.I)
    if match:return {**base,'operation':'speak','target':literal(match[1])}
    match=re.fullmatch(r'(?:speak|say|tell me|read (?:aloud|out))(?: me)? (?:my |the |all )?(?:(unread|new|inbox|latest|recent) )?'
                       r'(?:gmail )?(?:e-?mails|inbox|mail)(?: aloud| out loud)?[.!?]*',clean,re.I)
    if match:return {**base,'operation':'speak','query':'is:unread' if (match[1] or '').casefold() in {'unread','new'} else 'in:inbox'}
    # Send.
    match=re.fullmatch(r'send (?:an? |new )?(?:gmail )?e-?mail to (\S+@\S+?(?:\s*,\s*\S+@\S+?)*) with subject\s+'
                       r'(["\'‘“].*?["\'’”]|[^"\'‘“].+?)\s+and\s+body\s+(["\'‘“].*["\'’”])[.!?]*',clean,re.I|re.S)
    if match:return {**base,'operation':'send','to':match[1],'subject':literal(match[2]),'body':literal(match[3]),'fields':['subject','body','to']}
    match=re.fullmatch(r'send (?:the |my )?(?:gmail |email )?draft'+subject+r'(.+)',clean,re.I)
    if match:return {**base,'operation':'send_draft','target':literal(match[1])}
    if re.fullmatch(r'send (?:the |that |this |my )?(?:last |latest )?(?:gmail |email )?draft[.!?]*',clean,re.I):
        return {**base,'operation':'send_draft','reference':'last draft'}
    # Delete (Trash) and restore.
    match=re.fullmatch(r'(?:delete|trash|remove) '+ref+' '+mail+r'[.!?]*',clean,re.I)
    if match:return selected(match,'trash')
    match=re.fullmatch(r'(?:delete|discard|remove) (?:the |my )?(?:gmail |email )?draft'+subject+r'(.+)',clean,re.I)
    if match:return {**base,'operation':'delete_draft','target':literal(match[1])}
    match=re.fullmatch(r'(?:delete|trash|remove) (?:the |my )?'+mail+subject+r'(.+)',clean,re.I)
    if match:return {**base,'operation':'trash','target':literal(match[1])}
    match=re.fullmatch(r'(?:delete|trash|remove) '+sender+r'[.!?]*',clean,re.I)
    if match:return {**base,'operation':'trash','query':'from:'+match[1]}
    match=re.fullmatch(r'(?:restore|recover|undelete) (?:the |my )?'+mail+subject+r'(.+)',clean,re.I)
    if match:return {**base,'operation':'restore','target':literal(match[1])}
    if re.fullmatch(r'(?:restore|recover|undelete) (?:the |my )?(?:last |latest )?(?:deleted |trashed )?'+mail+r'[.!?]*',clean,re.I):
        return {**base,'operation':'restore','reference':'latest','query':'in:trash'}
    # Mark, star and archive.
    match=re.fullmatch(r'mark '+ref+' '+mail+r' as (read|unread|starred|important|not important)[.!?]*',clean,re.I)
    if match:return selected(match,'mark',label=match[2].casefold())
    if re.fullmatch(r'mark (?:all )?(?:my |the )?unread (?:gmail )?e-?mails as read[.!?]*',clean,re.I):
        return {**base,'operation':'mark','query':'is:unread','label':'read'}
    match=re.fullmatch(r'(star|unstar|archive) '+ref+' '+mail+r'[.!?]*',clean,re.I)
    if match:
        verb=match[1].casefold()
        return {**base,'operation':'archive' if verb=='archive' else 'mark','reference':reference(match[2]),'query':'in:inbox',
                'label':'' if verb=='archive' else 'starred' if verb=='star' else 'unstarred'}
    match=re.fullmatch(r'(star|unstar|archive) (?:the |my )?'+mail+subject+r'(.+)',clean,re.I)
    if match:
        verb=match[1].casefold()
        return {**base,'operation':'archive' if verb=='archive' else 'mark','target':literal(match[2]),
                'label':'' if verb=='archive' else 'starred' if verb=='star' else 'unstarred'}
    # Labels (grouping into folders).
    match=re.fullmatch(r'(?:label|tag|move|put|group) '+ref+' '+mail+into+r'(.+?)(?: label| folder)?[.!?]*',clean,re.I)
    if match:return selected(match,'label',label=literal(match[2]))
    match=re.fullmatch(r'(?:label|tag|move|put|group) (?:the |my )?'+mail+subject+r'(["\'‘“].+?["\'’”])'+into+r'(.+?)(?: label| folder)?[.!?]*',clean,re.I)
    if match:return {**base,'operation':'label','target':literal(match[1]),'label':literal(match[2])}
    match=re.fullmatch(r'(?:label|tag|move|put|group) '+sender+into+r'(.+?)(?: label| folder)?[.!?]*',clean,re.I)
    if match:return {**base,'operation':'label','query':'from:'+match[1],'label':literal(match[2])}
    match=re.fullmatch(r'(?:group|organi[sz]e|sort|show|list) (?:all )?(?:my |the )?(?:(unread|inbox|latest|recent) )?(?:gmail )?e-?mails by sender[.!?]*',clean,re.I)
    if match:return {**base,'operation':'group','query':'is:unread' if (match[1] or '').casefold()=='unread' else 'in:inbox'}
    if re.fullmatch(r'(?:list|show|check)(?: me)? (?:my |all |the )?(?:gmail|email) labels[.!?]*',clean,re.I):
        return {**base,'operation':'list_labels'}
    return None


def validate_request(request,goal):
    from .gmail_api import raw_message, recipients
    if not isinstance(request,dict):raise ValueError('Invalid Gmail request.')
    if request.get('question'):raise TaskClarification(str(request['question'])[:500],'gmail')
    request={'label':'',**request}
    operation=request.get('operation')
    if operation not in OPERATIONS:raise TaskClarification(UNSUPPORTED,'gmail')
    verb=re.match(r'^(?:please\s+)?([a-z]+)',goal.strip(),re.I)[1].casefold()
    if operation not in ALLOWED.get(VERBS.get(verb),set()):
        raise ValueError('Gmail interpretation changed the requested operation; no action issued.')
    for key in ('query','target','reference','subject','body','to','label'):
        if not isinstance(request.get(key),str):raise ValueError('Invalid Gmail request field: '+key)
    fields=request.get('fields')
    if not isinstance(fields,list) or set(fields)-{'subject','body','to'}:raise ValueError('Invalid Gmail replacement fields.')
    if len(request['query'])>500 or len(request['body'])>10000 or len(request['label'])>100:raise ValueError('Gmail request exceeds the size budget.')
    if request['target'] and request['target'].casefold() not in literal(goal).casefold():
        raise ValueError('Gmail target must be explicitly named by the user.')
    if operation=='draft':
        if not re.match(r'^(?:please\s+)?(?:draft|compose|write|create|make)\b',goal.strip(),re.I):raise ValueError('Draft creation was not requested.')
        raw_message({key:request[key] for key in ('subject','body','to')})
    if operation=='update_draft':
        if not re.match(r'^(?:please\s+)?(?:update|edit|change|replace)\b',goal.strip(),re.I) or not re.search(r'\bdraft\b',goal,re.I):
            raise TaskClarification('Only drafts can be edited. Name the Gmail draft and the fields you want to change.','gmail')
        if not fields:raise TaskClarification('Which draft fields should I change: subject, body or recipient?','gmail')
    if operation=='send':
        if not request['to'].strip():raise TaskClarification('Who should I send it to? Say the exact email address.','gmail')
        if any(address.casefold() not in goal.casefold() for address in recipients(request['to']).split(', ')):
            raise TaskClarification('Provide the exact recipient email address; I will not guess an address from a name.','gmail')
        if not request['subject'].strip() or not request['body'].strip():
            raise TaskClarification('What should the email say? Give a topic or the exact subject and body.','gmail')
        raw_message({key:request[key] for key in ('subject','body','to')},send=True)
    elif 'to' in fields and request['to'] and request['to'] not in goal:
        raise TaskClarification('Provide the exact recipient email address; I will not guess an address from a name.','gmail')
    if operation in {'send_draft','delete_draft'} and not (request['target'] or request['reference']=='last draft'):
        raise TaskClarification('Which Gmail draft? Give its exact subject.','gmail')
    if operation in MESSAGE_WRITES and not (request['reference'] or request['target'] or request['query'].strip()):
        raise TaskClarification('Which emails? Say for example "the latest email", "the first email" or "emails from name@example.com".','gmail')
    if operation=='mark' and request['label'] not in MARKS:
        raise TaskClarification('Mark it as read, unread, starred, unstarred, important or not important?','gmail')
    if operation=='label':
        if not request['label'].strip():raise TaskClarification('Which label should I use?','gmail')
        if request['label'].casefold() not in goal.casefold():raise TaskClarification('Say the exact label name to use.','gmail')
        if request['label'].casefold() in {'trash','bin','the trash','deleted'}:request={**request,'operation':'trash','label':''}
    return request


def sender_name(value):
    name,address=parseaddr(str(value))
    return ' '.join((name or address or 'Unknown sender').split())[:120]


def spoken_message(message):
    """A listener-friendly rendering: sender name, subject, body without quoted replies."""
    lines=[line for line in message['body'].splitlines() if not line.lstrip().startswith('>')]
    body=re.split(r'\n\s*On .{5,200} wrote:\s*\n',"\n".join(lines),maxsplit=1)[0]
    body=' '.join(body.split())
    if len(body)>1500:body=body[:1500].rsplit(' ',1)[0]+'. The rest is in the transcript.'
    return ('Email from '+sender_name(message['from'])+'. Subject: '+(message['subject'] or 'no subject')+'.\n'
            +(body or 'The email has no text.'))


def run_gmail(brain,goal,cancelled):
    """All supported mail requests use API dispatch, with writes approved once."""
    if not gmail_request(goal):return None
    goal=spoken_addresses(goal)
    # Preserve the separately configured SMTP sender's existing planner/approval
    # path for generic email requests that do not name Gmail.
    if (re.match(r'^(?:please\s+)?send\b',goal.strip(),re.I)
            and not re.search(r'\bgmail\b',goal,re.I)
            and 'send_email' in {row['action'] for row in ToolRegistry(brain.actions).catalog(goal)}):
        return None
    if re.match(r'^(?:please\s+)?(?:reply|forward)\b',goal.strip(),re.I):raise TaskClarification(UNSUPPORTED,'gmail')
    if unread_request(goal):
        answer=run_unread(brain,goal,cancelled)
        # The exact unread workflow's fresh observations are the selection source.
        brain.actions.gmail_message_results=json.loads(brain.tool_observations[-1]['result'])['messages']
        return answer
    if cancelled():raise ValueError('Task cancelled before Gmail request.')
    # This domain runner needs the whole API workflow, not a top-N generic
    # ranking that might hide prerequisites such as draft lookup.
    registry=ToolRegistry(brain.actions)
    names={row['action'] for row in registry.catalog('gmail')+registry.search('gmail',limit=30)}
    if 'gmail_api_list' not in names:
        raise TaskClarification('Gmail API is not available in this task. Connect it locally and reload Jarvis after approval. No email action issued.','gmail_api')
    request=explicit_request(goal)
    if request is None:
        brain.actions.report('brain','Interpreting Gmail request using local text only')
        request=brain.client.request('gmail_request',cancelled,goal=goal)
    request=validate_request(request,goal)
    if cancelled():raise ValueError('Task cancelled before Gmail dispatch.')
    completed=[]
    def call(name,args=None,value='inspect'):
        if name not in names:raise TaskClarification('Required Gmail API tool is outside this task scope: '+name+'. Reconnect Gmail API if it was connected before this update.','gmail_api')
        step={'action':name,'value':value,'content':json.dumps(args or {},ensure_ascii=False),
              'expected':'Verify Gmail API response','browser':'chrome','folder':'','find':'','platform':''}
        brain.validate_remaining([step],goal)
        brain.save_plan([step],completed,'Direct Gmail API workflow')
        brain.actions.report('plan',name)
        # No automatic retry: uncertain mutations cannot be issued again.
        result=brain.dispatch(step,cancelled)
        if cancelled():raise ValueError('Task cancelled after Gmail dispatch; inspect before another write.')
        data=json.loads(result.evidence)
        completed.append(step)
        brain.tool_observations.append({'action':name,'value':value,'result':result.evidence,'verified':True})
        brain.checkpoint('verified',action=name,target=value,evidence='Gmail API response received')
        return data
    def subject_query(target):
        if any(char in target for char in ('"','\r','\n')):raise TaskClarification('Use a plain single-line subject without embedded quotes.','gmail')
        return 'subject:"'+target+'"'
    def select_draft():
        target=request['target']
        if target:
            listing=call('gmail_api_list_drafts',{'query':subject_query(target),'limit':10})
            if listing.get('next_page_available'):raise TaskClarification('More than ten drafts match; narrow the subject before editing.','gmail')
            matches=[]
            for row in listing['drafts']:
                item=call('gmail_api_read_draft',value=row['id'])
                if item['subject'].casefold()==target.casefold():matches.append(item)
            if len(matches)!=1:raise TaskClarification('I need one exact matching draft; found '+str(len(matches))+'. Use its full subject.','gmail')
            return matches[0]
        draft_id=getattr(brain.actions,'gmail_last_draft_id',None)
        if request['reference']=='last draft' and draft_id:
            return call('gmail_api_read_draft',value=draft_id)
        raise TaskClarification('Which Gmail draft should I use? Give its exact subject.','gmail')
    def select_messages(default='in:inbox',limit=5):
        """Ordinals use the latest listed IDs; subjects must match exactly one message."""
        cached=getattr(brain.actions,'gmail_message_results',[])
        ordinal={'first':0,'second':1,'third':2,'fourth':3,'fifth':4}
        reference=request['reference']
        if reference and reference!='latest':
            index=ordinal.get(reference,int(reference[0])-1 if reference[0:1].isdigit() else -1)
            if not 0<=index<len(cached):raise TaskClarification('List your emails first, then choose an item from those results.','gmail')
            return [cached[index]],False
        query=request['query'] or default
        if request['target']:query=('in:trash ' if default=='in:trash' else '')+subject_query(request['target'])
        listing=call('gmail_api_list',{'query':query,'limit':1 if reference=='latest' else limit,'summaries':True})
        rows=listing['messages'];more=listing.get('next_page_available',False)
        brain.actions.gmail_message_results=rows
        if request['target']:
            rows=[row for row in rows if row['subject'].casefold()==request['target'].casefold()]
            if len(rows)!=1 or more:raise TaskClarification('Use a more specific email subject; I could not select one unique message.','gmail')
        return rows,more
    def line(row):return sender_name(row['from'])+' — '+(' '.join(row['subject'].split())[:200] or '(no subject)')
    operation=request['operation']
    readonly_note=True
    if operation=='draft':
        data=call('gmail_api_draft',{key:request[key] for key in ('subject','body','to')},'new')
        if not all(data.get(key) is True for key in ('subject_verified','body_verified')) or data.get('sent') is not False:raise ValueError('Draft readback was not verified.')
        brain.actions.gmail_last_draft_id=data['draft_id']
        answer='Draft saved in Gmail. Subject: '+request['subject']+'. '+('Recipient: '+request['to'] if request['to'] else 'Recipient left blank.')+' Nothing was sent.'
        readonly_note=False
    elif operation=='send':
        data=call('gmail_api_send',{key:request[key] for key in ('to','subject','body')},'new')
        if data.get('sent') is not True or data.get('subject_verified') is not True:raise ValueError('Send readback was not verified.')
        answer='Email sent to '+data['to']+'. Subject: '+request['subject']+'. It is in your Sent mail.'
        readonly_note=False
    elif operation in {'read_draft','update_draft','send_draft','delete_draft'}:
        draft=select_draft()
        brain.actions.gmail_last_draft_id=draft['id']
        readonly_note=False
        if operation=='update_draft':
            replacement={key:request[key] if key in request['fields'] else draft[key] for key in ('subject','body','to')}
            replacement['expected_sha256']=draft['sha256']
            data=call('gmail_api_update_draft',replacement,draft['id'])
            if not all(data.get(key) is True for key in ('subject_verified','body_verified')) or data.get('sent') is not False:raise ValueError('Updated draft readback was not verified.')
            answer='Gmail draft updated and read back successfully. Unchanged subject/body/recipient fields were preserved. Nothing was sent.'
        elif operation=='send_draft':
            data=call('gmail_api_send_draft',{'expected_sha256':draft['sha256']},draft['id'])
            if data.get('sent') is not True:raise ValueError('Draft send was not verified.')
            brain.actions.gmail_last_draft_id=None
            answer='Draft "'+draft['subject']+'" sent to '+data['to']+'. It is in your Sent mail.'
        elif operation=='delete_draft':
            data=call('gmail_api_delete_draft',{'expected_sha256':draft['sha256']},draft['id'])
            if data.get('deleted') is not True:raise ValueError('Draft deletion was not verified.')
            brain.actions.gmail_last_draft_id=None
            answer='Draft "'+draft['subject']+'" deleted. Nothing was sent.'
        else:answer='Gmail draft: '+draft['subject']+'\nTo: '+(draft['to'] or '(blank)')+'\n'+draft['body']
    elif operation=='list_drafts':
        listing=call('gmail_api_list_drafts',{'query':request['query'],'limit':5})
        drafts=[call('gmail_api_read_draft',value=row['id']) for row in listing['drafts']]
        answer='Gmail drafts:\n'+'\n'.join(str(i)+'. '+row['subject'] for i,row in enumerate(drafts,1)) if drafts else 'No matching Gmail drafts found.'
        if listing.get('next_page_available'):answer+='\nMore drafts are available; this lists at most five.'
    elif operation=='list_labels':
        data=call('gmail_api_list_labels')
        labels=sorted(row['name'] for row in data['labels'] if row['type']=='user')
        answer='Your Gmail labels: '+', '.join(labels)+'.' if labels else 'You have no custom Gmail labels yet.'
    elif operation in MESSAGE_WRITES:
        single=bool(request['reference'] or request['target'])
        rows,more=select_messages('in:trash' if operation=='restore' else 'in:inbox',5 if single else 25)
        readonly_note=False
        if not rows:answer='No matching emails found. Nothing was changed.'
        else:
            args={'ids':[row['id'] for row in rows],'preview':[line(row) for row in rows]}
            moving=re.match(r'^(?:please\s+)?move\b',goal.strip(),re.I) and request['label'].upper()!='INBOX'
            if operation=='trash':tool='gmail_api_trash'
            elif operation=='restore':tool='gmail_api_untrash'
            else:
                tool='gmail_api_modify_labels'
                add,remove=(([],['INBOX']) if operation=='archive' else MARKS[request['label']] if operation=='mark'
                            else ([request['label']],['INBOX'] if moving else []))
                args.update({'add':add,'remove':remove})
            data=call(tool,args,'selected')
            if data.get('changed')!=len(rows):raise ValueError('Gmail change was not verified for every selected email.')
            count=str(len(rows))+(' email' if len(rows)==1 else ' emails')
            summary='\n'.join('- '+row for row in args['preview'])
            if operation=='trash':
                answer='Moved '+count+' to Trash. You can restore them for 30 days.\n'+summary
                trashed=set(args['ids'])
                brain.actions.gmail_message_results=[row for row in getattr(brain.actions,'gmail_message_results',[]) if row['id'] not in trashed]
            elif operation=='restore':answer='Restored '+count+' from Trash.\n'+summary
            elif operation=='archive':answer='Archived '+count+'. They stay in All Mail.\n'+summary
            elif operation=='mark':answer='Marked '+count+' as '+request['label']+'.\n'+summary
            else:
                answer=('Moved ' if moving else 'Labelled ')+count+(' to "' if moving else ' as "')+request['label']+'".'
                if data.get('created_labels'):answer+=' Created the new label "'+request['label']+'".'
                answer+='\n'+summary
            if more:answer+='\nMore matching emails remain; this changed at most 25. Ask again to continue.'
    elif operation=='group':
        rows,more=select_messages(request['query'] or 'in:inbox',25)
        groups={}
        for row in rows:groups.setdefault(sender_name(row['from']),[]).append(' '.join(row['subject'].split())[:120] or '(no subject)')
        ordered=sorted(groups.items(),key=lambda item:-len(item[1]))
        answer=('Your '+str(len(rows))+' latest '+('unread ' if 'unread' in (request['query'] or '') else '')+'emails grouped by sender:\n'
                +'\n'.join(name+' ('+str(len(subjects))+'): '+'; '.join(subjects[:5])+('; …' if len(subjects)>5 else '') for name,subjects in ordered)
                if rows else 'No matching emails found.')
        if more:answer+='\nOlder emails were not included; this groups the latest 25.'
    elif operation=='speak':
        readonly_note=False
        if request['reference'] or request['target']:
            rows,_=select_messages()
            answer='\n\n'.join(spoken_message(call('gmail_api_read',value=row['id'])) for row in rows) or 'No matching emails found.'
        else:
            query=request['query'] or 'in:inbox'
            rows,more=select_messages(query,5)
            kind='unread ' if 'unread' in query else ''
            words=('First','Second','Third','Fourth','Fifth')
            answer=('Here are your '+str(len(rows))+' latest '+kind+'emails.\n'
                    +'\n'.join(words[i]+', from '+sender_name(row['from'])+': '+(' '.join(row['subject'].split()) or 'no subject')+'.' for i,row in enumerate(rows))
                    if rows else 'You have no '+kind+'emails right now.')
            if more:answer+='\nThere are more. Say "read aloud the first email" to hear one in full.'
    else:
        rows,more=select_messages()
        if operation=='read':
            messages=[call('gmail_api_read',value=row['id']) for row in rows]
            answer='\n\n'.join('From: '+row['from']+'\nTo: '+row.get('to','')+'\nSubject: '+row['subject']+'\n'+row['body']+
                                ('\n[Body truncated to the local display budget.]' if row.get('body_truncated') else '') for row in messages) or 'No matching emails found.'
        else:
            answer='\n'.join(str(i)+'. '+row['from']+' — '+row['subject'] for i,row in enumerate(rows,1)) or 'No matching emails found.'
            if more:answer+='\nMore results are available; this lists at most five.'
    if readonly_note:answer+='\nNo emails were changed or marked as read.'
    brain.save_plan([],completed,'Gmail API workflow verified')
    brain.checkpoint('goal_verified',source='gmail_api_workflow',evidence='Requested Gmail API operation and readback verified')
    return GmailResult(answer)


def unread_request(goal):
    # Full match prevents dropping additional filters, body reads or write requests.
    return bool(re.fullmatch(
        r'(?:please\s+)?(?:find|show|list|check)(?:\s+me)?\s+'
        r'(?:(?:my|the|all)\s+)?unread\s+(?:gmail\s+)?(?:e-?mails?|mail|messages in gmail)[.!?]*',
        str(goal).strip(), re.I))


def run_unread(brain, goal, cancelled):
    """One bounded API search via the standard dispatcher, no desktop or inference."""
    if not unread_request(goal):return None
    if cancelled():raise ValueError('Task cancelled before Gmail search.')
    if 'gmail_api_list' not in {row['action'] for row in ToolRegistry(brain.actions).catalog(goal)}:
        raise TaskClarification('Gmail API is not available in this task. Connect it locally and reload Jarvis after approval; no mailbox messages were read.', 'gmail_api')
    step={'action':'gmail_api_list','value':'unread emails','browser':'chrome',
          'folder':'','find':'','platform':'',
          'content':json.dumps({'query':'is:unread','limit':5,'summaries':True}),
          'expected':'Bounded unread message sender and subject metadata returned by Gmail API'}
    brain.validate_remaining([step],goal)
    brain.actions.report('brain','Searching unread emails through Gmail API')
    brain.actions.report('plan','gmail_api_list is:unread (metadata only)')
    brain.save_plan([step],[], 'Direct read-only unread Gmail search')
    brain.checkpoint('planned',evidence='gmail_api_list is:unread')
    result=brain.dispatch(step,cancelled)
    if cancelled():raise ValueError('Task cancelled after Gmail search; no further action.')
    evidence=json.loads(result.evidence)
    rows=evidence.get('messages')
    if not isinstance(rows,list) or len(rows)>5 or evidence.get('content_is_untrusted') is not True:
        raise ValueError('Unread search returned incomplete or invalid metadata.')
    if any(not isinstance(row,dict) or not isinstance(row.get('unread'),bool)
           or any(not isinstance(row.get(key),str) for key in ('id','from','subject','date')) for row in rows):
        raise ValueError('Unread search metadata could not be verified.')
    # Another client can change UNREAD between search and metadata read.
    unread=[row for row in rows if row['unread']]
    brain.tool_observations.append({'action':step['action'],'value':step['value'],
                                    'result':result.evidence,'verified':True})
    brain.save_plan([], [step], 'Gmail API metadata verified')
    brain.checkpoint('verified', action=step['action'], target='unread emails',
                     evidence='Search and bounded metadata reads succeeded; no mailbox mutation')
    brain.checkpoint('goal_verified',source='gmail_api_metadata',evidence='Unread search result verified')
    def text(value):return ' '.join(value.split())[:200]
    if unread:
        answer='Here are '+str(len(unread))+' unread emails from your connected Gmail account:\n'
        answer+='\n'.join(str(index)+'. '+(text(row['from']) or 'Unknown sender')+' — '+
                          (text(row['subject']) or '(no subject)') for index,row in enumerate(unread,1))
    else:
        answer=('No unread emails were found in your connected Gmail account.' if not rows
                else 'The matched emails are no longer unread; their status changed during the search.')
    if evidence.get('next_page_available'):answer+='\nMore unread search results are available; this search shows at most five.'
    return UnreadSearchResult(answer+'\nNo emails were changed or marked as read.')
