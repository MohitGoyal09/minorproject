import os
import json
import shutil
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, FastAPI, Depends, UploadFile, File, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.db.session import engine, Base, get_db
from app.auth.security import authenticate, create_access_token, get_current_user
from app.models.accounting import (
    Tenant,
    Account,
    Document,
    Invoice,
    LineItem,
    InvoiceTax,
    JournalEntry,
    JournalLine,
    AuditLog,
    DocumentStatus,
    EntryPostingStatus,
    User,
)
from app.db.seed_accounts import seed_standard_accounts
from app.schemas.accounting import (
    DocumentValidationReport,
    ProposedJournalEntry,
    ProposedJournalLine,
    EntryType,
    ValidationCheckResult,
    ValidationCheckStatus,
)
from app.schemas.invoice import (
    ExtractedInvoice,
    ExtractionConfidence,
    InvoiceCorrectionRequest,
    InvoiceLineItem as InvoiceLineItemSchema,
    TaxBreakdown as TaxBreakdownSchema,
)
from app.engine.ingestion import DocumentIngestionService
from app.engine.interpreter import AccountingInterpreter, EmptyInvoiceError
from app.engine.invariants import run_comprehensive_validation
from app.engine.ledger import post_journal_entry, generate_trial_balance
from app.engine.statements import FinancialStatementService
from app.engine import export as export_service
from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class PostJournalRequest(BaseModel):
    """The client names the document; the server owns the journal.

    Journal lines are never accepted from the client: they are rebuilt from the
    stored invoice, so a fabricated or edited entry cannot reach the ledger.
    """

    document_id: str
    approve_with_warnings: bool = False

# Initialize database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI-Powered Accounting Automation System",
    description="End-to-End Multimodal Invoice Intelligence & Verified Double-Entry Accounting",
    version="1.0.0",
)

# Enable CORS for Frontend React Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

public_router = APIRouter(prefix="/api")

# One guard for every business route. New endpoints are protected automatically.
protected_router = APIRouter(prefix="/api", dependencies=[Depends(get_current_user)])

UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_or_create_default_tenant(db: Session) -> Tenant:
    tenant = db.query(Tenant).first()
    if not tenant:
        tenant = Tenant(
            id=str(uuid.uuid4()),
            name="Modern Tech Solutions Pvt Ltd",
            gstin="07BBBBB1111B1Z2",
            currency="INR"
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        seed_standard_accounts(db, tenant.id)
    return tenant


# ---------------------------------------------------------------------------
# Shared invoice pipeline helpers
# ---------------------------------------------------------------------------

def _extracted_invoice_from_db(inv: Invoice) -> ExtractedInvoice:
    """Rebuild the domain model from stored fields, so corrections survive reads."""
    return ExtractedInvoice(
        invoice_number=inv.invoice_number,
        invoice_date=inv.invoice_date,
        due_date=inv.due_date,
        vendor_name=inv.vendor_name,
        vendor_gstin=inv.vendor_gstin,
        vendor_address=inv.vendor_address,
        buyer_name=inv.buyer_name,
        buyer_gstin=inv.buyer_gstin,
        place_of_supply=inv.place_of_supply,
        place_of_supply_state_code=inv.place_of_supply_state_code,
        payment_terms=inv.payment_terms,
        subtotal=inv.subtotal,
        total_tax=inv.total_tax,
        total_discount=inv.total_discount,
        round_off=inv.round_off,
        grand_total=inv.grand_total,
        currency=inv.currency or "INR",
        is_settled_or_paid=bool(inv.is_settled_or_paid),
        taxes=[
            TaxBreakdownSchema(
                tax_type=tax.tax_type,
                rate_percent=tax.rate_percent,
                taxable_amount=tax.taxable_amount,
                tax_amount=tax.tax_amount,
            )
            for tax in inv.taxes
        ],
        line_items=[
            InvoiceLineItemSchema(
                item_id=item.item_id,
                description=item.description,
                hsn_sac=item.hsn_sac,
                unit=item.unit,
                quantity=item.quantity,
                unit_price=item.unit_price,
                discount_amount=item.discount_amount,
                tax_rate_percent=item.tax_rate_percent,
                tax_amount=item.tax_amount,
                total_amount=item.total_amount,
            )
            for item in inv.line_items
        ],
        confidence=ExtractionConfidence(inv.confidence or "HIGH"),
        validation_flags=[flag for flag in (inv.validation_flags or "").split("; ") if flag],
    )


def _persist_invoice(db: Session, doc: Document, tenant: Tenant, extracted: ExtractedInvoice) -> Invoice:
    """Replace the stored invoice and its line items with the given extraction."""
    existing = db.query(Invoice).filter(Invoice.document_id == doc.id).first()
    if existing:
        db.delete(existing)
        db.flush()

    db_invoice = Invoice(
        document_id=doc.id,
        tenant_id=tenant.id,
        invoice_number=extracted.invoice_number,
        invoice_date=extracted.invoice_date,
        due_date=extracted.due_date,
        vendor_name=extracted.vendor_name,
        vendor_gstin=extracted.vendor_gstin,
        vendor_address=extracted.vendor_address,
        buyer_name=extracted.buyer_name,
        buyer_gstin=extracted.buyer_gstin,
        place_of_supply=extracted.place_of_supply,
        place_of_supply_state_code=extracted.place_of_supply_state_code,
        payment_terms=extracted.payment_terms,
        subtotal=extracted.subtotal,
        total_tax=extracted.total_tax,
        total_discount=extracted.total_discount,
        round_off=extracted.round_off,
        grand_total=extracted.grand_total,
        currency=extracted.currency or "INR",
        is_settled_or_paid=bool(extracted.is_settled_or_paid),
        confidence=extracted.confidence.value,
        validation_flags="; ".join(extracted.validation_flags) if extracted.validation_flags else None,
    )
    db.add(db_invoice)
    db.flush()

    for item in extracted.line_items:
        db.add(LineItem(
            invoice_id=db_invoice.id,
            item_id=item.item_id,
            description=item.description,
            hsn_sac=item.hsn_sac,
            unit=item.unit,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_amount=item.discount_amount,
            tax_rate_percent=item.tax_rate_percent,
            tax_amount=item.tax_amount,
            total_amount=item.total_amount,
        ))

    for tax in extracted.taxes:
        db.add(InvoiceTax(
            invoice_id=db_invoice.id,
            tax_type=tax.tax_type,
            rate_percent=tax.rate_percent,
            taxable_amount=tax.taxable_amount,
            tax_amount=tax.tax_amount,
        ))

    db.flush()
    return db_invoice


def _is_duplicate(db: Session, tenant: Tenant, extracted: ExtractedInvoice, document_id: str) -> bool:
    from app.engine.ledger import find_duplicate_entry

    return find_duplicate_entry(
        db, tenant.id, extracted.invoice_number, extracted, exclude_document_id=document_id
    ) is not None


def _proposal_and_validation(db: Session, tenant: Tenant, extracted: ExtractedInvoice, document_id: str):
    try:
        proposal = AccountingInterpreter.interpret_invoice(
            invoice=extracted,
            document_id=document_id,
            creditor_account_code="2010",
        )
    except EmptyInvoiceError as exc:
        empty_report = DocumentValidationReport(
            is_valid=False,
            can_post_automatically=False,
            has_blocking_failures=True,
            checks=[ValidationCheckResult(
                check_name="Invoice Content",
                status=ValidationCheckStatus.FAIL,
                expected_value="At least one line with a positive taxable value",
                actual_value="No taxable value",
                explanation=str(exc),
                requires_human_review=True,
            )],
            summary_message="No taxable value. Add or correct line items before posting.",
        )
        return None, empty_report
    active_codes = {
        account.code
        for account in db.query(Account).filter(Account.tenant_id == tenant.id, Account.is_active == True).all()
    }
    report = run_comprehensive_validation(
        invoice=extracted,
        entry=proposal,
        active_account_codes=active_codes,
        is_duplicate=_is_duplicate(db, tenant, extracted, document_id),
    )
    proposal.validation_report = report
    return proposal, report


def _apply_document_status(doc: Document, report) -> None:
    doc.status = (
        DocumentStatus.REVIEW_REQUIRED
        if (report.has_blocking_failures or not report.can_post_automatically)
        else DocumentStatus.PROCESSED
    )


def _serialize_invoice(inv: Invoice) -> dict:
    return {
        "invoice_number": inv.invoice_number,
        "invoice_date": inv.invoice_date.isoformat(),
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
        "vendor_name": inv.vendor_name,
        "vendor_gstin": inv.vendor_gstin,
        "buyer_name": inv.buyer_name,
        "buyer_gstin": inv.buyer_gstin,
        "vendor_address": inv.vendor_address,
        "place_of_supply": inv.place_of_supply,
        "place_of_supply_state_code": inv.place_of_supply_state_code,
        "payment_terms": inv.payment_terms,
        "currency": inv.currency or "INR",
        "is_settled_or_paid": bool(inv.is_settled_or_paid),
        "confidence": inv.confidence or "HIGH",
        "subtotal": float(inv.subtotal),
        "total_tax": float(inv.total_tax),
        "total_discount": float(inv.total_discount),
        "round_off": float(inv.round_off),
        "grand_total": float(inv.grand_total),
        "validation_flags": inv.validation_flags.split("; ") if inv.validation_flags else [],
        "taxes": [
            {
                "tax_type": tax.tax_type,
                "rate_percent": float(tax.rate_percent),
                "taxable_amount": float(tax.taxable_amount),
                "tax_amount": float(tax.tax_amount),
            }
            for tax in inv.taxes
        ],
        "line_items": [
            {
                "item_id": item.item_id,
                "description": item.description,
                "hsn_sac": item.hsn_sac,
                "unit": item.unit,
                "quantity": float(item.quantity),
                "unit_price": float(item.unit_price),
                "discount_amount": float(item.discount_amount),
                "tax_rate_percent": float(item.tax_rate_percent),
                "tax_amount": float(item.tax_amount),
                "total_amount": float(item.total_amount),
            }
            for item in inv.line_items
        ],
    }


def _ledger_entries(db: Session, tenant_id: str) -> List[dict]:
    """Posted journal entries, ready for JSON, CSV and Tally export."""
    entries = (
        db.query(JournalEntry)
        .filter(JournalEntry.tenant_id == tenant_id, JournalEntry.status == EntryPostingStatus.POSTED)
        .order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
        .all()
    )
    return [
        {
            "id": entry.id,
            "invoice_number": entry.invoice_number,
            "entry_date": entry.entry_date.isoformat(),
            "transaction_type": entry.transaction_type.value,
            "narration": entry.narration,
            "lines": [
                {
                    "account_code": line.account.code,
                    "account_name": line.account.name,
                    "entry_type": line.entry_type.value,
                    "amount": float(line.amount),
                    "description": line.description,
                }
                for line in entry.lines
            ],
        }
        for entry in entries
    ]


@public_router.get("/health")
def health_check():
    return {"status": "ok", "system": "AI-Powered Accounting Automation Engine", "version": "1.0.0"}


@protected_router.get("/tenant")
def get_tenant_info(db: Session = Depends(get_db)):
    tenant = get_or_create_default_tenant(db)
    return {
        "id": tenant.id,
        "name": tenant.name,
        "gstin": tenant.gstin,
        "currency": tenant.currency
    }


@protected_router.get("/accounts")
def list_accounts(db: Session = Depends(get_db)):
    tenant = get_or_create_default_tenant(db)
    accounts = db.query(Account).filter(Account.tenant_id == tenant.id, Account.is_active == True).order_by(Account.code).all()
    return [
        {
            "id": a.id,
            "code": a.code,
            "name": a.name,
            "category": a.category.value,
            "normal_balance": a.normal_balance.value
        }
        for a in accounts
    ]


@protected_router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    tenant = get_or_create_default_tenant(db)
    file_id = str(uuid.uuid4())
    safe_filename = f"{file_id}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    doc = Document(
        id=file_id,
        tenant_id=tenant.id,
        filename=file.filename,
        file_path=file_path,
        mime_type=file.content_type or "application/pdf",
        status=DocumentStatus.UPLOADED
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return {"document_id": doc.id, "filename": doc.filename, "status": doc.status}


@protected_router.get("/documents")
def list_documents(db: Session = Depends(get_db)):
    tenant = get_or_create_default_tenant(db)
    docs = db.query(Document).filter(Document.tenant_id == tenant.id).order_by(Document.uploaded_at.desc()).all()
    
    results = []
    for d in docs:
        inv = d.invoice
        results.append({
            "id": d.id,
            "filename": d.filename,
            "status": d.status,
            "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
            "invoice_number": inv.invoice_number if inv else None,
            "vendor_name": inv.vendor_name if inv else None,
            "grand_total": float(inv.grand_total) if inv else None
        })
    return results


@protected_router.post("/documents/{doc_id}/process")
def process_document(doc_id: str, db: Session = Depends(get_db)):
    tenant = get_or_create_default_tenant(db)
    doc = db.query(Document).filter(Document.id == doc_id, Document.tenant_id == tenant.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status == DocumentStatus.POSTED or db.query(JournalEntry).filter(
        JournalEntry.document_id == doc.id,
        JournalEntry.status == EntryPostingStatus.POSTED,
    ).first():
        raise HTTPException(
            status_code=409,
            detail="This document is posted. Posted entries are immutable; raise a reversing entry instead.",
        )

    # 1. Run Ingestion, Table Layout Correction & Heuristics
    try:
        extracted = DocumentIngestionService.process_pdf_invoice(doc.file_path)
    except Exception as e:
        doc.status = DocumentStatus.REVIEW_REQUIRED
        db.commit()
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")

    # 2. Persist Extracted Invoice
    _persist_invoice(db, doc, tenant, extracted)

    # 3. Interpret Transaction, Generate Journal Proposal & Validate
    try:
        proposal, validation_report = _proposal_and_validation(db, tenant, extracted, doc.id)
    except Exception as exc:
        # A document with no taxable value cannot produce a journal entry.
        doc.status = DocumentStatus.REVIEW_REQUIRED
        db.commit()
        raise HTTPException(
            status_code=422,
            detail=f"Invoice has no postable value (no lines or zero totals): {exc}",
        )

    _apply_document_status(doc, validation_report)
    db.commit()

    if proposal is None:
        raise HTTPException(status_code=422, detail=validation_report.summary_message)

    return {
        "status": doc.status,
        "extracted_invoice": extracted.model_dump(),
        "proposed_journal_entry": proposal.model_dump(),
        "validation_report": validation_report.model_dump()
    }


@protected_router.get("/documents/{doc_id}")
def get_document_details(doc_id: str, db: Session = Depends(get_db)):
    tenant = get_or_create_default_tenant(db)
    doc = db.query(Document).filter(Document.id == doc_id, Document.tenant_id == tenant.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    inv = doc.invoice
    inv_data = None
    proposal_data = None
    validation_data = None

    if inv:
        inv_data = _serialize_invoice(inv)

        # Rebuild the proposal from the stored (possibly corrected) invoice.
        extracted_obj = _extracted_invoice_from_db(inv)
        proposal, validation_report = _proposal_and_validation(db, tenant, extracted_obj, doc.id)
        proposal_data = proposal.model_dump() if proposal is not None else None
        validation_data = validation_report.model_dump()

        # The stored status must agree with the report returned right now.
        if doc.status not in (DocumentStatus.POSTED, DocumentStatus.REJECTED):
            _apply_document_status(doc, validation_report)
            db.commit()

    return {
        "id": doc.id,
        "filename": doc.filename,
        "status": doc.status,
        "invoice": inv_data,
        "proposal": proposal_data,
        "validation_report": validation_data
    }


@protected_router.put("/documents/{doc_id}/invoice")
def correct_invoice(doc_id: str, correction: InvoiceCorrectionRequest, db: Session = Depends(get_db)):
    """Apply a human correction from the review interface and re-validate."""
    tenant = get_or_create_default_tenant(db)
    doc = db.query(Document).filter(Document.id == doc_id, Document.tenant_id == tenant.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    already_posted = (
        doc.status == DocumentStatus.POSTED
        or db.query(JournalEntry)
        .filter(JournalEntry.document_id == doc.id, JournalEntry.status == EntryPostingStatus.POSTED)
        .first()
        is not None
    )
    if already_posted:
        raise HTTPException(
            status_code=409,
            detail="This invoice is already posted to the General Ledger. Posted entries are immutable; raise a reversing entry instead.",
        )

    extracted = ExtractedInvoice(
        **correction.model_dump(),
        confidence=ExtractionConfidence.HIGH,
        validation_flags=["Fields corrected by a human reviewer."],
    )

    db_invoice = _persist_invoice(db, doc, tenant, extracted)
    try:
        proposal, validation_report = _proposal_and_validation(db, tenant, extracted, doc.id)
    except Exception as exc:
        db.commit()
        raise HTTPException(
            status_code=422,
            detail=f"These values cannot produce a journal entry: {exc}",
        )
    _apply_document_status(doc, validation_report)

    if proposal is None:
        db.commit()
        raise HTTPException(status_code=422, detail=validation_report.summary_message)

    db.add(AuditLog(
        tenant_id=tenant.id,
        entity_name="Invoice",
        entity_id=doc.id,
        action="EDIT",
        performed_by="USER_REVIEWER",
        details=json.dumps({
            "invoice_number": extracted.invoice_number,
            "vendor_name": extracted.vendor_name,
            "grand_total": str(extracted.grand_total),
            "line_items": len(extracted.line_items),
        }),
    ))
    db.commit()

    return {
        "id": doc.id,
        "filename": doc.filename,
        "status": doc.status,
        "invoice": _serialize_invoice(db_invoice),
        "proposal": proposal.model_dump(),
        "validation_report": validation_report.model_dump()
    }


@protected_router.post("/journal/post")
def post_entry(
    request: PostJournalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Post the server-rebuilt proposal for a stored document.

    The ledger is written from the invoice in the database, never from lines the
    client sends back, so a fabricated entry cannot be posted.
    """
    tenant = get_or_create_default_tenant(db)
    doc = (
        db.query(Document)
        .filter(Document.id == request.document_id, Document.tenant_id == tenant.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status == DocumentStatus.POSTED:
        raise HTTPException(status_code=409, detail="This document is already posted; posted entries are immutable.")
    if not doc.invoice:
        raise HTTPException(status_code=409, detail="This document has no stored invoice. Process it before posting.")

    extracted = _extracted_invoice_from_db(doc.invoice)
    try:
        proposal, report = _proposal_and_validation(db, tenant, extracted, doc.id)
    except Exception as exc:
        doc.status = DocumentStatus.REVIEW_REQUIRED
        db.commit()
        raise HTTPException(status_code=422, detail=f"Cannot build a journal entry for this document: {exc}")

    if proposal is None:
        raise HTTPException(status_code=409, detail=report.summary_message)

    if report.has_blocking_failures:
        failing = [c.check_name for c in report.checks if c.status.value == "FAIL"]
        raise HTTPException(
            status_code=409,
            detail=f"Posting blocked by validation: {', '.join(failing)}",
        )
    if not report.can_post_automatically and not request.approve_with_warnings:
        raise HTTPException(
            status_code=409,
            detail="This entry needs reviewer approval. Resend with approve_with_warnings=true after checking it.",
        )

    try:
        posted = post_journal_entry(
            db,
            tenant.id,
            proposal,
            posted_by=current_user.email,
            allow_review_override=request.approve_with_warnings,
            invoice=extracted,
        )
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    doc.status = DocumentStatus.POSTED
    db.commit()

    return {
        "status": "SUCCESS",
        "journal_entry_id": posted.id,
        "invoice_number": posted.invoice_number,
    }


@protected_router.get("/reports/ledger")
def get_general_ledger(db: Session = Depends(get_db)):
    tenant = get_or_create_default_tenant(db)
    return _ledger_entries(db, tenant.id)


@protected_router.get("/reports/trial-balance")
def get_trial_balance_report(db: Session = Depends(get_db)):
    tenant = get_or_create_default_tenant(db)
    tb = generate_trial_balance(db, tenant.id, as_of_date=date.today())
    return {
        "as_of_date": tb.as_of_date.isoformat(),
        "is_balanced": tb.is_balanced,
        "total_debit_balance": float(tb.total_debit_balance),
        "total_credit_balance": float(tb.total_credit_balance),
        "rows": [
            {
                "account_code": r.account_code,
                "account_name": r.account_name,
                "category": r.category,
                "total_debits": float(r.total_debits),
                "total_credits": float(r.total_credits),
                "closing_balance": float(r.closing_balance),
                "balance_type": r.balance_type
            }
            for r in tb.rows
        ]
    }


@protected_router.get("/reports/profit-and-loss")
def get_profit_and_loss(db: Session = Depends(get_db)):
    tenant = get_or_create_default_tenant(db)
    pnl = FinancialStatementService.generate_profit_and_loss(db, tenant.id, as_of_date=date.today())
    # Format Decimals as floats for JSON serialization
    pnl["total_revenue"] = float(pnl["total_revenue"])
    pnl["total_expenses"] = float(pnl["total_expenses"])
    pnl["net_profit"] = float(pnl["net_profit"])
    for item in pnl["revenues"]:
        item["amount"] = float(item["amount"])
    for item in pnl["expenses"]:
        item["amount"] = float(item["amount"])
    return pnl


@protected_router.get("/reports/balance-sheet")
def get_balance_sheet(db: Session = Depends(get_db)):
    tenant = get_or_create_default_tenant(db)
    bs = FinancialStatementService.generate_balance_sheet(db, tenant.id, as_of_date=date.today())
    bs["total_assets"] = float(bs["total_assets"])
    bs["total_liabilities"] = float(bs["total_liabilities"])
    bs["total_equity"] = float(bs["total_equity"])
    bs["retained_earnings"] = float(bs["retained_earnings"])
    bs["total_liabilities_and_equity"] = float(bs["total_liabilities_and_equity"])
    for item in bs["assets"]:
        item["amount"] = float(item["amount"])
    for item in bs["liabilities"]:
        item["amount"] = float(item["amount"])
    for item in bs["equity"]:
        item["amount"] = float(item["amount"])
    return bs


@protected_router.get("/reports/audit-logs")
def get_audit_logs(db: Session = Depends(get_db)):
    tenant = get_or_create_default_tenant(db)
    logs = db.query(AuditLog).filter(AuditLog.tenant_id == tenant.id).order_by(AuditLog.timestamp.desc()).all()
    return [
        {
            "id": l.id,
            "entity_name": l.entity_name,
            "entity_id": l.entity_id,
            "action": l.action,
            "performed_by": l.performed_by,
            "details": l.details,
            "timestamp": l.timestamp.isoformat()
        }
        for l in logs
    ]


# ---------------------------------------------------------------------------
# Report export (methodology stage 9)
# ---------------------------------------------------------------------------

EXPORTABLE_REPORTS = ("ledger", "trial-balance", "profit-and-loss", "balance-sheet")


@protected_router.get("/reports/export/{report_name}")
def export_report(report_name: str, format: str = "csv", db: Session = Depends(get_db)):
    """Download a report as CSV / Excel, or the journal as Tally import XML."""
    tenant = get_or_create_default_tenant(db)

    if report_name == "tally":
        xml = export_service.journal_to_tally_xml(_ledger_entries(db, tenant.id), tenant.name)
        return Response(
            content=xml,
            media_type="application/xml",
            headers={
                "Content-Disposition": f'attachment; filename="tally-vouchers-{date.today().isoformat()}.xml"'
            },
        )

    if report_name not in EXPORTABLE_REPORTS:
        raise HTTPException(status_code=404, detail=f"Unknown report '{report_name}'")
    if format not in ("csv", "xlsx"):
        raise HTTPException(status_code=400, detail="Supported formats are 'csv' and 'xlsx'")

    if report_name == "ledger":
        table = export_service.ledger_table(_ledger_entries(db, tenant.id))
    elif report_name == "trial-balance":
        table = export_service.trial_balance_table(get_trial_balance_report(db))
    elif report_name == "profit-and-loss":
        table = export_service.profit_and_loss_table(get_profit_and_loss(db))
    else:
        table = export_service.balance_sheet_table(get_balance_sheet(db))

    filename = f"{report_name}-{date.today().isoformat()}"
    if format == "csv":
        return Response(
            content=export_service.to_csv(table),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
        )

    return Response(
        content=export_service.to_xlsx(table, report_name),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
    )


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

@public_router.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Exchange credentials for a bearer token."""
    user = authenticate(db, payload.email, payload.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    tenant = get_or_create_default_tenant(db)
    db.add(AuditLog(
        tenant_id=tenant.id,
        entity_name="User",
        entity_id=user.id,
        action="LOGIN",
        performed_by=user.email,
        details=json.dumps({"email": user.email, "role": user.role}),
    ))
    db.commit()

    return {
        "access_token": create_access_token(user.id, user.email),
        "token_type": "bearer",
        "expires_in_minutes": int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480")),
        "user": {"id": user.id, "email": user.email, "role": user.role},
    }


@protected_router.get("/auth/me")
def current_user_profile(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email, "role": current_user.role}


app.include_router(public_router)
app.include_router(protected_router)
