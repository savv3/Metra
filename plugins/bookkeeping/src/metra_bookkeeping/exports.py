"""Reports as files: CSV for spreadsheets and PDF for printing and
keeping. Every report page offers both (``?format=csv`` or ``?format=pdf``)."""

import csv
import io
import re
from decimal import Decimal

from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.text import slugify

from apps.plugins import api

FORMULA_START = ("=", "+", "-", "@", "\t", "\r")
NUMBER = re.compile(r"^-?[0-9]+(,[0-9]+)?$")


def amount(value):
    """1234,50: a comma for decimals and no grouping, as spreadsheets set to
    Finnish or Swedish read it."""
    if value in (None, ""):
        return ""
    return f"{Decimal(value):.2f}".replace(".", ",")


def _safe(value):
    """Keep spreadsheet programs from running a cell as a formula."""
    text = "" if value is None else str(value)
    if text.startswith(FORMULA_START) and not NUMBER.match(text):
        return "'" + text
    return text


def csv_response(name, header, rows):
    """A semicolon-separated UTF-8 file with a byte order mark, so Excel shows
    å, ä and ö correctly."""
    buffer = io.StringIO()
    buffer.write("﻿")
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow([_safe(value) for value in header])
    for row in rows:
        writer.writerow([_safe(value) for value in row])
    response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename(name, "csv")}"'
    response["Cache-Control"] = "private, no-store"
    return response


def pdf_response(request, template, context, name, language=None):
    """The report as a PDF, with numbers and dates written as in
    ``language`` (by default the reader's). Raises api.PDFUnavailable
    without WeasyPrint."""
    with translation.override(language or translation.get_language()):
        html = render_to_string(template, context | {"organisation": api.Organisation.current()})
    response = HttpResponse(api.render_pdf(html), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename(name, "pdf")}"'
    response["Cache-Control"] = "private, no-store"
    return response


def filename(name, extension):
    return f"{slugify(name) or 'report'}.{extension}"
