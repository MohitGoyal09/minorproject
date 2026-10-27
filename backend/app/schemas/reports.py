from decimal import Decimal
from datetime import date
from typing import List, Dict
from pydantic import BaseModel, Field, ConfigDict


class LedgerAccountBalance(BaseModel):
    """Summarized ledger balance for an account."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    account_code: str
    account_name: str
    category: str
    total_debits: Decimal = Decimal("0.00")
    total_credits: Decimal = Decimal("0.00")
    closing_balance: Decimal = Decimal("0.00")
    balance_type: str = Field(..., description="DEBIT or CREDIT")


class TrialBalanceReport(BaseModel):
    """Trial Balance statement for a given period."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    as_of_date: date
    rows: List[LedgerAccountBalance]
    total_debit_balance: Decimal
    total_credit_balance: Decimal
    is_balanced: bool

    @classmethod
    def from_rows(cls, as_of_date: date, rows: List[LedgerAccountBalance]):
        total_dr = sum((r.closing_balance for r in rows if r.balance_type == "DEBIT"), start=Decimal("0.00")).quantize(Decimal("0.01"))
        total_cr = sum((r.closing_balance for r in rows if r.balance_type == "CREDIT"), start=Decimal("0.00")).quantize(Decimal("0.01"))
        return cls(
            as_of_date=as_of_date,
            rows=rows,
            total_debit_balance=total_dr,
            total_credit_balance=total_cr,
            is_balanced=(total_dr == total_cr)
        )
