from sqlalchemy.orm import Session
from app.models.accounting import Tenant, Account
from app.schemas.accounting import AccountCategory, NormalBalance


STANDARD_CHART_OF_ACCOUNTS = [
    # ASSETS (1000 - 1999)
    {"code": "1010", "name": "Cash in Hand", "category": AccountCategory.ASSET, "normal_balance": NormalBalance.DEBIT},
    {"code": "1020", "name": "Current Bank Account", "category": AccountCategory.ASSET, "normal_balance": NormalBalance.DEBIT},
    {"code": "1050", "name": "Office Furniture & Fixtures", "category": AccountCategory.ASSET, "normal_balance": NormalBalance.DEBIT},
    {"code": "1060", "name": "IT & Computer Equipment", "category": AccountCategory.ASSET, "normal_balance": NormalBalance.DEBIT},
    {"code": "1081", "name": "Input CGST A/c", "category": AccountCategory.ASSET, "normal_balance": NormalBalance.DEBIT},
    {"code": "1082", "name": "Input SGST A/c", "category": AccountCategory.ASSET, "normal_balance": NormalBalance.DEBIT},
    {"code": "1083", "name": "Input IGST A/c", "category": AccountCategory.ASSET, "normal_balance": NormalBalance.DEBIT},

    # LIABILITIES (2000 - 2999)
    {"code": "2010", "name": "Accounts Payable / Creditors", "category": AccountCategory.LIABILITY, "normal_balance": NormalBalance.CREDIT},
    {"code": "2081", "name": "Output CGST A/c", "category": AccountCategory.LIABILITY, "normal_balance": NormalBalance.CREDIT},
    {"code": "2082", "name": "Output SGST A/c", "category": AccountCategory.LIABILITY, "normal_balance": NormalBalance.CREDIT},
    {"code": "2083", "name": "Output IGST A/c", "category": AccountCategory.LIABILITY, "normal_balance": NormalBalance.CREDIT},

    # EQUITY (3000 - 3999)
    {"code": "3010", "name": "Owner Capital", "category": AccountCategory.EQUITY, "normal_balance": NormalBalance.CREDIT},

    # REVENUE (4000 - 4999)
    {"code": "4010", "name": "Sales & Service Revenue", "category": AccountCategory.REVENUE, "normal_balance": NormalBalance.CREDIT},

    # EXPENSES (5000 - 5999)
    {"code": "5010", "name": "Office Supplies & Stationery", "category": AccountCategory.EXPENSE, "normal_balance": NormalBalance.DEBIT},
    {"code": "5020", "name": "Server, Cloud & Software Expense", "category": AccountCategory.EXPENSE, "normal_balance": NormalBalance.DEBIT},
    {"code": "5030", "name": "Office Rent Expense", "category": AccountCategory.EXPENSE, "normal_balance": NormalBalance.DEBIT},
    {"code": "5040", "name": "Electricity & Utility Expense", "category": AccountCategory.EXPENSE, "normal_balance": NormalBalance.DEBIT},
]


def seed_standard_accounts(db: Session, tenant_id: str):
    """Populates standard Chart of Accounts for a newly created tenant."""
    existing_codes = {acc.code for acc in db.query(Account).filter(Account.tenant_id == tenant_id).all()}

    accounts_to_create = []
    for acc_data in STANDARD_CHART_OF_ACCOUNTS:
        if acc_data["code"] not in existing_codes:
            account = Account(
                tenant_id=tenant_id,
                code=acc_data["code"],
                name=acc_data["name"],
                category=acc_data["category"],
                normal_balance=acc_data["normal_balance"],
                is_active=True
            )
            accounts_to_create.append(account)

    if accounts_to_create:
        db.add_all(accounts_to_create)
        db.commit()

    return len(accounts_to_create)
