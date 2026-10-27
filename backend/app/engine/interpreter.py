from decimal import Decimal
from datetime import date
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session

from app.schemas.invoice import ExtractedInvoice
from app.schemas.accounting import (
    ProposedJournalEntry,
    ProposedJournalLine,
    EntryType,
    TransactionType,
    AccountCategory,
)
from app.models.accounting import Account, Tenant


class AccountingPolicy:
    """Configurable tenant accounting policy rules."""
    CAPITALIZATION_THRESHOLD = Decimal("10000.00")  # Purchases > 10k of durable goods capitalized
    ELIGIBLE_FOR_ITC = True  # Input Tax Credit eligible by default


class AccountingInterpreter:
    """
    Semantic interpretation layer that bridges extracted invoice data into
    strict double-entry bookkeeping proposals under Indian GST rules.
    """

    # Keyword rules for account mapping
    KEYWORD_MAPPINGS = [
        # Fixed Assets
        (["furniture", "desk", "chair", "table", "cabinet"], "1050", "Office Furniture & Fixtures", AccountCategory.ASSET),
        (["server", "laptop", "computer", "macbook", "monitor", "printer"], "1060", "IT & Computer Equipment", AccountCategory.ASSET),
        
        # Operating Expenses
        (["cloud", "hosting", "aws", "azure", "saas", "software", "license", "api"], "5020", "Server, Cloud & Software Expense", AccountCategory.EXPENSE),
        (["paper", "pen", "stationery", "print", "cartridge", "notebook"], "5010", "Office Supplies & Stationery", AccountCategory.EXPENSE),
        (["rent", "lease", "premise"], "5030", "Office Rent Expense", AccountCategory.EXPENSE),
        (["electric", "power", "utility", "water", "internet", "broadband"], "5040", "Electricity & Utility Expense", AccountCategory.EXPENSE),
    ]

    @classmethod
    def match_account_for_item(cls, description: str, amount: Decimal) -> Tuple[str, str, AccountCategory]:
        """Matches line item description to COA, applying capitalization thresholds."""
        desc_lower = description.lower()
        
        for keywords, code, name, category in cls.KEYWORD_MAPPINGS:
            if any(kw in desc_lower for kw in keywords):
                # Apply capitalization policy: if durable good is below threshold, expense it
                if category == AccountCategory.ASSET and amount < AccountingPolicy.CAPITALIZATION_THRESHOLD:
                    return ("5010", "Office Supplies & Stationery", AccountCategory.EXPENSE)
                return (code, name, category)

        # Default fallback
        if amount >= AccountingPolicy.CAPITALIZATION_THRESHOLD:
            return ("1060", "IT & Computer Equipment", AccountCategory.ASSET)
        return ("5010", "Office Supplies & Stationery", AccountCategory.EXPENSE)

    @classmethod
    def interpret_invoice(
        cls,
        invoice: ExtractedInvoice,
        document_id: str = "doc_simulated",
        creditor_account_code: str = "2010"
    ) -> ProposedJournalEntry:
        """
        Interprets an ExtractedInvoice and constructs a balanced ProposedJournalEntry.
        """
        lines: List[ProposedJournalLine] = []
        applied_rules: List[str] = []
        review_reasons: List[str] = []
        requires_review = False

        # 1. Group Line Items by mapped account
        account_totals: Dict[Tuple[str, str], Decimal] = {}
        for item in invoice.line_items:
            acc_code, acc_name, category = cls.match_account_for_item(item.description, item.total_amount)
            key = (acc_code, acc_name)
            account_totals[key] = account_totals.get(key, Decimal("0.00")) + item.total_amount

            if category == AccountCategory.ASSET:
                applied_rules.append(f"Capitalized item '{item.description}' under Fixed Assets (Threshold > ₹{AccountingPolicy.CAPITALIZATION_THRESHOLD})")
            else:
                applied_rules.append(f"Expensed item '{item.description}' as Operating Expense")

        # Fallback if no line items were extracted: use subtotal on general supplies
        if not account_totals:
            acc_code, acc_name, _ = cls.match_account_for_item(invoice.vendor_name, invoice.subtotal)
            account_totals[(acc_code, acc_name)] = invoice.subtotal

        # Create Debit lines for goods/services
        for (code, name), amt in account_totals.items():
            lines.append(
                ProposedJournalLine(
                    account_code=code,
                    account_name=name,
                    entry_type=EntryType.DEBIT,
                    amount=amt,
                    description=f"Base cost from invoice {invoice.invoice_number}"
                )
            )

        # 2. Determine GST Treatment (Input Tax Credit)
        has_igst = False
        if invoice.vendor_gstin and invoice.buyer_gstin:
            vendor_state = invoice.vendor_gstin[:2]
            buyer_state = invoice.buyer_gstin[:2]
            if vendor_state != buyer_state:
                has_igst = True

        if invoice.total_tax > Decimal("0.00"):
            if has_igst:
                applied_rules.append("Inter-state supply detected: IGST Input Tax Credit applied")
                lines.append(
                    ProposedJournalLine(
                        account_code="1083",
                        account_name="Input IGST A/c",
                        entry_type=EntryType.DEBIT,
                        amount=invoice.total_tax,
                        description="Input IGST on inter-state purchase"
                    )
                )
            else:
                applied_rules.append("Intra-state supply detected: CGST & SGST Input Tax Credit applied equally")
                half_tax = (invoice.total_tax / Decimal("2.00")).quantize(Decimal("0.01"))
                lines.append(
                    ProposedJournalLine(
                        account_code="1081",
                        account_name="Input CGST A/c",
                        entry_type=EntryType.DEBIT,
                        amount=half_tax,
                        description="Input CGST (50% of GST)"
                    )
                )
                lines.append(
                    ProposedJournalLine(
                        account_code="1082",
                        account_name="Input SGST A/c",
                        entry_type=EntryType.DEBIT,
                        amount=invoice.total_tax - half_tax,
                        description="Input SGST (50% of GST)"
                    )
                )

        # 3. Credit Supplier (Accounts Payable)
        lines.append(
            ProposedJournalLine(
                account_code=creditor_account_code,
                account_name=f"Accounts Payable - {invoice.vendor_name}",
                entry_type=EntryType.CREDIT,
                amount=invoice.grand_total,
                description=f"Amount payable to {invoice.vendor_name} for invoice {invoice.invoice_number}"
            )
        )

        # 4. Check for Warnings or Ambiguity
        if invoice.validation_flags:
            requires_review = True
            review_reasons.extend(invoice.validation_flags)

        total_deb = sum((l.amount for l in lines if l.entry_type == EntryType.DEBIT), start=Decimal("0.00"))
        if total_deb != invoice.grand_total:
            requires_review = True
            review_reasons.append(f"Calculated debits ({total_deb}) do not equal credit payable ({invoice.grand_total})")

        # Determine transaction type enum
        is_asset = any(l.account_code.startswith("105") or l.account_code.startswith("106") for l in lines)
        tx_type = TransactionType.ASSET_ACQUISITION_CREDIT if is_asset else TransactionType.EXPENSE_OFFICE_CREDIT

        narration = f"Being purchase from {invoice.vendor_name} vide invoice #{invoice.invoice_number} dated {invoice.invoice_date}"

        return ProposedJournalEntry(
            source_document_id=document_id,
            invoice_number=invoice.invoice_number,
            entry_date=invoice.invoice_date,
            transaction_type=tx_type,
            narration=narration,
            lines=lines,
            reasoning="Automatically interpreted based on Chart of Accounts and GST state matching.",
            applied_rules=applied_rules,
            requires_human_review=requires_review,
            review_reasons=review_reasons
        )
