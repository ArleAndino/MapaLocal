"""In-memory graph metrics, BFS routes and bounded read-only SQLite queries."""
from collections import deque, Counter
import sqlite3
import time


def enrich(graph):
    nodes = {n['id']: n for n in graph['nodes']}
    incoming = {key: set() for key in nodes}
    outgoing = {key: set() for key in nodes}
    ins, outs, pairs = Counter(), Counter(), Counter()
    for edge in graph['edges']:
        a, b = edge['source'], edge['target']
        outgoing[a].add(b)
        incoming[b].add(a)
        outs[a] += 1
        ins[b] += 1
        pairs[a, b] += 1
    for key, node in nodes.items():
        node.update(in_degree=len(incoming[key]), out_degree=len(outgoing[key]),
                    neighbors=len(incoming[key] | outgoing[key]),
                    degree=len(incoming[key]) + len(outgoing[key]),
                    references_in=ins[key], references_out=outs[key], weight=ins[key]+outs[key])
    graph['connections'] = [{'source': a, 'target': b, 'weight': count}
                            for (a, b), count in sorted(pairs.items())]
    graph['summary'].update(nodes=len(nodes), edges=len(graph['edges']), connections=len(pairs),
                            isolated=sum(n['neighbors'] == 0 for n in nodes.values()))
    return graph


def route(graph, start, end, direction='directed', kind=''):
    ids = {n['id'] for n in graph['nodes']}
    if start not in ids or end not in ids:
        raise ValueError('Selecciona rutas exactas de archivos indexados para A y B.')
    if direction not in {'directed', 'undirected'}:
        raise ValueError('Dirección inválida.')
    adjacency = {key: {} for key in ids}
    for edge in graph['edges']:
        if kind and edge['kind'] != kind:
            continue
        adjacency[edge['source']].setdefault(edge['target'], edge)
        if direction == 'undirected':
            adjacency[edge['target']].setdefault(edge['source'], edge)
    previous = {start: None}
    queue = deque([start])
    while queue and end not in previous:
        current = queue.popleft()
        for neighbor in sorted(adjacency[current]):
            if neighbor not in previous:
                previous[neighbor] = current
                queue.append(neighbor)
    if end not in previous:
        return {'found': False, 'nodes': [], 'steps': [], 'hops': None}
    path = [end]
    while path[-1] != start:
        path.append(previous[path[-1]])
    path.reverse()
    steps = []
    for a, b in zip(path, path[1:]):
        edge = adjacency[a][b]
        steps.append({'from': a, 'to': b, 'edge': edge,
                      'reversed': edge['source'] != a})
    return {'found': True, 'nodes': path, 'steps': steps, 'hops': len(steps)}


def query(graph, sql):
    if not isinstance(sql, str) or not sql.strip() or len(sql) > 12000:
        raise ValueError('Escribe una consulta SELECT de hasta 12.000 caracteres.')
    connection = sqlite3.connect(':memory:')
    try:
        connection.executescript('''
          CREATE TABLE nodes(id TEXT PRIMARY KEY, name TEXT, language TEXT, folder TEXT,
            lines INTEGER, in_degree INTEGER, out_degree INTEGER, neighbors INTEGER,
            degree INTEGER, references_in INTEGER, references_out INTEGER, weight INTEGER);
          CREATE TABLE edges(source TEXT, target TEXT, kind TEXT, detail TEXT);
          CREATE TABLE connections(source TEXT, target TEXT, weight INTEGER);
          CREATE INDEX edge_source ON edges(source);
          CREATE INDEX edge_target ON edges(target);
        ''')
        fields = ['id','name','language','folder','lines','in_degree','out_degree','neighbors',
                  'degree','references_in','references_out','weight']
        connection.executemany('INSERT INTO nodes VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                               [[n.get(k) for k in fields] for n in graph['nodes']])
        connection.executemany('INSERT INTO edges VALUES (?,?,?,?)',
                               [[e[k] for k in ['source','target','kind','detail']] for e in graph['edges']])
        connection.executemany('INSERT INTO connections VALUES (?,?,?)',
                               [[e[k] for k in ['source','target','weight']] for e in graph['connections']])
        allowed_functions = {'count','sum','avg','min','max','round','abs','lower','upper',
                             'length','substr','substring','coalesce','ifnull','nullif','like',
                             'glob','replace','trim','ltrim','rtrim','total','typeof','instr',
                             'row_number','rank','dense_rank'}
        def authorize(action, a, b, db, trigger):
            if action in {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE}:
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_READ and a in {'nodes','edges','connections'}:
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_FUNCTION and (b or '').lower() in allowed_functions:
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY
        connection.set_authorizer(authorize)
        deadline = time.monotonic() + 2
        connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1_000_000)
        cursor = connection.execute(sql)
        if cursor.description is None:
            raise ValueError('Solo se permiten consultas SELECT de lectura.')
        rows = cursor.fetchmany(501)
        return {'columns': [d[0] for d in cursor.description], 'rows': rows[:500],
                'truncated': len(rows) > 500, 'limit': 500}
    except sqlite3.Error as error:
        raise ValueError(f'Consulta no válida o límite excedido: {error}') from error
    finally:
        connection.close()
