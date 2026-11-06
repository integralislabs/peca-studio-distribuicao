#define AppVersion "1.9.1"
[Setup]
AppId={{957614DF-7227-47A9-A66A-2834CB6D3200}
AppName=Peça Studio
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\PecaStudio
DefaultGroupName=Peça Studio
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputBaseFilename=PecaStudio-Setup-{#AppVersion}
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\brand\integralis-icon.ico
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\PecaStudio.exe
[Files]
Source: "{#BuildDir}\PecaStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Peça Studio"; Filename: "{app}\PecaStudio.exe"
[Run]
Filename: "{app}\PecaStudio.exe"; Description: "Abrir Peça Studio"; Flags: nowait postinstall skipifsilent unchecked



