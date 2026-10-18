"""Invoice PDFs, made with WeasyPrint from an HTML template.

WeasyPrint needs the Pango library (installed in the Docker image; on a Mac
``brew install pango``). It is imported only when a PDF is made, so the rest
of the app works without it.
"""

import base64
import io
import mimetypes

import barcode
import segno.helpers
from barcode.writer import SVGWriter
from django.template.loader import render_to_string
from django.utils import translation

from apps.register.models import Organisation

from .reference import rf_reference


class PDFUnavailable(RuntimeError):
    """WeasyPrint or its system libraries are missing."""


def _data_uri(content, mime):
    return f"data:{mime};base64,{base64.b64encode(content).decode()}"


def barcode_svg(digits):
    """The virtual barcode as Code 128 (the banks' standard), as a data URI."""
    if not digits:
        return ""

    out = io.BytesIO()
    barcode.get("code128", digits, writer=SVGWriter()).write(
        out,
        options={"write_text": False, "module_height": 13, "module_width": 0.25, "quiet_zone": 6},
    )
    return _data_uri(out.getvalue(), "image/svg+xml")


def payment_qr(invoice):
    """A SEPA payment QR code (EPC069-12), which Finnish bank apps read."""
    iban = invoice.seller.get("iban", "").replace(" ", "")
    if not (invoice.reference and iban and invoice.total > 0):
        return ""
    reference = invoice.reference
    if not reference.upper().startswith("RF"):
        reference = rf_reference(reference)  # the EPC code carries RF references only
    qr = segno.helpers.make_epc_qr(
        name=invoice.seller.get("name", "")[:70],
        iban=iban,
        amount=invoice.total,
        reference=reference,
        bic=invoice.seller.get("bic") or None,
    )
    return qr.svg_data_uri(scale=3, border=2)


def logo_uri(organisation):
    if not organisation or not organisation.logo:
        return ""
    with organisation.logo.open("rb") as file:
        content = file.read()
    return _data_uri(content, mimetypes.guess_type(organisation.logo.name)[0] or "image/png")


def invoice_html(invoices, preview=False):
    """One HTML document with a page (or more) per invoice."""
    organisation = Organisation.current()
    pages = []
    for invoice in invoices:
        pages.append(
            {
                "invoice": invoice,
                "lines": list(invoice.lines.all()),
                "breakdown": invoice.vat_breakdown(),
                "barcode": invoice.barcode,
                "barcode_svg": barcode_svg(invoice.barcode),
                "qr": payment_qr(invoice),
                "seller": invoice.seller or _draft_seller(invoice, organisation),
                "buyer": invoice.buyer or invoice.buyer_from_register(),
            }
        )
    return render_to_string(
        "invoicing/pdf/invoices.html",
        {
            "pages": pages,
            "organisation": organisation,
            "logo": logo_uri(organisation),
            "preview": preview,
        },
    )


def _draft_seller(invoice, organisation):
    from .models import BillingSettings

    billing = BillingSettings.current()
    return {
        "name": organisation.name if organisation else "",
        "address": [
            organisation.street_address,
            f"{organisation.postal_code} {organisation.city}".strip(),
        ]
        if organisation
        else [],
        "business_id": organisation.business_id if organisation else "",
        "vat_number": organisation.vat_number if organisation else "",
        "iban": billing.iban,
        "bic": billing.bic,
        "vat_exemption_text": "" if billing.vat_registered else billing.vat_exemption_text,
        "late_interest_text": billing.late_interest_text,
        "footer": billing.footer,
    }


def render_pdf(invoices, preview=False, language=None):
    """PDF bytes for one or more invoices (a print batch is many)."""
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as error:
        raise PDFUnavailable(
            "Making PDFs needs WeasyPrint and the Pango library (see README)."
        ) from error
    with translation.override(language or translation.get_language()):
        html = invoice_html(invoices, preview=preview)
    return HTML(string=html).write_pdf()
