"""Tests for human correction of extracted invoices and report exports."""

import os

from app.main import app  # noqa: F401 - imported so the API surface is loaded

DATA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "sample_invoices")
)


def upload_and_process(client, filename="INV-2026-001.pdf"):
    with open(os.path.join(DATA_DIR, filename), "rb") as handle:
        upload = client.post(
            "/api/documents/upload",
            files={"file": (filename, handle, "application/pdf")},
        )
    assert upload.status_code == 200
    document_id = upload.json()["document_id"]

    processed = client.post(f"/api/documents/{document_id}/process")
    assert processed.status_code == 200
    return document_id, processed.json()


def correction_payload(processed, **overrides):
    invoice = processed["extracted_invoice"]
    payload = {
        "invoice_number": invoice["invoice_number"],
        "invoice_date": invoice["invoice_date"],
        "due_date": invoice.get("due_date"),
        "vendor_name": invoice["vendor_name"],
        "vendor_gstin": invoice.get("vendor_gstin"),
        "buyer_name": invoice.get("buyer_name"),
        "buyer_gstin": invoice.get("buyer_gstin"),
        "place_of_supply": invoice.get("place_of_supply"),
        "subtotal": invoice["subtotal"],
        "total_tax": invoice["total_tax"],
        "total_discount": invoice["total_discount"],
        "grand_total": invoice["grand_total"],
        "line_items": [
            {
                "description": item["description"],
                "hsn_sac": item.get("hsn_sac"),
                "quantity": item["quantity"],
                "unit_price": item["unit_price"],
                "discount_amount": item["discount_amount"],
                "tax_rate_percent": item.get("tax_rate_percent", 0),
                "total_amount": item["total_amount"],
            }
            for item in invoice["line_items"]
        ],
    }
    payload.update(overrides)
    return payload


# --- corrections ----------------------------------------------------------

def test_corrected_vendor_survives_a_reload(client):
    document_id, processed = upload_and_process(client)

    updated = client.put(
        f"/api/documents/{document_id}/invoice",
        json=correction_payload(
            processed,
            vendor_name="ABC Furniture Mart Pvt Ltd",
            buyer_name="Modern Tech Solutions Ltd",
        ),
    )
    assert updated.status_code == 200

    reloaded = client.get(f"/api/documents/{document_id}")
    assert reloaded.status_code == 200
    assert reloaded.json()["invoice"]["vendor_name"] == "ABC Furniture Mart Pvt Ltd"
    assert reloaded.json()["invoice"]["buyer_name"] == "Modern Tech Solutions Ltd"


def test_correction_rebuilds_the_journal_proposal(client):
    document_id, processed = upload_and_process(client)
    payload = correction_payload(processed)
    payload["line_items"][1]["quantity"] = 5.00
    payload["line_items"][1]["total_amount"] = 25000.00
    payload["subtotal"] = 55000.00
    payload["total_tax"] = 9900.00
    payload["grand_total"] = 64900.00

    updated = client.put(f"/api/documents/{document_id}/invoice", json=payload)

    assert updated.status_code == 200
    body = updated.json()
    assert body["invoice"]["grand_total"] == 64900.00
    assert body["proposal"]["total_credits"] == 64900.00
    assert body["proposal"]["total_debits"] == 64900.00
    assert body["proposal"]["is_balanced"] is True


def test_inconsistent_correction_keeps_the_posting_gate_closed(client):
    document_id, processed = upload_and_process(client)

    updated = client.put(
        f"/api/documents/{document_id}/invoice",
        json=correction_payload(processed, grand_total=1000.00),
    )

    assert updated.status_code == 200
    body = updated.json()
    assert body["validation_report"]["has_blocking_failures"] is True
    assert body["status"] == "REVIEW_REQUIRED"


def test_posted_invoice_cannot_be_edited(client):
    document_id, processed = upload_and_process(client)
    posted = client.post("/api/journal/post", json=processed["proposed_journal_entry"])
    assert posted.status_code == 200

    updated = client.put(
        f"/api/documents/{document_id}/invoice",
        json=correction_payload(processed, vendor_name="Edited After Posting"),
    )

    assert updated.status_code == 409


def test_correction_rejects_negative_amounts(client):
    document_id, processed = upload_and_process(client)
    payload = correction_payload(processed)
    payload["line_items"][0]["total_amount"] = -100.00

    updated = client.put(f"/api/documents/{document_id}/invoice", json=payload)

    assert updated.status_code == 422


def test_correction_rejects_malformed_gstin(client):
    document_id, processed = upload_and_process(client)

    updated = client.put(
        f"/api/documents/{document_id}/invoice",
        json=correction_payload(processed, vendor_gstin="NOTAGSTIN"),
    )

    assert updated.status_code == 422


def test_correction_requires_at_least_one_line_item(client):
    document_id, processed = upload_and_process(client)

    updated = client.put(
        f"/api/documents/{document_id}/invoice",
        json=correction_payload(processed, line_items=[]),
    )

    assert updated.status_code == 422


def test_correction_for_unknown_document_returns_404(client):
    _, processed = upload_and_process(client)

    updated = client.put(
        "/api/documents/does-not-exist/invoice",
        json=correction_payload(processed),
    )

    assert updated.status_code == 404


def test_corrections_are_recorded_in_the_audit_trail(client):
    document_id, processed = upload_and_process(client)

    client.put(
        f"/api/documents/{document_id}/invoice",
        json=correction_payload(processed, vendor_name="Corrected Vendor"),
    )

    logs = client.get("/api/reports/audit-logs").json()
    assert any(log["action"] == "EDIT" for log in logs)


# --- exports --------------------------------------------------------------

def test_export_ledger_as_csv(client):
    _, processed = upload_and_process(client)
    client.post("/api/journal/post", json=processed["proposed_journal_entry"])

    response = client.get("/api/reports/export/ledger?format=csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    body = response.text
    assert "INV-2026-001" in body
    assert "Account Code" in body


def test_export_trial_balance_as_excel(client):
    _, processed = upload_and_process(client)
    client.post("/api/journal/post", json=processed["proposed_journal_entry"])

    response = client.get("/api/reports/export/trial-balance?format=xlsx")

    assert response.status_code == 200
    assert "spreadsheetml" in response.headers["content-type"]
    assert response.content[:2] == b"PK"


def test_export_financial_statements(client):
    _, processed = upload_and_process(client)
    client.post("/api/journal/post", json=processed["proposed_journal_entry"])

    for report in ("profit-and-loss", "balance-sheet"):
        response = client.get(f"/api/reports/export/{report}?format=csv")
        assert response.status_code == 200
        assert "Amount" in response.text


def test_export_journal_as_tally_xml(client):
    _, processed = upload_and_process(client)
    client.post("/api/journal/post", json=processed["proposed_journal_entry"])

    response = client.get("/api/reports/export/tally")

    assert response.status_code == 200
    assert "xml" in response.headers["content-type"]
    assert "<ENVELOPE>" in response.text
    assert "<VOUCHER" in response.text
    assert "INV-2026-001" in response.text
    assert "59000.00" in response.text


def test_export_rejects_unknown_report_and_format(client):
    assert client.get("/api/reports/export/unknown-report").status_code == 404
    assert client.get("/api/reports/export/ledger?format=pdf").status_code == 400
