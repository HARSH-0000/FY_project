# Irium MVP - Multi-Agent FinTech Research & Document Analysis System

## 🎯 Overview

Irium is an intelligent, multi-agent AI research system designed specifically for FinTech and financial services. It leverages LangGraph-based workflow orchestration, advanced document processing, and tiered research strategies to provide accurate, verified financial information and analysis.

The system intelligently routes queries through three specialized tiers (Simple, Verification, Complex) and employs multiple specialized AI agents to plan, search, read, consolidate evidence, write, and critique research outputs.

## ✨ Key Features

### 🤖 Multi-Agent Architecture
- **Router Agent**: Classifies queries into three tiers (Simple, Verification, Complex)
- **Simple Agent**: Handles general financial definitions and stable concepts
- **Verification Agent**: Retrieves current, factual information from authoritative sources
- **Planner Agent**: Breaks down complex queries into actionable research tasks
- **Reader Agent**: Extracts relevant information from search results
- **Evidence Agent**: Consolidates findings into structured evidence
- **Writer Agent**: Synthesizes comprehensive answers from evidence
- **Critic Agent**: Reviews and validates research quality with retry logic

### 🔍 Intelligent Research Workflows
- **Three-Tier Classification System**:
  - **SIMPLE**: General financial concepts and definitions (e.g., "What is EBITDA?")
  - **VERIFICATION**: Current facts and real-time data (e.g., "Current RBI repo rate")
  - **COMPLEX**: Multi-source analysis and comparisons (e.g., "Compare HDFC vs ICICI performance")
- **LangGraph Orchestration**: State-based workflow management with conditional routing
- **Iterative Refinement**: Critic-driven retry mechanism for answer quality improvement

### 📄 Advanced Document Processing
- **Multi-Format Support**: PDF, DOCX, TXT document parsing
- **Intelligent Extraction**: Context-aware content extraction with metadata
- **Document Analysis Agent**: Specialized agent for document-based queries

### 🔐 Enterprise-Grade Security & Privacy
- **PII Detection & Protection**: Algorithmic detection with multiple policies (REDACT, BLOCK, MASK, LOG_ONLY)
- **Supported PII Categories**: 
  - Payment cards (Luhn checksum validation)
  - Indian Aadhaar (Verhoeff checksum)
  - Indian PAN, US SSN, emails, phone numbers, bank accounts, IFSC codes
- **Log Sanitization**: Automatic PII scrubbing in all application logs
- **False Positive Mitigation**: Financial context-aware validation to avoid flagging currency amounts and financial figures

### 🚀 Performance & Observability
- **Redis-Based Caching**: Tier-differentiated TTL strategy
  - Simple queries: 24 hours
  - Verification: 5 minutes
  - Complex: 1 hour
  - Search results: 30 minutes
- **Graceful Fallback**: Automatic in-memory caching when Redis unavailable
- **Distributed Tracing**: Request correlation with trace IDs
- **Comprehensive Metrics**: HTTP latency, agent execution times, LLM performance, cache hit rates
- **Health Checks**: Readiness probes for LLM, search, database, and observability systems

### 🧠 Flexible LLM Support
- **Multiple Providers**:
  - Google Gemini (gemini-1.5-flash, gemini-1.5-pro, gemini-pro)
  - Groq (llama-3.3-70b-versatile, mixtral-8x7b-32768, gemma2-9b-it)
- **Configurable Selection**: Environment-based provider and model switching
- **Fallback Handling**: Graceful degradation on API failures

### 🔎 Powered by Tavily Search
- Web search integration for real-time information retrieval
- Configurable result limits and relevance filtering
- Source attribution and citation management

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend                            │
│          (HTML/CSS/JS - Landing & Chat Interface)          │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                     FastAPI Backend                         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │            Observability Middleware                    │ │
│  │    (Trace IDs, Metrics, Response Time Tracking)        │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              API Routes Layer                          │ │
│  │  • Research  • Documents  • Auth  • Health            │ │
│  │  • Cache Management  • Memory  • Observability        │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              LangGraph Research Workflow                    │
│                                                             │
│   ┌─────────┐       ┌──────────────┐                      │
│   │ Router  │──────▶│   Simple     │──────▶ END           │
│   │  Agent  │       │   Agent      │                      │
│   └────┬────┘       └──────────────┘                      │
│        │                                                   │
│        │            ┌──────────────┐                      │
│        ├───────────▶│Verification  │──────▶ END           │
│        │            │   Agent      │                      │
│        │            └──────────────┘                      │
│        │                                                   │
│        │            ┌──────────┐    ┌────────┐           │
│        └───────────▶│ Planner  │───▶│ Search │           │
│                     │  Agent   │    │ Reader │           │
│                     └──────────┘    └───┬────┘           │
│                                         │                 │
│                     ┌───────────────────▼────────┐       │
│                     │  Consolidate Evidence      │       │
│                     └───────────┬────────────────┘       │
│                                 │                         │
│                     ┌───────────▼────────┐               │
│                     │  Writer Agent      │               │
│                     └───────────┬────────┘               │
│                                 │                         │
│                     ┌───────────▼────────┐               │
│                     │  Critic Agent      │               │
│                     └───────────┬────────┘               │
│                                 │                         │
│                          Needs Correction?                │
│                          Yes │     │ No                   │
│                    ┌─────────┘     └─────────┐          │
│                    │ Retry (Max 2)            │          │
│                    └──────▶ Search            ▼          │
│                                          Finalize ──▶ END │
│                                                           │
└───────────────────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   Services Layer                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │   LLM    │  │  Search  │  │  Cache   │  │   PII    │   │
│  │ Service  │  │ (Tavily) │  │ (Redis)  │  │ Detector │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              External Integrations                          │
│  • Google Gemini API    • Groq API    • Tavily Search       │
│  • Redis Cache          • PostgreSQL (Optional)            │
└─────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
FY Project 11/
├── app/
│   ├── agents/              # Specialized AI agents
│   │   ├── router.py        # Query classification
│   │   ├── simple.py        # General financial concepts
│   │   ├── verification.py  # Fact verification
│   │   ├── planner.py       # Task decomposition
│   │   ├── reader.py        # Information extraction
│   │   ├── evidence.py      # Evidence consolidation
│   │   ├── writer.py        # Answer synthesis
│   │   ├── critic.py        # Quality review
│   │   └── document_analysis.py  # Document processing
│   ├── api/
│   │   └── routes/          # API endpoints
│   │       ├── research.py
│   │       ├── documents.py
│   │       ├── auth.py
│   │       ├── cache.py
│   │       ├── memory.py
│   │       ├── observability.py
│   │       └── health.py
│   ├── core/                # Core configuration
│   │   ├── config.py
│   │   ├── logging.py
│   │   └── observability.py
│   ├── database/            # Database models & session
│   │   ├── models.py
│   │   └── session.py
│   ├── documents/           # Document parsers
│   │   ├── pdf_parser.py
│   │   ├── docx_parser.py
│   │   └── parser.py
│   ├── providers/           # External API integrations
│   │   └── tavily.py
│   ├── schemas/             # Pydantic models
│   │   ├── research.py
│   │   ├── evidence.py
│   │   └── documents.py
│   ├── services/            # Business logic services
│   │   ├── llm.py           # LLM orchestration
│   │   ├── search.py        # Search service
│   │   ├── cache.py         # Caching layer
│   │   ├── pii_detector.py  # PII protection
│   │   ├── research.py
│   │   ├── auth.py
│   │   └── memory.py
│   ├── workflows/           # LangGraph workflows
│   │   └── research_graph.py
│   └── main.py              # FastAPI application
├── frontend/                # Web interface
│   ├── landing.html         # Landing page
│   ├── index.html           # Chat interface
│   ├── app.js               # Frontend logic
│   ├── style.css
│   └── landing.css
├── data/                    # Data storage
│   ├── uploads/             # Uploaded documents
│   ├── irium.db             # SQLite database
│   └── persistent_memory.db # Memory storage
├── docs/                    # Documentation
│   ├── OBSERVABILITY.md
│   ├── PII_PROTECTION.md
│   ├── REDIS_CACHING.md
│   └── PERSISTENT_MEMORY.md
├── tests/                   # Test files
├── .env                     # Environment variables
├── .env.example             # Environment template
├── requirements.txt         # Python dependencies
├── Dockerfile              # Container definition
└── docker-compose.yml      # Multi-service orchestration
```

## 🚀 Getting Started

### Prerequisites

- **Python 3.13** or compatible version
- **Redis** (optional, falls back to in-memory cache)
- **PostgreSQL** (optional, currently using localStorage)
- **API Keys**:
  - Google Gemini API key OR Groq API key
  - Tavily Search API key

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd "FY Project 11"
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   
   # Windows
   .\venv\Scripts\activate
   
   # Linux/Mac
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
   
   # Edit .env with your API keys
   ```

5. **Set up environment variables** (`.env`):
   ```env
   # LLM Configuration
   GOOGLE_API_KEY=your_google_api_key_here
   GROQ_API_KEY=your_groq_api_key_here
   LLM_PROVIDER=google  # or "groq"
   LLM_MODEL=gemini-1.5-flash
   
   # Search
   TAVILY_API_KEY=your_tavily_api_key_here
   
   # Application
   APP_ENV=development
   LOG_LEVEL=INFO
   MAX_UPLOAD_SIZE_MB=50
   
   # Research Configuration
   MAX_RETRIES=2
   SEARCH_MAX_RESULTS=10
   
   # PII Protection
   PII_DETECTION_ENABLED=true
   PII_POLICY=REDACT  # REDACT, BLOCK, MASK, LOG_ONLY
   
   # Redis (optional)
   REDIS_URL=redis://localhost:6379/0
   REDIS_ENABLED=true
   CACHE_DEFAULT_TTL=3600
   ```

6. **Run the application**:
   ```bash
   # Development
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   
   # Production
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

7. **Access the application**:
   - Landing page: http://localhost:8000
   - Chat interface: http://localhost:8000/app
   - API documentation: http://localhost:8000/docs
   - Health check: http://localhost:8000/health/ready

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## 📚 API Documentation

### Research Endpoints

#### POST `/api/research`
Execute a research query through the multi-agent workflow.

**Request Body**:
```json
{
  "query": "Compare HDFC Bank and ICICI Bank financial performance",
  "bypass_cache": false
}
```

**Response**:
```json
{
  "query": "Compare HDFC Bank and ICICI Bank financial performance",
  "answer": "Detailed comparison with analysis...",
  "evidence": [
    {
      "claim": "HDFC Bank revenue",
      "source": "https://example.com",
      "relevance": 0.95
    }
  ],
  "sources": [
    {
      "title": "HDFC Bank Annual Report",
      "url": "https://example.com"
    }
  ],
  "route": "COMPLEX",
  "processing_time_ms": 5420.32
}
```

### Document Endpoints

#### POST `/api/documents/upload`
Upload and process documents (PDF, DOCX, TXT).

#### POST `/api/documents/query`
Query uploaded documents.

### Cache Management

#### GET `/api/cache/stats`
Get cache statistics and performance metrics.

#### POST `/api/cache/clear`
Clear all cached entries.

### Observability

#### GET `/api/observability/metrics`
Get system performance metrics.

#### GET `/api/observability/traces?limit=50`
Get recent execution traces.

#### POST `/api/observability/reset`
Reset metrics counters.

### Health Checks

#### GET `/health/ready`
Comprehensive readiness check for all system components.

## 🔧 Configuration

### LLM Provider Configuration

**Google Gemini**:
```env
LLM_PROVIDER=google
LLM_MODEL=gemini-1.5-flash  # or gemini-1.5-pro, gemini-pro
GOOGLE_API_KEY=your_api_key
```

**Groq**:
```env
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile  # or mixtral-8x7b-32768, gemma2-9b-it
GROQ_API_KEY=your_api_key
```

### PII Protection Policies

- **REDACT** (Default): Replace PII with category tags
- **BLOCK**: Reject requests containing PII
- **MASK**: Partially obscure sensitive values
- **LOG_ONLY**: Log detection without modification

### Cache TTL Strategy

| Query Tier | TTL | Use Case |
|-----------|-----|----------|
| SIMPLE | 24 hours | Stable financial definitions |
| VERIFICATION | 5 minutes | Real-time market data |
| COMPLEX | 1 hour | Multi-source research |
| SEARCH | 30 minutes | Web search results |

## 🧪 Testing

```bash
# Run specific tests
python tests/groqtest.py
python tests/tavilytest.py
python tests/test_chatgroq.py
```

## 📊 Monitoring & Observability

### Metrics Available
- HTTP request latency distribution (avg, min, max, p95)
- Agent execution times by type (router, planner, reader, writer, etc.)
- LLM call performance and fallback tracking
- Search retrieval latency
- Cache hit/miss rates
- Error rates by component and type
- End-to-end workflow duration

### Trace Headers
- `X-Trace-ID`: Unique request identifier
- `X-Response-Time-Ms`: Request processing time

### Health Monitoring
The `/health/ready` endpoint checks:
- LLM provider configuration and credentials
- Search provider availability
- Database connection status
- Observability system health

## 🔒 Security Features

### PII Detection Algorithms
- **Payment Cards**: Luhn checksum validation (Visa, Mastercard, Amex, Discover, RuPay)
- **Aadhaar**: Verhoeff checksum algorithm
- **PAN**: Entity type validation
- **SSN**: Format and area/group validity checks
- **Email/Phone**: RFC compliance and boundary validation
- **Bank Accounts**: Mod-97 for IBAN, RBI pattern for IFSC

### False Positive Mitigation
- Currency prefix exemptions ($, ₹, €, Rs, USD, INR)
- Financial suffix exclusions (B, M, cr, crore, lakh, %, bps)
- Algorithmic checksum verification

### Log Sanitization
All application logs automatically scrubbed of PII before output.

## 🎯 Use Cases

### Financial Research
- Market analysis and comparisons
- Regulatory compliance research
- Financial metrics and KPI analysis
- Industry trend analysis

### Document Analysis
- Financial report processing
- Regulatory document analysis
- Policy document extraction
- Research paper analysis

### Real-Time Information
- Current interest rates
- Exchange rates
- Market data
- Recent regulatory changes

## 🛠️ Technology Stack

### Backend
- **FastAPI**: Modern Python web framework
- **LangGraph**: State-based AI workflow orchestration
- **LangChain**: LLM application framework
- **Pydantic**: Data validation
- **SQLAlchemy**: Database ORM

### AI/ML
- **Google Gemini**: Primary LLM provider
- **Groq**: Alternative fast inference
- **Tavily**: Web search API

### Infrastructure
- **Redis**: Distributed caching
- **PostgreSQL**: Relational database
- **Docker**: Containerization
- **Uvicorn**: ASGI server

### Frontend
- Vanilla JavaScript
- HTML5/CSS3
- Responsive design

## 📝 Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_API_KEY` | Google Gemini API key | - |
| `GROQ_API_KEY` | Groq API key | - |
| `LLM_PROVIDER` | LLM provider ("google" or "groq") | google |
| `LLM_MODEL` | Model to use | gemini-1.5-flash |
| `TAVILY_API_KEY` | Tavily search API key | - |
| `APP_ENV` | Environment (development/production) | development |
| `LOG_LEVEL` | Logging level | INFO |
| `MAX_RETRIES` | Research retry attempts | 2 |
| `SEARCH_MAX_RESULTS` | Max search results per query | 10 |
| `PII_DETECTION_ENABLED` | Enable PII detection | true |
| `PII_POLICY` | PII handling policy | REDACT |
| `REDIS_ENABLED` | Enable Redis caching | true |
| `REDIS_URL` | Redis connection URL | redis://localhost:6379/0 |
| `CACHE_DEFAULT_TTL` | Default cache TTL (seconds) | 3600 |

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## 📄 License

[Add your license information here]

## 🙏 Acknowledgments

- LangChain and LangGraph for AI workflow orchestration
- Google for Gemini API
- Groq for fast inference capabilities
- Tavily for search API
- FastAPI for the excellent web framework

## 📞 Support

For issues, questions, or contributions, please open an issue on the repository.

---

**Built with ❤️ for FinTech Research**
