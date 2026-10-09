"""Typed equivalents of the command reference, inside checked source scope."""
import base64
import json
from pathlib import Path

from .claude_code_guard import decide
from .command_reference import search


def execute(files, name, args, processes):
    if name=='command_reference':return search(args.get('query',''))
    if name=='read_slice':
        observed=files.call('Read',{'file_path':args['file_path']});lines=observed['content'].splitlines()
        count=min(400,max(1,int(args.get('count',80))))
        start=max(0,len(lines)-count) if args.get('tail') else max(0,int(args.get('start',1))-1)
        return {'path':observed['path'],'sha256':observed['sha256'],'total_lines':len(lines),
                'lines':[{'line':i+1,'text':line} for i,line in enumerate(lines[start:start+count],start)]}
    if name in {'parse_json','encode_base64','source_transform','copy_source'}:
        observed=files.call('Read',{'file_path':args['file_path']});text=observed['content']
        if name=='parse_json':
            value=json.loads(text)
            for field in str(args.get('field','')).split('.') if args.get('field') else []:
                value=value[int(field)] if isinstance(value,list) else value[field]
            return {'value':value}
        if name=='encode_base64':return {'base64':base64.b64encode(text.encode()).decode(),'encoding':'UTF-8 source text'}
        if name=='copy_source':
            return files.call('Write',{'file_path':args['destination'],'content':text})
        operation=args['operation'];content=args.get('content','')
        if operation=='append':new=text+content
        elif operation=='prepend':new=content+text
        elif operation=='remove_lines':
            targets=args.get('lines',[])
            if not isinstance(targets,list) or not targets or any(not isinstance(s,str) for s in targets):raise ValueError('Use exact current line text, never a broad regex deletion.')
            source=text.splitlines(keepends=True)
            if any(sum(line.rstrip('\r\n')==target for line in source)!=1 for target in targets):raise ValueError('Each removed source line must match exactly once.')
            new=''.join(line for line in source if line.rstrip('\r\n') not in targets)
        else:raise ValueError('Use append, prepend or remove_lines; replacement uses Edit.')
        return files.call('Write',{'file_path':args['file_path'],'content':new})
    if name=='search_regex':
        from .coder import project_files
        pattern=args['pattern']
        if not isinstance(pattern,str) or not 1<=len(pattern)<=200:raise ValueError('Use a bounded regex.')
        names=project_files(files.root,limit=161)
        if len(names)>160:raise ValueError('Narrow the selected project before searching.')
        for path in names:decide(files.root,'Read',{'file_path':path})
        if not names:return {'output':'','matches':False}
        from .coding_programs import locate
        binary=locate('rg')
        if not binary:raise ValueError('Ripgrep is not installed; use literal Grep or install it through the explicit setup workflow.')
        return processes.start([binary,'-n','--no-heading',*(['-i'] if args.get('ignore_case') else []),'--',pattern,*names],timeout_seconds=15,resolved=True)
    raise ValueError('Unknown typed command operation.')
