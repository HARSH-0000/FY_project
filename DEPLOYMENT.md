# 🚀 Deployment Guide - Irium MVP

This guide covers multiple deployment options for the Irium Multi-Agent Research System.

## 📋 Table of Contents

1. [Local Development](#local-development)
2. [Docker Deployment](#docker-deployment)
3. [Cloud Deployment](#cloud-deployment)
   - [AWS EC2](#aws-ec2)
   - [Google Cloud Platform](#google-cloud-platform)
   - [Azure](#azure)
   - [Railway](#railway)
   - [Render](#render)
4. [Production Best Practices](#production-best-practices)
5. [Troubleshooting](#troubleshooting)

---

## 🖥️ Local Development

### Prerequisites
- Python 3.11 or 3.13
- Redis (optional but recommended)
- PostgreSQL (optional)

### Step-by-Step Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd "FY Project 11"
   ```

2. **Create and activate virtual environment**:
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # Linux/Mac
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   # Copy example environment file
   cp .env.example .env
   ```

5. **Edit `.env` file with your credentials**:
   ```env
   # Required
   GOOGLE_API_KEY=your_google_api_key_here
   TAVILY_API_KEY=your_tavily_api_key_here
   
   # Optional
   GROQ_API_KEY=your_groq_api_key_here
   REDIS_URL=redis://localhost:6379/0
   ```

6. **Start Redis (optional)**:
   ```bash
   # Windows (if installed via Chocolatey/MSI)
   redis-server
   
   # Linux
   sudo service redis-server start
   
   # Mac
   brew services start redis
   
   # Or use Docker
   docker run -d -p 6379:6379 redis:alpine
   ```

7. **Run the application**:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

8. **Access the application**:
   - Landing Page: http://localhost:8000
   - Chat Interface: http://localhost:8000/app
   - API Docs: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health/ready

---

## 🐳 Docker Deployment

### Option 1: Docker Compose (Recommended)

This setup includes PostgreSQL and Redis services.

1. **Ensure Docker and Docker Compose are installed**:
   ```bash
   docker --version
   docker-compose --version
   ```

2. **Create `.env` file** with your API keys:
   ```env
   GOOGLE_API_KEY=your_google_api_key_here
   TAVILY_API_KEY=your_tavily_api_key_here
   GROQ_API_KEY=your_groq_api_key_here
   LLM_PROVIDER=google
   LLM_MODEL=gemini-1.5-flash
   ```

3. **Build and start all services**:
   ```bash
   docker-compose up -d
   ```

4. **View logs**:
   ```bash
   # All services
   docker-compose logs -f
   
   # Specific service
   docker-compose logs -f app
   ```

5. **Stop services**:
   ```bash
   docker-compose down
   
   # Remove volumes too
   docker-compose down -v
   ```

### Option 2: Docker Only (App Container)

Build and run just the application container:

```bash
# Build image
docker build -t irium-app .

# Run container
docker run -d \
  --name irium \
  -p 8000:8000 \
  -e GOOGLE_API_KEY=your_key \
  -e TAVILY_API_KEY=your_key \
  -e LLM_PROVIDER=google \
  -e LLM_MODEL=gemini-1.5-flash \
  irium-app

# View logs
docker logs -f irium

# Stop container
docker stop irium
docker rm irium
```

### Docker with External Redis

```bash
# Start Redis
docker run -d --name redis -p 6379:6379 redis:alpine

# Run app with Redis
docker run -d \
  --name irium \
  -p 8000:8000 \
  --link redis:redis \
  -e REDIS_URL=redis://redis:6379/0 \
  -e REDIS_ENABLED=true \
  -e GOOGLE_API_KEY=your_key \
  -e TAVILY_API_KEY=your_key \
  irium-app
```

---

## ☁️ Cloud Deployment

### AWS EC2

#### 1. Launch EC2 Instance

1. **Instance Configuration**:
   - AMI: Ubuntu Server 22.04 LTS
   - Instance Type: t3.medium or larger (2 vCPU, 4 GB RAM minimum)
   - Storage: 20 GB gp3
   - Security Group: Allow ports 22 (SSH), 80 (HTTP), 443 (HTTPS), 8000 (App)

2. **Connect to instance**:
   ```bash
   ssh -i your-key.pem ubuntu@your-ec2-ip
   ```

#### 2. Install Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11
sudo apt install -y python3.11 python3.11-venv python3-pip

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Logout and login to apply docker group
exit
```

#### 3. Deploy Application

```bash
# Clone repository
git clone <your-repo-url>
cd "FY Project 11"

# Create .env file
nano .env
# Add your API keys and configuration

# Deploy with Docker Compose
docker-compose up -d

# Check status
docker-compose ps
docker-compose logs -f
```

#### 4. Set Up Nginx Reverse Proxy (Optional)

```bash
# Install Nginx
sudo apt install -y nginx

# Create Nginx configuration
sudo nano /etc/nginx/sites-available/irium
```

Add this configuration:
```nginx
server {
    listen 80;
    server_name your-domain.com;  # or use IP

    client_max_body_size 50M;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Enable and restart:
```bash
sudo ln -s /etc/nginx/sites-available/irium /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### 5. Set Up SSL with Let's Encrypt (Optional)

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal is set up automatically
sudo certbot renew --dry-run
```

#### 6. Set Up as Systemd Service (Alternative to Docker)

If deploying without Docker:

```bash
# Create service file
sudo nano /etc/systemd/system/irium.service
```

Add:
```ini
[Unit]
Description=Irium Research System
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/FY Project 11
Environment="PATH=/home/ubuntu/FY Project 11/venv/bin"
EnvironmentFile=/home/ubuntu/FY Project 11/.env
ExecStart=/home/ubuntu/FY Project 11/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable irium
sudo systemctl start irium
sudo systemctl status irium
```

---

### Google Cloud Platform (GCP)

#### Option 1: Cloud Run (Serverless - Recommended)

1. **Install Google Cloud SDK**:
   ```bash
   curl https://sdk.cloud.google.com | bash
   exec -l $SHELL
   gcloud init
   ```

2. **Build and deploy**:
   ```bash
   # Set project
   gcloud config set project YOUR_PROJECT_ID
   
   # Build container
   gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/irium
   
   # Deploy to Cloud Run
   gcloud run deploy irium \
     --image gcr.io/YOUR_PROJECT_ID/irium \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --memory 2Gi \
     --cpu 2 \
     --set-env-vars GOOGLE_API_KEY=your_key,TAVILY_API_KEY=your_key,LLM_PROVIDER=groq
   ```

3. **Set secrets** (more secure than env vars):
   ```bash
   # Create secrets
   echo -n "your_google_api_key" | gcloud secrets create google-api-key --data-file=-
   echo -n "your_tavily_api_key" | gcloud secrets create tavily-api-key --data-file=-
   
   # Deploy with secrets
   gcloud run deploy irium \
     --image gcr.io/YOUR_PROJECT_ID/irium \
     --set-secrets GOOGLE_API_KEY=google-api-key:latest,TAVILY_API_KEY=tavily-api-key:latest
   ```

#### Option 2: Compute Engine (VM)

Similar to AWS EC2 - follow the same steps as AWS EC2 deployment.

---

### Microsoft Azure

#### Option 1: Azure Container Instances

```bash
# Login to Azure
az login

# Create resource group
az group create --name irium-rg --location eastus

# Create container
az container create \
  --resource-group irium-rg \
  --name irium-app \
  --image your-dockerhub-username/irium:latest \
  --dns-name-label irium-unique \
  --ports 8000 \
  --environment-variables \
    GOOGLE_API_KEY=your_key \
    TAVILY_API_KEY=your_key \
    LLM_PROVIDER=google
```

#### Option 2: Azure App Service

```bash
# Create App Service plan
az appservice plan create \
  --name irium-plan \
  --resource-group irium-rg \
  --is-linux \
  --sku B2

# Create web app
az webapp create \
  --resource-group irium-rg \
  --plan irium-plan \
  --name irium-app \
  --deployment-container-image-name your-dockerhub-username/irium:latest

# Configure environment variables
az webapp config appsettings set \
  --resource-group irium-rg \
  --name irium-app \
  --settings \
    GOOGLE_API_KEY=your_key \
    TAVILY_API_KEY=your_key \
    LLM_PROVIDER=google
```

---

### Railway (Easiest)

1. **Sign up at [Railway.app](https://railway.app)**

2. **Deploy from GitHub**:
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Select your repository
   - Railway auto-detects Dockerfile

3. **Add environment variables**:
   - Go to your project
   - Click "Variables"
   - Add:
     ```
     GOOGLE_API_KEY=your_key
     TAVILY_API_KEY=your_key
     LLM_PROVIDER=google
     LLM_MODEL=gemini-1.5-flash
     ```

4. **Add Redis** (optional):
   - Click "New"
   - Select "Database" → "Redis"
   - Copy the `REDIS_URL` to your app's environment variables

5. **Deploy**:
   - Railway automatically builds and deploys
   - Get your URL from the "Deployments" tab

---

### Render (Simple & Free Tier)

1. **Sign up at [Render.com](https://render.com)**

2. **Create Web Service**:
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Configure:
     - **Name**: irium-app
     - **Environment**: Docker
     - **Region**: Choose closest to you
     - **Instance Type**: Free or Starter

3. **Environment Variables**:
   ```
   GOOGLE_API_KEY=your_key
   TAVILY_API_KEY=your_key
   LLM_PROVIDER=google
   LLM_MODEL=gemini-1.5-flash
   APP_ENV=production
   ```

4. **Advanced Settings**:
   - Health Check Path: `/health/ready`
   - Port: 8000

5. **Add Redis** (optional):
   - Create new Redis instance
   - Copy internal Redis URL to `REDIS_URL` in web service

6. **Deploy**: Click "Create Web Service"

---

## 🔧 Production Best Practices

### 1. Environment Variables

**Never commit `.env` to Git!** Always use:
- Cloud provider secret managers (AWS Secrets Manager, GCP Secret Manager, Azure Key Vault)
- Environment variables in deployment platform
- `.env` file only for local development

### 2. Security Checklist

```bash
# Generate secure SECRET_KEY for JWT
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Use strong database passwords
# Enable HTTPS/SSL
# Set up firewall rules
# Use private networks for database connections
# Enable PII protection in production
```

### 3. Scaling Considerations

- **Horizontal Scaling**: Deploy multiple app instances behind a load balancer
- **Redis**: Use managed Redis (AWS ElastiCache, GCP Memorystore, Railway Redis)
- **Database**: Use managed PostgreSQL for persistence (if needed)
- **CDN**: Use CloudFront, Cloudflare, or similar for static assets

### 4. Monitoring & Logging

```env
# Production logging
LOG_LEVEL=INFO  # or WARNING for less verbose

# Enable observability
APP_ENV=production
```

Set up monitoring:
- Application logs → CloudWatch, Stackdriver, Application Insights
- Uptime monitoring → UptimeRobot, Pingdom
- Error tracking → Sentry
- Performance → New Relic, Datadog

### 5. Backup Strategy

```bash
# Backup PostgreSQL (if using)
pg_dump -U irium -h localhost irium_db > backup_$(date +%Y%m%d).sql

# Restore
psql -U irium -h localhost irium_db < backup_20250101.sql

# Backup uploaded files
tar -czf uploads_backup_$(date +%Y%m%d).tar.gz data/uploads/
```

### 6. Resource Requirements

**Minimum Production Requirements**:
- CPU: 2 cores
- RAM: 4 GB
- Storage: 20 GB
- Network: 1 Gbps

**Recommended for Production**:
- CPU: 4 cores
- RAM: 8 GB
- Storage: 50 GB SSD
- Redis: 1 GB

### 7. Performance Optimization

```env
# Optimize caching
REDIS_ENABLED=true
CACHE_DEFAULT_TTL=3600
CACHE_STABLE_TTL=86400
CACHE_VOLATILE_TTL=300

# Optimize search
SEARCH_MAX_RESULTS=10

# Enable compression in Nginx
gzip on;
gzip_types text/plain text/css application/json application/javascript;
```

---

## 🔍 Troubleshooting

### Common Issues

#### 1. Port Already in Use
```bash
# Find process using port 8000
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:8000 | xargs kill -9
```

#### 2. Redis Connection Failed
```bash
# Check if Redis is running
redis-cli ping  # Should return "PONG"

# If not, the app will use in-memory cache (fallback)
# This is normal for lightweight deployments
```

#### 3. API Key Invalid
```bash
# Test Google Gemini API
curl -H "Content-Type: application/json" \
  -d '{"contents":[{"parts":[{"text":"test"}]}]}' \
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key=YOUR_API_KEY"

# Test Tavily API
curl -X POST https://api.tavily.com/search \
  -H "Content-Type: application/json" \
  -d '{"api_key": "YOUR_API_KEY", "query": "test"}'
```

#### 4. Module Not Found
```bash
# Reinstall dependencies
pip install --upgrade -r requirements.txt

# Or clear cache and reinstall
pip cache purge
pip install -r requirements.txt
```

#### 5. Docker Build Fails
```bash
# Clear Docker cache
docker builder prune -a

# Rebuild without cache
docker-compose build --no-cache
```

#### 6. Health Check Fails
```bash
# Check health endpoint
curl http://localhost:8000/health/ready

# Check logs
docker-compose logs app

# Common causes:
# - API keys not set
# - LLM provider unavailable
# - Network issues
```

### Debugging Commands

```bash
# Check app status
docker-compose ps

# View real-time logs
docker-compose logs -f app

# Enter container shell
docker-compose exec app bash

# Check environment variables
docker-compose exec app env | grep API

# Restart service
docker-compose restart app

# Full reset
docker-compose down -v
docker-compose up -d --build
```

### Performance Issues

If experiencing slow responses:

1. **Enable Redis** if not already:
   ```env
   REDIS_ENABLED=true
   ```

2. **Use faster LLM model**:
   ```env
   LLM_PROVIDER=groq
   LLM_MODEL=llama-3.3-70b-versatile
   ```

3. **Reduce search results**:
   ```env
   SEARCH_MAX_RESULTS=5
   ```

4. **Check network latency** to API providers

---

## 📊 Deployment Comparison

| Platform | Difficulty | Cost | Free Tier | Auto-scaling | Best For |
|----------|-----------|------|-----------|--------------|----------|
| **Local** | Easy | $0 | N/A | No | Development |
| **Railway** | Very Easy | $5+/mo | Yes (500 hrs) | Yes | Quick deploys |
| **Render** | Very Easy | $7+/mo | Yes (750 hrs) | Yes | Simple hosting |
| **AWS EC2** | Medium | $15+/mo | Yes (12 mo) | Manual | Full control |
| **GCP Cloud Run** | Medium | Pay-per-use | Yes (generous) | Auto | Serverless |
| **Azure** | Medium | $13+/mo | Yes (12 mo) | Yes | Enterprise |
| **Docker** | Easy | Hardware cost | N/A | Manual | Self-hosted |

---

## 🎯 Quick Start Recommendations

### For Development
→ **Local setup** with Redis in Docker

### For Testing/Demo
→ **Railway** or **Render** (easiest, free tier available)

### For Production (Small)
→ **GCP Cloud Run** (serverless, auto-scaling)

### For Production (Enterprise)
→ **AWS EC2** with Nginx, SSL, and monitoring

### For Self-Hosted
→ **Docker Compose** on your own server

---

## 📞 Support

If you encounter issues:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review application logs
3. Verify API keys and network connectivity
4. Open an issue on GitHub with logs and error messages

---

**Happy Deploying! 🚀**
