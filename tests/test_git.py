from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analyzer import scan


@unittest.skipUnless(shutil.which('git'),'Git is required for native ignore tests')
class GitTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def git(self,*args):
        return subprocess.run(['git','-c','core.fsmonitor=false','-C',str(self.root),*args],check=True,capture_output=True).stdout.decode().strip()
    def put(self,name,content='export class A {}'):
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content,encoding='utf-8')
    def test_nested_ignores_negation_tracked_and_subdirectory(self):
        self.git('init','-b','feature/mapa')
        self.put('tracked.ts');self.git('add','tracked.ts')
        self.put('.gitignore','*.skip.ts\ntracked.ts\ngenerated/\n*.tmp.ts\n!keep.tmp.ts\n')
        self.put('tracked.ts');self.put('skip.skip.ts');self.put('keep.tmp.ts');self.put('gone.tmp.ts')
        self.put('generated/skip.ts');self.put('src/.gitignore','local.ts\n');self.put('src/local.ts');self.put('src/visible.ts')
        self.put('src/space ü.ts');self.put('.git/info/exclude','info.ts\n');self.put('info.ts')
        graph=scan(self.root)
        self.assertEqual({n['id'] for n in graph['nodes']},{'tracked.ts','keep.tmp.ts','src/visible.ts','src/space ü.ts'})
        self.assertEqual(graph['git']['branch'],'feature/mapa')
        self.assertTrue(graph['git']['ignore_applied'])
        self.assertEqual({n['id'] for n in scan(self.root/'src')['nodes']},{'visible.ts','space ü.ts'})
    def test_plain_folder_uses_gitignore_without_creating_git(self):
        self.put('.gitignore','*.ts\n!visible.ts\n');self.put('visible.ts');self.put('hidden.ts')
        graph=scan(self.root)
        self.assertEqual([n['id'] for n in graph['nodes']],['visible.ts'])
        self.assertFalse(graph['git']['repository'])
        self.assertFalse((self.root/'.git').exists())
    def test_detached_and_linked_worktree(self):
        self.git('init','-b','main');self.put('app.ts');self.git('add','app.ts')
        self.git('-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','fixture')
        commit=self.git('rev-parse','HEAD')
        self.git('checkout','--detach',commit)
        graph=scan(self.root)
        self.assertTrue(graph['git']['detached']);self.assertEqual(graph['git']['commit'],commit)
        worktree=self.root/'linked'
        self.git('worktree','add','-b','linked-branch',str(worktree),commit)
        self.assertEqual(scan(worktree)['git']['branch'],'linked-branch')
    def test_missing_git_warns(self):
        self.put('app.ts')
        with patch('git_info.shutil.which',return_value=None):graph=scan(self.root)
        self.assertFalse(graph['git']['available'])
        self.assertTrue(any('.gitignore' in w for w in graph['warnings']))

    def test_embedded_repository_is_still_scanned(self):
        self.git('init','-b','main')
        self.put('nested/app.ts');self.put('nested/skip.ts');self.put('nested/.gitignore','skip.ts\n')
        self.git('-C',str(self.root/'nested'),'init','-b','inner')
        graph=scan(self.root)
        self.assertEqual({n['id'] for n in graph['nodes']},{'nested/app.ts'})
        self.assertEqual(graph['git']['nested_repositories'][0]['branch'],'inner')

if __name__=='__main__':unittest.main()
