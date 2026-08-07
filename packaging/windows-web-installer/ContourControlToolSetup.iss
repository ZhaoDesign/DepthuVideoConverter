#define MyAppName "DepthuVideoConverter"
#define MyAppEnglishName "DepthuVideoConverter"
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
AppPublisherURL=https://github.com/ZhaoDesign/DepthuVideoConverter
AppSupportURL=https://github.com/ZhaoDesign/DepthuVideoConverter/issues
DefaultDirName={localappdata}\Programs\DepthuVideoConverter
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
SetupIconFile=..\..\assets\contour-control-tool.ico
WizardImageFile=..\..\assets\installer-banner.bmp
WizardSmallImageFile=..\..\assets\installer-small.bmp
UninstallDisplayIcon={app}\assets\contour-control-tool.ico
OutputDir=..\..\dist\windows-installer
OutputBaseFilename=DepthuVideoConverter-Windows-x64-WebSetup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
UsePreviousAppDir=yes
UsePreviousTasks=no
AlwaysRestart=no
RestartIfNeededByRun=no
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
SetupWindowTitle=安装 - {#MyAppName}
WelcomeLabel1=欢迎使用 {#MyAppName} 安装向导
WelcomeLabel2=此向导将把 {#MyAppName} 安装到您的电脑，并在安装过程中联网准备所需运行环境。整个过程不会打开浏览器或命令行窗口。
WizardSelectDir=选择安装位置
SelectDirDesc=选择安装位置
SelectDirLabel3=安装程序将把 {#MyAppName} 安装到以下文件夹。
SelectDirBrowseLabel=如需安装到其他位置，请点击“浏览”选择文件夹。
ReadyLabel1=安装程序已准备好开始安装 {#MyAppName}。
ReadyLabel2a=点击“安装”开始复制文件、创建快捷方式并安装运行环境。
InstallingLabel=正在安装 {#MyAppName}，请稍候。
FinishedHeadingLabel=完成 {#MyAppName} 安装向导
FinishedLabelNoIcons={#MyAppName} 已安装完成。
FinishedLabel={#MyAppName} 已安装完成。可通过桌面或开始菜单快捷方式启动。
ButtonNext=下一步(&N) >
ButtonBack=< 上一步(&B)
ButtonInstall=安装(&I)
ButtonFinish=完成(&F)
ButtonCancel=取消
ButtonBrowse=浏览(&B)...
ButtonWizardBrowse=浏览(&R)...
BrowseDialogTitle=选择文件夹
BrowseDialogLabel=请选择安装文件夹，然后点击“确定”。
StatusClosingApplications=正在关闭已运行的应用...
StatusCreateDirs=正在创建文件夹...
StatusExtractFiles=正在复制应用文件...
StatusCreateIcons=正在创建快捷方式...
StatusSavingUninstall=正在写入卸载信息...
StatusRunProgram=正在准备运行环境...
UninstallAppTitle=卸载
UninstallAppFullTitle=卸载 %1
ConfirmUninstall=确定要完全移除 %1 吗？
UninstallStatusLabel=正在从电脑中移除 %1，请稍候。
UninstalledAll=%1 已成功从电脑中移除。

[CustomMessages]
LaunchProgram=启动 %1

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加快捷方式"; Flags: checkedonce

[Files]
Source: "..\..\desktop_launcher.py"; DestDir: "{app}\app"; Flags: ignoreversion; BeforeInstall: StopExistingApp
Source: "..\..\desktop_qt_app.py"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\..\depth_video_converter.py"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\..\depth_video_cli.py"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\README_CN.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\assets\depth-video-converter.ico"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\..\assets\depth-video-converter.png"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\..\assets\contour-control-tool.ico"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\..\assets\contour-control-tool.png"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\..\assets\icon-play.png"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\..\assets\icon-pause.png"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\..\assets\icon-volume.png"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\..\assets\icon-volume-muted.png"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\..\assets\icon-folder.png"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\..\assets\icon-chevron-down.png"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\..\assets\icon-more.png"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\..\assets\icon-chevron-right.png"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\..\assets\icon-check-dark.png"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\..\assets\icon-fullscreen.png"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\..\assets\checkmark.png"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\..\depth_converter\*"; DestDir: "{app}\app\depth_converter"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\depth_anything_v2\*"; DestDir: "{app}\app\depth_anything_v2"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "install_runtime.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "runtime-requirements-cpu.txt"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "verify_runtime.py"; DestDir: "{app}\installer"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{localappdata}\CCT\rt311cpu\{#MyAppExeName}"; Parameters: """{app}\app\desktop_qt_app.py"""; WorkingDir: "{app}"; IconFilename: "{app}\assets\contour-control-tool.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{localappdata}\CCT\rt311cpu\{#MyAppExeName}"; Parameters: """{app}\app\desktop_qt_app.py"""; WorkingDir: "{app}"; IconFilename: "{app}\assets\contour-control-tool.ico"; Tasks: desktopicon

[Run]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\install_runtime.ps1"" -InstallDir ""{app}"""; StatusMsg: "正在联网下载并安装运行环境，首次安装可能需要几分钟..."; Flags: waituntilterminated runhidden
Filename: "{localappdata}\CCT\rt311cpu\{#MyAppExeName}"; Parameters: """{app}\app\desktop_qt_app.py"""; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent unchecked; Check: RuntimeAlreadyInstalled

[InstallDelete]
Type: files; Name: "{group}\{#MyAppName}.lnk"
Type: files; Name: "{autodesktop}\{#MyAppName}.lnk"
Type: files; Name: "{group}\Uninstall {#MyAppName}.lnk"
Type: files; Name: "{autodesktop}\Uninstall {#MyAppName}.lnk"
Type: files; Name: "{group}\卸载 {#MyAppName}.lnk"
Type: files; Name: "{autodesktop}\卸载 {#MyAppName}.lnk"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\assets"
Type: filesandordirs; Name: "{app}\installer"
Type: filesandordirs; Name: "{localappdata}\CCT\rt311cpu"
Type: dirifempty; Name: "{localappdata}\CCT"

[Code]
function RuntimeAlreadyInstalled: Boolean;
var
  MarkerPath: String;
begin
  MarkerPath := ExpandConstant('{localappdata}\CCT\rt311cpu\.runtime-cpu-ok');
  Result := FileExists(MarkerPath) and FileExists(ExpandConstant('{localappdata}\CCT\rt311cpu\pythonw.exe'));
end;

function VCRedistInstalled: Boolean;
begin
  Result := FileExists(ExpandConstant('{sys}\vcruntime140.dll')) and
            FileExists(ExpandConstant('{sys}\vcruntime140_1.dll'));
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  MarkerPath: String;
begin
  if CurStep = ssPostInstall then
  begin
    MarkerPath := ExpandConstant('{localappdata}\CCT\rt311cpu\.runtime-cpu-ok');
    if not FileExists(MarkerPath) then
    begin
      MsgBox('运行环境安装未成功完成。可能原因：' + #13#10 +
             '• 网络连接不稳定' + #13#10 +
             '• 防火墙阻止下载' + #13#10 +
             '• 磁盘空间不足' + #13#10 + #13#10 +
             '请检查日志：' + #13#10 +
             ExpandConstant('{localappdata}\DepthuVideoConverter\installer.log') + #13#10 + #13#10 +
             '可重新运行安装程序以重试。', mbError, MB_OK);
    end;
    if not VCRedistInstalled then
    begin
      MsgBox('未检测到 Visual C++ 运行库 (vcruntime140.dll)。' + #13#10 +
             '应用启动可能失败。' + #13#10 + #13#10 +
             '请下载安装 Microsoft Visual C++ Redistributable：' + #13#10 +
             'https://aka.ms/vs/17/release/vc_redist.x64.exe', mbInformation, MB_OK);
    end;
  end;
end;

procedure StopExistingApp;
var
  ResultCode: Integer;
  PowerShellArgs: String;
begin
  PowerShellArgs :=
    '-NoProfile -ExecutionPolicy Bypass -Command "' +
    '$procs = Get-CimInstance Win32_Process | Where-Object { ' +
    '$_.CommandLine -like ''*desktop_launcher.py*'' -or ' +
    '$_.CommandLine -like ''*desktop_qt_app.py*'' -or ' +
    '$_.ExecutablePath -like ''*\\CCT\\rt311cpu\\pythonw.exe'' ' +
    '}; ' +
    'foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }"';
  Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'), PowerShellArgs, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;
