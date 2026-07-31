#define MyAppName "视频深度控制图工具"
#define MyAppEnglishName "Contour Control Tool"
#define MyAppPublisher "ZhaoDesign"
#define MyAppVersion GetEnv("APP_VERSION")
#if MyAppVersion == ""
#define MyAppVersion "0.1.0"
#endif
#define MyAppExeName "pythonw.exe"

[Setup]
AppId={{8E32A2D1-F74A-4B6C-A9D5-3F8B56C0FD22}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Contour Control Tool
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
SetupIconFile=..\..\assets\depth-video-converter.ico
UninstallDisplayIcon={app}\assets\depth-video-converter.ico
OutputDir=..\..\dist\windows-installer
OutputBaseFilename=ContourControlTool-Windows-x64-WebSetup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UsePreviousAppDir=yes
AlwaysRestart=no
RestartIfNeededByRun=no
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "desktopuninstall"; Description: "Create a desktop quick uninstall shortcut"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\desktop_launcher.py"; DestDir: "{app}\app"; Flags: ignoreversion; BeforeInstall: StopExistingApp
Source: "..\..\depth_video_converter.py"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\..\depth_video_cli.py"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\README_CN.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\assets\depth-video-converter.ico"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\..\assets\depth-video-converter.png"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\..\depth_converter\*"; DestDir: "{app}\app\depth_converter"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\depth_anything_v2\*"; DestDir: "{app}\app\depth_anything_v2"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "install_runtime.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "runtime-requirements-cpu.txt"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "verify_runtime.py"; DestDir: "{app}\installer"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{localappdata}\CCT\rt311cpu\{#MyAppExeName}"; Parameters: """{app}\app\desktop_launcher.py"""; WorkingDir: "{app}"; IconFilename: "{app}\assets\depth-video-converter.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"; IconFilename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{localappdata}\CCT\rt311cpu\{#MyAppExeName}"; Parameters: """{app}\app\desktop_launcher.py"""; WorkingDir: "{app}"; IconFilename: "{app}\assets\depth-video-converter.ico"; Tasks: desktopicon
Name: "{autodesktop}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"; IconFilename: "{uninstallexe}"; Tasks: desktopuninstall

[Run]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\install_runtime.ps1"" -InstallDir ""{app}"""; StatusMsg: "正在联网下载并安装运行环境，首次安装可能需要几分钟..."; Flags: waituntilterminated
Filename: "{localappdata}\CCT\rt311cpu\{#MyAppExeName}"; Parameters: """{app}\app\desktop_launcher.py"""; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent unchecked

[UninstallDelete]
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\assets"
Type: filesandordirs; Name: "{app}\installer"
Type: filesandordirs; Name: "{localappdata}\CCT\rt311cpu"
Type: dirifempty; Name: "{localappdata}\CCT"

[Code]
procedure StopExistingApp;
var
  ResultCode: Integer;
  PowerShellArgs: String;
begin
  PowerShellArgs :=
    '-NoProfile -ExecutionPolicy Bypass -Command "' +
    '$procs = Get-CimInstance Win32_Process | Where-Object { ' +
    '$_.CommandLine -like ''*desktop_launcher.py*'' -or ' +
    '$_.ExecutablePath -like ''*\\CCT\\rt311cpu\\pythonw.exe'' ' +
    '}; ' +
    'foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }"';
  Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'), PowerShellArgs, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;
