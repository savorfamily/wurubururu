; Windows 설치 파일 (Inno Setup 6). 실행: iscc /DMyAppVersion=0.1.0 packaging\wurubururu.iss
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

[Setup]
AppId={{8C1E8B9A-4A5F-4C59-9D7B-2F1C3E5A9B10}
AppName=wurubururu
AppVerName=우르부르 {#MyAppVersion}
AppVersion={#MyAppVersion}
AppPublisher=Savorfamily
AppPublisherURL=https://github.com/savorfamily/wurubururu
DefaultDirName={localappdata}\Programs\wurubururu
DefaultGroupName=우르부르
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=wurubururu-{#MyAppVersion}-windows-setup
SetupIconFile=build\icon.ico
UninstallDisplayIcon={app}\wurubururu.exe
UninstallDisplayName=우르부르 (wurubururu)
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "autostart"; Description: "Windows에 로그인할 때 자동으로 실행"
Name: "desktopicon"; Description: "바탕 화면에 바로 가기 만들기"; Flags: unchecked

[Files]
Source: "..\dist\wurubururu\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\우르부르"; Filename: "{app}\wurubururu.exe"
Name: "{group}\우르부르 제거"; Filename: "{uninstallexe}"
Name: "{userdesktop}\우르부르"; Filename: "{app}\wurubururu.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "wurubururu"; ValueData: """{app}\wurubururu.exe"""; Flags: uninsdeletevalue; Tasks: autostart
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "wurubururu"; Flags: uninsdeletevalue dontcreatekey

[Run]
Filename: "https://github.com/savorfamily/wurubururu#windows-11"; Description: "기기 드라이버 설정 방법 보기 (처음 한 번 필요)"; Flags: shellexec postinstall skipifsilent
Filename: "{app}\wurubururu.exe"; Description: "우르부르 실행"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "taskkill"; Parameters: "/F /IM wurubururu.exe"; Flags: runhidden; RunOnceId: "KillApp"
