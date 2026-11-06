"""Local snapshots. Atomic writes; history contains metadata, not source contents."""
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
from uuid import uuid4


class History:
    def __init__(self, directory):
        self.directory = Path(directory)

    def path(self, identifier):
        if not isinstance(identifier, str) or not re.fullmatch(r'[a-f0-9]{32}', identifier):
            raise ValueError('Identificador de análisis inválido.')
        return self.directory / (identifier + '.json')

    def save(self, graph, view=None, label='Análisis automático'):
        identifier = uuid4().hex
        snapshot = {'format': 'mapalocal', 'version': 1, 'id': identifier,
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'label': str(label)[:120], 'graph': graph, 'view': view}
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self.path(identifier)
        temporary = target.with_suffix('.tmp')
        try:
            temporary.write_text(json.dumps(snapshot, ensure_ascii=False, allow_nan=False), encoding='utf-8')
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        return snapshot

    def load(self, identifier):
        snapshot = json.loads(self.path(identifier).read_text(encoding='utf-8'))
        if snapshot.get('format') != 'mapalocal' or snapshot.get('version') != 1:
            raise ValueError('Formato de análisis no compatible.')
        return snapshot

    def list(self):
        results = []
        for path in sorted(self.directory.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                snapshot = self.load(path.stem)
                results.append({key: snapshot[key] for key in ('id','created_at','label')} |
                               {'root': snapshot['graph']['root'], 'summary': snapshot['graph']['summary'],
                                'git': snapshot['graph'].get('git'), 'has_view': bool(snapshot.get('view'))})
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return results


def validate_view(view, graph):
    if not isinstance(view, dict):
        raise ValueError('Vista inválida.')
    ids = {n['id'] for n in graph['nodes']}
    def number(value):
        return isinstance(value, (int,float)) and not isinstance(value,bool) and math.isfinite(value) and abs(value) < 1e9
    positions = view.get('positions')
    if not isinstance(positions, dict) or set(positions) != ids:
        raise ValueError('Las posiciones no corresponden al análisis activo.')
    for position in positions.values():
        if not isinstance(position, dict) or not all(number(position.get(k)) for k in ('x','y')):
            raise ValueError('Posición inválida.')
    camera = view.get('camera', {})
    if not isinstance(camera, dict) or not all(number(camera.get(k)) for k in ('x','y','k')) or not .01 <= camera['k'] <= 12:
        raise ValueError('Zoom o cámara inválidos.')
    if len(json.dumps(view)) > 4_000_000:
        raise ValueError('Vista demasiado grande.')
    return view
