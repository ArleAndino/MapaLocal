"""Local, best-effort static repository index. Never executes repository code."""
from pathlib import Path
import json
import os
import re
from collections import defaultdict
from graph_query import enrich
from git_info import git_context

EXCLUDED = {'.git', 'node_modules', 'bin', 'obj', 'dist', 'build', 'coverage',
            '.angular', '.next', '.vs', '.idea', '__pycache__', '.venv', 'vendor'}
EXTENSIONS = {'.ts', '.tsx', '.js', '.jsx', '.cs', '.css', '.scss', '.sass', '.less'}
MAX_FILE = 2_000_000
MAX_FILES = 12000
# Preserve offsets while masking comments and optionally strings.
LEX = re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|@"(?:""|[^"])*"|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`')

def mask(source, strings=False):
    def sub(m):
        if strings or m.group().startswith(('//', '/*')):
            return re.sub(r'[^\n]', ' ', m.group())
        return m.group()
    return LEX.sub(sub, source)

def read(path):
    if path.stat().st_size > MAX_FILE:
        raise ValueError('Archivo mayor a 2 MB')
    return path.read_text(encoding='utf-8-sig', errors='replace')

def symbols(source, language):
    code = mask(source, True)
    result = []
    types = list(re.finditer(r'\b(class|interface|enum|struct|record|namespace)\s+([\w.]+)', code))
    scopes = []
    for match in types:
        opening = code.find('{', match.end())
        semicolon = code.find(';', match.end())
        end = len(code)
        if opening >= 0 and (semicolon < 0 or opening < semicolon):
            depth = 1
            end = opening + 1
            while end < len(code) and depth:
                depth += (code[end] == '{') - (code[end] == '}')
                end += 1
            scopes.append((match.start(), end, match[2]))
        result.append({'name': match[2], 'kind': match[1], 'line': code.count('\n', 0, match.start()) + 1})
    if language == 'C#':
        pattern = r'\b([A-Za-z_]\w*)\s*(?:<[^<>\n]+>)?\s*\([^;{}]*\)\s*(?:where\s+[^{}]+)?\s*(?:\{|=>)'
    else:
        pattern = r'\b([A-Za-z_$][\w$]*)\s*(?:<[^<>\n]+>)?\s*\([^;{}]*\)\s*(?::\s*[^\n{=]+)?\s*(?:\{|=>)'
    skip = {'if', 'for', 'foreach', 'while', 'switch', 'catch', 'using', 'lock', 'with'}
    for match in re.finditer(pattern, code):
        if match[1] in skip:
            continue
        parents = [s for s in scopes if s[0] < match.start() < s[1]]
        owner = parents[-1][2] if parents else None
        result.append({'name': match[1], 'kind': 'method' if owner else 'function',
                       'owner': owner, 'line': code.count('\n', 0, match.start()) + 1})
    return sorted(result, key=lambda s: s['line'])

def config(path, root, seen=None):
    seen = set() if seen is None else seen
    path = path.resolve()
    if path in seen or not path.is_relative_to(root):
        return {}
    seen.add(path)
    raw = json.loads(re.sub(r',\s*([}\]])', r'\1', mask(read(path))))
    settings = {}
    parent = raw.get('extends')
    if isinstance(parent, str) and parent.startswith('.'):
        p = path.parent / parent
        if not p.suffix:
            p = p.with_suffix('.json')
        settings = config(p, root, seen)
    opts = raw.get('compilerOptions', {})
    if 'baseUrl' in opts:
        settings['base'] = (path.parent / opts['baseUrl']).resolve()
    if 'paths' in opts:
        base = settings.get('base', path.parent)
        settings['paths'] = [(key, [(base / v).as_posix() for v in values])
                             for key, values in opts['paths'].items()]
    return settings

def scan(root_path, extra_excludes=(), progress=None):
    report = progress or (lambda percent, phase, detail: None)
    report(0, 'Descubriendo archivos', 'Calculando el total de archivos…')
    root = Path(root_path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError('La ruta no es una carpeta existente.')
    excluded = EXCLUDED | set(extra_excludes)
    paths, configs, projects, warnings = [], {}, [], []
    report(0, 'Leyendo Git y .gitignore', 'Consultando rama y reglas de exclusión…')
    git, allowed, git_warnings = git_context(root)
    warnings.extend(git_warnings)
    allowed_dirs = set()
    if allowed is not None:
        for filename in allowed:
            allowed_dirs.update(p.as_posix() for p in Path(filename).parents)
    def walk_error(error):
        warnings.append(str(error))
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        report(0, 'Descubriendo archivos', f'{len(paths)} archivos encontrados; total aún desconocido')
        dirs[:] = sorted(d for d in dirs if d not in excluded and not (Path(directory) / d).is_symlink()
                         and (allowed is None or (Path(directory)/d).relative_to(root).as_posix() in allowed_dirs))
        for name in sorted(files):
            p = Path(directory) / name
            if allowed is not None and p.relative_to(root).as_posix() not in allowed:
                continue
            if p.is_symlink() or not p.resolve().is_relative_to(root):
                continue
            if name == 'tsconfig.json':
                try:
                    configs[p.parent] = config(p, root)
                except (OSError, ValueError, TypeError, AttributeError) as e:
                    warnings.append(f'{p.relative_to(root)}: configuración no interpretada ({e})')
            if p.suffix == '.csproj':
                projects.append(p)
            if p.suffix.lower() in EXTENSIONS:
                paths.append(p)
                if len(paths) > MAX_FILES:
                    raise ValueError(f'El repositorio supera {MAX_FILES} archivos. Selecciona una subcarpeta o añade exclusiones.')
    nodes, source_by_id, path_ids = [], {}, {}
    report(10, 'Leyendo símbolos', f'{len(paths)} archivos encontrados')
    for index, p in enumerate(paths):
        report(10 + int(35 * index / max(1, len(paths))), 'Leyendo símbolos', p.relative_to(root).as_posix())
        node_id = p.relative_to(root).as_posix()
        try:
            source = read(p)
        except (OSError, ValueError) as e:
            warnings.append(f'{node_id}: {e}')
            continue
        language = {'.cs': 'C#', '.ts': 'TypeScript', '.tsx': 'TypeScript',
                    '.css': 'CSS', '.scss': 'SCSS', '.sass': 'Sass', '.less': 'Less'}.get(p.suffix.lower(), 'JavaScript')
        project = next((x.relative_to(root).as_posix() for x in sorted(projects, key=lambda x: -len(x.parts)) if p.is_relative_to(x.parent)), '')
        node = {'id': node_id, 'name': p.name, 'language': language,
                'folder': p.parent.relative_to(root).as_posix(), 'project': project,
                'lines': source.count('\n') + 1, 'symbols': symbols(source, language) if language in {'C#','TypeScript','JavaScript'} else [], 'imports': []}
        nodes.append(node)
        source_by_id[node_id] = source
        path_ids[p.resolve()] = node_id
    edges, edge_keys = [], set()
    def edge(a, b, kind, detail):
        key = a, b, kind, detail
        if a != b and key not in edge_keys:
            edge_keys.add(key)
            edges.append({'source': a, 'target': b, 'kind': kind, 'detail': detail})
    def resolve(candidate):
        p = Path(candidate)
        candidates = [p]
        if p.suffix in {'.js', '.jsx', '.mjs', '.cjs'}:
            candidates += [p.with_suffix('.ts'), p.with_suffix('.tsx')]
        candidates += [Path(str(p) + ext) for ext in ('.ts', '.tsx', '.js', '.jsx', '.d.ts')]
        candidates += [p / ('index' + ext) for ext in ('.ts', '.tsx', '.js', '.jsx')]
        return next((path_ids[c.resolve()] for c in candidates if c.resolve() in path_ids), None)
    type_index = defaultdict(list)
    cs_data = {}
    globals_by_project = defaultdict(set)
    for index, n in enumerate(nodes):
        report(45 + int(10 * index / max(1, len(nodes))), 'Indexando tipos', n['id'])
        if n['language'] != 'C#':
            continue
        code = mask(source_by_id[n['id']], True)
        namespaces = re.findall(r'\bnamespace\s+([\w.]+)', code)
        usings = re.findall(r'\busing\s+(?:static\s+)?(?:\w+\s*=\s*)?(?:global::)?([\w.]+)\s*;', code)
        globals_by_project[n['project']].update(re.findall(r'\bglobal\s+using\s+([\w.]+)\s*;', code))
        ns = namespaces[0] if namespaces else ''
        n['namespace'] = ns
        n['imports'] = [{'specifier': u, 'status': 'namespace'} for u in usings]
        cs_data[n['id']] = (code, ns, usings)
        for s in n['symbols']:
            if s['kind'] in {'class', 'interface', 'record', 'struct', 'enum'}:
                type_index[s['name']].append((n['id'], ns))
    for index, n in enumerate(nodes):
        report(55 + int(40 * index / max(1, len(nodes))), 'Resolviendo dependencias', n['id'])
        if n['language'] == 'C#':
            code, ns, usings = cs_data[n['id']]
            available = set(usings) | globals_by_project[n['project']] | {ns, ''}
            # Exclude declaration headers and using lines from reference evidence.
            body = re.sub(r'\b(?:global\s+)?using\s+[^;]+;', '', code)
            body = re.sub(r'\b(?:class|interface|record|struct|enum)\s+\w+', '', body)
            for word in set(re.findall(r'\b[A-Za-z_]\w*\b', body)) & type_index.keys():
                for target, target_ns in type_index[word]:
                    if target_ns in available or (target_ns and re.search(r'\b' + re.escape(target_ns + '.' + word) + r'\b', body)):
                        edge(n['id'], target, 'csharp-inferred', word)
            continue
        code = mask(source_by_id[n['id']])
        masked_code = mask(code, True)
        p = root / n['id']
        style_language = n['language'] in {'CSS', 'SCSS', 'Sass', 'Less'}
        style_specs = []
        if style_language:
            for match in re.finditer(r'@(import|use|forward)\s+([^;\n]+)', code):
                if masked_code[match.start()] != '@':
                    continue
                style_specs.extend(re.findall(r'[\'"]([^\'"]+)[\'"]', match[2]))
                style_specs.extend(re.findall(r'url\(\s*([^\s\'"()]+)\s*\)', match[2]))
        else:
            for match in re.finditer(r'\bstyleUrls\s*:\s*\[([^\]]*)\]|\bstyleUrl\s*:\s*([\'"][^\'"]+[\'"])', code):
                if not masked_code[match.start():match.start()+8].strip():
                    continue
                style_specs.extend(re.findall(r'[\'"]([^\'"]+)[\'"]', match[1] or match[2]))
        for spec in dict.fromkeys(style_specs):
            if re.match(r'^(?:https?:|//|data:|sass:)', spec):
                n['imports'].append({'specifier': spec, 'target': None, 'status': 'external'})
                continue
            base = p.parent / spec
            candidates = [base]
            if not base.suffix:
                candidates += [Path(str(base)+ext) for ext in ('.scss','.sass','.css','.less')]
                candidates += [base/'_index.scss', base/'index.scss']
            candidates += [c.with_name('_'+c.name) for c in list(candidates)]
            target = next((path_ids[c.resolve()] for c in candidates if c.resolve() in path_ids), None)
            n['imports'].append({'specifier': spec, 'target': target, 'status': 'resolved' if target else 'unresolved'})
            if target:
                edge(n['id'], target, 'style', spec)
        if style_language:
            continue
        specs = []
        patterns = [r'\b(?:import|export)\s+(?:type\s+)?[^;\n]*?\bfrom\s*[\'"]([^\'"]+)[\'"]',
                    r'\bimport\s*[\'"]([^\'"]+)[\'"]',
                    r'\b(?:import|require)\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)']
        # Multiline import/export bindings.
        patterns.append(r'\b(?:import|export)\s+(?:type\s+)?\{[^}]*\}\s*from\s*[\'"]([^\'"]+)[\'"]')
        for pattern in patterns:
            for m in re.finditer(pattern, code):
                if masked_code[m.start():m.start()+6].strip():
                    specs.append(m[1])
        p = root / n['id']
        settings = next((configs[d] for d in [p.parent, *p.parent.parents] if d in configs), {})
        for spec in dict.fromkeys(specs):
            target = None
            local = spec.startswith('.')
            if local:
                target = resolve(p.parent / spec)
            else:
                for pattern, values in sorted(settings.get('paths', []), key=lambda item: -len(item[0].split('*')[0])):
                    match = re.fullmatch(re.escape(pattern).replace(r'\*', '(.*)'), spec)
                    if match:
                        local = True
                        for value in values:
                            target = resolve(value.replace('*', match[1] if match.groups() else ''))
                            if target:
                                break
                        break
                if not target and 'base' in settings:
                    target = resolve(settings['base'] / spec)
            n['imports'].append({'specifier': spec, 'target': target,
                                 'status': 'resolved' if target else 'unresolved' if local else 'external'})
            if target:
                edge(n['id'], target, 'style' if Path(target).suffix.lower() in {'.css','.scss','.sass','.less'} else 'import', spec)
    report(95, 'Calculando métricas', f'{len(nodes)} nodos · {len(edges)} aristas')
    return enrich({'root': str(root), 'git': git, 'nodes': nodes, 'edges': edges, 'warnings': warnings,
            'summary': {'files': len(nodes), 'edges': len(edges),
                        'unresolved': sum(i['status'] == 'unresolved' for n in nodes for i in n['imports'])}})
