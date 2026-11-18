"""Regression tests for the posting trust boundary and the audit findings.

Each test names the failure it prevents. The attacker or bad input is the point:
a balanced-but-fabricated journal, a cash invoice, a duplicate number, a
valueless document, and a reprocess after posting.
"""

import os

import pymupdf
import pytest

from app.auth.security import ADMIN_EMAIL

DATA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "sample_invoices")
)


def upload(client, filename):
    with open(os.path.join(DATA_DIR, filename), "rb") as handle:
        response = client.post(
            "/api/documents/upload",
            files={"file": (filename, handle, "application/pdf")},
        )
    assert response.status_code == 200
    return response.json()["document_id"]


def upload_and_process(client, filename="INV-2026-001.pdf"):
    document_id = upload(client, filename)
    processed = client.post(f"/api/documents/{document_id}/process")
    assert processed.status_code == 200, processed.text
    return document_id, processed.json()


def correction_from(processed, **overrides):
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


# --- F-01: client-supplied journals are not authoritative -------------------

def test_a_fabricated_journal_payload_is_rejected(client):
    invoice = upload(client, "INV-2026-001.pdf")
    fabricated = {
        "source_document_id": invoice,
        "invoice_number": "FAKE-999",
        "entry_date": "2026-11-19",
        "transaction_type": "PURCHASE_GOODS_CREDIT",
        "narration": "fabricated",
        "reasoning": "fabricated",
        "lines": [
            {"account_code": "5010", "account_name": "x", "entry_type": "DEBIT", "amount": 100},
            {"account_code": "2010", "account_name": "x", "entry_type": "CREDIT", "amount": 100},
        ],
    }

    response = client.post("/api/journal/post", json=fabricated)

    assert response.status_code == 422
    assert client.get("/api/documents").json()[0]["status"] != "POSTED"


def test_an_unprocessed_document_cannot_be_posted(client):
    document_id = upload(client, "INV-2026-001.pdf")

    response = client.post("/api/journal/post", json={"document_id": document_id})

    assert response.status_code == 409
    assert "no stored invoice" in response.json()["detail"].lower()


def test_posting_writes_the_authenticated_user_to_the_audit_trail(client):
    document_id, _ = upload_and_process(client)

    assert client.post("/api/journal/post", json={"document_id": document_id}).status_code == 200

    logs = client.get("/api/reports/audit-logs").json()
    posts = [log for log in logs if log["action"] == "POST"]
    assert posts and posts[0]["performed_by"] == ADMIN_EMAIL


# --- F-02: cash settlement reconciles, it is not a false failure -----------

def test_a_cash_invoice_reconciles_and_posts(client):
    document_id, processed = upload_and_process(client)
    corrected = client.put(
        f"/api/documents/{document_id}/invoice",
        json=correction_from(processed, payment_terms="Paid via Cash"),
    )
    assert corrected.status_code == 200

    report = corrected.json()["validation_report"]
    reconciliation = [c for c in report["checks"] if c["check_name"] == "Source Invoice Payable Reconciliation"]
    assert reconciliation and reconciliation[0]["status"] == "PASS"
    assert report["has_blocking_failures"] is False

    posted = client.post("/api/journal/post", json={"document_id": document_id, "approve_with_warnings": True})
    assert posted.status_code == 200


# --- F-05: posted documents are immutable ---------------------------------

def test_reprocessing_a_posted_document_is_rejected(client):
    document_id, _ = upload_and_process(client)
    assert client.post("/api/journal/post", json={"document_id": document_id}).status_code == 200

    again = client.post(f"/api/documents/{document_id}/process")

    assert again.status_code == 409
    assert client.get(f"/api/documents/{document_id}").json()["status"] == "POSTED"


# --- F-10: no value means a controlled rejection, not a 500 ---------------

def test_a_pdf_with_no_table_is_rejected_cleanly(client, tmp_path):
    path = tmp_path / "empty.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "This page has no invoice table at all.")
    document.save(str(path))
    document.close()

    with open(path, "rb") as handle:
        uploaded = client.post(
            "/api/documents/upload",
            files={"file": ("empty.pdf", handle, "application/pdf")},
        )
    document_id = uploaded.json()["document_id"]

    response = client.post(f"/api/documents/{document_id}/process")

    assert response.status_code == 422
    assert "job" not in response.text.lower()  # no traceback leaked
    assert client.get(f"/api/documents/{document_id}").json()["status"] == "REVIEW_REQUIRED"


# --- F-04: duplicate identity is supplier + normalised number -------------

def test_the_same_supplier_invoice_cannot_be_posted_twice(client):
    first, _ = upload_and_process(client)
    assert client.post("/api/journal/post", json={"document_id": first}).status_code == 200

    second, _ = upload_and_process(client, "INV-2026-001.pdf")

    response = client.post("/api/journal/post", json={"document_id": second})

    assert response.status_code == 409
    assert "duplicate" in response.json()["detail"].lower()


def test_a_different_supplier_may_reuse_the_invoice_number(client):
    first, _ = upload_and_process(client, "INV-2026-001.pdf")
    assert client.post("/api/journal/post", json={"document_id": first}).status_code == 200

    # Different vendor (GSTIN 27...), same invoice number as the first.
    second, processed = upload_and_process(client, "INV-2026-002.pdf")
    corrected = client.put(
        f"/api/documents/{second}/invoice",
        json=correction_from(processed, invoice_number="INV-2026-001"),
    )
    assert corrected.status_code == 200

    response = client.post("/api/journal/post", json={"document_id": second, "approve_with_warnings": True})

    assert response.status_code == 200, response.text


def test_a_posted_document_is_not_reported_as_its_own_duplicate(client):
    document_id, _ = upload_and_process(client)
    assert client.post("/api/journal/post", json={"document_id": document_id}).status_code == 200

    detail = client.get(f"/api/documents/{document_id}").json()

    duplicate_checks = [c for c in detail["validation_report"]["checks"] if c["check_name"] == "Duplicate Invoice Posting Gate"]
    assert duplicate_checks == []
    assert detail["validation_report"]["has_blocking_failures"] is False
