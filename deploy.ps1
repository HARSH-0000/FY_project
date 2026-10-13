# Irium MVP - Quick Deployment Script (PowerShell)
# This script helps you deploy the Irium application on Windows

$ErrorActionPreference = "Stop"

Write-Host "🚀 Irium MVP Deployment Script" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Helper functions
function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-ErrorMsg {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

function Write-Info {
    param([string]$Message)
    Write-Host "ℹ $Message" -ForegroundColor Cyan
}

function Test-CommandExists {
    param([string]$Command)
    $null = Get-Command $Command -ErrorAction SilentlyContinue
    return $?
}

# Check prerequisites
function Test-Prerequisites {
    Write-Host "Checking prerequisites..." -ForegroundColor Yellow
    
    if (-not (Test-CommandExists "python")) {
        Write-ErrorMsg "Python is not installed or not in PATH"
        Write-Info "Download from: https://www.python.org/downloads/"
        exit 1
    }
    Write-Success "Python found"
    
    if (-not (Test-CommandExists "pip")) {
        Write-ErrorMsg "pip is not installed"
        exit 1
    }
    Write-Success "pip found"
    
    Write-Host ""
}

# Local deployment
function Deploy-Local {
    Write-Host "🖥️  Local Deployment" -ForegroundColor Cyan
    Write-Host "====================" -ForegroundColor Cyan
    Write-Host ""
    
    # Create virtual environment
    if (-not (Test-Path "venv")) {
        Write-Info "Creating virtual environment..."
        python -m venv venv
        Write-Success "Virtual environment created"
    } else {
        Write-Info "Virtual environment already exists"
    }
    
    # Activate virtual environment
    Write-Info "Activating virtual environment..."
    & ".\venv\Scripts\Activate.ps1"
    Write-Success "Virtual environment activated"
    
    # Install dependencies
    Write-Info "Installing dependencies..."
    pip install -r requirements.txt
    Write-Success "Dependencies installed"
    
    # Check .env file
    if (-not (Test-Path ".env")) {
        Write-Warning ".env file not found"
        Write-Info "Copying .env.example to .env..."
        Copy-Item ".env.example" ".env"
        Write-Warning "Please edit .env file with your API keys before running the app"
        Write-Host ""
        Write-Info "Required API keys:"
        Write-Info "  - GOOGLE_API_KEY or GROQ_API_KEY"
        Write-Info "  - TAVILY_API_KEY"
        Write-Host ""
        Write-Info "To start the application after configuring .env:"
        Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
        Write-Host "  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000" -ForegroundColor Yellow
        exit 0
    } else {
        Write-Success ".env file found"
    }
    
    Write-Host ""
    Write-Success "Local deployment setup complete!"
    Write-Host ""
    Write-Info "Application is ready to start!"
    Write-Host ""
    
    $start = Read-Host "Do you want to start the application now? (y/n)"
    if ($start -eq "y" -or $start -eq "Y") {
        Write-Info "Starting application..."
        Write-Host ""
        Write-Info "Access the application at:"
        Write-Host "  Landing Page: http://localhost:8000" -ForegroundColor Green
        Write-Host "  Chat Interface: http://localhost:8000/app" -ForegroundColor Green
        Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor Green
        Write-Host ""
        Write-Warning "Press Ctrl+C to stop the server"
        Write-Host ""
        uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    } else {
        Write-Info "To start manually, run:"
        Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
        Write-Host "  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000" -ForegroundColor Yellow
    }
    Write-Host ""
}

# Docker deployment
function Deploy-Docker {
    Write-Host "🐳 Docker Deployment" -ForegroundColor Cyan
    Write-Host "====================" -ForegroundColor Cyan
    Write-Host ""
    
    # Check Docker
    if (-not (Test-CommandExists "docker")) {
        Write-ErrorMsg "Docker is not installed"
        Write-Info "Install Docker Desktop from: https://www.docker.com/products/docker-desktop"
        exit 1
    }
    Write-Success "Docker found"
    
    # Check Docker Compose
    if (-not (Test-CommandExists "docker-compose")) {
        Write-ErrorMsg "Docker Compose is not installed"
        Write-Info "Install Docker Desktop which includes Docker Compose"
        exit 1
    }
    Write-Success "Docker Compose found"
    
    # Check if Docker is running
    try {
        docker ps | Out-Null
        Write-Success "Docker daemon is running"
    } catch {
        Write-ErrorMsg "Docker daemon is not running"
        Write-Info "Please start Docker Desktop"
        exit 1
    }
    
    # Check .env file
    if (-not (Test-Path ".env")) {
        Write-Warning ".env file not found"
        Write-Info "Copying .env.example to .env..."
        Copy-Item ".env.example" ".env"
        Write-Warning "Please edit .env file with your API keys"
        Write-Host ""
        Write-Info "After configuring .env, run this script again"
        exit 0
    }
    Write-Success ".env file found"
    
    # Build and start containers
    Write-Info "Building and starting containers..."
    Write-Warning "This may take a few minutes..."
    Write-Host ""
    
    docker-compose up -d --build
    
    Write-Host ""
    Write-Success "Docker deployment complete!"
    Write-Host ""
    Write-Info "Services are starting up..."
    Write-Host ""
    Write-Info "Useful commands:"
    Write-Host "  Check status: docker-compose ps" -ForegroundColor Yellow
    Write-Host "  View logs: docker-compose logs -f" -ForegroundColor Yellow
    Write-Host "  Stop services: docker-compose down" -ForegroundColor Yellow
    Write-Host ""
    Write-Info "Access the application at:"
    Write-Host "  http://localhost:8000" -ForegroundColor Green
    Write-Host ""
    
    Start-Sleep -Seconds 5
    
    Write-Info "Checking container status..."
    docker-compose ps
    Write-Host ""
}

# Production deployment info
function Show-ProductionInfo {
    Write-Host "☁️  Production Deployment Setup" -ForegroundColor Cyan
    Write-Host "===============================" -ForegroundColor Cyan
    Write-Host ""
    
    Write-Info "For production deployment, please refer to DEPLOYMENT.md"
    Write-Host ""
    Write-Info "Available platforms:"
    Write-Host "  1. AWS EC2" -ForegroundColor Yellow
    Write-Host "  2. Google Cloud Run" -ForegroundColor Yellow
    Write-Host "  3. Azure Container Instances" -ForegroundColor Yellow
    Write-Host "  4. Railway (Easiest)" -ForegroundColor Yellow
    Write-Host "  5. Render" -ForegroundColor Yellow
    Write-Host ""
    Write-Info "Each platform has detailed instructions in DEPLOYMENT.md"
    Write-Host ""
    
    $open = Read-Host "Do you want to open DEPLOYMENT.md? (y/n)"
    if ($open -eq "y" -or $open -eq "Y") {
        if (Test-Path "DEPLOYMENT.md") {
            Start-Process "DEPLOYMENT.md"
        } else {
            Write-Warning "DEPLOYMENT.md not found"
        }
    }
}

# Health check
function Test-Health {
    Write-Host "🏥 Health Check" -ForegroundColor Cyan
    Write-Host "===============" -ForegroundColor Cyan
    Write-Host ""
    
    Write-Info "Checking application health..."
    
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8000/health/ready" -Method Get -TimeoutSec 5
        Write-Success "Application is healthy!"
        Write-Host ""
        Write-Info "Health Status:"
        $response | ConvertTo-Json -Depth 10 | Write-Host
    } catch {
        Write-ErrorMsg "Application is not responding"
        Write-Info "Make sure the application is running on port 8000"
        Write-Host ""
        Write-Info "Common issues:"
        Write-Host "  - Application not started" -ForegroundColor Yellow
        Write-Host "  - Port 8000 is blocked by firewall" -ForegroundColor Yellow
        Write-Host "  - Another application is using port 8000" -ForegroundColor Yellow
    }
    Write-Host ""
}

# Install Redis (optional)
function Install-Redis {
    Write-Host "📦 Redis Installation" -ForegroundColor Cyan
    Write-Host "=====================" -ForegroundColor Cyan
    Write-Host ""
    
    Write-Info "Redis is optional but recommended for better caching performance"
    Write-Host ""
    Write-Info "Options to install Redis on Windows:"
    Write-Host ""
    Write-Host "1. Using Docker (Recommended):" -ForegroundColor Yellow
    Write-Host "   docker run -d --name redis -p 6379:6379 redis:alpine" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "2. Using WSL2 (Windows Subsystem for Linux):" -ForegroundColor Yellow
    Write-Host "   wsl --install" -ForegroundColor Cyan
    Write-Host "   wsl sudo apt update && sudo apt install redis-server" -ForegroundColor Cyan
    Write-Host "   wsl sudo service redis-server start" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "3. Using Memurai (Windows native Redis alternative):" -ForegroundColor Yellow
    Write-Host "   Download from: https://www.memurai.com/" -ForegroundColor Cyan
    Write-Host ""
    
    $install = Read-Host "Do you want to start Redis using Docker? (y/n)"
    if ($install -eq "y" -or $install -eq "Y") {
        if (-not (Test-CommandExists "docker")) {
            Write-ErrorMsg "Docker is not installed"
            return
        }
        
        Write-Info "Starting Redis container..."
        try {
            docker run -d --name redis -p 6379:6379 redis:alpine
            Write-Success "Redis started successfully!"
            Write-Host ""
            Write-Info "Redis is now running on port 6379"
            Write-Info "Update your .env file with: REDIS_URL=redis://localhost:6379/0"
        } catch {
            Write-ErrorMsg "Failed to start Redis"
            Write-Host $_.Exception.Message
        }
    }
    Write-Host ""
}

# Main menu
function Show-Menu {
    Write-Host "Select deployment option:" -ForegroundColor Cyan
    Write-Host "  1) Local Development" -ForegroundColor White
    Write-Host "  2) Docker (with PostgreSQL)" -ForegroundColor White
    Write-Host "  3) Production Setup Info" -ForegroundColor White
    Write-Host "  4) Health Check" -ForegroundColor White
    Write-Host "  5) Install Redis (Optional)" -ForegroundColor White
    Write-Host "  6) Exit" -ForegroundColor White
    Write-Host ""
    
    $option = Read-Host "Enter option [1-6]"
    
    switch ($option) {
        "1" {
            Test-Prerequisites
            Deploy-Local
        }
        "2" {
            Deploy-Docker
        }
        "3" {
            Show-ProductionInfo
        }
        "4" {
            Test-Health
        }
        "5" {
            Install-Redis
        }
        "6" {
            Write-Info "Goodbye!"
            exit 0
        }
        default {
            Write-ErrorMsg "Invalid option"
            exit 1
        }
    }
}

# Run main menu
Show-Menu
