"""Local compiler adapters. No build or code from the scanned repository is executed."""
import json
from pathlib import Path
import re
import shutil
import subprocess
from html.parser import HTMLParser
from urllib.parse import urlsplit
from graph_query import enrich

ENGINES = Path(__file__).parent / 'engines'
ROSLYN = ENGINES / 'Roslyn/bin/Release/net9.0/Roslyn.dll'


def capabilities():
    return {'typescript': bool(shutil.which('node') and (ENGINES/'node_modules/typescript/lib/typescript.js').is_file()),
            'csharp': bool(shutil.which('dotnet') and ROSLYN.is_file())}


def run_engine(command, payload):
    result = subprocess.run(command, input=json.dumps(payload), text=True, encoding='utf-8',
                            errors='replace', capture_output=True, timeout=120,
                            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0), cwd=ENGINES)
    if result.returncode:
        raise ValueError(result.stderr[-2000:] or 'El motor no pudo finalizar.')
    return json.loads(result.stdout)


class Events(HTMLParser):
    def __init__(self):
        super().__init__(); self.events=[]
    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name.startswith('(') and name.endswith(')') and value:
                for method in re.findall(r'(?<![\w.])([A-Za-z_$][\w$]*)\s*\(',value):
                    self.events.append((method,self.getpos()[0],name))


def analyze_deep(graph, sources, report):
    files={n['id']:n for n in graph['nodes']}
    for n in files.values():
        n.update(kind='view' if n['language']=='HTML' else 'file',source_file=n['id'])
        n.setdefault('diagnostics',[]);n.setdefault('unresolved_calls',[])
    available=capabilities();results=[];coverage=[]
    for language,languages,command in [('typescript',{'TypeScript','JavaScript'},['node',str(ENGINES/'ts.cjs')]),
                                       ('csharp',{'C#'},['dotnet',str(ROSLYN)])]:
        indexed=[{'id':n['id'],'source':sources[n['id']]} for n in files.values() if n['language'] in languages and n['id'] in sources]
        if not indexed:continue
        if not available[language]:
            coverage.append({'engine':language,'state':'unavailable'})
            graph['warnings'].append(f'Motor {language} no instalado. Consulta README: preparación del análisis profundo.')
            continue
        report(96,'Análisis profundo',f'{language}: {len(indexed)} archivos')
        try:
            result=run_engine(command,{'root':graph['root'],'files':indexed});results.append(result)
            coverage.append({'engine':language,'state':'completed','files':len(indexed)})
            for f in indexed:files[f['id']]['syntax_checked']=True
        except (ValueError,OSError,subprocess.TimeoutExpired) as error:
            coverage.append({'engine':language,'state':'failed'})
            graph['warnings'].append(f'{language}: {error}')
    methods={};classes={};http=[];endpoints=[];templates=[]
    for result in results:
        for diagnostic in result.get('diagnostics',[]):
            if diagnostic['file'] in files:files[diagnostic['file']]['diagnostics'].append(diagnostic)
        for method in result['methods']:
            parent=files[method['file']]
            node={**method,'source_file':method['file'],'language':parent['language'],
                  'syntax_checked':parent.get('syntax_checked',False),
                  'folder':parent['folder'],'project':parent['project'],'symbols':[],'imports':[],
                  'diagnostics':[],'lines':method['endLine']-method['line']+1,'unresolved_calls':[]}
            methods[node['id']]=node;graph['nodes'].append(node)
            container=parent['id']
            if node['owner']:
                container=parent['id']+'::class:'+node['owner']
                if container not in classes:
                    symbol=next((s for s in parent['symbols'] if s['name']==node['owner']),{})
                    classes[container]={**parent,'id':container,'name':node['owner'],'kind':'class','line':symbol.get('line',node['line']),
                                        'symbols':[],'imports':[],'diagnostics':[],'unresolved_calls':[]}
                    graph['nodes'].append(classes[container])
                    graph['edges'].append({'source':parent['id'],'target':container,'kind':'contains','file':parent['id'],'line':classes[container]['line'],'detail':node['owner'],'confidence':'resolved'})
            graph['edges'].append({'source':container,'target':node['id'],'kind':'contains',
                                   'detail':f"{node['owner']}.{node['name']} · L{node['line']}",'line':node['line'],'file':parent['id'],'confidence':'resolved'})
        http.extend(result.get('http',[]));endpoints.extend(result.get('endpoints',[]));templates.extend(result.get('templates',[]))
    def add(a,b,kind,file,line,detail,confidence):
        graph['edges'].append({'source':a,'target':b,'kind':kind,'file':file,'line':line,
                               'detail':detail,'confidence':confidence})
    for result in results:
        for call in result['calls']:
            if call['source'] not in methods:continue
            if call['target'] in methods:
                add(call['source'],call['target'],'call',call['file'],call['line'],call['expression'],'resolved')
            else:
                methods[call['source']]['unresolved_calls'].append(call)
                files[call['file']]['unresolved_calls'].append(call)
    for template in templates:
        owner_file=template['file']
        if template['inline']:
            view_id=owner_file+'::template:'+str(template['line']);content=template['value'];line_offset=template['line']-1
            parent=files[owner_file]
            graph['nodes'].append({'id':view_id,'name':'Vista inline · '+parent['name'],'kind':'view','source_file':owner_file,
                                   'line':template['line'],'language':'HTML','folder':parent['folder'],'project':parent['project'],
                                   'lines':content.count('\n')+1,'symbols':[],'imports':[],'diagnostics':[]})
        else:
            candidate=(Path(graph['root'])/owner_file).parent/template['value']
            try:view_id=candidate.resolve().relative_to(Path(graph['root'])).as_posix()
            except ValueError:continue
            if view_id not in sources:
                graph['warnings'].append(f'Vista no indexada: {template["value"]} ({owner_file})');continue
            content=sources[view_id];line_offset=0
        add(owner_file,view_id,'template',owner_file,template['line'],'template Angular literal','inferred')
        parser=Events();parser.feed(content)
        for method,line,event in parser.events:
            candidates=[m for m in methods.values() if m['file']==owner_file and m['name']==method and (not template.get('owner') or m['owner']==template['owner'])]
            if len(candidates)==1:add(view_id,candidates[0]['id'],'event',files[owner_file]['id'] if template['inline'] else view_id,line+line_offset,event+' → '+method,'inferred')
    for request in http:
        url=urlsplit(request['url']).path.rstrip('/') or '/'
        matches=[]
        for endpoint in endpoints:
            pattern=re.escape('/'+endpoint['url'].strip('/'))
            pattern=re.sub(r'\\\{[^}]*\\\}',r'[^/]+',pattern)
            if endpoint['verb']==request['verb'] and re.fullmatch(pattern,url,re.IGNORECASE):matches.append(endpoint)
        if len(matches)==1:add(request['source'],matches[0]['target'],'http',request['file'],request['line'],request['verb']+' '+request['url'],'inferred')
        elif request['source'] in methods:methods[request['source']]['unresolved_calls'].append({**request,'expression':request['verb']+' '+request['url'],'confidence':'unresolved'})
    for node in graph['nodes']:
        if node['id'] in methods:
            node['diagnostics']=[d for d in files[node['file']]['diagnostics'] if node['line']<=d.get('line',1)<=node['endLine']]
        node['has_errors']=any(d.get('severity')=='error' for d in node['diagnostics'])
    graph['deep']={'coverage':coverage,'methods':len(methods),'unresolved_calls':sum(len(m['unresolved_calls']) for m in methods.values()),
                   'limitations':['Análisis estático, no ejecución.','TypeScript usa el tsconfig raíz; C# usa una compilación en memoria sin MSBuild ni referencias NuGet.',
                                  'Vistas Angular y rutas HTTP literales inferidas; no cubre bindings dinámicos, Razor, reflexión ni DI en ejecución.']}
    graph['analysis_mode']='deep';graph['summary']['errors']=sum(n.get('has_errors',False) for n in files.values())
    return enrich(graph)
