import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analyzer import scan, symbols
from app import Server

class AnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
    def tearDown(self):
        self.temp.cleanup()
    def put(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    def test_ts_imports_aliases_barrels_and_exclusions(self):
        self.put('tsconfig.json', '{// comment\n"compilerOptions":{"paths":{"@app/*":["src/*"],},},}')
        self.put('src/main.ts', '''import { A } from '@app/a';
import { B } from './barrel';
const lazy = import('./lazy.js');
// import './fake';
const text = "import './ghost'";
import './missing';
import { Component } from '@angular/core';''')
        self.put('src/a.ts', 'export class A {}')
        self.put('src/barrel/index.ts', "export { A } from '../a';")
        self.put('src/lazy.ts', 'export class Lazy {}')
        self.put('node_modules/no.ts', 'export class Nope {}')
        g = scan(self.root)
        self.assertEqual(len(g['nodes']), 4)
        self.assertEqual(len(g['edges']), 4)
        self.assertEqual(g['summary']['unresolved'], 1)
        self.assertFalse(any(i['specifier'] in {'./fake', './ghost'} for n in g['nodes'] for i in n['imports']))
    def test_config_inheritance_relative_to_declaring_file(self):
        self.put('tsconfig.json', '{"compilerOptions":{"paths":{"@/*":["lib/*"]}}}')
        self.put('nested/tsconfig.json', '{"extends":"../tsconfig.json"}')
        self.put('nested/main.ts', "import { Thing } from '@/thing';")
        self.put('lib/thing.ts', 'export class Thing {}')
        self.assertEqual(scan(self.root)['edges'][0]['target'], 'lib/thing.ts')
    def test_csharp_using_is_not_itself_dependency(self):
        self.put('A.cs', 'using Services; namespace Api; public class A { public Service Get() { return new Service(); } }')
        self.put('Service.cs', 'namespace Services; public class Service {}')
        self.put('Unused.cs', 'namespace Services; public class Unused {}')
        self.put('Comment.cs', 'using Services; namespace Api; // Service\n public class Comment { string x = "Service"; }')
        g = scan(self.root)
        self.assertEqual([(e['source'],e['target']) for e in g['edges']], [('A.cs','Service.cs')])
    def test_symbol_lines(self):
        result = symbols('export class A {\n  run() { return 1; }\n}', 'TypeScript')
        self.assertTrue(any(s['name']=='run' and s['line']==2 and s['owner']=='A' for s in result))
    def test_missing_root(self):
        with self.assertRaises(ValueError): scan(self.root/'absent')

class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=Server(0)
        cls.thread=threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
    def test_scan_source_and_access_controls(self):
        token=json.load(urlopen(self.base+'/api/config'))['token']
        root=str(Path(__file__).resolve().parents[1]/'demo')
        payload=json.dumps({'root':root}).encode()
        def request(path, data=None, headers=None):
            return urlopen(Request(self.base+path,data=data,headers=headers or {}))
        with self.assertRaises(HTTPError) as e: request('/api/scan',payload)
        self.assertEqual(e.exception.code,403)
        headers={'X-Local-Token':token,'Content-Type':'application/json'}
        graph=json.load(request('/api/scan',payload,headers))
        self.assertEqual(graph['summary']['files'],8)
        self.assertEqual(graph['summary']['edges'],6)
        route_payload=json.dumps({'start':'frontend/app.component.ts','end':'frontend/_palette.scss'}).encode()
        self.assertEqual(json.load(request('/api/path',route_payload,headers))['hops'],2)
        sql_payload=json.dumps({'sql':'SELECT COUNT(*) FROM nodes'}).encode()
        self.assertEqual(json.load(request('/api/query',sql_payload,headers))['rows'],[[8]])
        with self.assertRaises(HTTPError):request('/api/query',sql_payload)
        self.assertIn('AppComponent',json.load(request('/api/file?id=frontend/app.component.ts',headers=headers))['source'])
        with self.assertRaises(HTTPError): request('/api/file?id=../../app.py',headers=headers)
        with self.assertRaises(HTTPError): request('/api/scan',payload,{**headers,'Origin':'https://example.org'})
        with self.assertRaises(HTTPError): request('/',headers={'Host':'example.org'})
        self.assertIn(b'MapaLocal',request('/').read())

if __name__=='__main__': unittest.main()
