"""Install optional compiler engines for deep analysis; no repository code is run."""
from pathlib import Path
import shutil
import subprocess
import sys

root=Path(__file__).parent
try:
    npm=shutil.which('npm');dotnet=shutil.which('dotnet')
    if not npm or not dotnet:
        raise RuntimeError('Instala Node.js (14.17 o superior) y .NET SDK 9 antes de continuar.')
    subprocess.run([npm,'ci','--ignore-scripts','--no-audit','--no-fund'],cwd=root/'engines',check=True)
    subprocess.run([dotnet,'build','Roslyn.csproj','-c','Release','--nologo'],cwd=root/'engines/Roslyn',check=True)
    print('Motores listos. Reinicia MapaLocal o vuelve a analizar en modo Profundo.')
except (OSError,RuntimeError,subprocess.CalledProcessError) as error:
    print(f'No se pudo preparar el análisis profundo: {error}',file=sys.stderr)
    sys.exit(1)
