# AI Accounting Automation System - Launch Script
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Starting AI-Powered Accounting Automation System" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Start FastAPI Backend on port 8000
Write-Host "`n[1/2] Launching FastAPI Backend on http://127.0.0.1:8000 ..." -ForegroundColor Green
$backendProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:PYTHONPATH='backend'; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload" -PassThru

# 2. Start React Vite Frontend on port 5173
Write-Host "[2/2] Launching React Frontend on http://localhost:5173 ..." -ForegroundColor Green
$frontendProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev" -PassThru

Write-Host "`nSystem is running!" -ForegroundColor Yellow
Write-Host "Open your browser at: http://localhost:5173" -ForegroundColor Yellow
Write-Host "Swagger API docs at: http://127.0.0.1:8000/docs" -ForegroundColor Yellow
