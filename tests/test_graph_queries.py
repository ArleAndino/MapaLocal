import sys
from pathlib import Path
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from graph_query import enrich, route, query
from analyzer import scan


def fixture():
    return enrich({'nodes': [{'id': key, 'name': key, 'language': 'C#', 'folder': '.', 'lines': 3}
                              for key in ['A','B','C','D']],
                   'edges': [{'source': a, 'target': b, 'kind': kind, 'detail': detail}
                             for a,b,kind,detail in [('A','B','import','one'),('A','B','import','two'),
                                                     ('B','A','import','back'),('B','C','style','css')]],
                   'summary': {}})


class GraphTests(unittest.TestCase):
    def test_counts_parallel_edges_reciprocal_and_isolated(self):
        graph = fixture()
        self.assertEqual(graph['summary'], {'nodes':4,'edges':4,'connections':3,'isolated':1})
        a = graph['nodes'][0]
        self.assertEqual((a['neighbors'],a['degree'],a['weight']), (1,2,3))
        self.assertEqual(sum(n['weight'] for n in graph['nodes']),2*len(graph['edges']))
        self.assertEqual(graph['connections'][0]['weight'],2)

    def test_shortest_path_direction_cycles_and_filter(self):
        graph=fixture()
        result=route(graph,'A','C')
        self.assertEqual(result['nodes'],['A','B','C'])
        self.assertEqual(result['hops'],2)
        self.assertFalse(route(graph,'C','A')['found'])
        reverse=route(graph,'C','A','undirected')
        self.assertTrue(reverse['found'])
        self.assertTrue(reverse['steps'][0]['reversed'])
        self.assertFalse(route(graph,'A','C',kind='import')['found'])
        self.assertFalse(route(graph,'A','D')['found'])
        self.assertEqual(route(graph,'A','A')['hops'],0)
        with self.assertRaises(ValueError):route(graph,'missing','A')

    def test_sql_rank_aggregate_join_and_readonly(self):
        graph=fixture()
        result=query(graph,'SELECT id, weight FROM nodes ORDER BY weight DESC, id')
        self.assertEqual(result['rows'][0],('B',4))
        self.assertEqual(query(graph,'SELECT COUNT(*) FROM edges')['rows'],[(4,)])
        self.assertEqual(query(graph,'SELECT SUM(weight) FROM connections')['rows'],[(4,)])
        self.assertEqual(query(graph,'SELECT n.id FROM nodes n JOIN edges e ON n.id=e.source WHERE e.target=\'C\'')['rows'],[('B',)])
        for sql in ['DELETE FROM nodes','DROP TABLE edges',"ATTACH DATABASE 'other.db' AS other",'PRAGMA table_info(nodes)',"SELECT load_extension('x')",'SELECT randomblob(1000000)','SELECT 1; SELECT 2']:
            with self.subTest(sql=sql),self.assertRaises(ValueError):query(graph,sql)
        self.assertEqual(len(graph['nodes']),4)

    def test_sql_row_limit_and_execution_budget(self):
        graph=fixture()
        result=query(graph,'WITH RECURSIVE t(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM t WHERE x<600) SELECT x FROM t')
        self.assertEqual(len(result['rows']),500)
        self.assertTrue(result['truncated'])
        with self.assertRaises(ValueError):
            query(graph,'WITH RECURSIVE t(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM t) SELECT SUM(x) FROM t')

    def test_styles_angular_sass_and_external(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            files={'app.ts':'''@Component({styleUrls: ['./app.scss']})
              // styleUrl: './ghost.css'
              export class App {}''',
                   'other.ts':"@Component({styleUrl: './reset.css'}) export class Other {}",
                   'app.scss':"@use './palette'; @import './reset.css'; @import 'https://example.com/x.css';",
                   '_palette.scss':'$accent: pink;', 'reset.css':'body { margin: 0; }'}
            for name,source in files.items():(root/name).write_text(source,encoding='utf-8')
            graph=scan(root)
            self.assertEqual(graph['summary']['files'],5)
            self.assertEqual(graph['summary']['edges'],4)
            self.assertEqual(graph['summary']['unresolved'],0)
            self.assertEqual({n['language'] for n in graph['nodes']},{'TypeScript','SCSS','CSS'})
            self.assertEqual(route(graph,'app.ts','_palette.scss')['hops'],2)
            self.assertTrue(all(e['kind']=='style' for e in graph['edges']))

if __name__=='__main__':unittest.main()
