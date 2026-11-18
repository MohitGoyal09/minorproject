import os
import json
from decimal import Decimal
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INVOICES_DIR = os.path.join(DATA_DIR, "sample_invoices")
GROUND_TRUTH_DIR = os.path.join(DATA_DIR, "ground_truth")

os.makedirs(INVOICES_DIR, exist_ok=True)
os.makedirs(GROUND_TRUTH_DIR, exist_ok=True)


def build_pdf_invoice(filepath: str, data: dict):
    """Generates a clean PDF invoice using ReportLab."""
    doc = SimpleDocTemplate(filepath, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    styles = getSampleStyleSheet()

    # Title & Vendor Header
    title_style = ParagraphStyle(name='TitleStyle', fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor('#1E3A8A'))
    normal_bold = ParagraphStyle(name='Bold', fontName='Helvetica-Bold', fontSize=10, leading=14)
    normal = ParagraphStyle(name='Normal', fontName='Helvetica', fontSize=10, leading=14)

    story.append(Paragraph(data["vendor_name"], title_style))
    story.append(Paragraph(f"GSTIN: {data.get('vendor_gstin', 'N/A')}", normal))
    story.append(Paragraph(f"Address: {data.get('vendor_address', 'New Delhi, India')}", normal))
    story.append(Spacer(1, 15))

    # Meta Info Table (Invoice #, Date, Buyer)
    meta_data = [
        [Paragraph(f"<b>Invoice No:</b> {data['invoice_number']}", normal), Paragraph(f"<b>Billed To:</b> {data['buyer_name']}", normal)],
        [Paragraph(f"<b>Invoice Date:</b> {data['invoice_date']}", normal), Paragraph(f"<b>Buyer GSTIN:</b> {data.get('buyer_gstin', 'N/A')}", normal)],
        [Paragraph(f"<b>Due Date:</b> {data.get('due_date', 'N/A')}", normal), Paragraph(f"<b>Place of Supply:</b> {data.get('place_of_supply', 'Delhi (07)')}", normal)],
    ]
    meta_table = Table(meta_data, colWidths=[270, 270])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 15))

    # Line Items Table
    table_data = [["Item Description", "HSN/SAC", "Qty", "Unit Price", "Discount", "Total (₹)"]]
    for item in data["line_items"]:
        table_data.append([
            item["description"],
            item.get("hsn_sac", "-"),
            str(item["quantity"]),
            f"{float(item['unit_price']):,.2f}",
            f"{float(item.get('discount_amount', 0)):,.2f}",
            f"{float(item['total_amount']):,.2f}"
        ])

    items_table = Table(table_data, colWidths=[200, 70, 50, 75, 65, 80])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 15))

    # Summary Totals Table
    totals_data = [
        ["Subtotal:", f"INR {float(data['subtotal']):,.2f}"],
        ["Total Tax (GST):", f"INR {float(data['total_tax']):,.2f}"],
        ["Total Discount:", f"INR {float(data.get('total_discount', 0)):,.2f}"],
        ["Grand Total:", f"INR {float(data['grand_total']):,.2f}"],
    ]
    totals_table = Table(totals_data, colWidths=[420, 120])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 11),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#1E3A8A')),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#0F172A')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(totals_table)

    doc.build(story)


def generate_seed_data():
    invoices = [
        # 1. Golden Case: Office Furniture (Asset Purchase)
        {
            "invoice_number": "INV-2026-001",
            "invoice_date": "2026-10-15",
            "due_date": "2026-11-15",
            "vendor_name": "ABC Furniture Mart",
            "vendor_gstin": "07AAAAA0000A1Z5",
            "vendor_address": "Kirti Nagar Industrial Area, New Delhi",
            "buyer_name": "Modern Tech Solutions Pvt Ltd",
            "buyer_gstin": "07BBBBB1111B1Z2",
            "subtotal": 50000.00,
            "total_discount": 0.00,
            "total_tax": 9000.00,
            "grand_total": 59000.00,
            "line_items": [
                {"description": "Executive Wooden Desk", "hsn_sac": "9403", "quantity": 2, "unit_price": 15000.00, "discount_amount": 0.00, "tax_rate_percent": 18.0, "total_amount": 30000.00},
                {"description": "Ergonomic Mesh Chair", "hsn_sac": "9403", "quantity": 4, "unit_price": 5000.00, "discount_amount": 0.00, "tax_rate_percent": 18.0, "total_amount": 20000.00}
            ],
            "taxes": [
                {"tax_type": "CGST", "rate_percent": 9.0, "taxable_amount": 50000.00, "tax_amount": 4500.00},
                {"tax_type": "SGST", "rate_percent": 9.0, "taxable_amount": 50000.00, "tax_amount": 4500.00}
            ],
            "accounting_ground_truth": {
                "transaction_type": "ASSET_ACQUISITION_CREDIT",
                "policy_applied": "Capitalize equipment/furniture with unit eligible cost > INR 10,000; expense low-value chairs <= 10,000",
                "journal_lines": [
                    {"account_code": "1050", "account_name": "Office Furniture & Fixtures", "entry_type": "DEBIT", "amount": 30000.00},
                    {"account_code": "5010", "account_name": "Office Supplies & Stationery", "entry_type": "DEBIT", "amount": 20000.00},
                    {"account_code": "1081", "account_name": "Input CGST A/c", "entry_type": "DEBIT", "amount": 4500.00},
                    {"account_code": "1082", "account_name": "Input SGST A/c", "entry_type": "DEBIT", "amount": 4500.00},
                    {"account_code": "2010", "account_name": "ABC Furniture Mart (Creditor)", "entry_type": "CREDIT", "amount": 59000.00}
                ]
            }
        },
        # 2. Cloud Hosting Subscription (Expense)
        {
            "invoice_number": "INV-2026-002",
            "invoice_date": "2026-10-18",
            "due_date": "2026-10-28",
            "vendor_name": "CloudGrid Technologies India",
            "vendor_gstin": "27CCCCC2222C1Z8",
            "vendor_address": "BKC, Mumbai, Maharashtra",
            "buyer_name": "Modern Tech Solutions Pvt Ltd",
            "buyer_gstin": "07BBBBB1111B1Z2",
            "subtotal": 12000.00,
            "total_discount": 0.00,
            "total_tax": 2160.00,
            "grand_total": 14160.00,
            "line_items": [
                {"description": "Dedicated Cloud Server (Monthly)", "hsn_sac": "998315", "quantity": 1, "unit_price": 12000.00, "discount_amount": 0.00, "tax_rate_percent": 18.0, "total_amount": 12000.00}
            ],
            "taxes": [
                {"tax_type": "IGST", "rate_percent": 18.0, "taxable_amount": 12000.00, "tax_amount": 2160.00}
            ],
            "accounting_ground_truth": {
                "transaction_type": "EXPENSE_OFFICE_CREDIT",
                "policy_applied": "Inter-state supply: IGST applied. Monthly software/cloud classified as operating expense.",
                "journal_lines": [
                    {"account_code": "5020", "account_name": "Server & Hosting Expense A/c", "entry_type": "DEBIT", "amount": 12000.00},
                    {"account_code": "1083", "account_name": "Input IGST A/c", "entry_type": "DEBIT", "amount": 2160.00},
                    {"account_code": "2010", "account_name": "CloudGrid Technologies (Creditor)", "entry_type": "CREDIT", "amount": 14160.00}
                ]
            }
        },
        # 3. Office Stationery with Discount (Expense)
        {
            "invoice_number": "INV-2026-003",
            "invoice_date": "2026-10-20",
            "due_date": "2026-10-20",
            "vendor_name": "Delhi Paper & Print Hub",
            "vendor_gstin": "07DDDDD3333D1Z9",
            "vendor_address": "Connaught Place, New Delhi",
            "buyer_name": "Modern Tech Solutions Pvt Ltd",
            "buyer_gstin": "07BBBBB1111B1Z2",
            "subtotal": 4000.00,
            "total_discount": 500.00,
            "total_tax": 420.00,
            "grand_total": 3920.00,
            "line_items": [
                {"description": "A4 Printing Paper (Cartons)", "hsn_sac": "4802", "quantity": 10, "unit_price": 400.00, "discount_amount": 500.00, "tax_rate_percent": 12.0, "total_amount": 3500.00}
            ],
            "taxes": [
                {"tax_type": "CGST", "rate_percent": 6.0, "taxable_amount": 3500.00, "tax_amount": 210.00},
                {"tax_type": "SGST", "rate_percent": 6.0, "taxable_amount": 3500.00, "tax_amount": 210.00}
            ],
            "accounting_ground_truth": {
                "transaction_type": "EXPENSE_OFFICE_CREDIT",
                "policy_applied": "Consumables expensed immediately. Discount reduces taxable value.",
                "journal_lines": [
                    {"account_code": "5010", "account_name": "Office Supplies Expense A/c", "entry_type": "DEBIT", "amount": 3500.00},
                    {"account_code": "1081", "account_name": "Input CGST A/c", "entry_type": "DEBIT", "amount": 210.00},
                    {"account_code": "1082", "account_name": "Input SGST A/c", "entry_type": "DEBIT", "amount": 210.00},
                    {"account_code": "2010", "account_name": "Delhi Paper Hub (Creditor)", "entry_type": "CREDIT", "amount": 3920.00}
                ]
            }
        },
        # 4. Multi-Item Invoice with Capitalization Threshold & Intra-state Mixed Slabs (Northstar Office Systems)
        {
            "invoice_number": "NOS/26-27/0418",
            "invoice_date": "2026-10-18",
            "due_date": "2026-11-17",
            "vendor_name": "NORTHSTAR OFFICE SYSTEMS",
            "vendor_gstin": "09AABCN4821K1Z6",
            "vendor_address": "Sector 62, Noida, Uttar Pradesh",
            "buyer_name": "Modern Tech Solutions Private Limited",
            "buyer_gstin": "09AAFCM7314R1Z2",
            "place_of_supply": "Uttar Pradesh (09)",
            "subtotal": 44750.00,
            "total_discount": 2800.00,
            "total_tax": 7680.00,
            "grand_total": 52430.00,
            "line_items": [
                {"description": "Executive ergonomic chair", "hsn_sac": "9401", "quantity": 3, "unit_price": 6200.00, "discount_amount": 1860.00, "tax_rate_percent": 18.0, "total_amount": 16740.00},
                {"description": "USB-C docking station, 12-in-1", "hsn_sac": "8471", "quantity": 2, "unit_price": 8500.00, "discount_amount": 850.00, "tax_rate_percent": 18.0, "total_amount": 16150.00},
                {"description": "A4 copier paper, 5-ream carton", "hsn_sac": "4802", "quantity": 5, "unit_price": 1250.00, "discount_amount": 0.00, "tax_rate_percent": 12.0, "total_amount": 6250.00},
                {"description": "Braided USB-C cable, 2 m", "hsn_sac": "8544", "quantity": 10, "unit_price": 450.00, "discount_amount": 90.00, "tax_rate_percent": 18.0, "total_amount": 4410.00},
                {"description": "Freight & handling", "hsn_sac": "9965", "quantity": 1, "unit_price": 1200.00, "discount_amount": 0.00, "tax_rate_percent": 18.0, "total_amount": 1200.00}
            ],
            "taxes": [
                {"tax_type": "CGST", "rate_percent": 9.0, "taxable_amount": 38500.00, "tax_amount": 3465.00},
                {"tax_type": "SGST", "rate_percent": 9.0, "taxable_amount": 38500.00, "tax_amount": 3465.00},
                {"tax_type": "CGST", "rate_percent": 6.0, "taxable_amount": 6250.00, "tax_amount": 375.00},
                {"tax_type": "SGST", "rate_percent": 6.0, "taxable_amount": 6250.00, "tax_amount": 375.00}
            ],
            "accounting_ground_truth": {
                "transaction_type": "EXPENSE_OFFICE_CREDIT",
                "policy_applied": "Chairs unit cost 5,580 <= 10k expensed under 5010; Docking station unit cost 8,075 <= 10k expensed under 5060; Cables under 5060; Freight under 5050; Intra-state UP-UP CGST+SGST.",
                "journal_lines": [
                    {"account_code": "5010", "account_name": "Office Supplies & Stationery", "entry_type": "DEBIT", "amount": 22990.00},
                    {"account_code": "5060", "account_name": "Computer Accessories & Peripherals Expense", "entry_type": "DEBIT", "amount": 20560.00},
                    {"account_code": "5050", "account_name": "Freight, Shipping & Cartage Expense", "entry_type": "DEBIT", "amount": 1200.00},
                    {"account_code": "1081", "account_name": "Input CGST A/c", "entry_type": "DEBIT", "amount": 3840.00},
                    {"account_code": "1082", "account_name": "Input SGST A/c", "entry_type": "DEBIT", "amount": 3840.00},
                    {"account_code": "2010", "account_name": "Accounts Payable (Creditors)", "entry_type": "CREDIT", "amount": 52430.00}
                ]
            }
        }
    ]

    for inv in invoices:
        clean_name = inv['invoice_number'].replace('/', '-')
        pdf_path = os.path.join(INVOICES_DIR, f"{clean_name}.pdf")
        json_path = os.path.join(GROUND_TRUTH_DIR, f"{clean_name}.json")

        # Build PDF
        build_pdf_invoice(pdf_path, inv)
        print(f"Generated PDF: {pdf_path}")

        # Save Ground Truth JSON
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(inv, f, indent=2)
        print(f"Generated Ground Truth: {json_path}")


if __name__ == "__main__":
    generate_seed_data()
