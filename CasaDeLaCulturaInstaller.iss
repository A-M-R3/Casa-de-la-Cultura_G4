[Setup]
AppName=Casa de la Cultura
AppVersion=1.0
DefaultDirName={localappdata}\Casa de la Cultura
DefaultGroupName=Casa de la Cultura
OutputBaseFilename=CasaDeLaCultura_Installer
Compression=lzma2/ultra
SolidCompression=yes
DisableProgramGroupPage=no
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64os
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=.

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs; Excludes: "venv\*;python_embed\*;repositories\*;*.pyc;__pycache__\*;*.zip;*.iss;.git\*"
Source: "logo.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "python_embed\*"; DestDir: "{app}\python_embed"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Casa de la Cultura"; Filename: "{app}\run_app.bat"; WorkingDir: "{app}"; IconFilename: "{app}\logo.ico"
Name: "{userdesktop}\Casa de la Cultura"; Filename: "{app}\run_app.bat"; WorkingDir: "{app}"; Tasks: desktopicon; IconFilename: "{app}\logo.ico"
