$ErrorActionPreference = "Stop"

Write-Host "========================================="
Write-Host "  Soft IP 主诉评估系统 v0.1.0"
Write-Host "========================================="

$pythonExe = $null
$pythonArgs = @()

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCmd) {
    $pythonExe = $pythonCmd.Source
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonExe = "py"
    $pythonArgs = @()
} else {
    throw "Python not found. Please install Python 3 first."
}

cmd /c chcp 65001 > $null
$env:PYTHONIOENCODING = "utf-8"
$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = "false"

Write-Host "Installing dependencies..."
& $pythonExe @pythonArgs -m pip install -r requirements.txt

Write-Host "Starting Streamlit on http://localhost:8501"
& $pythonExe @pythonArgs -m streamlit run app.py --server.port 8501 --server.headless true --browser.gatherUsageStats false
