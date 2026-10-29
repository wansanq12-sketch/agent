; Version is supplied from the repository's VERSION file by the build workflow.
#ifndef AppVersion
  #error AppVersion must be supplied with /DAppVersion=major.minor.patch
#endif
[Setup]
AppId={{F3549C87-9EB4-4F88-8E66-95527B911C93}
AppName=夜璃
AppVersion={#AppVersion}
AppVerName=夜璃 {#AppVersion}
AppPublisher=夜璃
VersionInfoVersion={#AppVersion}.0
DefaultDirName={localappdata}\Programs\Yeli
DefaultGroupName=夜璃
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
UsePreviousAppDir=yes
DisableProgramGroupPage=yes
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\Yeli.ico
OutputDir=..\dist
OutputBaseFilename=Yeli-Setup-{#AppVersion}-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
SetupIconFile=..\assets\icons\yeli.ico
ShowLanguageDialog=no

[Languages]
Name: "chinesesimplified"; MessagesFile: "languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; Flags: unchecked

[Files]
Source: "..\assets\icons\yeli.ico"; DestDir: "{app}"; DestName: "Yeli.ico"; Flags: ignoreversion
Source: "..\dist\Yeli.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README-EXE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\skills\hex-aram\*"; DestDir: "{app}\skills\hex-aram"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\夜璃"; Filename: "{app}\Yeli.exe"; IconFilename: "{app}\Yeli.ico"
Name: "{autodesktop}\夜璃"; Filename: "{app}\Yeli.exe"; Tasks: desktopicon; IconFilename: "{app}\Yeli.ico"

[Run]
Filename: "{app}\Yeli.exe"; Description: "启动夜璃"; Flags: nowait postinstall skipifsilent

; User data is NEVER installed, overwritten, or removed by this installer.
; Stable location: %LOCALAPPDATA%\Yeli\data (shared with older EXE releases).
