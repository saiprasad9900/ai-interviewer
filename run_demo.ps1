# Run ARIA without any API keys (demo / mock LLM mode)
$env:USE_MOCK_LLM = "1"
$env:GROQ_API_KEY = ""
$env:OPENAI_API_KEY = ""

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "Starting backend (demo mode) on http://localhost:8000 ..."
Start-Process -FilePath ".\.venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000" `
    -WorkingDirectory $root -WindowStyle Normal

Start-Sleep -Seconds 3

Write-Host "Starting frontend on http://localhost:8501 ..."
Start-Process -FilePath ".\.venv\Scripts\streamlit.exe" `
    -ArgumentList "run", "frontend/app.py", "--server.headless", "true" `
    -WorkingDirectory $root -WindowStyle Normal

Write-Host "Open http://localhost:8501 in your browser."
