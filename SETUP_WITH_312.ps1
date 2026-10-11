# Irium Setup Script for Python 3.12
# This script will guide you through the setup process

param(
    [switch]$SkipPythonCheck
)

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  Irium MVP Setup with Python 3.12   " -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python 3.12 is installed
$python312Available = $false
try {
    $version = py -3.12 --version 2>&1
    if ($version -match "Python 3\.12") {
        $python312Available = $true
        Write-Host "✅ Python 3.12 found: $version" -ForegroundColor Green
    }
} catch {
    # Not found
}

if (-not $python312Available -and -not $SkipPythonCheck) {
    Write-Host "❌ Python 3.12 is NOT installed" -ForegroundColor Red
    Write-Host ""
    Write-Host "You need to install Python 3.12 first:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Option 1: Direct Download (Recommended)" -ForegroundColor Cyan
    Write-Host "  1. Download: https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"
    Write-Host "  2. Run the installer"
    Write-Host "  3. ✅ CHECK 'Add Python to PATH'"
    Write-Host "  4. Complete installation"
    Write-Host "  5. Restart PowerShell"
    Write-Host "  6. Run this script again"
    Write-Host ""
    Write-Host "Option 2: Microsoft Store" -ForegroundColor Cyan
    Write-Host "  - Search for 'Python 3.12' in Microsoft Store"
    Write-Host "  - Click Install"
    Write-Host ""
    
    $openBrowser = Read-Host "Open download page in browser? (Y/N)"
    if ($openBrowser -eq "Y" -or $openBrowser -eq "y") {
        Start-Process "https://www.python.org/downloads/release/python-3127/"
    }
    
    Write-Host ""
    Write-Host "After installing Python 3.12, run this script again." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Starting setup..." -ForegroundColor Cyan
Write-Host ""

# Step 1: Remove old virtual environments
Write-Host "Step 1: Cleaning old virtual environments..." -ForegroundColor Yellow
Remove-Item -Recurse -Force "venv" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "app\.venv" -ErrorAction SilentlyContinue
Write-Host "✅ Cleaned" -ForegroundColor Green
Write-Host ""

# Step 2: Create new virtual environment with Python 3.12
Write-Host "Step 2: Creating virtual environment with Python 3.12..." -ForegroundColor Yellow
py -3.12 -m venv venv

if (-not (Test-Path "venv\Scripts\python.exe")) {
    Write-Host "❌ Failed to create virtual environment" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Virtual environment created" -ForegroundColor Green
Write-Host ""

# Step 3: Activate and upgrade pip
Write-Host "Step 3: Upgrading pip..." -ForegroundColor Yellow
& "venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel --quiet
Write-Host "✅ Pip upgraded" -ForegroundColor Green
Write-Host ""

# Step 4: Install dependencies
Write-Host "Step 4: Installing dependencies (this may take 2-3 minutes)..." -ForegroundColor Yellow
Write-Host "Please wait..." -ForegroundColor Cyan

$installOutput = & "venv\Scripts\pip.exe" install -r requirements.txt 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Dependencies installed successfully" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to install dependencies" -ForegroundColor Red
    Write-Host ""
    Write-Host "Error output:" -ForegroundColor Yellow
    Write-Host $installOutput
    Write-Host ""
    Write-Host "Try installing manually:" -ForegroundColor Yellow
    Write-Host "  .\venv\Scripts\Activate" -ForegroundColor Cyan
    Write-Host "  pip install -r requirements.txt" -ForegroundColor Cyan
    exit 1
}
Write-Host ""

# Step 5: Verify installation
Write-Host "Step 5: Verifying installation..." -ForegroundColor Yellow

$verifyScript = @"
import sys
try:
    import langchain
    import langchain_google_genai
    import langchain_groq
    import fastapi
    import sqlalchemy
    print('SUCCESS')
except ImportError as e:
    print(f'FAILED: {e}')
    sys.exit(1)
"@

$verifyResult = & "venv\Scripts\python.exe" -c $verifyScript 2>&1

if ($verifyResult -match "SUCCESS") {
    Write-Host "✅ All packages verified" -ForegroundColor Green
} else {
    Write-Host "⚠️  Some packages may have issues" -ForegroundColor Yellow
    Write-Host $verifyResult
}
Write-Host ""

# Summary
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "        Setup Complete! 🎉           " -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Configure API keys in .env file:" -ForegroundColor Cyan
Write-Host "   - Get Google Gemini key: https://makersuite.google.com/app/apikey"
Write-Host "   - Get Tavily key: https://tavily.com/"
Write-Host "   - Edit .env file and add your keys"
Write-Host ""
Write-Host "2. Start PostgreSQL:" -ForegroundColor Cyan
Write-Host "   docker run -d --name irium_postgres ``" -ForegroundColor White
Write-Host "     -e POSTGRES_USER=irium ``" -ForegroundColor White
Write-Host "     -e POSTGRES_PASSWORD=irium_password ``" -ForegroundColor White
Write-Host "     -e POSTGRES_DB=irium_db ``" -ForegroundColor White
Write-Host "     -p 5432:5432 ``" -ForegroundColor White
Write-Host "     postgres:15-alpine" -ForegroundColor White
Write-Host ""
Write-Host "3. Activate virtual environment:" -ForegroundColor Cyan
Write-Host "   .\venv\Scripts\Activate" -ForegroundColor White
Write-Host ""
Write-Host "4. Run test:" -ForegroundColor Cyan
Write-Host "   python test_setup.py" -ForegroundColor White
Write-Host ""
Write-Host "5. Start Irium:" -ForegroundColor Cyan
Write-Host "   uvicorn app.main:app --reload" -ForegroundColor White
Write-Host ""
Write-Host "6. Open browser:" -ForegroundColor Cyan
Write-Host "   http://localhost:8000/static/index.html" -ForegroundColor White
Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "For detailed instructions, see:" -ForegroundColor Yellow
Write-Host "  - INSTALL_PYTHON_312.md" -ForegroundColor Cyan
Write-Host "  - INSTALLATION_STEPS.md" -ForegroundColor Cyan
Write-Host ""
