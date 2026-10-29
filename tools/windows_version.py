"""Generate Windows file-version metadata from the single release VERSION file."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

def generate():
    version = (ROOT / 'VERSION').read_text(encoding='ascii').strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Invalid release version')
    numbers = tuple(int(part) for part in version.split('.')) + (0,)
    if any(number > 65535 for number in numbers):
        raise ValueError('Windows version components must be <= 65535')
    destination = ROOT / 'build/windows-version.txt'
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(f'''VSVersionInfo(
 ffi=FixedFileInfo(filevers={numbers!r},prodvers={numbers!r},mask=0x3f,flags=0x0,OS=0x40004,fileType=0x1,subtype=0x0,date=(0,0)),
 kids=[StringFileInfo([StringTable('040904B0',[
  StringStruct('CompanyName','Yeli'),StringStruct('FileDescription','Yeli Desktop Companion'),
  StringStruct('FileVersion','{version}'),StringStruct('ProductVersion','{version}'),
  StringStruct('ProductName','Yeli'),StringStruct('OriginalFilename','Yeli.exe')])]),
  VarFileInfo([VarStruct('Translation',[1033,1200])])])
''', encoding='utf-8')
    return destination

if __name__ == '__main__':
    print(generate())
