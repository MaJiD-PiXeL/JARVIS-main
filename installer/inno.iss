[Setup]
AppName=دستیار فارسی جارویس
AppVersion=1.0
AppPublisher=Jarvis Team
DefaultDirName={pf}\JarvisAssistant
DefaultGroupName=دستیار فارسی جارویس
OutputDir=output
OutputBaseFilename=JarvisInstaller
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
WizardStyle=modern
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\Jarvis.exe
DisableProgramGroupPage=no


[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"


[Files]
; Copy FULL PyInstaller folder
Source: "..\dist\Jarvis\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion


[Icons]
; Start Menu shortcut
Name: "{group}\جارویس فارسی"; Filename: "{app}\Jarvis.exe"

; Desktop shortcut
Name: "{commondesktop}\جارویس فارسی"; Filename: "{app}\Jarvis.exe"


[Run]
; Launch after install
Filename: "{app}\Jarvis.exe"; Description: "اجرای جارویس فارسی"; Flags: nowait postinstall skipifsilent
