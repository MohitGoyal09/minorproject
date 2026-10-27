from decimal import Decimal
from datetime import date
from typing import Dict, List, Any
from sqlalchemy.orm import Session

from app.models.accounting import (
    Tenant,
    Account,
    JournalEntry,
    JournalLine,
    EntryPostingStatus,
)
from app.schemas.accounting import AccountCategory, NormalBalance, EntryType
from app.engine.ledger import generate_trial_balance


class FinancialStatementService:
    """
    Generates verified Profit & Loss Statements and Balance Sheets directly
    from authoritative double-entry journal postings.
    """

    @classmethod
    def generate_profit_and_loss(cls, db: Session, tenant_id: str, as_of_date: date) -> Dict[str, Any]:
        """
        Calculates Net Profit / Loss = Total Revenue - Total Expenses.
        """
        tb = generate_trial_balance(db, tenant_id, as_of_date)

        revenue_items = []
        expense_items = []
        total_revenue = Decimal("0.00")
        total_expenses = Decimal("0.00")

        for row in tb.rows:
            if row.category == "REVENUE":
                revenue_items.append({"code": row.account_code, "name": row.account_name, "amount": row.closing_balance})
                total_revenue += row.closing_balance
            elif row.category == "EXPENSE":
                expense_items.append({"code": row.account_code, "name": row.account_name, "amount": row.closing_balance})
                total_expenses += row.closing_balance

        net_profit = (total_revenue - total_expenses).quantize(Decimal("0.01"))

        return {
            "as_of_date": as_of_date.isoformat(),
            "revenues": revenue_items,
            "total_revenue": total_revenue,
            "expenses": expense_items,
            "total_expenses": total_expenses,
            "net_profit": net_profit,
            "is_profitable": net_profit >= Decimal("0.00")
        }

    @classmethod
    def generate_balance_sheet(cls, db: Session, tenant_id: str, as_of_date: date) -> Dict[str, Any]:
        """
        Calculates Assets = Liabilities + Equity + Net Profit.
        """
        tb = generate_trial_balance(db, tenant_id, as_of_date)
        pnl = cls.generate_profit_and_loss(db, tenant_id, as_of_date)
        net_profit = pnl["net_profit"]

        assets = []
        liabilities = []
        equity = []

        total_assets = Decimal("0.00")
        total_liabilities = Decimal("0.00")
        total_equity = Decimal("0.00")

        for row in tb.rows:
            if row.category == "ASSET":
                assets.append({"code": row.account_code, "name": row.account_name, "amount": row.closing_balance})
                total_assets += row.closing_balance
            elif row.category == "LIABILITY":
                liabilities.append({"code": row.account_code, "name": row.account_name, "amount": row.closing_balance})
                total_liabilities += row.closing_balance
            elif row.category == "EQUITY":
                equity.append({"code": row.account_code, "name": row.account_name, "amount": row.closing_balance})
                total_equity += row.closing_balance

        # Add Net Profit to Equity section
        retained_earnings = net_profit
        total_equity_with_earnings = (total_equity + retained_earnings).quantize(Decimal("0.01"))
        total_liabilities_and_equity = (total_liabilities + total_equity_with_earnings).quantize(Decimal("0.01"))

        is_balanced = total_assets == total_liabilities_and_equity

        return {
            "as_of_date": as_of_date.isoformat(),
            "assets": assets,
            "total_assets": total_assets,
            "liabilities": liabilities,
            "total_liabilities": total_liabilities,
            "equity": equity,
            "retained_earnings": retained_earnings,
            "total_equity": total_equity_with_earnings,
            "total_liabilities_and_equity": total_liabilities_and_equity,
            "is_balanced": is_balanced
        }
