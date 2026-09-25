; installer.iss — build bằng Inno Setup (ISCC.exe installer.iss) SAU KHI đã có
; thư mục dist\slhtool\ (từ bước `pyinstaller slhtool.spec`).
; Kết quả: file  Output\SLHTool_Setup.exe  — đưa file này cho người dùng tải về.
;
; Cài vào thư mục riêng của người dùng (không phải Program Files) nên KHÔNG cần
; quyền Admin / không hiện hộp thoại UAC — phù hợp máy dùng chung, máy công ty.

#define MyAppName "SLH Tool"
#define MyAppVersion "1.0.0"
; ^ PHẢI khớp APP_VERSION trong slhtool.py — đổi 1 chỗ thì đổi luôn 2 chỗ kia
;   (chỗ kia là version_info.txt).
#define MyAppExeName "slhtool.exe"

[Setup]
; AppId CỐ ĐỊNH — KHÔNG BAO GIỜ ĐỔI GUID NÀY Ở CÁC BẢN SAU, kể cả khi đổi tên app.
; Đây là cách Windows/Inno Setup nhận ra "đây là app cũ, cài đè lên" thay vì cài
; thành 2 app riêng biệt khi người dùng chạy Setup.exe của bản mới.
AppId={{6F1B9C1E-6E3B-4C2A-9C0E-2B4F0B7B6D31}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=SLH Tool
DefaultDirName={localappdata}\Programs\SLHTool
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=Output
OutputBaseFilename=SLHTool_Setup
SetupIconFile=app.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Tạo biểu tượng ngoài Desktop"; GroupDescription: "Biểu tượng bổ sung:"

[Files]
; Toàn bộ thư mục onedir mà PyInstaller build ra (exe + các .dll/.pyd đi kèm)
Source: "dist\slhtool\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Gỡ cài đặt {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Mở {#MyAppName} ngay"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; KHÔNG xoá %APPDATA%\SLHTool khi gỡ cài đặt — đó là nơi lưu cấu hình, danh
; sách name, gói HanLP đã tải, để nếu người dùng cài lại thì không mất dữ liệu.
