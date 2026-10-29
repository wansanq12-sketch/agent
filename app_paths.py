"""Keep writable user data outside a frozen executable's temporary resources."""
import os
from pathlib import Path
import sys

def data_directory(root, frozen=None, environment=None):
    environment=os.environ if environment is None else environment
    frozen=getattr(sys,'frozen',False) if frozen is None else frozen
    if environment.get('COMPANION_DATA_DIR'):
        return Path(environment['COMPANION_DATA_DIR'])
    if frozen:
        local=environment.get('LOCALAPPDATA')
        return (Path(local) if local else Path.home()/'AppData/Local')/'Yeli/data'
    return Path(root)/'data'
