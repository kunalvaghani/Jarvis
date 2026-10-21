from pathlib import Path
p=Path(__file__).resolve().parents[2]/'integrations/jarvis-connectors/connectors/apps/blender'
import sys, json
sys.path.insert(0,str(p.resolve()))
from blender_connector.catalog import ACTIONS,MISSING
lines=['"""Generated typed tools; regenerate with generate_adapter.py, never model-generated code."""','from adapter import BlenderAdapter, tool','class BlenderConnector(BlenderAdapter):']
rows=[]
for name,spec in ACTIONS.items():
    args=[]; mapping=[]
    for key,arg in spec.fields.items():
        typ={'str':'str','int':'int','float':'float','bool':'bool','list':'list[dict]' if key=='steps' else 'list[list[int]]' if key=='faces' else 'list[list[float]]' if key=='points' or (key=='vertices' and arg.kind=='list') else 'list[int]' if key=='indices' else 'list[float]' if key not in {'names','objects','materials'} else 'list[str]','dict':'dict','json':'dict'}[arg.kind]
        default=arg.default
        expression=key
        if default is None:
            if arg.kind=='list': default=[]; expression=f'({key} or None)'
            elif arg.kind=='bool': typ='str';default='unchanged';expression=f"(None if {key} == 'unchanged' else {{'true':True,'false':False}}[{key}])"
            elif arg.kind in ('float','int'): typ='str';default='';expression=f'({arg.kind}({key}) if {key} else None)'
        if arg.kind=='json':
            # JSON-valued properties use an explicit {value: ...} envelope within the host schema subset.
            expression=f"{key}.get('value')"
        args.append(f'{key}: {typ}'+('' if default is MISSING else ' = '+repr(default)))
        mapping.append(repr(key)+': '+expression)
    args += ["expected_scope: str = ''", "host_authorization: str = ''"]
    access='read' if spec.risk=='read' else 'write'
    lines += [f"    @tool(access='{access}', destructive={spec.risk in ('filesystem','destructive')})",f"    def blender_{name}(self, *, {', '.join(args)}) -> dict:",f'        """{spec.description}. Category {spec.group}; risk {spec.risk}. Empty optional arrays omit changes."""',f"        return self._run({name!r}, {{{', '.join(mapping)}}}, expected_scope, host_authorization)"]
    rows.append({'tool':'blender_'+name,'category':spec.group,'risk':spec.risk,'description':spec.description,'coverage':'UNTESTED','fields':{k:{'kind':v.kind,'nullable':v.default is None,**({} if v.default is MISSING else {'default':v.default})} for k,v in spec.fields.items()}})
for name,fields in [('bridge_health',''),('job_status',"job_id: str, "),('wait_job',"job_id: str, timeout: float = 1.0, poll_seconds: float = 0.15, ")]:
    mapping='{}' if name=='bridge_health' else "{'job_id':job_id}" if name=='job_status' else "{'job_id':job_id, 'timeout':min(timeout, 8.0), 'poll_seconds':poll_seconds}"
    lines += ['    @tool()',f"    def blender_{name}(self, *, {fields}expected_scope: str = '') -> dict:",f'        """Read scoped Blender {name}; never resubmit a job."""',f"        return self._run({name!r}, {mapping}, expected_scope)"]
    rows.append({'tool':'blender_'+name,'category':'bridge','risk':'read','description':name,'coverage':'UNTESTED'})
lines += ["if __name__ == '__main__':",'    BlenderConnector.main()']
(p/'server.py').write_text('\n'.join(lines)+'\n',encoding='utf-8')
(p/'catalog.json').write_text(json.dumps(rows,indent=2)+'\n')
