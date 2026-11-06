import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analyzer import scan
from app import Server
from history import History, validate_view


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.directory=Path(self.temp.name)
    def tearDown(self):
        self.temp.cleanup()

    def test_progress_and_persistent_snapshot(self):
        demo=Path(__file__).resolve().parents[1]/'demo'
        updates=[]
        graph=scan(demo,progress=lambda percent,phase,detail:updates.append(percent))
        self.assertEqual(updates,sorted(updates))
        self.assertEqual(updates[0],0)
        self.assertEqual(updates[-1],95)
        view={'positions':{n['id']:{'x':1,'y':2} for n in graph['nodes']},'camera':{'x':3,'y':4,'k':1}}
        validate_view(view,graph)
        saved=History(self.directory).save(graph,view)
        restored=History(self.directory).load(saved['id'])
        self.assertEqual(restored['graph'],graph)
        self.assertEqual(restored['view'],view)
        self.assertTrue(History(self.directory).list()[0]['has_view'])
        with self.assertRaises(ValueError):History(self.directory).load('../outside')
        view['camera']['k']=float('nan')
        with self.assertRaises(ValueError):validate_view(view,graph)

    def test_async_scan_save_reload_errors_and_auth(self):
        server=Server(0,history_dir=self.directory)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        def call(path,payload=None,authenticated=True):
            headers={'X-Local-Token':server.token} if authenticated else {}
            data=None if payload is None else json.dumps(payload).encode()
            return json.load(urlopen(Request(base+path,data=data,headers=headers),timeout=5))
        def wait(job):
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                state=call('/api/progress?id='+job['id'])
                if state['state']!='running':return state
                time.sleep(.01)
            self.fail('Job did not finish')
        try:
            with self.assertRaises(HTTPError):call('/api/history',authenticated=False)
            demo=str(Path(__file__).resolve().parents[1]/'demo')
            job=call('/api/scan/start',{'root':demo})
            done=wait(job)
            self.assertEqual((done['state'],done['percent']),('done',100))
            graph=call('/api/graph?id='+job['id'])
            self.assertEqual(graph['summary']['nodes'],8)
            view={'positions':{n['id']:{'x':4,'y':8} for n in graph['nodes']},'camera':{'x':0,'y':0,'k':1}}
            saved=call('/api/history/save',{'analysis_id':job['id'],'view':view})
            self.assertEqual(len(call('/api/history')['items']),2)
            loaded=call('/api/history/load',{'id':saved['id']})
            self.assertEqual(loaded['view'],view)
            self.assertEqual(call('/api/query',{'sql':'SELECT COUNT(*) FROM nodes'})['rows'],[[8]])
            self.assertTrue(call('/api/path',{'start':'frontend/app.component.ts','end':'frontend/reset.css'})['found'])
            with self.assertRaises(HTTPError):call('/api/history/save',{'analysis_id':'outdated','view':view})
            with self.assertRaises(HTTPError):call('/api/history/load',{'id':'../outside'})
            failed=wait(call('/api/scan/start',{'root':str(self.directory/'missing')}))
            self.assertEqual(failed['state'],'error')
            self.assertEqual(server.graph['analysis_id'],job['id'])
            self.assertEqual(len(History(self.directory).list()),2)
        finally:
            server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
