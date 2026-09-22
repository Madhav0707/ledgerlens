from decimal import Decimal

from services.invoice_service import extract_invoice_draft


def test_csv_invoice_extraction_is_a_reviewable_draft():
    data = b"product,quantity,unit_cost,total\nPhone,2,9500,19000\n"
    draft = extract_invoice_draft("supplier_invoice.csv", data)

    assert draft.lines[0].product_name == "Phone"
    assert draft.lines[0].quantity == 2
    assert draft.lines[0].unit_cost == Decimal("9500.00")
    assert draft.total == Decimal("19000.00")


def test_invalid_invoice_rows_are_flagged():
    draft = extract_invoice_draft("supplier_invoice.csv", b"product,quantity,unit_cost\nPhone,,bad\n")

    assert draft.lines == []
    assert draft.warnings