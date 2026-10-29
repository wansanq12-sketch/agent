# Build on Windows with: python -m PyInstaller --noconfirm Yeli-Windows.spec
import json
from pathlib import Path
from PyInstaller.utils.hooks import collect_all
root=Path(SPECPATH)
datas=[]
for folder in ('web','skills','config'):
    for p in (root/folder).rglob('*'):
        if p.is_file() and not p.is_symlink() and not p.name.startswith('.'):
            datas.append((str(p),str(p.relative_to(root).parent)))
datas.append((str(root/'assets/yeli-reference-v1.png'),'assets'))
datas.append((str(root/'assets/actions/manifest.json'),'assets/actions'))
manifest=json.loads((root/'assets/actions/manifest.json').read_text(encoding='utf-8'))
for name in sorted({a['file'] for a in manifest['actions'].values()}):
    datas.append((str(root/'assets/actions'/name),'assets/actions'))
binaries=[];hiddenimports=[]
for package in ('rapidocr_onnxruntime','onnxruntime'):
    data,binary,hidden=collect_all(package)
    datas+=data;binaries+=binary;hiddenimports+=hidden
analysis=Analysis([str(root/'windows_main.py')],pathex=[str(root)],binaries=binaries,datas=datas,hiddenimports=hiddenimports,hookspath=[],hooksconfig={},runtime_hooks=[],excludes=['tkinter','pytest'],noarchive=False)
pyz=PYZ(analysis.pure)
exe=EXE(pyz,analysis.scripts,analysis.binaries,analysis.datas,[],name='Yeli',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False,disable_windowed_traceback=False)
