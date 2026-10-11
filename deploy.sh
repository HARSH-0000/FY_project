#!/bin/bash

# Irium MVP - Quick Deployment Script
# This script helps you deploy the Irium application quickly

set -e

echo "🚀 Irium MVP Deployment Script"
echo "================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "ℹ $1"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
check_prerequisites() {
    echo "Checking prerequisites..."
    
    if ! command_exists python3; then
        print_error "Python 3 is not installed"
        exit 1
    fi
    print_success "Python 3 found"
    
    if ! command_exists pip3; then
        print_error "pip3 is not installed"
        exit 1
    fi
    print_success "pip3 found"
    
    echo ""
}

# Local deployment
deploy_local() {
    echo "🖥️  Local Deployment"
    echo "===================="
    echo ""
    
    # Create virtual environment
    if [ ! -d "venv" ]; then
        print_info "Creating virtual environment..."
        python3 -m venv venv
        print_success "Virtual environment created"
    else
        print_info "Virtual environment already exists"
    fi
    
    # Activate virtual environment
    print_info "Activating virtual environment..."
    source venv/bin/activate
    print_success "Virtual environment activated"
    
    # Install dependencies
    print_info "Installing dependencies..."
    pip install -r requirements.txt
    print_success "Dependencies installed"
    
    # Check .env file
    if [ ! -f ".env" ]; then
        print_warning ".env file not found"
        print_info "Copying .env.example to .env..."
        cp .env.example .env
        print_warning "Please edit .env file with your API keys before running the app"
        echo ""
        print_info "Required API keys:"
        print_info "  - GOOGLE_API_KEY or GROQ_API_KEY"
        print_info "  - TAVILY_API_KEY"
        echo ""
        exit 0
    else
        print_success ".env file found"
    fi
    
    echo ""
    print_success "Local deployment setup complete!"
    echo ""
    print_info "To start the application, run:"
    echo "  source venv/bin/activate"
    echo "  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
    echo ""
}

# Docker deployment
deploy_docker() {
    echo "🐳 Docker Deployment"
    echo "===================="
    echo ""
    
    # Check Docker
    if ! command_exists docker; then
        print_error "Docker is not installed"
        print_info "Install from: https://docs.docker.com/get-docker/"
        exit 1
    fi
    print_success "Docker found"
    
    # Check Docker Compose
    if ! command_exists docker-compose; then
        print_error "Docker Compose is not installed"
        print_info "Install from: https://docs.docker.com/compose/install/"
        exit 1
    fi
    print_success "Docker Compose found"
    
    # Check .env file
    if [ ! -f ".env" ]; then
        print_warning ".env file not found"
        print_info "Copying .env.example to .env..."
        cp .env.example .env
        print_warning "Please edit .env file with your API keys"
        echo ""
        exit 0
    fi
    
    # Build and start containers
    print_info "Building and starting containers..."
    docker-compose up -d --build
    
    echo ""
    print_success "Docker deployment complete!"
    echo ""
    print_info "Services are starting up..."
    print_info "Check status: docker-compose ps"
    print_info "View logs: docker-compose logs -f"
    print_info "Access app: http://localhost:8000"
    echo ""
}

# Production deployment
deploy_production() {
    echo "☁️  Production Deployment Setup"
    echo "==============================="
    echo ""
    
    print_info "For production deployment, please refer to DEPLOYMENT.md"
    print_info "Available platforms:"
    echo "  1. AWS EC2"
    echo "  2. Google Cloud Run"
    echo "  3. Azure Container Instances"
    echo "  4. Railway (Easiest)"
    echo "  5. Render"
    echo ""
    print_info "Each platform has detailed instructions in DEPLOYMENT.md"
    echo ""
}

# Health check
health_check() {
    echo "🏥 Health Check"
    echo "==============="
    echo ""
    
    print_info "Checking application health..."
    
    if curl -s http://localhost:8000/health/ready > /dev/null; then
        print_success "Application is healthy!"
        echo ""
        print_info "Response:"
        curl -s http://localhost:8000/health/ready | python3 -m json.tool
    else
        print_error "Application is not responding"
        print_info "Make sure the application is running on port 8000"
    fi
    echo ""
}

# Main menu
show_menu() {
    echo "Select deployment option:"
    echo "  1) Local Development"
    echo "  2) Docker (with PostgreSQL)"
    echo "  3) Production Setup Info"
    echo "  4) Health Check"
    echo "  5) Exit"
    echo ""
    read -p "Enter option [1-5]: " option
    
    case $option in
        1)
            check_prerequisites
            deploy_local
            ;;
        2)
            deploy_docker
            ;;
        3)
            deploy_production
            ;;
        4)
            health_check
            ;;
        5)
            print_info "Goodbye!"
            exit 0
            ;;
        *)
            print_error "Invalid option"
            exit 1
            ;;
    esac
}

# Run main menu
show_menu
