"""Report export (stage 9): CSV, Excel and Tally voucher XML.

Every exporter takes the already-computed report data, so the numbers come from
the same deterministic services that render the dashboards. No second source of
truth exists.
"""

import csv
import io
from datetime import date
from decimal import Decimal
from typing import Dict, List, Sequence, Tuple
from xml.sax.saxutils import escape

Table = Tuple[List[str], List[List[str]]]


def _amount(value) -> str:
    return f"{Decimal(str(value)):.2f}"


def _csv_bytes(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def ledger_table(entries: Sequence[Dict]) -> Table:
    headers = [
        "Date", "Invoice", "Transaction Type", "Account Code", "Account Name",
        "Entry Type", "Debit", "Credit", "Description",
    ]
    rows: List[List[str]] = []
    for entry in entries:
        for line in entry["lines"]:
            is_debit = line["entry_type"] == "DEBIT"
            rows.append([
                entry["entry_date"],
                entry["invoice_number"],
                entry["transaction_type"],
                line["account_code"],
                line["account_name"],
                line["entry_type"],
                _amount(line["amount"]) if is_debit else "",
                "" if is_debit else _amount(line["amount"]),
                line.get("description") or entry.get("narration", ""),
            ])
    return headers, rows


def trial_balance_table(report: Dict) -> Table:
    headers = [
        "Account Code", "Account Name", "Category",
        "Total Debits", "Total Credits", "Closing Balance", "Balance Type",
    ]
    rows = [
        [
            row["account_code"], row["account_name"], row["category"],
            _amount(row["total_debits"]), _amount(row["total_credits"]),
            _amount(row["closing_balance"]), row["balance_type"],
        ]
        for row in report["rows"]
    ]
    rows.append([
        "TOTAL", "", "", _amount(report["total_debit_balance"]),
        _amount(report["total_credit_balance"]), "", "",
    ])
    return headers, rows


def profit_and_loss_table(report: Dict) -> Table:
    headers = ["Section", "Code", "Account", "Amount"]
    rows: List[List[str]] = []
    for item in report["revenues"]:
        rows.append(["Revenue", item["code"], item["name"], _amount(item["amount"])])
    for item in report["expenses"]:
        rows.append(["Expense", item["code"], item["name"], _amount(item["amount"])])
    rows.append(["Net Profit", "", "", _amount(report["net_profit"])])
    return headers, rows


def balance_sheet_table(report: Dict) -> Table:
    headers = ["Section", "Code", "Account", "Amount"]
    rows: List[List[str]] = []
    for item in report["assets"]:
        rows.append(["Assets", item["code"], item["name"], _amount(item["amount"])])
    for item in report["liabilities"]:
        rows.append(["Liabilities", item["code"], item["name"], _amount(item["amount"])])
    for item in report["equity"]:
        rows.append(["Equity", item["code"], item["name"], _amount(item["amount"])])
    rows.append(["Retained Earnings", "", "", _amount(report["retained_earnings"])])
    return headers, rows


def to_csv(table: Table) -> bytes:
    return _csv_bytes(*table)


def to_xlsx(table: Table, sheet_name: str = "Report") -> bytes:
    from openpyxl import Workbook

    headers, rows = table
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name[:31]
    sheet.append(list(headers))
    for row in rows:
        sheet.append([float(value) if _is_number(value) else value for value in row])

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _is_number(value: str) -> bool:
    try:
        Decimal(str(value))
    except Exception:
        return False
    return True


def journal_to_tally_xml(entries: Sequence[Dict], company_name: str) -> str:
    """Tally Prime import envelope for purchase vouchers.

    Tally's sign convention: debit lines are marked positive and carry a
    negative amount; credit lines carry a positive amount.
    """
    vouchers: List[str] = []
    for entry in entries:
        lines: List[str] = []
        for line in entry["lines"]:
            is_debit = line["entry_type"] == "DEBIT"
            amount = Decimal(str(line["amount"]))
            signed = -amount if is_debit else amount
            lines.append(
                "      <ALLLEDGERENTRIES.LIST>\n"
                f"       <LEDGERNAME>{escape(line['account_name'])}</LEDGERNAME>\n"
                f"       <ISDEEMEDPOSITIVE>{'Yes' if is_debit else 'No'}</ISDEEMEDPOSITIVE>\n"
                f"       <AMOUNT>{signed:.2f}</AMOUNT>\n"
                "      </ALLLEDGERENTRIES.LIST>"
            )

        entry_date = entry["entry_date"].replace("-", "")
        vouchers.append(
            "    <VOUCHER VCHTYPE=\"Purchase\" ACTION=\"Create\">\n"
            f"     <DATE>{entry_date}</DATE>\n"
            f"     <NARRATION>{escape(entry.get('narration') or '')}</NARRATION>\n"
            "     <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>\n"
            f"     <VOUCHERNUMBER>{escape(entry['invoice_number'])}</VOUCHERNUMBER>\n"
            + "\n".join(lines) + "\n"
            "    </VOUCHER>"
        )

    body = "\n".join(vouchers)
    return (
        "<ENVELOPE>\n"
        " <HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>\n"
        " <BODY><IMPORTDATA>\n"
        "  <REQUESTDESC>\n"
        "   <REPORTNAME>Vouchers</REPORTNAME>\n"
        "   <STATICVARIABLES>\n"
        f"    <SVCURRENTCOMPANY>{escape(company_name)}</SVCURRENTCOMPANY>\n"
        "   </STATICVARIABLES>\n"
        "  </REQUESTDESC>\n"
        "  <REQUESTDATA>\n"
        "   <TALLYMESSAGE xmlns:UDF=\"TallyUDF\">\n"
        f"{body}\n"
        "   </TALLYMESSAGE>\n"
        "  </REQUESTDATA>\n"
        " </IMPORTDATA></BODY>\n"
        "</ENVELOPE>\n"
    )
