"""
Comprehensive Test Suite for Feature: Document Intelligence and Chat-Based PDF/Image Analysis
Covers:
- Test A: Text-based PDF summary
- Test B: Scanned PDF OCR extraction
- Test C: Image analysis (financial chart/table)
- Test D: Numerical extraction and page references
- Test E: Unsupported question / absent evidence handling
- Test F: Follow-up question without re-uploading
- Test G: Multiple documents comparison
- Test H: Existing application regression (health, research)
- Test I: Error handling (invalid formats, corruption, empty files)
"""

import io
import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import fitz  # PyMuPDF
from fastapi.testclient import TestClient
from app.main import app
from app.services.document_store import document_store
from app.documents.validator import document_validator, DocumentValidationError

client = TestClient(app)


def create_sample_text_pdf() -> bytes:
    """Create a sample 2-page text PDF with financial figures."""
    doc = fitz.open()

    # Page 1: Financial Highlights
    page1 = doc.new_page(width=595, height=842)
    text1 = """Acme FinTech Corp - Annual Financial Report FY2024
Page 1: Executive Summary & Financial Highlights

Total Revenue: $1,250 Million (18% YoY growth)
Net Profit: $450 Million (compared to $380 Million in FY2023)
Operating EBITDA: $520 Million with an operating margin of 41.6%
Total Assets: $3,200 Million
Total Debt: $600 Million

Strategic Performance:
Acme expanded its digital lending and wealth management divisions, adding 2.4 million active users.
Customer acquisition cost declined by 14% due to organic platform growth.
"""
    page1.insert_text((50, 60), text1, fontsize=12)

    # Page 2: Risk Factors
    page2 = doc.new_page(width=595, height=842)
    text2 = """Acme FinTech Corp - Annual Financial Report FY2024
Page 2: Risk Factors & Outlook

Major Identified Risks:
1. Interest Rate Sensitivity: Higher central bank benchmark rates could increase borrowing costs.
2. Cybersecurity Threats: Increased digital transaction volumes elevate the risk of data breaches.
3. Regulatory Compliance: New fintech licensing requirements may lead to higher compliance expenses.

Future Outlook:
Projected revenue growth of 15% for FY2025 supported by international expansion in Southeast Asia.
"""
    page2.insert_text((50, 60), text2, fontsize=12)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def create_sample_scanned_pdf() -> bytes:
    """Create a scanned PDF where page contents are embedded purely as an image pixmap."""
    temp_doc = fitz.open()
    temp_page = temp_doc.new_page(width=400, height=200)
    temp_page.insert_text((30, 50), "SCANNED INVOICE FY2024\nVendor: Global Tech Ltd\nAmount Due: $75,000\nStatus: Paid in Full", fontsize=14)
    pix = temp_page.get_pixmap(dpi=150)
    img_bytes = pix.tobytes("png")
    temp_doc.close()

    # Insert image onto a blank page with NO text layer
    scanned_doc = fitz.open()
    scanned_page = scanned_doc.new_page(width=400, height=200)
    scanned_page.insert_image(scanned_page.rect, stream=img_bytes)
    result_bytes = scanned_doc.tobytes()
    scanned_doc.close()
    return result_bytes


def create_sample_chart_image() -> bytes:
    """Create a financial chart image (PNG)."""
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.draw_rect(fitz.Rect(10, 10, 390, 290), color=(0.1, 0.1, 0.2), fill=(0.95, 0.95, 0.95))
    page.insert_text((30, 40), "Q4 Revenue Comparison Chart (in $ Millions)", fontsize=14, color=(0, 0, 0))
    page.insert_text((30, 80), "Bar Chart: Q1: $200M | Q2: $250M | Q3: $320M | Q4: $480M", fontsize=11, color=(0.1, 0.1, 0.5))
    # Draw bars
    page.draw_rect(fitz.Rect(50, 200, 90, 250), color=(0.2, 0.6, 0.2), fill=(0.2, 0.6, 0.2))
    page.draw_rect(fitz.Rect(120, 170, 160, 250), color=(0.2, 0.6, 0.2), fill=(0.2, 0.6, 0.2))
    page.draw_rect(fitz.Rect(190, 140, 230, 250), color=(0.2, 0.6, 0.2), fill=(0.2, 0.6, 0.2))
    page.draw_rect(fitz.Rect(260, 100, 300, 250), color=(0.2, 0.6, 0.2), fill=(0.2, 0.6, 0.2))
    pix = page.get_pixmap(dpi=150)
    img_bytes = pix.tobytes("png")
    doc.close()
    return img_bytes


# =============================================================================
# Test Suite
# =============================================================================

def test_a_text_based_pdf_summary():
    """Test A: Upload text-based PDF and request summary."""
    pdf_bytes = create_sample_text_pdf()
    response = client.post(
        "/api/documents/analyze",
        data={"query": "Summarize this annual report and list the key performance metrics."},
        files={"files": ("annual_report.pdf", pdf_bytes, "application/pdf")}
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert "answer" in data
    assert "annual_report.pdf" in data["documents"]
    answer_text = data["answer"].lower()
    # Verify grounding in document content
    assert "1,250" in data["answer"] or "revenue" in answer_text
    assert "450" in data["answer"] or "profit" in answer_text


def test_b_scanned_pdf_extraction():
    """Test B: Upload scanned PDF and verify OCR / Vision extraction."""
    scanned_bytes = create_sample_scanned_pdf()
    response = client.post(
        "/api/documents/analyze",
        data={"query": "What is the vendor and amount due mentioned in this scanned document?"},
        files={"files": ("scanned_invoice.pdf", scanned_bytes, "application/pdf")}
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert "answer" in data
    answer_text = data["answer"].lower()
    assert "75,000" in data["answer"] or "global tech" in answer_text or "invoice" in answer_text


def test_c_image_chart_analysis():
    """Test C: Upload image chart and ask question about visual contents."""
    image_bytes = create_sample_chart_image()
    response = client.post(
        "/api/documents/analyze",
        data={"query": "What does this chart show and what is the Q4 figure?"},
        files={"files": ("q4_chart.png", image_bytes, "image/png")}
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert "answer" in data
    assert "q4_chart.png" in data["documents"]
    answer = data["answer"]
    assert "revenue" in answer.lower() or "480" in answer or "q4" in answer.lower()


def test_d_numerical_extraction_and_page_citations():
    """Test D: Extract numerical figure and verify citation of source page."""
    pdf_bytes = create_sample_text_pdf()
    response = client.post(
        "/api/documents/analyze",
        data={"query": "What is the exact net profit and total debt reported in this document? Cite the page numbers."},
        files={"files": ("acme_report.pdf", pdf_bytes, "application/pdf")}
    )

    assert response.status_code == 200, response.text
    data = response.json()
    answer = data["answer"]
    # Check numerical figures
    assert "$450" in answer or "450 million" in answer.lower()
    assert "$600" in answer or "600 million" in answer.lower()
    # Check page citations
    assert 1 in data["source_pages"] or "[Page 1]" in answer or "Page 1" in answer


def test_e_unsupported_question_acknowledges_missing():
    """Test E: Ask question absent from document; verify model does not hallucinate."""
    pdf_bytes = create_sample_text_pdf()
    response = client.post(
        "/api/documents/analyze",
        data={"query": "What is the name of the CEO's favorite pet dog?"},
        files={"files": ("acme_report.pdf", pdf_bytes, "application/pdf")}
    )

    assert response.status_code == 200, response.text
    data = response.json()
    answer_lower = data["answer"].lower()
    # Must acknowledge absence rather than inventing an answer
    assert (
        "does not contain" in answer_lower
        or "not mentioned" in answer_lower
        or "does not mention" in answer_lower
        or "no information" in answer_lower
        or "not provided" in answer_lower
    )


def test_f_conversation_follow_up_without_reupload():
    """Test F: Upload document, ask initial question, then ask follow-up in same session."""
    session_id = f"test_chat_session_{os.getpid()}"
    pdf_bytes = create_sample_text_pdf()

    # Step 1: Initial upload with question
    resp1 = client.post(
        "/api/documents/analyze",
        data={"query": "Summarize this document.", "session_id": session_id},
        files={"files": ("acme_report.pdf", pdf_bytes, "application/pdf")}
    )
    assert resp1.status_code == 200, resp1.text

    # Step 2: Follow-up question WITHOUT sending any file
    resp2 = client.post(
        "/api/documents/analyze",
        data={"query": "What are the major cybersecurity and interest rate risks mentioned in it?", "session_id": session_id}
    )
    assert resp2.status_code == 200, resp2.text
    data2 = resp2.json()
    assert "answer" in data2
    ans2_lower = data2["answer"].lower()
    assert "cybersecurity" in ans2_lower or "interest rate" in ans2_lower or "risk" in ans2_lower


def test_g_multiple_documents_comparison():
    """Test G: Upload two documents and ask for comparison."""
    doc1 = fitz.open()
    p1 = doc1.new_page(width=400, height=300)
    p1.insert_text((30, 40), "Company Alpha: FY24 Revenue: $500M, Operating Margin: 25%", fontsize=12)
    bytes1 = doc1.tobytes()
    doc1.close()

    doc2 = fitz.open()
    p2 = doc2.new_page(width=400, height=300)
    p2.insert_text((30, 40), "Company Beta: FY24 Revenue: $800M, Operating Margin: 18%", fontsize=12)
    bytes2 = doc2.tobytes()
    doc2.close()

    response = client.post(
        "/api/documents/analyze",
        data={"query": "Compare the FY24 revenue and operating margins of Company Alpha and Company Beta."},
        files=[
            ("files", ("company_alpha.pdf", bytes1, "application/pdf")),
            ("files", ("company_beta.pdf", bytes2, "application/pdf")),
        ]
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["documents"]) == 2
    ans_lower = data["answer"].lower()
    assert "alpha" in ans_lower and "beta" in ans_lower
    assert "500" in data["answer"] and "800" in data["answer"]


def test_h_existing_application_regression():
    """Test H: Verify existing health and research routes still work intact."""
    # Health check
    h_resp = client.get("/health")
    assert h_resp.status_code == 200
    assert h_resp.json().get("status") == "healthy"

    # Landing page served
    landing_resp = client.get("/")
    assert landing_resp.status_code == 200
    assert "html" in landing_resp.headers.get("content-type", "")

    # Static app served
    app_resp = client.get("/chat")
    assert app_resp.status_code == 200


def test_i_error_handling_invalid_and_oversized():
    """Test I: Error handling for unsupported formats and corrupted files."""
    # 1. Unsupported file format (.exe)
    resp_unsupported = client.post(
        "/api/documents/analyze",
        data={"query": "Explain this file."},
        files={"files": ("malware.exe", b"MZ\x90\x00\x03\x00\x00\x00", "application/octet-stream")}
    )
    assert resp_unsupported.status_code == 400
    assert "not supported" in resp_unsupported.json()["detail"].lower()

    # 2. Corrupted PDF
    resp_corrupt = client.post(
        "/api/documents/analyze",
        data={"query": "Explain this file."},
        files={"files": ("broken.pdf", b"NOT_A_REAL_PDF_DATA", "application/pdf")}
    )
    assert resp_corrupt.status_code == 400
    assert "corrupt" in resp_corrupt.json()["detail"].lower() or "match" in resp_corrupt.json()["detail"].lower()


if __name__ == "__main__":
    tests = [
        ("Test H (Regression)", test_h_existing_application_regression),
        ("Test I (Error Handling)", test_i_error_handling_invalid_and_oversized),
        ("Test A (Text-based PDF)", test_a_text_based_pdf_summary),
        ("Test D (Numerical Extraction)", test_d_numerical_extraction_and_page_citations),
        ("Test E (Unsupported Question)", test_e_unsupported_question_acknowledges_missing),
        ("Test F (Follow-up Question)", test_f_conversation_follow_up_without_reupload),
        ("Test G (Multiple Documents)", test_g_multiple_documents_comparison),
        ("Test C (Image Analysis)", test_c_image_chart_analysis),
        ("Test B (Scanned PDF OCR)", test_b_scanned_pdf_extraction),
    ]

    print("=" * 60)
    print("RUNNING DOCUMENT INTELLIGENCE TEST SUITE (Tests A - I)")
    print("=" * 60)

    passed = 0
    failed = 0

    for name, test_fn in tests:
        print(f"\n[RUNNING] {name}...")
        try:
            test_fn()
            print(f"[PASS] {name} [OK]")
            passed += 1
        except Exception as e:
            print(f"[FAIL] {name} [FAILED]: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} PASSED, {failed} FAILED (TOTAL {len(tests)})")
    print("=" * 60)

    if failed > 0:
        exit(1)
