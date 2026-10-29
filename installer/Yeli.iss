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
UninstallDisplayIcon={app}\Yeli.exe
OutputDir=..\dist
OutputBaseFilename=Yeli-Setup-{#AppVersion}-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\Yeli.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README-EXE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\skills\hex-aram\*"; DestDir: "{app}\skills\hex-aram"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\夜璃"; Filename: "{app}\Yeli.exe"
Name: "{autodesktop}\夜璃"; Filename: "{app}\Yeli.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Yeli.exe"; Description: "Launch Yeli"; Flags: nowait postinstall skipifsilent

; User data is NEVER installed, overwritten, or removed by this installer.
; Stable location: %LOCALAPPDATA%\Yeli\data (shared with older EXE releases).
