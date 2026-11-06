"""Run: python app.py [repository] [--port 8765] [--no-browser]."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
from urllib.parse import urlsplit, parse_qs
import webbrowser
import subprocess
import sys
from analyzer import scan, read
from graph_query import query, route
from history import History, validate_view
from deep_analysis import capabilities
from git_info import git_context

STATIC = Path(__file__).parent / 'static'

class Server(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, port, initial='', history_dir=None):
        super().__init__(('127.0.0.1', port), Handler)
        self.token = secrets.token_urlsafe(32)
        self.graph = None
        self.lock = threading.Lock()
        self.initial = initial
        self.history = History(history_dir or Path(__file__).parent / 'analyses')
        self.job = None

    def run_scan(self, job_id, root, excludes, mode='normal'):
        def progress(percent, phase, detail):
            self.job = {'id': job_id, 'state': 'running', 'percent': percent, 'phase': phase, 'detail': detail}
        try:
            graph = scan(root, excludes, progress=progress, mode=mode)
            graph['analysis_id'] = job_id
            graph['scan_options'] = {'extra_excludes': excludes,'mode':mode}
            progress(98, 'Guardando JSON', 'Guardando el análisis en este equipo…')
            snapshot = self.history.save(graph)
            self.graph = graph
            self.job = {'id': job_id, 'state': 'done', 'percent': 100, 'phase': 'Listo', 'snapshot_id': snapshot['id']}
        except Exception as error:
            self.job = {'id': job_id, 'state': 'error', 'error': str(error)}
        finally:
            self.lock.release()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, value, status=200, mime='application/json; charset=utf-8'):
        data = json.dumps(value, ensure_ascii=False).encode() if mime.startswith('application/json') else value
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(data)

    def valid_host(self):
        return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

    def do_GET(self):
        if not self.valid_host():
            return self.reply({'error': 'Host no permitido'}, 403)
        url = urlsplit(self.path)
        if url.path == '/api/config':
            return self.reply({'token': self.server.token, 'initial': self.server.initial,
                               'version':(Path(__file__).parent/'VERSION').read_text().strip(),'engines':capabilities()})
        if url.path in {'/api/progress', '/api/history', '/api/graph'}:
            if self.headers.get('X-Local-Token') != self.server.token:
                return self.reply({'error': 'Token requerido'}, 403)
            if url.path == '/api/history':
                return self.reply({'items': self.server.history.list(), 'directory': str(self.server.history.directory)})
            requested = parse_qs(url.query).get('id', [''])[0]
            if url.path == '/api/progress':
                job = self.server.job
                if not job or job['id'] != requested:
                    return self.reply({'error': 'Análisis no disponible. Vuelve a analizar.'}, 404)
                return self.reply(job)
            graph = self.server.graph
            if not graph or graph.get('analysis_id') != requested:
                return self.reply({'error': 'El análisis activo cambió.'}, 409)
            return self.reply(graph)
        if url.path == '/api/file':
            if self.headers.get('X-Local-Token') != self.server.token:
                return self.reply({'error': 'Token requerido'}, 403)
            graph = self.server.graph
            node_id = parse_qs(url.query).get('id', [''])[0]
            node=next((n for n in graph['nodes'] if n['id']==node_id),None) if graph else None
            if not node:
                return self.reply({'error': 'Archivo no indexado'}, 404)
            root = Path(graph['root'])
            path = (root / node.get('source_file',node_id)).resolve()
            if not path.is_relative_to(root):
                return self.reply({'error': 'Ruta fuera del repositorio'}, 403)
            try:
                return self.reply({'source': read(path)})
            except (OSError, ValueError) as e:
                return self.reply({'error': str(e)}, 400)
        files = {'/product.js': ('product.js','text/javascript'), '/layouts.js': ('layouts.js','text/javascript'), '/layout-worker.js': ('layout-worker.js','text/javascript'), '/theme.js': ('theme.js', 'text/javascript'), '/workflow.js': ('workflow.js', 'text/javascript'), '/queries.js': ('queries.js', 'text/javascript'), '/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}
        if url.path not in files:
            return self.reply({'error': 'No encontrado'}, 404)
        name, mime = files[url.path]
        self.reply((STATIC / name).read_bytes(), mime=mime + '; charset=utf-8')

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= (4_000_000 if self.path == '/api/history/save' else 16384):
                return self.reply({'error': 'Solicitud inválida'}, 400)
            body = self.rfile.read(length)
        except ValueError:
            return self.reply({'error': 'Solicitud inválida'}, 400)
        origin = f'http://127.0.0.1:{self.server.server_port}'
        if not self.valid_host() or self.headers.get('X-Local-Token') != self.server.token or self.headers.get('Origin', origin) != origin:
            return self.reply({'error': 'Solicitud no permitida'}, 403)
        if self.path in {'/api/open-folder','/api/project-info'}:
            try:
                if self.path=='/api/open-folder':
                    result=subprocess.run([sys.executable,str(Path(__file__).parent/'pick_folder.py')],capture_output=True,text=True,encoding='utf-8',timeout=180,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                    if result.returncode:raise ValueError('No se pudo abrir el selector de carpetas. Pega la ruta manualmente.')
                    return self.reply(json.loads(result.stdout))
                payload=json.loads(body);root=Path(payload.get('root','')).expanduser().resolve()
                if not root.is_dir():raise ValueError('La carpeta no existe.')
                metadata,_,warnings=git_context(root)
                return self.reply({'root':str(root),'git':metadata,'warnings':warnings})
            except (OSError,ValueError,TypeError,subprocess.TimeoutExpired) as error:
                return self.reply({'error':str(error)},400)
        if self.path in {'/api/scan/start', '/api/history/save', '/api/history/load'}:
            if not self.server.lock.acquire(blocking=False):
                return self.reply({'error': 'Hay un análisis en curso; espera a que termine.'}, 409)
            background = False
            try:
                payload = json.loads(body)
                if self.path == '/api/scan/start':
                    root, excludes = payload.get('root'), payload.get('excludes', [])
                    mode=payload.get('mode','normal')
                    if mode not in {'normal','deep'}:raise ValueError('Modo inválido.')
                    if not isinstance(root, str) or not root.strip() or not isinstance(excludes, list) or not all(isinstance(x,str) for x in excludes):
                        raise ValueError('Ruta o exclusiones inválidas.')
                    job_id = secrets.token_hex(16)
                    self.server.job = {'id': job_id, 'state': 'running', 'percent': 0, 'phase': 'Iniciando', 'detail': ''}
                    threading.Thread(target=self.server.run_scan, args=(job_id,root,excludes,mode), daemon=True).start()
                    background = True
                    return self.reply({'id': job_id}, 202)
                if self.path == '/api/history/load':
                    snapshot = self.server.history.load(payload.get('id'))
                    self.server.graph = snapshot['graph']
                    return self.reply(snapshot)
                graph = self.server.graph
                if not graph or payload.get('analysis_id') != graph.get('analysis_id'):
                    raise ValueError('El análisis activo cambió. Vuelve a cargarlo antes de guardar.')
                view = validate_view(payload.get('view'), graph)
                snapshot = self.server.history.save(graph, view, payload.get('label', 'Vista guardada'))
                return self.reply({'id': snapshot['id'], 'created_at': snapshot['created_at']})
            except (ValueError, OSError, TypeError, AttributeError) as error:
                return self.reply({'error': str(error)}, 400)
            finally:
                if not background:
                    self.server.lock.release()
        if self.path in {'/api/query', '/api/path'}:
            try:
                payload = json.loads(body)
                graph = self.server.graph
                if not graph:
                    raise ValueError('Analiza un repositorio primero.')
                result = query(graph, payload.get('sql')) if self.path == '/api/query' else route(
                    graph, payload.get('start'), payload.get('end'), payload.get('direction', 'directed'), payload.get('kind', ''))
                return self.reply(result)
            except (ValueError, TypeError, AttributeError) as e:
                return self.reply({'error': str(e)}, 400)
        if self.path != '/api/scan':
            return self.reply({'error': 'No encontrado'}, 404)
        if not self.server.lock.acquire(blocking=False):
            return self.reply({'error': 'Ya hay un análisis en curso.'}, 409)
        try:
            payload = json.loads(body)
            if not isinstance(payload.get('root'), str) or not payload['root'].strip():
                raise ValueError('Indica la carpeta del repositorio.')
            excludes = payload.get('excludes', [])
            if not isinstance(excludes, list) or not all(isinstance(x, str) for x in excludes):
                raise ValueError('Exclusiones inválidas')
            graph = scan(payload['root'], excludes)
            self.server.graph = graph
            self.reply(graph)
        except (ValueError, OSError, TypeError, AttributeError) as e:
            self.reply({'error': str(e)}, 400)
        finally:
            self.server.lock.release()

def main():
    parser = argparse.ArgumentParser(description='Mapa local de dependencias TypeScript y C#')
    parser.add_argument('repository', nargs='?', default='')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    server = Server(args.port, str(Path(args.repository).resolve()) if args.repository else '')
    url = f'http://127.0.0.1:{server.server_port}'
    print(f'MapaLocal: {url}\nCtrl+C para cerrar. El código permanece en este equipo.', flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
