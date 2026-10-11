"""
Test suite for Feature 1: Simple Landing Page and Navigation to Irium
"""
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_landing_page_file_exists():
    """Verify landing.html and landing.css files exist and have appropriate content."""
    base_dir = Path(__file__).resolve().parent.parent
    landing_html = base_dir / "frontend" / "landing.html"
    landing_css = base_dir / "frontend" / "landing.css"
    chat_html = base_dir / "frontend" / "index.html"

    assert landing_html.exists(), "landing.html must exist in frontend/"
    assert landing_css.exists(), "landing.css must exist in frontend/"
    assert chat_html.exists(), "index.html must exist in frontend/"

    html_content = landing_html.read_text(encoding="utf-8")
    assert "Irium" in html_content
    assert "financial research assistant" in html_content.lower()
    assert "start research" in html_content.lower() or "explore irium" in html_content.lower()
    assert "index.html" in html_content

    css_content = landing_css.read_text(encoding="utf-8")
    assert "@media" in css_content, "landing.css must contain responsive media queries"


def test_root_route_serves_landing_page():
    """Verify GET / returns the landing page with 200 OK."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Irium" in response.text
    assert "financial research assistant" in response.text.lower()


def test_landing_route():
    """Verify GET /landing returns the landing page."""
    response = client.get("/landing")
    assert response.status_code == 200
    assert "Irium" in response.text


def test_chat_app_route():
    """Verify GET /app and GET /chat return the chat application."""
    for path in ["/app", "/chat", "/index.html"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "messageInput" in response.text
        assert "welcomeScreen" in response.text


def test_static_files_accessible():
    """Verify static files are served properly from both /static/ and root / paths."""
    response_landing = client.get("/static/landing.html")
    assert response_landing.status_code == 200

    response_chat = client.get("/static/index.html")
    assert response_chat.status_code == 200

    response_css = client.get("/static/landing.css")
    assert response_css.status_code == 200

    # Also test relative asset resolution from root
    assert client.get("/landing.css").status_code == 200
    assert client.get("/style.css").status_code == 200
    assert client.get("/app.js").status_code == 200


def test_health_check_regression():
    """Ensure existing health check endpoint continues to work without regression."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "healthy"


if __name__ == "__main__":
    tests = [
        test_landing_page_file_exists,
        test_root_route_serves_landing_page,
        test_landing_route,
        test_chat_app_route,
        test_static_files_accessible,
        test_health_check_regression,
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

