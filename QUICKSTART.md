# ⚡ Quick Start Guide - Irium MVP

Get up and running in 5 minutes!

## 🎯 Choose Your Path

### Option 1: Automated Setup (Recommended)

**Windows**:
```powershell
.\deploy.ps1
```

**Linux/Mac**:
```bash
chmod +x deploy.sh
./deploy.sh
```

Follow the interactive prompts to choose your deployment method.

---

### Option 2: Manual Local Setup

1. **Get API Keys** (Required):
   - **Google Gemini**: https://makersuite.google.com/app/apikey
   - **Tavily Search**: https://tavily.com/ (free tier available)

2. **Setup Environment**:
   ```bash
   # Clone or navigate to project
   cd "FY Project 11"
   
   # Copy environment file
   cp .env.example .env
   ```

3. **Edit `.env` file** with your API keys:
   ```env
   GOOGLE_API_KEY=your_actual_api_key_here
   TAVILY_API_KEY=your_actual_api_key_here
   LLM_PROVIDER=google
   LLM_MODEL=gemini-1.5-flash
   ```

4. **Install and Run**:
   
   **Windows**:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```
   
   **Linux/Mac**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

5. **Open Browser**:
   - http://localhost:8000 - Landing page
   - http://localhost:8000/app - Chat interface
   - http://localhost:8000/docs - API documentation

---

### Option 3: Docker (Includes Database)

1. **Prerequisites**: 
   - Install [Docker Desktop](https://www.docker.com/products/docker-desktop)
   - Make sure Docker is running

2. **Setup**:
   ```bash
   # Copy and configure environment
   cp .env.example .env
   # Edit .env with your API keys
   
   # Start everything
   docker-compose up -d
   ```

3. **Access**:
   - http://localhost:8000

4. **Useful Commands**:
   ```bash
   docker-compose logs -f        # View logs
   docker-compose ps             # Check status
   docker-compose down           # Stop all services
   docker-compose restart app    # Restart just the app
   ```

---

## 🧪 Test Your Setup

### 1. Check Health
```bash
# Windows PowerShell
Invoke-RestMethod http://localhost:8000/health/ready | ConvertTo-Json

# Linux/Mac/Git Bash
curl http://localhost:8000/health/ready | jq
```

### 2. Test the API

**Simple Query**:
```bash
curl -X POST http://localhost:8000/api/research \
  -H "Content-Type: application/json" \
  -d '{"query": "What is EBITDA?"}'
```

**Complex Query**:
```bash
curl -X POST http://localhost:8000/api/research \
  -H "Content-Type: application/json" \
  -d '{"query": "Compare HDFC Bank and ICICI Bank financial performance"}'
```

### 3. Use the Web Interface
Open http://localhost:8000/app and try these queries:
- "What is compound interest?"
- "What is the current RBI repo rate?"
- "Compare SBI and HDFC Bank market cap"

---

## 🔧 Common Issues

### Issue: Port 8000 already in use

**Windows**:
```powershell
# Find and kill process
netstat -ano | findstr :8000
taskkill /PID <PID_NUMBER> /F
```

**Linux/Mac**:
```bash
# Find and kill process
lsof -ti:8000 | xargs kill -9
```

### Issue: Module not found

```bash
# Reinstall dependencies
pip install --upgrade -r requirements.txt
```

### Issue: API key errors

1. Check `.env` file exists in project root
2. Verify API keys are correct (no extra spaces)
3. Test API keys:
   ```bash
   # Test Google Gemini
   curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key=YOUR_KEY" \
     -H 'Content-Type: application/json' \
     -d '{"contents":[{"parts":[{"text":"test"}]}]}'
   ```

### Issue: Redis connection failed

This is **OK**! The app will use in-memory caching if Redis is unavailable.

To add Redis:
```bash
# Using Docker
docker run -d --name redis -p 6379:6379 redis:alpine

# Update .env
REDIS_ENABLED=true
REDIS_URL=redis://localhost:6379/0
```

---

## 📁 Project Structure Overview

```
FY Project 11/
├── app/                    # Main application
│   ├── agents/            # AI agents (router, planner, writer, etc.)
│   ├── api/routes/        # API endpoints
│   ├── services/          # Business logic (LLM, search, cache)
│   └── workflows/         # LangGraph workflows
├── frontend/              # Web interface
├── data/                  # Uploads and databases
├── .env                   # Your configuration (create from .env.example)
├── requirements.txt       # Python dependencies
└── docker-compose.yml     # Docker setup
```

---

## 🎓 Next Steps

### Learn More
- Read [README.md](README.md) for detailed features and architecture
- Check [DEPLOYMENT.md](DEPLOYMENT.md) for production deployment
- Explore `/docs` folder for advanced features

### Try These Features

1. **Multi-Tier Routing**:
   - Try simple questions: "What is NPV?"
   - Try current facts: "Current US interest rate"
   - Try complex analysis: "Analyze Tesla's financial performance"

2. **Document Analysis**:
   - Upload a PDF via the web interface
   - Ask questions about the document

3. **Caching**:
   - Ask the same question twice
   - Check response time improvement

4. **PII Protection**:
   - Try entering a credit card number
   - Watch it get redacted (if PII_DETECTION_ENABLED=true)

### Customize

Edit `.env` to configure:
```env
# Use Groq for faster inference
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile

# Adjust search results
SEARCH_MAX_RESULTS=5

# Configure PII protection
PII_DETECTION_ENABLED=true
PII_POLICY=REDACT  # or BLOCK, MASK, LOG_ONLY

# Caching TTL (seconds)
CACHE_DEFAULT_TTL=3600
```

---

## 🚀 Deploy to Production

**Easiest Options**:

1. **Railway** (Click to deploy):
   - Sign up at https://railway.app
   - Connect GitHub repo
   - Add environment variables
   - Deploy! ✨

2. **Render** (Free tier):
   - Sign up at https://render.com
   - New Web Service → Connect repo
   - Add environment variables
   - Deploy! ✨

3. **Google Cloud Run** (Serverless):
   ```bash
   gcloud run deploy irium \
     --source . \
     --set-env-vars GOOGLE_API_KEY=xxx,TAVILY_API_KEY=xxx
   ```

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete instructions.

---

## 💡 Pro Tips

1. **Speed up LLM responses**: Use Groq instead of Google Gemini
2. **Enable Redis**: 5-10x faster for repeated queries
3. **Adjust caching**: Tune TTL based on your use case
4. **Monitor performance**: Check `/api/observability/metrics`
5. **Use trace IDs**: Track requests with `X-Trace-ID` header

---

## 📞 Need Help?

1. Check [Troubleshooting](DEPLOYMENT.md#troubleshooting) section
2. Review application logs
3. Test API endpoints at http://localhost:8000/docs
4. Verify API keys are valid
5. Open an issue on GitHub

---

## ✅ Success Checklist

- [ ] API keys configured in `.env`
- [ ] Dependencies installed
- [ ] Application starts without errors
- [ ] Health check returns OK
- [ ] Web interface loads
- [ ] Can submit a research query
- [ ] Receives a response with sources

If all checked, you're ready to go! 🎉

---

**Need more details?** Check out:
- [README.md](README.md) - Full documentation
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment guide
- http://localhost:8000/docs - Interactive API docs

**Happy researching! 🔍**
