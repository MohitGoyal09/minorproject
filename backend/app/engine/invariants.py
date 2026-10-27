from decimal import Decimal
from typing import List, Set, Tuple
from app.schemas.accounting import ProposedJournalEntry, EntryType
from app.schemas.invoice import ExtractedInvoice, InvoiceLineItem


class InvariantViolation(Exception):
    """Raised when a non-negotiable accounting or mathematical rule is broken."""
    pass


def validate_double_entry_invariants(entry: ProposedJournalEntry) -> Tuple[bool, List[str]]:
    """
    Validates core financial invariants for a double-entry journal proposal.
    Returns (is_valid, list_of_errors).
    """
    errors: List[str] = []

    # 1. At least 2 lines
    if len(entry.lines) < 2:
        errors.append("Journal entry must have at least 2 lines (at least one Debit and one Credit).")

    # 2. Must have at least one debit and at least one credit
    has_debit = any(l.entry_type == EntryType.DEBIT for l in entry.lines)
    has_credit = any(l.entry_type == EntryType.CREDIT for l in entry.lines)
    if not has_debit or not has_credit:
        errors.append("Journal entry must contain both a Debit line and a Credit line.")

    # 3. All amounts must be strictly positive
    for idx, line in enumerate(entry.lines):
        if line.amount <= Decimal("0.00"):
            errors.append(f"Line {idx+1} ({line.account_name}) amount must be strictly greater than 0.")

    # 4. Total Debits must equal Total Credits exactly (Zero tolerance for drift)
    total_debits = entry.total_debits
    total_credits = entry.total_credits
    if total_debits != total_credits:
        errors.append(
            f"Double-entry imbalance: Total Debits ({total_debits}) != Total Credits ({total_credits}). Difference: {abs(total_debits - total_credits)}"
        )

    return (len(errors) == 0, errors)


def validate_chart_of_accounts(entry: ProposedJournalEntry, active_account_codes: Set[str]) -> Tuple[bool, List[str]]:
    """
    Validates that every referenced account exists and is active in the company's Chart of Accounts.
    """
    errors: List[str] = []
    for line in entry.lines:
        if line.account_code not in active_account_codes:
            errors.append(
                f"Account '{line.account_name}' with code '{line.account_code}' does not exist or is inactive in Chart of Accounts."
            )
    return (len(errors) == 0, errors)


def validate_invoice_arithmetic(invoice: ExtractedInvoice, tolerance: Decimal = Decimal("0.05")) -> Tuple[bool, List[str]]:
    """
    Validates invoice math consistency according to Rana et al. (2025) heuristic checks:
    - Line item arithmetic: (Qty * Unit Price) - Discount == Line Total
    - Sum of line items == Subtotal
    - Subtotal + Total Tax - Total Discount == Grand Total
    """
    warnings: List[str] = []

    # 1. Check each line item
    sum_calculated_lines = Decimal("0.00")
    for idx, item in enumerate(invoice.line_items):
        expected_line = (item.quantity * item.unit_price) - item.discount_amount
        # Note: some suppliers present line totals including tax, some excluding
        diff = abs(expected_line - item.total_amount)
        if diff > tolerance:
            warnings.append(
                f"Line item {idx+1} ('{item.description}'): Math mismatch. Qty({item.quantity}) * Rate({item.unit_price}) - Disc({item.discount_amount}) = {expected_line}, but extracted total is {item.total_amount}."
            )
        sum_calculated_lines += item.total_amount

    # 2. Check line items sum vs subtotal (if line items exist)
    if invoice.line_items:
        diff_subtotal = abs(sum_calculated_lines - invoice.subtotal)
        if diff_subtotal > tolerance:
            warnings.append(
                f"Subtotal discrepancy: Sum of line items ({sum_calculated_lines}) does not match extracted subtotal ({invoice.subtotal})."
            )

    # 3. Check Grand Total reconciliation: Subtotal + Total Tax - Total Discount == Grand Total
    expected_grand_total = invoice.subtotal + invoice.total_tax - invoice.total_discount
    diff_grand_total = abs(expected_grand_total - invoice.grand_total)
    if diff_grand_total > tolerance:
        warnings.append(
            f"Grand total discrepancy: Subtotal ({invoice.subtotal}) + Tax ({invoice.total_tax}) - Discount ({invoice.total_discount}) = {expected_grand_total}, but extracted grand total is {invoice.grand_total}."
        )

    return (len(warnings) == 0, warnings)
