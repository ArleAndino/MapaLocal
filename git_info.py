"""Read-only Git discovery, including native ignore semantics."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def git_context(root):
    executable = shutil.which('git')
    metadata = {'available': bool(executable), 'repository': False, 'branch': None,
                'commit': None, 'detached': False, 'ignore_applied': False}
    if not executable:
        return metadata, None, ['Git no está instalado: no se aplicó .gitignore ni se pudo consultar la rama.']
    env = dict(os.environ)
    for key in ('GIT_DIR','GIT_WORK_TREE','GIT_INDEX_FILE','GIT_COMMON_DIR','GIT_PREFIX'):
        env.pop(key, None)
    env['GIT_OPTIONAL_LOCKS'] = '0'
    base = [executable, '-c', 'core.fsmonitor=false', '-C', str(root)]
    def run(args, prefix=None):
        return subprocess.run((prefix or base) + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              env=env, timeout=30, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    def text(result):
        return result.stdout.decode('utf-8', errors='replace').strip()
    try:
        probe = run(['rev-parse','--show-toplevel'])
        if probe.returncode == 0:
            metadata.update(repository=True, root=text(probe))
            branch = run(['symbolic-ref','--quiet','--short','HEAD'])
            commit = run(['rev-parse','--verify','HEAD'])
            metadata.update(branch=text(branch) if branch.returncode == 0 else None,
                            commit=text(commit) if commit.returncode == 0 else None,
                            detached=branch.returncode != 0 and commit.returncode == 0)
            result = run(['ls-files','--cached','--others','--exclude-standard','-z','--','.'])
        else:
            # Only use a temporary index for ordinary folders. Never initialize the user's folder.
            if any((p/'.git').exists() for p in (root, *root.parents)):
                raise ValueError(probe.stderr.decode('utf-8', errors='replace').strip())
            with tempfile.TemporaryDirectory(prefix='mapalocal-git-') as directory:
                init = run(['init','--bare','--template=',directory])
                if init.returncode:
                    raise ValueError('No se pudo preparar el lector temporal de .gitignore.')
                prefix = [executable, '-c','core.bare=false','-c','core.fsmonitor=false',
                          '--git-dir='+directory, '--work-tree='+str(root), '-C',str(root)]
                result = run(['ls-files','--others','--exclude-standard','-z','--','.'], prefix)
        if result.returncode:
            raise ValueError(result.stderr.decode('utf-8',errors='replace').strip())
        paths = {part.decode('utf-8', errors='surrogateescape') for part in result.stdout.split(b'\0') if part}
        # Git reports embedded repositories/submodules as directory entries.
        # Keep recursive repository scanning, applying each nested repository's rules.
        nested_repositories = []
        nested_warnings = []
        for name in list(paths):
            child = root / name
            if child.is_dir() and not child.is_symlink() and child.resolve().is_relative_to(root.resolve()) and child.resolve() != root.resolve():
                paths.remove(name)
                child_info, child_paths, child_warnings = git_context(child.resolve())
                nested_repositories.append(child_info)
                nested_warnings.extend(child_warnings)
                if child_paths is not None:
                    paths.update((Path(name)/entry).as_posix() for entry in child_paths)
        if nested_repositories:
            metadata['nested_repositories'] = nested_repositories
        metadata['ignore_applied'] = True
        return metadata, paths, nested_warnings
    except (OSError, subprocess.TimeoutExpired, ValueError) as error:
        raise ValueError(f'No se pudo leer la configuración Git: {error}') from error
