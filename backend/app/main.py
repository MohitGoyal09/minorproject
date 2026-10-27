import os
import shutil
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.db.session import engine, Base, get_db
from app.models.accounting import (
    Tenant,
    Account,
    Document,
    Invoice,
    LineItem,
    JournalEntry,
    JournalLine,
    AuditLog,
    DocumentStatus,
    EntryPostingStatus,
)
from app.db.seed_accounts import seed_standard_accounts
from app.schemas.accounting import ProposedJournalEntry, ProposedJournalLine, EntryType
from app.engine.ingestion import DocumentIngestionService
from app.engine.interpreter import AccountingInterpreter
from app.engine.invariants import run_comprehensive_validation
from app.engine.ledger import post_journal_entry, generate_trial_balance
from app.engine.statements import FinancialStatementService

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

UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "sample_invoices"))
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


@app.get("/api/health")
def health_check():
    return {"status": "ok", "system": "AI-Powered Accounting Automation Engine", "version": "1.0.0"}


@app.get("/api/tenant")
def get_tenant_info(db: Session = Depends(get_db)):
    tenant = get_or_create_default_tenant(db)
    return {
        "id": tenant.id,
        "name": tenant.name,
        "gstin": tenant.gstin,
        "currency": tenant.currency
    }


@app.get("/api/accounts")
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


@app.post("/api/documents/upload")
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


@app.get("/api/documents")
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


@app.post("/api/documents/{doc_id}/process")
def process_document(doc_id: str, db: Session = Depends(get_db)):
    tenant = get_or_create_default_tenant(db)
    doc = db.query(Document).filter(Document.id == doc_id, Document.tenant_id == tenant.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # 1. Run Ingestion, Table Layout Correction & Heuristics
    try:
        extracted = DocumentIngestionService.process_pdf_invoice(doc.file_path)
    except Exception as e:
        doc.status = DocumentStatus.REVIEW_REQUIRED
        db.commit()
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")

    # 2. Persist Extracted Invoice
    existing_inv = db.query(Invoice).filter(Invoice.document_id == doc.id).first()
    if existing_inv:
        db.delete(existing_inv)
        db.flush()

    db_invoice = Invoice(
        document_id=doc.id,
        tenant_id=tenant.id,
        invoice_number=extracted.invoice_number,
        invoice_date=extracted.invoice_date,
        due_date=extracted.due_date,
        vendor_name=extracted.vendor_name,
        vendor_gstin=extracted.vendor_gstin,
        buyer_name=extracted.buyer_name,
        buyer_gstin=extracted.buyer_gstin,
        subtotal=extracted.subtotal,
        total_tax=extracted.total_tax,
        total_discount=extracted.total_discount,
        grand_total=extracted.grand_total,
        validation_flags="; ".join(extracted.validation_flags) if extracted.validation_flags else None
    )
    db.add(db_invoice)
    db.flush()

    for item in extracted.line_items:
        db_item = LineItem(
            invoice_id=db_invoice.id,
            description=item.description,
            hsn_sac=item.hsn_sac,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_amount=item.discount_amount,
            total_amount=item.total_amount
        )
        db.add(db_item)

    # 3. Interpret Transaction and Generate Journal Proposal
    proposal = AccountingInterpreter.interpret_invoice(
        invoice=extracted,
        document_id=doc.id,
        creditor_account_code="2010"
    )

    # 4. Run Multi-Stage Deterministic Validation Suite
    active_codes = {acc.code for acc in db.query(Account).filter(Account.tenant_id == tenant.id, Account.is_active == True).all()}
    validation_report = run_comprehensive_validation(
        invoice=extracted,
        entry=proposal,
        active_account_codes=active_codes
    )
    proposal.validation_report = validation_report

    doc.status = DocumentStatus.REVIEW_REQUIRED if (validation_report.has_blocking_failures or not validation_report.can_post_automatically) else DocumentStatus.PROCESSED
    db.commit()

    return {
        "status": doc.status,
        "extracted_invoice": extracted.model_dump(),
        "proposed_journal_entry": proposal.model_dump(),
        "validation_report": validation_report.model_dump()
    }


@app.get("/api/documents/{doc_id}")
def get_document_details(doc_id: str, db: Session = Depends(get_db)):
    tenant = get_or_create_default_tenant(db)
    doc = db.query(Document).filter(Document.id == doc_id, Document.tenant_id == tenant.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    inv = doc.invoice
    inv_data = None
    proposal_data = None

    if inv:
        line_items_data = [
            {
                "description": it.description,
                "hsn_sac": it.hsn_sac,
                "quantity": float(it.quantity),
                "unit_price": float(it.unit_price),
                "discount_amount": float(it.discount_amount),
                "total_amount": float(it.total_amount)
            }
            for it in inv.line_items
        ]
        inv_data = {
            "invoice_number": inv.invoice_number,
            "invoice_date": inv.invoice_date.isoformat(),
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
            "vendor_name": inv.vendor_name,
            "vendor_gstin": inv.vendor_gstin,
            "buyer_name": inv.buyer_name,
            "buyer_gstin": inv.buyer_gstin,
            "subtotal": float(inv.subtotal),
            "total_tax": float(inv.total_tax),
            "total_discount": float(inv.total_discount),
            "grand_total": float(inv.grand_total),
            "validation_flags": inv.validation_flags.split("; ") if inv.validation_flags else [],
            "line_items": line_items_data
        }

        # Re-generate proposal and validation report on the fly for review
        extracted_obj = DocumentIngestionService.process_pdf_invoice(doc.file_path)
        proposal = AccountingInterpreter.interpret_invoice(extracted_obj, document_id=doc.id)
        active_codes = {acc.code for acc in db.query(Account).filter(Account.tenant_id == tenant.id, Account.is_active == True).all()}
        validation_report = run_comprehensive_validation(
            invoice=extracted_obj,
            entry=proposal,
            active_account_codes=active_codes
        )
        proposal.validation_report = validation_report
        proposal_data = proposal.model_dump()
        validation_data = validation_report.model_dump()

    return {
        "id": doc.id,
        "filename": doc.filename,
        "status": doc.status,
        "invoice": inv_data,
        "proposal": proposal_data,
        "validation_report": validation_data if inv else None
    }


@app.post("/api/journal/post")
def post_entry(proposal: ProposedJournalEntry, db: Session = Depends(get_db)):
    tenant = get_or_create_default_tenant(db)
    try:
        posted = post_journal_entry(db, tenant.id, proposal, posted_by="USER_REVIEWER", allow_review_override=True)
        
        # Update linked document status
        if proposal.source_document_id:
            doc = db.query(Document).filter(Document.id == proposal.source_document_id).first()
            if doc:
                doc.status = DocumentStatus.POSTED
                db.commit()

        return {"status": "SUCCESS", "journal_entry_id": posted.id, "invoice_number": posted.invoice_number}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/reports/ledger")
def get_general_ledger(db: Session = Depends(get_db)):
    tenant = get_or_create_default_tenant(db)
    entries = (
        db.query(JournalEntry)
        .filter(JournalEntry.tenant_id == tenant.id, JournalEntry.status == EntryPostingStatus.POSTED)
        .order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
        .all()
    )

    results = []
    for e in entries:
        lines = [
            {
                "account_code": l.account.code,
                "account_name": l.account.name,
                "entry_type": l.entry_type.value,
                "amount": float(l.amount),
                "description": l.description
            }
            for l in e.lines
        ]
        results.append({
            "id": e.id,
            "invoice_number": e.invoice_number,
            "entry_date": e.entry_date.isoformat(),
            "transaction_type": e.transaction_type.value,
            "narration": e.narration,
            "lines": lines
        })
    return results


@app.get("/api/reports/trial-balance")
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


@app.get("/api/reports/profit-and-loss")
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


@app.get("/api/reports/balance-sheet")
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


@app.get("/api/reports/audit-logs")
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
