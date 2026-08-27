; Inno Setup script for Vocal Remover.
; Build with: ISCC.exe installer.iss
; Requires the onedir PyInstaller build to already exist at dist\VocalRemover\
; (run build.spec first -- see scripts\release.ps1 for the full one-command flow).
;
; Installs per-user (no admin/UAC prompt) so an unsigned installer doesn't need
; elevation -- see CLAUDE.md for why the app is unsigned (cost, personal project).

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

#define MyAppName "Vocal Remover"
#define MyAppExeName "VocalRemover.exe"
#define MyAppPublisher "Volta Softwares"

[Setup]
AppId={{B6C4D1F0-6C6C-4B77-9E9A-6B7E6B0A0A11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\VocalRemover
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist\installer
OutputBaseFilename=VocalRemoverSetup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=app\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "dist\VocalRemover\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
