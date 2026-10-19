; Inno Setup — ltts Windows-приложение
; iscc /DRepoRoot=D:\WORK\local-tts packaging\windows\ltts.iss

#ifndef RepoRoot
  #define RepoRoot "..\..\"
#endif

#define AppName "ltts"
#define AppVersion "0.1.0"
#define AppPublisher "ltts"
#define AppExeName "ltts-desktop.exe"
#define DistDir RepoRoot + "dist\ltts"
#define AppIcon RepoRoot + "src\ltts\assets\app.ico"

[Setup]
SetupIconFile={#AppIcon}
UninstallDisplayIcon={app}\{#AppExeName}
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\ltts
DefaultGroupName=ltts
DisableProgramGroupPage=yes
OutputDir={#RepoRoot}dist
OutputBaseFilename=ltts-setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Значок на рабочем столе"; GroupDescription: "Дополнительно:"
Name: "autostart"; Description: "Запускать ltts при входе в Windows"; GroupDescription: "Дополнительно:"; Flags: unchecked

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\ltts"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"
Name: "{group}\ltts (консоль)"; Filename: "{app}\ltts.exe"; Parameters: "doctor"; IconFilename: "{app}\ltts.exe"
Name: "{autodesktop}\ltts"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Запустить ltts"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
function IsWebView2Installed: Boolean;
var
  Ver: String;
begin
  Result := RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Ver) or
            RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Ver);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if WizardIsTaskSelected('autostart') then
      RegWriteStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'ltts', ExpandConstant('"{app}\{#AppExeName}"'));
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'ltts');
end;

function InitializeSetup(): Boolean;
begin
  if not IsWebView2Installed then
    MsgBox('Для окна ltts нужен Microsoft WebView2 Runtime. Если окно не откроется — установите WebView2 с сайта Microsoft.', mbInformation, MB_OK);
  Result := True;
end;
