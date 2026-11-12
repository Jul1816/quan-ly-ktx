# Script khởi chạy nhanh Streamlit Web GUI bằng PowerShell
$Host.UI.RawUI.WindowTitle = "Quản lý Ký túc xá Sinh viên - Streamlit"
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  HỆ THỐNG QUẢN LÝ KÝ TÚC XÁ SINH VIÊN (STREAMLIT + MYSQL)" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

$envPath = Join-Path $PSScriptRoot ".env"
$envExamplePath = Join-Path $PSScriptRoot ".env.example"

if (-not (Test-Path $envPath)) {
    if (Test-Path $envExamplePath) {
        Write-Host "[CẢNH BÁO] Chưa tìm thấy file .env! Đang tự tạo từ .env.example..." -ForegroundColor Yellow
        Copy-Item -Path $envExamplePath -Destination $envPath
    }
}

Write-Host "[INFO] Đang khởi động Streamlit Web GUI tại http://localhost:8501 ..." -ForegroundColor Green
Write-Host "[INFO] Nhấn Ctrl+C để dừng máy chủ." -ForegroundColor DarkGray
Write-Host ""

python -m streamlit run (Join-Path $PSScriptRoot "app.py")
