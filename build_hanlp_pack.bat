@echo off
REM ============================================================================
REM  build_hanlp_pack.bat
REM  Dựng "gói HanLP" — một bản Python riêng, đã cài sẵn torch (CPU) + hanlp +
REM  tải sẵn model — để người dùng KHÔNG cần tự cài Python vẫn dùng được HanLP.
REM
REM  CHỈ CHẠY FILE NÀY 1 LẦN, TRÊN 1 MÁY WINDOWS THẬT CÓ MẠNG (không chạy được
REM  trên máy dùng để lập trình bằng Claude vì đó là máy Linux).
REM  Việc này KHÔNG liên quan tới việc build file .exe — build .exe đã được
REM  GitHub Actions tự làm mỗi lần bạn "git tag" (xem README.md).
REM
REM  Sau khi chạy xong sẽ có file hanlp_pack.zip (khoảng 1-2 GB) — bạn tự tay
REM  upload file này lên GitHub Releases (không phải qua Actions), xem bước 6
REM  trong README.md.
REM ============================================================================
setlocal enabledelayedexpansion
set PYVER=3.11.9
set WORKDIR=%~dp0hanlp_pack_build
set RUNTIME=%WORKDIR%\hanlp_runtime

if exist "%WORKDIR%" (
    echo Thư mục %WORKDIR% đã có sẵn — xoá đi để build lại từ đầu? (Ctrl+C để huỷ)
    pause
    rmdir /s /q "%WORKDIR%"
)
mkdir "%RUNTIME%"
cd /d "%WORKDIR%"

echo.
echo === 1/6: Tải Python embeddable (%PYVER%) ===
curl -L -o python_embed.zip https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-embed-amd64.zip
if errorlevel 1 goto :loi
powershell -NoProfile -Command "Expand-Archive -Path python_embed.zip -DestinationPath '%RUNTIME%' -Force"

echo.
echo === 2/6: Bật 'import site' để pip cài được gói (sửa file ._pth) ===
REM Tên file python311._pth ứng với PYVER=3.11.x ở trên (bỏ số vá "PATCH").
REM Nếu đổi PYVER sang 3.12.x thì đổi luôn tên "python311._pth" bên dưới thành "python312._pth".
for %%f in ("%RUNTIME%\python3*.zip") do set PYZIP=%%~nxf
(
    echo !PYZIP!
    echo .
    echo Lib\site-packages
    echo import site
) > "%RUNTIME%\python311._pth"

echo.
echo === 3/6: Cài pip ===
curl -L -o get-pip.py https://bootstrap.pypa.io/get-pip.py
"%RUNTIME%\python.exe" get-pip.py
if errorlevel 1 goto :loi

echo.
echo === 4/6: Cài torch (bản CPU, không cần GPU/CUDA) + hanlp ===
"%RUNTIME%\python.exe" -m pip install --no-warn-script-location torch --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto :loi
"%RUNTIME%\python.exe" -m pip install --no-warn-script-location hanlp
if errorlevel 1 goto :loi

echo.
echo === 5/6: Tải sẵn model (để người dùng chạy OFFLINE được ngay từ lần đầu) ===
REM HANLP_HOME đặt NGAY TRONG gói — phải trùng với đường dẫn app.py sẽ trỏ tới
REM (APP_DATA_DIR/hanlp_runtime/hanlp_home), xem hàm _hanlp_worker trong van_ban_tool.py.
set HANLP_HOME=%RUNTIME%\hanlp_home
"%RUNTIME%\python.exe" -c "import hanlp; hanlp.load(hanlp.pretrained.mtl.CLOSE_TOK_POS_NER_SRL_DEP_SDP_CON_ELECTRA_SMALL_ZH); print('Đã tải xong model.')"
if errorlevel 1 goto :loi

echo.
echo === 6/6: Nén thành hanlp_pack.zip ===
cd /d "%~dp0"
powershell -NoProfile -Command "Compress-Archive -Path '%RUNTIME%' -DestinationPath 'hanlp_pack.zip' -Force"

echo.
echo ============================================================================
echo  XONG! File hanlp_pack.zip nằm cạnh file .bat này.
echo  Bước tiếp theo (làm TAY, không phải chạy lệnh):
echo    1. Vào GitHub repo cua ban  -^>  Releases  -^>  Draft a new release
echo    2. Tag: hanlp-pack-v1   (đúng như vậy, app.py đang trỏ tới tag này)
echo    3. Kéo-thả file hanlp_pack.zip vào phần "Attach binaries"
echo    4. Publish release
echo  Chi tiết đầy đủ xem README.md, mục "Gói HanLP".
echo ============================================================================
goto :xong

:loi
echo.
echo *** CO LOI XAY RA — xem thông báo lỗi ở trên. ***

:xong
pause
