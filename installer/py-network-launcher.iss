[Setup]
AppId={{5E296F2B-0E9B-4A9F-8E36-0D31E5D8A4C7}
AppName=Py Network Launcher
AppVersion=0.1.0
DefaultDirName={autopf}\Py Network Launcher
DefaultGroupName=Py Network Launcher
UninstallDisplayIcon={app}\Py Network Launcher.exe
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
OutputDir=dist
OutputBaseFilename=PyNetworkLauncherSetup

[Files]
Source: "..\dist\Py Network Launcher\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Py Network Launcher"; Filename: "{app}\Py Network Launcher.exe"
Name: "{autodesktop}\Py Network Launcher"; Filename: "{app}\Py Network Launcher.exe"

[Run]
Filename: "{cmd}"; Parameters: "/C netsh advfirewall firewall delete rule name=""Py Network Launcher TCP"""; Flags: runhidden
Filename: "{cmd}"; Parameters: "/C netsh advfirewall firewall delete rule name=""Py Network Launcher UDP"""; Flags: runhidden
Filename: "{cmd}"; Parameters: "/C netsh advfirewall firewall add rule name=""Py Network Launcher TCP"" dir=in action=allow program=""{app}\Py Network Launcher.exe"" protocol=TCP profile=private enable=yes"; Flags: runhidden
Filename: "{cmd}"; Parameters: "/C netsh advfirewall firewall add rule name=""Py Network Launcher UDP"" dir=in action=allow program=""{app}\Py Network Launcher.exe"" protocol=UDP profile=private enable=yes"; Flags: runhidden
Filename: "{app}\Py Network Launcher.exe"; Description: "Lancer Py Network Launcher"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C netsh advfirewall firewall delete rule name=""Py Network Launcher TCP"""; Flags: runhidden
Filename: "{cmd}"; Parameters: "/C netsh advfirewall firewall delete rule name=""Py Network Launcher UDP"""; Flags: runhidden
