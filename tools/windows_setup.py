"""User-invoked Windows installation and launch, isolated in a project venv."""
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
if os.name!='nt':raise SystemExit('Windows only')
if not (3,11)<=sys.version_info[:2]<=(3,12):raise SystemExit('Please install Python 3.11 or 3.12 (64-bit) from python.org, then try again.')
python=ROOT/'.venv-windows/Scripts/python.exe'
try:
    if not python.exists():subprocess.run([sys.executable,'-m','venv',str(ROOT/'.venv-windows')],check=True)
    if '--setup' in sys.argv or not (ROOT/'.venv-windows/ready').exists():
        subprocess.run([str(python),'-m','pip','install','-r',str(ROOT/'requirements-windows.txt')],check=True)
        (ROOT/'.venv-windows/ready').touch()
    subprocess.run([str(python),str(ROOT/'tools/launch.py')],cwd=ROOT,check=True)
except (OSError,subprocess.CalledProcessError) as exc:
    print('Setup or launch failed:',exc);input('Press Enter to close...');raise SystemExit(1)
