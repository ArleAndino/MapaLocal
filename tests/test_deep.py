from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analyzer import scan
from deep_analysis import capabilities
from graph_query import route,query


@unittest.skipUnless(all(capabilities().values()),'Optional TypeScript/Roslyn engines are not installed')
class DeepTests(unittest.TestCase):
    def test_flow_from_template_through_http_to_csharp(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            files={
                'component.ts':"""import { Service } from './service';
function Component(x:any){return (cls:any)=>cls;}
@Component({templateUrl:'./component.html'})
export class ComponentA { constructor(private service:Service){} save(){this.service.create();} }""",
                'service.ts':"""class HttpClient { post(url:string,data:any){} }
export class Service { constructor(private http:HttpClient){} create(){this.http.post('/api/orders',{});} }""",
                'component.html':'<button (click)="save()">Save</button>',
                'Controller.cs':"""using System;
class RouteAttribute:Attribute{ public RouteAttribute(string s){} }
class HttpPostAttribute:Attribute{ public HttpPostAttribute(){} }
[Route("api/orders")] public class OrdersController {
 private Service service=new Service();
 [HttpPost] public void Create(){service.Save();}
}
public class Service {public void Save(){} }""",
                'Broken.ts':'export class Broken { run( {',
                'Broken.cs':'public class Broken { void Run( {',
                'Throws.ts':'export function risky(){throw new Error("expected");}'
            }
            for name,source in files.items():(root/name).write_text(source,encoding='utf-8')
            normal=scan(root)
            self.assertFalse(any(n['kind']=='method' for n in normal['nodes']))
            graph=scan(root,mode='deep')
            self.assertTrue(all(e['state']=='completed' for e in graph['deep']['coverage']),graph['warnings'])
            errors={n['id'] for n in graph['nodes'] if n.get('has_errors')}
            self.assertIn('Broken.ts',errors);self.assertIn('Broken.cs',errors);self.assertNotIn('Throws.ts',errors)
            target=next(n for n in graph['nodes'] if n['kind']=='method' and n['source_file']=='Controller.cs' and n['name']=='Save')
            path=route(graph,'component.html',target['id'])
            self.assertTrue(path['found'],graph)
            self.assertEqual([s['edge']['kind'] for s in path['steps']],['event','call','http','call'])
            self.assertEqual([s['edge']['confidence'] for s in path['steps']],['inferred','resolved','inferred','resolved'])
            self.assertTrue(all(s['edge']['line']>0 for s in path['steps']))
            self.assertGreater(query(graph,"SELECT COUNT(*) FROM nodes WHERE has_errors=1")['rows'][0][0],0)

    def test_missing_engine_is_visible_and_not_false_success(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            Path(directory,'app.ts').write_text('export function go(){}')
            with patch('deep_analysis.capabilities',return_value={'typescript':False,'csharp':False}):graph=scan(directory,mode='deep')
            self.assertEqual(graph['deep']['coverage'][0]['state'],'unavailable')
            self.assertTrue(graph['warnings'])

if __name__=='__main__':unittest.main()
