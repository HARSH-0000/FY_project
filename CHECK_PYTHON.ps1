# Check Python Installation Script

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "Checking Python Installations" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""

# Check default python
Write-Host "1. Default Python:" -ForegroundColor Yellow
try {
    $version = python --version 2>&1
    Write-Host "   $version" -ForegroundColor Green
} catch {
    Write-Host "   Not found" -ForegroundColor Red
}
Write-Host ""

# Check all Python versions via py launcher
Write-Host "2. All Python Versions (via py launcher):" -ForegroundColor Yellow
try {
    py --list 2>&1 | ForEach-Object { Write-Host "   $_" -ForegroundColor Green }
} catch {
    Write-Host "   py launcher not available" -ForegroundColor Red
}
Write-Host ""

# Check specific versions
Write-Host "3. Testing Specific Versions:" -ForegroundColor Yellow

$versions = @("3.12", "3.11", "3.10", "3.13")
foreach ($ver in $versions) {
    try {
        $result = py -$ver --version 2>&1
        if ($result -match "Python") {
            Write-Host "   Python $ver : $result" -ForegroundColor Green
        }
    } catch {
        # Version not found, skip
    }
}
Write-Host ""

# Check current directory venv
Write-Host "4. Virtual Environment Status:" -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "   venv folder EXISTS" -ForegroundColor Green
    if (Test-Path "venv\Scripts\python.exe") {
        $venvVersion = & "venv\Scripts\python.exe" --version 2>&1
        Write-Host "   venv Python: $venvVersion" -ForegroundColor Green
    }
} else {
    Write-Host "   No venv folder found" -ForegroundColor Yellow
}

if (Test-Path "app\.venv") {
    Write-Host "   app\.venv folder EXISTS" -ForegroundColor Green
    if (Test-Path "app\.venv\Scripts\python.exe") {
        $appVenvVersion = & "app\.venv\Scripts\python.exe" --version 2>&1
        Write-Host "   app\.venv Python: $appVenvVersion" -ForegroundColor Green
    }
} else {
    Write-Host "   No app\.venv folder found" -ForegroundColor Yellow
}
Write-Host ""

# Recommendation
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "RECOMMENDATION:" -ForegroundColor Yellow
Write-Host "=" * 60 -ForegroundColor Cyan

if (py -3.12 --version 2>&1 | Select-String "Python 3.12") {
    Write-Host "✅ Python 3.12 is available! Use it:" -ForegroundColor Green
    Write-Host ""
    Write-Host "   Remove-Item -Recurse -Force venv, app\.venv -ErrorAction SilentlyContinue" -ForegroundColor Cyan
    Write-Host "   py -3.12 -m venv venv" -ForegroundColor Cyan
    Write-Host "   .\venv\Scripts\Activate" -ForegroundColor Cyan
    Write-Host "   pip install -r requirements.txt" -ForegroundColor Cyan
} elseif (py -3.11 --version 2>&1 | Select-String "Python 3.11") {
    Write-Host "✅ Python 3.11 is available! Use it:" -ForegroundColor Green
    Write-Host ""
    Write-Host "   Remove-Item -Recurse -Force venv, app\.venv -ErrorAction SilentlyContinue" -ForegroundColor Cyan
    Write-Host "   py -3.11 -m venv venv" -ForegroundColor Cyan
    Write-Host "   .\venv\Scripts\Activate" -ForegroundColor Cyan
    Write-Host "   pip install -r requirements.txt" -ForegroundColor Cyan
} elseif (py -3.10 --version 2>&1 | Select-String "Python 3.10") {
    Write-Host "✅ Python 3.10 is available! Use it:" -ForegroundColor Green
    Write-Host ""
    Write-Host "   Remove-Item -Recurse -Force venv, app\.venv -ErrorAction SilentlyContinue" -ForegroundColor Cyan
    Write-Host "   py -3.10 -m venv venv" -ForegroundColor Cyan
    Write-Host "   .\venv\Scripts\Activate" -ForegroundColor Cyan
    Write-Host "   pip install -r requirements.txt" -ForegroundColor Cyan
} else {
    Write-Host "❌ Python 3.10, 3.11, or 3.12 NOT found" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Python 3.12:" -ForegroundColor Yellow
    Write-Host "   1. Download: https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe" -ForegroundColor Cyan
    Write-Host "   2. Run installer" -ForegroundColor Cyan
    Write-Host "   3. Check 'Add Python to PATH'" -ForegroundColor Cyan
    Write-Host "   4. Restart PowerShell" -ForegroundColor Cyan
    Write-Host "   5. Run this script again" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "=" * 60 -ForegroundColor Cyan
