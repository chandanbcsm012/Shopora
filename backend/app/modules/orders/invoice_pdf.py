"""Renders an order's invoice as a PDF using reportlab, per docs/CONTRACTS.md.
PDFs are generated on demand into an in-memory `io.BytesIO` and never
persisted to disk -- "re-download"/"admin regenerate" just means calling
`generate_invoice_pdf` again, always fresh from current order data.

`order` is expected to expose: `id`, `status`, `total_cents`, `currency`,
`items` (each with `sku_snapshot`, `product_name_snapshot`, `quantity`,
`unit_price_cents`), and optionally `payment_method`/`payment_status`
(transient attributes the caller may attach for display purposes -- see
`orders.service.get_invoice_pdf_bytes`). `shipping_address`/
`billing_address` may be `None` or any object exposing the `Address` field
set (full_name, phone, address_line1, ...).
"""
from __future__ import annotations

import io
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _money(cents: int, currency: str) -> str:
    return f"{currency} {cents / 100:.2f}"


def _status_value(status: Any) -> str:
    return status.value if hasattr(status, "value") else str(status)


def _address_lines(address: Any) -> list[str]:
    if address is None:
        return ["N/A"]

    lines = [address.full_name]
    if getattr(address, "company", None):
        lines.append(address.company)
    lines.append(address.address_line1)
    if getattr(address, "address_line2", None):
        lines.append(address.address_line2)
    city_line = ", ".join(
        part
        for part in (address.city, getattr(address, "state", None), address.postal_code)
        if part
    )
    if city_line:
        lines.append(city_line)
    lines.append(address.country)
    lines.append(f"Phone: {address.phone}")
    return lines


def generate_invoice_pdf(order: Any, invoice: Any, shipping_address: Any, billing_address: Any) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75 * inch, bottomMargin=0.75 * inch)
    styles = getSampleStyleSheet()

    invoice_number = f"INV-{invoice.sequence_number:06d}"

    elements: list[Any] = []
    elements.append(Paragraph("Shopora", styles["Title"]))
    elements.append(Spacer(1, 0.15 * inch))
    elements.append(Paragraph(f"Invoice {invoice_number}", styles["Heading2"]))
    elements.append(Paragraph(f"Invoice date: {invoice.created_at.strftime('%Y-%m-%d %H:%M UTC')}", styles["Normal"]))
    elements.append(Paragraph(f"Order ID: {order.id}", styles["Normal"]))
    elements.append(Paragraph(f"Order status: {_status_value(order.status)}", styles["Normal"]))
    elements.append(Spacer(1, 0.25 * inch))

    address_table = Table(
        [
            [Paragraph("<b>Bill To</b>", styles["Normal"]), Paragraph("<b>Ship To</b>", styles["Normal"])],
            [
                Paragraph("<br/>".join(_address_lines(billing_address)), styles["Normal"]),
                Paragraph("<br/>".join(_address_lines(shipping_address)), styles["Normal"]),
            ],
        ],
        colWidths=[3 * inch, 3 * inch],
    )
    address_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(address_table)
    elements.append(Spacer(1, 0.3 * inch))

    cell_style = styles["Normal"]
    item_rows = [["SKU", "Product", "Qty", "Unit Price", "Line Total"]]
    for item in order.items:
        line_total = item.quantity * item.unit_price_cents
        item_rows.append(
            [
                # Plain strings don't wrap inside a reportlab Table cell and
                # can overflow into the next column (seen with real SKUs
                # like "MOB-APP-APP-100") -- wrapping in a Paragraph, same
                # as the address blocks above, makes the cell actually
                # respect colWidths.
                Paragraph(item.sku_snapshot, cell_style),
                Paragraph(item.product_name_snapshot, cell_style),
                str(item.quantity),
                _money(item.unit_price_cents, order.currency),
                _money(line_total, order.currency),
            ]
        )

    items_table = Table(item_rows, colWidths=[1.3 * inch, 2.1 * inch, 0.6 * inch, 1.1 * inch, 1.1 * inch])
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(items_table)
    elements.append(Spacer(1, 0.25 * inch))

    # INR Currency & GST (foundation scope): when the order carries a
    # (non-null) tax breakdown, render it between the item table and the
    # existing "Order Total / Payment Method / Payment Status" summary
    # block, same row-label/value table style, reusing `_money()` (never a
    # second money-formatting helper / hardcoded currency symbol).
    if getattr(order, "tax_total_cents", None) is not None:
        tax_rows = [
            ["Taxable Amount", _money(order.taxable_amount_cents, order.currency)],
            ["CGST", _money(order.cgst_cents, order.currency)],
            ["SGST", _money(order.sgst_cents, order.currency)],
            ["IGST", _money(order.igst_cents, order.currency)],
            ["Grand Total", _money(order.grand_total_cents, order.currency)],
        ]
        tax_table = Table(tax_rows, colWidths=[4.2 * inch, 2 * inch])
        tax_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ]
            )
        )
        elements.append(tax_table)
        elements.append(Spacer(1, 0.25 * inch))

    payment_method = getattr(order, "payment_method", None) or "N/A"
    payment_status = getattr(order, "payment_status", None) or "N/A"

    summary_rows = [
        ["Order Total", _money(order.total_cents, order.currency)],
        ["Payment Method", str(payment_method)],
        ["Payment Status", str(payment_status)],
    ]
    summary_table = Table(summary_rows, colWidths=[4.2 * inch, 2 * inch])
    summary_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ]
        )
    )
    elements.append(summary_table)

    doc.build(elements)
    return buffer.getvalue()
