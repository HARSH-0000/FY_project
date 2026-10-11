#!/usr/bin/env python3
"""
Quick setup test for Irium MVP
Tests basic imports and configuration
"""

import sys

def test_imports():
    """Test that all required packages can be imported."""
    print("🧪 Testing imports...")
    
    try:
        import fastapi
        print("✅ FastAPI")
    except ImportError as e:
        print(f"❌ FastAPI: {e}")
        return False
    
    try:
        import langchain
        print("✅ LangChain")
    except ImportError as e:
        print(f"❌ LangChain: {e}")
        return False
    
    try:
        import langgraph
        print("✅ LangGraph")
    except ImportError as e:
        print(f"❌ LangGraph: {e}")
        return False
    
    try:
        import tavily
        print("✅ Tavily")
    except ImportError as e:
        print(f"❌ Tavily: {e}")
        return False
    
    try:
        import fitz  # PyMuPDF
        print("✅ PyMuPDF")
    except ImportError as e:
        print(f"❌ PyMuPDF: {e}")
        return False
    
    try:
        import docx
        print("✅ python-docx")
    except ImportError as e:
        print(f"❌ python-docx: {e}")
        return False
    
    try:
        import sqlalchemy
        print("✅ SQLAlchemy")
    except ImportError as e:
        print(f"❌ SQLAlchemy: {e}")
        return False
    
    return True


def test_configuration():
    """Test configuration loading."""
    print("\n🔧 Testing configuration...")
    
    try:
        from app.core.config import settings
        
        print(f"✅ Configuration loaded")
        print(f"   - LLM Provider: {settings.LLM_PROVIDER}")
        print(f"   - LLM Model: {settings.LLM_MODEL}")
        print(f"   - Environment: {settings.APP_ENV}")
        
        # Check for API keys
        warnings = []
        if not settings.GOOGLE_API_KEY and settings.LLM_PROVIDER == "google":
            warnings.append("GOOGLE_API_KEY not configured")
        if not settings.GROQ_API_KEY and settings.LLM_PROVIDER == "groq":
            warnings.append("GROQ_API_KEY not configured")
        if not settings.TAVILY_API_KEY:
            warnings.append("TAVILY_API_KEY not configured")
        
        if warnings:
            print("\n⚠️  Configuration warnings:")
            for warning in warnings:
                print(f"   - {warning}")
            return False
        else:
            print("✅ All API keys configured")
            return True
            
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False


def test_agents():
    """Test agent imports."""
    print("\n🤖 Testing agents...")
    
    try:
        from app.agents import (
            router_agent,
            simple_agent,
            verification_agent,
            planner_agent,
            reader_agent,
            evidence_agent,
            writer_agent,
            critic_agent
        )
        print("✅ All agents imported successfully")
        return True
    except Exception as e:
        print(f"❌ Agent import failed: {e}")
        return False


def test_database():
    """Test database connection."""
    print("\n🗄️  Testing database...")
    
    try:
        from app.database import Base, engine
        
        # Try to connect
        with engine.connect() as conn:
            print("✅ Database connection successful")
            return True
    except Exception as e:
        print(f"⚠️  Database connection failed: {e}")
        print("   (This is OK if you haven't started PostgreSQL yet)")
        return True  # Don't fail the test for DB connection


def main():
    """Run all tests."""
    print("=" * 60)
    print("🔍 Irium MVP - Setup Test")
    print("=" * 60)
    print()
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("Configuration", test_configuration()))
    results.append(("Agents", test_agents()))
    results.append(("Database", test_database()))
    
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n🎉 All tests passed! Irium is ready to run.")
        print("\nNext steps:")
        print("1. Start PostgreSQL (or use Docker)")
        print("2. Run: uvicorn app.main:app --reload")
        print("3. Open: http://localhost:8000/docs")
        return 0
    else:
        print("\n❌ Some tests failed. Please check the errors above.")
        print("\nMake sure:")
        print("1. All dependencies are installed: pip install -r requirements.txt")
        print("2. .env file is configured with API keys")
        print("3. PostgreSQL is running (if testing database)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
