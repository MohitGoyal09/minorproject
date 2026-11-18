"""Regression tests for summary-total and tax-component extraction (F-13/F-18)."""

from decimal import Decimal

from app.engine.table_corrector import TableLayoutCorrector


def totals(rows):
    return TableLayoutCorrector.extract_summary_totals(rows)


def test_tax_components_are_summed_not_overwritten():
    rows = [["CGST 9%", "90.00"], ["SGST 9%", "90.00"]]

    result = totals(rows)

    assert result["total_tax"] == Decimal("180.00")


def test_an_explicit_total_tax_row_beats_the_component_sum():
    rows = [["CGST 9%", "90.00"], ["SGST 9%", "90.00"], ["Total Tax (GST)", "180.00"]]

    result = totals(rows)

    assert result["total_tax"] == Decimal("180.00")


def test_net_payable_maps_to_the_grand_total():
    assert totals([["Net Payable:", "1,180.00"]])["grand_total"] == Decimal("1180.00")


def test_total_amount_maps_to_the_grand_total():
    assert totals([["Total Amount:", "1,180.00"]])["grand_total"] == Decimal("1180.00")


def test_grand_total_wins_over_the_gst_label_in_the_same_row():
    result = totals([["Grand Total (incl. GST):", "1,180.00"]])

    assert result["grand_total"] == Decimal("1180.00")
    assert "total_tax" not in result


def test_round_off_is_recognised():
    assert totals([["Round Off:", "0.05"]])["round_off"] == Decimal("0.05")


def test_a_percentage_is_not_mistaken_for_an_amount():
    assert TableLayoutCorrector.extract_monetary_amount("CGST 9% 4,500") == Decimal("4500.00")


def test_one_and_three_decimal_amounts_parse():
    assert TableLayoutCorrector.extract_monetary_amount("1,234.5") == Decimal("1234.50")
    assert TableLayoutCorrector.extract_monetary_amount("1,234.567") == Decimal("1234.57")


def test_tax_components_are_returned_as_structured_rows():
    rows = [["CGST 9%", "90.00"], ["SGST 9%", "90.00"], ["Total Tax (GST)", "180.00"]]

    components = TableLayoutCorrector.extract_tax_components(rows)

    assert [(c["tax_type"], c["tax_amount"]) for c in components] == [
        ("CGST", Decimal("90.00")),
        ("SGST", Decimal("90.00")),
    ]
    assert all(c["rate_percent"] == Decimal("9") for c in components)
