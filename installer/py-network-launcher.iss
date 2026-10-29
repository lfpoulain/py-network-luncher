; Installeur Windows de Py Network Launcher (Inno Setup 6).
; Généré par scripts\build.ps1 : ISCC.exe /DAppVersion=x.y.z installer\py-network-launcher.iss

#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif
#define AppName "Py Network Launcher"
#define AppExe "Py Network Launcher.exe"
#define AppUrl "https://github.com/lfpoulain/py-network-luncher"

[Setup]
AppId={{5E296F2B-0E9B-4A9F-8E36-0D31E5D8A4C7}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=LFPoulain
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
AppUpdatesURL={#AppUrl}/releases
VersionInfoProductVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
SetupIconFile=..\assets\app_icon.ico
LicenseFile=..\LICENSE
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
; L'application en cours est arrêtée par StopRunningApp ([Code]) ; le gestionnaire de redémarrage reste en secours.
CloseApplications=yes
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
OutputDir=..\dist
OutputBaseFilename=PyNetworkLauncher-Setup-{#AppVersion}

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\{#AppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; Supprime l'entrée « démarrer avec Windows » créée par l'application lors de la désinstallation.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "{#AppName}"; Flags: uninsdeletevalue dontcreatekey

[Run]
; Autorise l'API (TCP) et la découverte (UDP) sur les réseaux privés.
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#AppName} TCP"""; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#AppName} UDP"""; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""{#AppName} TCP"" dir=in action=allow program=""{app}\{#AppExe}"" protocol=TCP profile=private,domain enable=yes"; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""{#AppName} UDP"" dir=in action=allow program=""{app}\{#AppExe}"" protocol=UDP profile=private,domain enable=yes"; Flags: runhidden
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#AppName} TCP"""; Flags: runhidden; RunOnceId: "DelFirewallTcp"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#AppName} UDP"""; Flags: runhidden; RunOnceId: "DelFirewallUdp"

[Code]
// Fermer la fenêtre ne quitte pas l'application (elle se réduit dans la zone de notification) : ni la demande de
// fermeture d'Inno Setup ni le gestionnaire de redémarrage de Windows ne peuvent l'arrêter. On arrête donc le
// processus avec son arborescence (flet.exe). Une modification non encore sauvegardée l'est en moins d'une seconde.
procedure StopRunningApp();
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM "{#AppExe}"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  if ResultCode = 0 then
    Sleep(500);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopRunningApp();
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  StopRunningApp();
  Result := True;
end;
