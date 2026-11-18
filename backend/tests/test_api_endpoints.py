import os

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "sample_invoices"))


def test_api_health_and_tenant(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    res_t = client.get("/api/tenant")
    assert res_t.status_code == 200
    assert res_t.json()["name"] == "Modern Tech Solutions Pvt Ltd"


def test_api_list_accounts(client):
    res = client.get("/api/accounts")
    assert res.status_code == 200
    accounts = res.json()
    assert len(accounts) >= 10
    codes = [a["code"] for a in accounts]
    assert "1050" in codes  # Furniture
    assert "1081" in codes  # Input CGST
    assert "2010" in codes  # Creditors


def test_api_end_to_end_invoice_flow(client):
    """
    Simulates complete REST API flow:
    Upload PDF -> Process Document -> Verify Extracted Proposal -> Post Entry -> Check Trial Balance & Reports
    """
    pdf_path = os.path.join(DATA_DIR, "INV-2026-001.pdf")
    assert os.path.exists(pdf_path)

    # 1. Upload Document
    with open(pdf_path, "rb") as f:
        upload_res = client.post(
            "/api/documents/upload",
            files={"file": ("INV-2026-001.pdf", f, "application/pdf")}
        )
    assert upload_res.status_code == 200
    doc_id = upload_res.json()["document_id"]
    assert doc_id is not None

    # 2. Process Document (Extraction + Table Correction + Interpretation)
    process_res = client.post(f"/api/documents/{doc_id}/process")
    assert process_res.status_code == 200
    data = process_res.json()
    
    inv = data["extracted_invoice"]
    proposal = data["proposed_journal_entry"]

    assert inv["invoice_number"] == "INV-2026-001"
    assert inv["grand_total"] == 59000.00
    assert proposal["total_debits"] == 59000.00
    assert proposal["total_credits"] == 59000.00
    assert proposal["is_balanced"] is True

    # 3. Post the proposed journal entry
    post_res = client.post("/api/journal/post", json={"document_id": doc_id})
    assert post_res.status_code == 200
    assert post_res.json()["status"] == "SUCCESS"

    # 4. Check Trial Balance
    tb_res = client.get("/api/reports/trial-balance")
    assert tb_res.status_code == 200
    tb = tb_res.json()
    assert tb["is_balanced"] is True
    assert tb["total_debit_balance"] >= 59000.00
    assert tb["total_credit_balance"] >= 59000.00

    # 5. Check Balance Sheet (Asset = Desks 30,000 + Input GST 9,000 = 39,000; Chairs 20,000 expensed)
    bs_res = client.get("/api/reports/balance-sheet")
    assert bs_res.status_code == 200
    bs = bs_res.json()
    assert bs["is_balanced"] is True
    assert bs["total_assets"] >= 39000.00

    # 6. Check Audit Logs
    audit_res = client.get("/api/reports/audit-logs")
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert len(logs) > 0
    assert any(l["action"] == "POST" for l in logs)
