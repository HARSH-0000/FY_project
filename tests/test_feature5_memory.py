"""
Comprehensive Test Suite for Feature 5: Persistent Memory
Tests user preferences, session context, research history, cross-restart persistence,
user isolation, PII protection on stored memories, deletion, and API routes.
"""

from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.services.memory import PersistentMemoryService, memory_service
import tempfile
import os

client = TestClient(app)


def test_user_preferences_persistence_across_restart():
    """Verify user preferences persist across backend restarts (fresh service instantiation)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = Path(tmp.name)
    tmp.close()
    
    try:
        # Instance 1: write preferences
        service1 = PersistentMemoryService(db_path=db_path)
        service1.save_preference(user_id=42, key="report_structure", value="executive_summary_with_risks")
        service1.save_preference(user_id=42, key="level_of_detail", value="deep_dive")
        service1.save_preference(user_id=42, key="financial_analysis_format", value="valuation_centric")

        # Instance 2 (simulating fresh backend restart pointing to same disk file)
        service2 = PersistentMemoryService(db_path=db_path)
        prefs = service2.get_preferences(user_id=42)

        assert prefs["report_structure"] == "executive_summary_with_risks"
        assert prefs["level_of_detail"] == "deep_dive"
        assert prefs["financial_analysis_format"] == "valuation_centric"
    finally:
        try:
            if db_path.exists():
                os.unlink(db_path)
        except Exception:
            pass


def test_session_context_tracking():
    """Verify session tracking for discussed companies, research objectives, and follow-ups."""
    session_id = 901
    memory_service.update_session_context(
        session_id=session_id,
        company="HDFCBANK",
        objective="Assess net interest margin and NPA trends",
        follow_up="What is the gross NPA ratio for Q2?"
    )
    # Add second company to same session
    memory_service.update_session_context(session_id=session_id, company="ICICIBANK")

    context = memory_service.get_session_context(session_id)
    assert "HDFCBANK" in context["discussed_companies"]
    assert "ICICIBANK" in context["discussed_companies"]
    assert "NPA trends" in context["research_objective"]
    assert len(context["follow_up_questions"]) >= 1


def test_memory_isolation_between_users():
    """Verify strict tenant isolation: user 100 cannot access user 200's preferences."""
    memory_service.save_preference(user_id=100, key="report_structure", value="concise_bullets")
    memory_service.save_preference(user_id=200, key="report_structure", value="comprehensive_tables")

    prefs_100 = memory_service.get_preferences(user_id=100)
    prefs_200 = memory_service.get_preferences(user_id=200)

    assert prefs_100["report_structure"] == "concise_bullets"
    assert prefs_200["report_structure"] == "comprehensive_tables"
    assert prefs_100 != prefs_200


def test_pii_protection_in_stored_memory():
    """Verify sensitive PII (cards, emails) is automatically redacted before saving into memory."""
    memory_service.save_preference(
        user_id=77,
        key="analyst_contact",
        value="Send alert to private.cfo@fund.com"
    )
    prefs = memory_service.get_preferences(user_id=77)
    saved_val = prefs["analyst_contact"]
    assert "private.cfo@fund.com" not in saved_val
    assert "[EMAIL_REDACTED]" in saved_val


def test_memory_prompt_context_construction():
    """Verify prompt context builder creates non-overriding, structured context."""
    user_id = 88
    session_id = 888
    memory_service.save_preference(user_id=user_id, key="report_structure", value="executive_summary")
    memory_service.update_session_context(session_id=session_id, company="AAPL")

    context_str = memory_service.build_memory_prompt_context(
        query="What was the latest iPhone revenue?",
        user_id=user_id,
        session_id=session_id
    )

    assert "[PERSISTENT MEMORY CONTEXT]" in context_str
    assert "User Preferences" in context_str
    assert "executive_summary" in context_str
    assert "AAPL" in context_str


def test_memory_deletion():
    """Verify deleting memory removes the entry permanently."""
    user_id = 99
    memory_service.save_preference(user_id=user_id, key="temp_pref", value="to_delete")
    assert "temp_pref" in memory_service.get_preferences(user_id)

    deleted = memory_service.delete_memory(category="user_preferences", key="temp_pref", user_id=user_id)
    assert deleted is True
    assert "temp_pref" not in memory_service.get_preferences(user_id)


def test_research_history_recording():
    """Verify research history is stored and retrievable."""
    user_id = 55
    memory_service.record_research_history(
        query="Explain repo rate impact",
        route="SIMPLE",
        summary="Repo rate influences commercial lending rates.",
        sources_count=3,
        user_id=user_id
    )

    history = memory_service.get_research_history(user_id=user_id, limit=5)
    assert len(history) >= 1
    assert history[0]["query"] == "Explain repo rate impact"
    assert history[0]["route"] == "SIMPLE"


def test_memory_api_endpoints():
    """Test REST API routes for preferences, session context, history, and clear."""
    # 1. Post preference
    res_pref = client.post("/api/memory/preferences", json={
        "report_structure": "detailed_tables",
        "level_of_detail": "comprehensive"
    })
    assert res_pref.status_code == 200
    data = res_pref.json()
    assert data["preferences"]["report_structure"] == "detailed_tables"

    # 2. Get preferences
    res_get = client.get("/api/memory/preferences")
    assert res_get.status_code == 200

    # 3. Post session context
    res_sess = client.post("/api/memory/session/701", json={
        "company": "NVDA",
        "objective": "Analyze datacenter GPU demand"
    })
    assert res_sess.status_code == 200
    sess_data = res_sess.json()
    assert "NVDA" in sess_data["context"]["discussed_companies"]

    # 4. Get session context
    res_sess_get = client.get("/api/memory/session/701")
    assert res_sess_get.status_code == 200

    # 5. Clear session
    res_clear = client.post("/api/memory/clear?session_id=701")
    assert res_clear.status_code == 200


if __name__ == "__main__":
    tests = [
        test_user_preferences_persistence_across_restart,
        test_session_context_tracking,
        test_memory_isolation_between_users,
        test_pii_protection_in_stored_memory,
        test_memory_prompt_context_construction,
        test_memory_deletion,
        test_research_history_recording,
        test_memory_api_endpoints,
    ]
    passed = 0
    for t in tests:
        print(f"Running {t.__name__}...", end=" ")
        try:
            t()
            print("PASSED")
            passed += 1
        except Exception as e:
            print(f"FAILED: {e}")
            raise
    print(f"\nAll {passed}/{len(tests)} tests passed successfully!")
