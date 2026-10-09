"""Static repository intelligence and JSON contracts. Never imports analyzed code."""
import ast
import hashlib
import json
from pathlib import Path
import re
import tokenize

JSON_TYPES = ['null', 'boolean', 'integer', 'number', 'string', 'array', 'object']


def annotation(node, enums=None, depth=0):
    if depth > 12:
        raise ValueError('Type annotation exceeds the nesting limit.')
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:return annotation(ast.parse(node.value, mode='eval').body, enums, depth+1)
        except SyntaxError:return {'type': JSON_TYPES}
    if node is None:return {'type': JSON_TYPES}
    name=ast.unparse(node).removeprefix('typing.').removeprefix('collections.abc.')
    simple={'str':'string','bool':'boolean','int':'integer','float':'number','None':'null','NoneType':'null',
            'dict':'object','Dict':'object','list':'array','List':'array','tuple':'array','Tuple':'array',
            'set':'array','Set':'array','Sequence':'array','Iterable':'array','Mapping':'object'}
    if name in (enums or {}):return {'enum':enums[name]}
    if name in simple:return {'type':simple[name]}
    if isinstance(node,ast.BinOp) and isinstance(node.op,ast.BitOr):
        return {'anyOf':[annotation(node.left,enums,depth+1),annotation(node.right,enums,depth+1)]}
    if isinstance(node,ast.Subscript):
        base=ast.unparse(node.value).split('.')[-1]
        parts=list(node.slice.elts) if isinstance(node.slice,ast.Tuple) else [node.slice]
        if base=='Literal':
            try:return {'enum':[ast.literal_eval(p) for p in parts]}
            except (ValueError,TypeError):return {'type':JSON_TYPES}
        if base in {'Union','Optional'}:
            choices=[annotation(p,enums,depth+1) for p in parts]
            return {'anyOf':choices+([{'type':'null'}] if base=='Optional' else [])}
        if base=='Annotated':return annotation(parts[0],enums,depth+1)
        if base in {'list','List','Sequence','Iterable','set','Set'}:
            return {'type':'array','maxItems':1000,'items':annotation(parts[0],enums,depth+1)}
        if base in {'tuple','Tuple'}:
            return {'type':'array','maxItems':1000,'items':annotation(parts[0],enums,depth+1)} if len(parts)==2 and isinstance(parts[1],ast.Constant) and parts[1].value is Ellipsis else {
                'type':'array','prefixItems':[annotation(p,enums,depth+1) for p in parts], 'minItems':len(parts),'maxItems':len(parts)}
        if base in {'dict','Dict','Mapping'}:
            return {'type':'object','maxProperties':1000,'additionalProperties':annotation(parts[-1],enums,depth+1)}
    return {'type':JSON_TYPES}  # Unresolved custom types are explicit JSON-only, not executable converters.


def validate(schema, value, depth=0):
    """Validate the finite generated JSON-schema subset, including exact numeric types."""
    if depth>20:raise ValueError('Arguments exceed the nesting limit.')
    if 'anyOf' in schema:
        for choice in schema['anyOf']:
            try:validate(choice,value,depth+1);return
            except ValueError:pass
        raise ValueError('Argument does not match any allowed type.')
    if 'enum' in schema and not any(type(value) is type(v) and value==v for v in schema['enum']):
        raise ValueError('Argument is not an allowed enum value.')
    kinds=schema.get('type',JSON_TYPES);kinds=[kinds] if isinstance(kinds,str) else kinds
    import math
    valid={'null':value is None,'boolean':type(value) is bool,'integer':type(value) is int,
           'number':type(value) in (int,float) and math.isfinite(value), 'string':isinstance(value,str),
           'array':isinstance(value,list),'object':isinstance(value,dict)}
    if not any(valid.get(k,False) for k in kinds):raise ValueError('Argument has an incorrect JSON type.')
    if isinstance(value,str) and len(value)>schema.get('maxLength',10000):raise ValueError('String argument too large.')
    if isinstance(value,list):
        if not schema.get('minItems',0)<=len(value)<=schema.get('maxItems',1000):raise ValueError('Array size outside schema.')
        for i,item in enumerate(value):
            parts=schema.get('prefixItems',[])
            validate(parts[i] if i<len(parts) else schema.get('items',{}),item,depth+1)
    if isinstance(value,dict):
        if len(value)>schema.get('maxProperties',1000):raise ValueError('Object argument too large.')
        if not all(isinstance(k,str) and len(k)<200 for k in value):raise ValueError('Object keys must be bounded strings.')
        if set(schema.get('required',[]))-value.keys():raise ValueError('Missing required arguments.')
        properties=schema.get('properties',{});extra=schema.get('additionalProperties',{})
        if extra is False and value.keys()-properties.keys():raise ValueError('Unexpected arguments.')
        for key,item in value.items():validate(properties.get(key,extra if isinstance(extra,dict) else {}),item,depth+1)


def signature(node, enums, skip_first=False):
    args=node.args;pos=[*args.posonlyargs,*args.args]
    defaults=[None]*(len(pos)-len(args.defaults))+list(args.defaults)
    entries=[];properties={};required=[]
    parameters=[(p,'positional_only' if i<len(args.posonlyargs) else 'positional',d)
                for i,(p,d) in enumerate(zip(pos,defaults))]
    parameters += [(p,'keyword_only',d) for p,d in zip(args.kwonlyargs,args.kw_defaults)]
    if args.vararg:parameters.append((args.vararg,'varargs',None))
    if args.kwarg:parameters.append((args.kwarg,'kwargs',None))
    for i,(p,kind,default) in enumerate(parameters):
        if skip_first and i==0:continue
        schema=annotation(p.annotation,enums)
        if kind=='varargs':schema={'type':'array','maxItems':100,'items':schema}
        if kind=='kwargs':schema={'type':'object','maxProperties':100,'additionalProperties':schema}
        entry={'name':p.arg,'kind':kind,'annotation':ast.unparse(p.annotation) if p.annotation else 'Any','required':default is None and kind not in {'varargs','kwargs'}}
        if default is not None:
            try:
                value=ast.literal_eval(default);json.dumps(value,allow_nan=False)
                schema={**schema,'default':value};entry['default']=value
            except (ValueError,TypeError):entry['default_expression']=ast.unparse(default)[:200]
        properties[p.arg]=schema;entries.append(entry)
        if entry['required']:required.append(p.arg)
    return entries,{'type':'object','properties':properties,'required':required,'additionalProperties':False}


def analyze(root, cancelled=lambda:False):
    root=Path(root);entities=[];diagnostics=[];imports=set();scanned=0;relationships=[];classes=[]
    enums={};enum_tables={};trees=[];metadata={}
    for path in sorted(root.rglob('*.py')):
        if cancelled():raise ValueError('Repository analysis cancelled.')
        relative=path.relative_to(root)
        if any(p in {'tests','test','docs','examples','__pycache__','.git'} or p.startswith('.') for p in relative.parts[:-1]):continue
        if len(trees)>=2000:raise ValueError('Repository analysis exceeds 2,000 source files.')
        try:
            if path.stat().st_size>1000000:raise ValueError('Source exceeds 1MB.')
            with tokenize.open(path) as source:tree=ast.parse(source.read(),filename=relative.as_posix())
            parts=list(relative.with_suffix('').parts);import_root='.'
            if parts[0]=='src':parts=parts[1:];import_root='src'
            if parts[-1]=='__init__':parts=parts[:-1]
            if not parts or any(not p.isidentifier() for p in parts):raise ValueError('Invalid Python module identifier.')
            trees.append((relative,tree,'.'.join(parts),import_root));scanned+=1
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):imports.update(a.name for a in node.names)
                elif isinstance(node,ast.ImportFrom):imports.add('.'*node.level+(node.module or ''))
            local_enums={}
            for node in tree.body:
                if isinstance(node,ast.ClassDef) and any(ast.unparse(b).split('.')[-1] in {'Enum','IntEnum','StrEnum'} for b in node.bases):
                    values=[]
                    for item in node.body:
                        if isinstance(item,ast.Assign):
                            try:values.append(ast.literal_eval(item.value))
                            except (ValueError,TypeError):pass
                    if values:local_enums[node.name]=values
            enum_tables['.'.join(parts)]=local_enums
        except (SyntaxError,UnicodeError,OSError,ValueError) as error:
            diagnostics.append({'file':relative.as_posix(),'error':str(error)[:300]})
    def entity(node,relative,module,import_root,owner=None,kind='function',constructor=None):
        if node.name.startswith('_'):return
        parameters,schema=signature(node,enums,kind in {'method','class_method'})
        supported=True;reason=''
        decorators=[ast.unparse(d) for d in node.decorator_list]
        if owner and 'property' in decorators:supported=False;reason='Property is discoverable but is not a callable adapter.'
        if kind=='method' and constructor is None:supported=False;reason='Constructor signature is unavailable; explicit adapter required.'
        if any(isinstance(d,ast.Call) and ast.unparse(d.func).split('.')[-1] in {'fixture','parametrize'} for d in node.decorator_list):
            supported=False;reason='Test-specific decorator is not a public runtime capability.'
        if kind=='method':
            schema={'type':'object','properties':{'constructor':constructor or {},'arguments':schema},'required':['constructor','arguments'],'additionalProperties':False}
        symbol=(owner+'.' if owner else '')+node.name
        calls=sorted({ast.unparse(n.func)[:120] for n in ast.walk(node) if isinstance(n,ast.Call)})[:100]
        relationships.append({'symbol':module+'.'+symbol,'calls':calls})
        entities.append({'module':module,'symbol':symbol,'file':relative.as_posix(),'import_root':import_root,
            'line':node.lineno,'kind':kind,'async':isinstance(node,ast.AsyncFunctionDef),'parameters':parameters,
            'schema':schema,'documentation_untrusted':(ast.get_docstring(node) or '')[:1200],
            'decorators_untrusted':decorators[:10],'supported':supported,'rejection':reason,
            'description':'Repository capability '+module+'.'+symbol+'. JSON arguments; isolated execution and approval required.'})
    for relative,tree,module,import_root in trees:
        enums=enum_tables.get(module,{})
        for node in tree.body:
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):entity(node,relative,module,import_root)
            elif isinstance(node,ast.ClassDef) and not node.name.startswith('_'):
                init=next((n for n in node.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name=='__init__'),None)
                constructor=signature(init,enums,True)[1] if init else None
                classes.append({'module':module,'name':node.name,'file':relative.as_posix(),'line':node.lineno,
                    'constructor_schema':constructor,'bases_untrusted':[ast.unparse(b) for b in node.bases],
                    'documentation_untrusted':(ast.get_docstring(node) or '')[:1200]})
                for method in node.body:
                    if isinstance(method,(ast.FunctionDef,ast.AsyncFunctionDef)):
                        decorators=[ast.unparse(d) for d in method.decorator_list]
                        kind='static_method' if 'staticmethod' in decorators else 'class_method' if 'classmethod' in decorators else 'method'
                        entity(method,relative,module,import_root,node.name,kind,constructor)
    for name in ('pyproject.toml','setup.cfg','requirements.txt','LICENSE','LICENSE.txt','LICENSE.md','COPYING'):
        path=root/name
        if path.is_file() and path.stat().st_size<=100000:metadata[name]=path.read_text(encoding='utf-8',errors='replace')[:10000]
    return {'files_scanned':scanned,'entities':entities,'classes':classes,'imports':sorted(imports),'relationships':relationships,
            'diagnostics':diagnostics,'metadata_untrusted':metadata,'analysis_version':2}
