"""PDFs made from HTML with WeasyPrint, for invoices and for plugins.

WeasyPrint needs the Pango library (installed in the Docker image; on a Mac
``brew install pango``). It is imported only when a PDF is made, so the rest
of the app works without it.
"""


class PDFUnavailable(RuntimeError):
    """WeasyPrint or its system libraries are missing."""


def html_to_pdf(html):
    """PDF bytes for an HTML document. Images must be inline (data: URIs)."""
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as error:
        raise PDFUnavailable(
            "Making PDFs needs WeasyPrint and the Pango library (see README)."
        ) from error
    return HTML(string=html).write_pdf()
