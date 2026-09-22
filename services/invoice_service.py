import csv
import io
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass
class InvoiceLineDraft:
    product_name: str
    quantity: int
    unit_cost: Decimal


@dataclass
class InvoiceDraft:
    supplier_name: str | None
    invoice_number: str | None
    invoice_date: str | None
    lines: list[InvoiceLineDraft]
    total: Decimal | None
    warnings: list[str]


def _money(value: str) -> Decimal | None:
    try:
        return Decimal(re.sub(r"[^0-9.-]", "", value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def extract_invoice_draft(filename: str, data: bytes) -> InvoiceDraft:
    if not filename.lower().endswith((".csv", ".pdf")):
        raise ValueError("Invoice extraction supports PDF and CSV files only.")
    if not data:
        raise ValueError("The invoice file is empty.")
    if filename.lower().endswith(".csv"):
        try:
            rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
        except UnicodeDecodeError as error:
            raise ValueError("Invoice CSV must be UTF-8 encoded.") from error
        lines = []
        warnings = []
        for row in rows:
            name = (row.get("product") or row.get("product_name") or "").strip()
            quantity_text = row.get("quantity", "")
            cost_text = row.get("unit_cost") or row.get("cost") or ""
            try:
                quantity = int(quantity_text)
            except ValueError:
                quantity = 0
            cost = _money(cost_text)
            if not name or quantity <= 0 or cost is None:
                warnings.append("One invoice row has missing or invalid product, quantity, or cost.")
                continue
            lines.append(InvoiceLineDraft(name, quantity, cost))
        total = _money(rows[0].get("total", "")) if rows else None
        if not lines:
            warnings.append("No valid invoice lines were extracted.")
        return InvoiceDraft(None, None, None, lines, total, warnings)

    from pypdf import PdfReader
    try:
        text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
    except Exception as error:
        raise ValueError("The invoice PDF could not be read.") from error
    supplier = re.search(r"supplier\s*[:#-]\s*(.+)", text, re.IGNORECASE)
    invoice_number = re.search(r"invoice\s*(?:number|no\.?)\s*[:#-]\s*([\w/-]+)", text, re.IGNORECASE)
    total_match = re.search(r"total\s*[:#-]\s*([₹$\d,.-]+)", text, re.IGNORECASE)
    warnings = ["PDF extraction is best-effort. Review every field before creating a purchase."]
    if not text.strip():
        warnings.append("No extractable text was found in the PDF.")
    return InvoiceDraft(
        supplier.group(1).strip() if supplier else None,
        invoice_number.group(1).strip() if invoice_number else None,
        None,
        [],
        _money(total_match.group(1)) if total_match else None,
        warnings,
    )