@echo off
chcp 65001 >nul
cd /d "%~dp0"

title Quan ly Ky tuc xa Sinh vien - Streamlit
echo ========================================================
echo   HE THONG QUAN LY KY TUC XA SINH VIEN - STREAMLIT MYSQL
echo ========================================================
echo.

:: 1. Kiem tra Python
set "PYTHON_CMD="
if exist ".venv\Scripts\python.exe" set "PYTHON_CMD=.venv\Scripts\python.exe"
if "%PYTHON_CMD%"=="" if exist "..\.venv\Scripts\python.exe" set "PYTHON_CMD=..\.venv\Scripts\python.exe"
if "%PYTHON_CMD%"=="" if exist "venv\Scripts\python.exe" set "PYTHON_CMD=venv\Scripts\python.exe"

if "%PYTHON_CMD%"=="" (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
)

if "%PYTHON_CMD%"=="" (
    where py >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py"
)

if not "%PYTHON_CMD%"=="" goto python_ok

echo [LOI] Khong tim thay Python tren he thong!
echo Vui long cai dat Python tai https://www.python.org/
echo Luu y tich chon: Add Python to PATH khi cai dat.
echo.
pause
exit /b 1

:python_ok
:: 2. Kiem tra file cau hinh .env
if not exist ".env" (
    if exist ".env.example" (
        echo [CANH BAO] Chua co file .env. Dang tao tu .env.example...
        copy .env.example .env >nul
        echo [INFO] Da tao file .env mac dinh.
        echo.
    )
)

:: 3. Kiem tra thu vien Streamlit
%PYTHON_CMD% -c "import streamlit" >nul 2>nul
if not errorlevel 1 goto streamlit_ok

echo [CANH BAO] Chua tim thay thu vien Streamlit!
echo Dang tien hanh cai dat cac thu vien can thiet tu requirements.txt...
echo.
%PYTHON_CMD% -m pip install -r requirements.txt
if not errorlevel 1 goto streamlit_ok

echo.
echo [LOI] Khong the cai dat thu vien. Vui long kiem tra ket noi mang.
pause
exit /b 1

:streamlit_ok
:: 4. Kiem tra xung dot cong 8501
netstat -ano | findstr /R /C:":8501 *LISTENING" >nul 2>nul
if not errorlevel 1 (
    echo [CANH BAO] Cong 8501 dang co ung dung su dung - co the Streamlit da chay san.
    echo Neu khong the mo trang web, ban hay tat ung dung dang chiem cong 8501.
    echo.
)

:: 5. Khoi chay Web GUI
echo [INFO] Dang khoi dong Web GUI tai http://localhost:8501 ...
echo [INFO] Nhan Ctrl+C tai cua so nay de dung server.
echo.

%PYTHON_CMD% -m streamlit run app.py

if errorlevel 1 (
    echo.
    echo [THONG BAO] Streamlit da dung hoac gap su co.
)

echo.
pause