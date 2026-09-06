#define MyAppName "Manual Studio Qt5"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "DSW"
#define MyAppExeName "ManualStudioQt5.exe"
#define MyRoot SourcePath + "..\"

[Setup]
AppId={{6E05CE39-21F3-4E84-8D56-11E29775B17D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Manual Studio Qt5
DefaultGroupName=Manual Studio Qt5
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputDir={#MyRoot}dist
OutputBaseFilename=ManualStudioQt5_Setup
SetupIconFile={#MyRoot}assets\manual_studio.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "{#MyRoot}build\ManualStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Manual Studio Qt5"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Manual Studio Qt5"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Executar Manual Studio Qt5"; Flags: nowait postinstall skipifsilent
