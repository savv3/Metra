import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django import forms
from django.conf import settings
from django.db import models
from django.template.defaultfilters import filesizeformat
from django.utils import timezone, translation
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from apps.plugins import api

from . import countries
from .models import (
    Account,
    Budget,
    FiscalYear,
    PostingSettings,
    SalesAccount,
    VatCode,
    VatRegistration,
    Voucher,
    VoucherLine,
    VoucherSeries,
    vat_label,
)

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")

# What a receipt may be: documents and pictures, nothing that runs. Checked
# by extension; the type stored is the one listed here.
RECEIPT_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".txt": "text/plain",
    ".xml": "application/xml",
}
RECEIPT_MB = 20


class FiscalYearForm(forms.ModelForm):
    class Meta:
        model = FiscalYear
        fields = ["start", "end", "length_reason", "staff"]
        widgets = {"start": DATE, "end": DATE}


class YearStaffForm(forms.ModelForm):
    """What can still change once a year has posted vouchers."""

    class Meta:
        model = FiscalYear
        fields = ["staff"]


class SetupForm(FiscalYearForm):
    """Starting the books: the first financial year, the kind of organisation
    and, unless there are accounts already, a chart of accounts for it."""

    class Meta(FiscalYearForm.Meta):
        fields = ["chart", "start", "end", "length_reason"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        rules = countries.get()
        self.fields["chart"] = forms.ChoiceField(
            label=gettext_lazy("Kind of organisation"),
            widget=forms.RadioSelect,
            choices=[
                (key, f"{chart.name}: {chart.description}") for key, chart in rules.CHARTS.items()
            ],
            initial=next(iter(rules.CHARTS)),
            help_text=gettext_lazy(
                "Decides the form of the income statement and the chart of accounts the books "
                "start with. Accounts can then be added, renamed and retired."
            ),
        )
        year = timezone.localdate().year
        self.fields["start"].initial = datetime.date(year, 1, 1)
        self.fields["end"].initial = datetime.date(year, 12, 31)


class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ["number", "name", "kind", "active", "long_term"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.has_entries():
            for name in ("number", "kind"):
                self.fields[name].disabled = True
                self.fields[name].help_text = _("The account has entries, so this stays.")


class VoucherSeriesForm(forms.ModelForm):
    class Meta:
        model = VoucherSeries
        fields = ["code", "name"]


class VoucherForm(forms.ModelForm):
    class Meta:
        model = Voucher
        fields = ["date", "description", "series", "kind"]
        widgets = {"date": DATE}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["kind"].choices = [
            (value, label)
            for value, label in Voucher.Kind.choices
            if value != Voucher.Kind.REVERSAL
        ]
        if VoucherSeries.objects.count() < 2:
            self.fields["series"].widget = forms.HiddenInput()
        self.fields["series"].initial = VoucherSeries.default().pk

    def clean_date(self):
        date = self.cleaned_data["date"]
        year = FiscalYear.for_date(date)
        if year is None:
            raise forms.ValidationError(_("No financial year covers this date."))
        if not year.is_open:
            raise forms.ValidationError(
                _("The financial year %(year)s is closed.") % {"year": year}
            )
        self.year = year
        return date

    def save(self, commit=True):
        self.instance.year = self.year
        return super().save(commit)


def vat_choices():
    """("sales:25.5", "Sales 25.5 %") and so on for the rates of the open years."""
    first_open = FiscalYear.objects.filter(status=FiscalYear.Status.OPEN).order_by("start").first()
    rates = countries.vat_rates(since=first_open.start if first_open else None)
    return [("", "–")] + [
        (f"{code}:{rate}", vat_label(code, rate)) for code in VatCode.values for rate in rates
    ]


class VoucherLineForm(forms.ModelForm):
    vat = forms.ChoiceField(
        label=gettext_lazy("VAT"),
        required=False,
        help_text=gettext_lazy("The VAT the line is for, when VAT registered."),
    )

    class Meta:
        model = VoucherLine
        fields = ["account", "description", "debit", "credit", "vat"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = vat_choices()
        if self.instance.vat_code:
            current = f"{self.instance.vat_code}:{self.instance.vat_rate}"
            self.initial["vat"] = current
            if current not in dict(choices):
                choices.append((current, self.instance.vat_display))
        self.fields["vat"].choices = choices
        accounts = Account.objects.filter(active=True)
        if self.instance.pk:
            accounts = accounts | Account.objects.filter(pk=self.instance.account_id)
        self.fields["account"].queryset = accounts
        for name in ("debit", "credit"):
            # Blank, not 0,00: an untouched empty line is left out.
            if not self.initial.get(name):
                self.initial.pop(name, None)
            self.fields[name].initial = None
            self.fields[name].required = False
            self.fields[name].widget.attrs.update({"inputmode": "decimal", "step": "0.01"})

    def clean(self):
        cleaned = super().clean()
        for name in ("debit", "credit"):
            if cleaned.get(name) is None:
                cleaned[name] = 0
        code, _sep, rate = (cleaned.get("vat") or "").partition(":")
        try:
            self.instance.vat_rate = Decimal(rate) if code else None
        except InvalidOperation:
            raise forms.ValidationError({"vat": _("Choose a VAT rate from the list.")}) from None
        self.instance.vat_code = code
        return cleaned


class BaseLineFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        lines = [
            form for form in self.forms if form.cleaned_data and not form.cleaned_data.get("DELETE")
        ]
        if not lines:
            raise forms.ValidationError(_("Add the voucher's lines."))


LineFormSet = forms.inlineformset_factory(
    Voucher,
    VoucherLine,
    form=VoucherLineForm,
    formset=BaseLineFormSet,
    extra=3,
    can_delete=True,
)


class ReceiptForm(forms.Form):
    file = forms.FileField(
        label=gettext_lazy("Receipt"),
        help_text=gettext_lazy("A PDF or a photo of the receipt or bill, up to %(mb)s MB.")
        % {"mb": RECEIPT_MB},
        widget=forms.ClearableFileInput(attrs={"accept": ",".join(RECEIPT_TYPES)}),
    )

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if Path(upload.name).suffix.lower() not in RECEIPT_TYPES:
            raise forms.ValidationError(_("This kind of file cannot be a receipt."))
        if upload.size > RECEIPT_MB * 2**20:
            raise forms.ValidationError(
                _("The file is larger than %(limit)s.")
                % {"limit": filesizeformat(RECEIPT_MB * 2**20)}
            )
        return upload

    @staticmethod
    def content_type(name):
        return RECEIPT_TYPES[Path(name).suffix.lower()]


class ReverseForm(forms.Form):
    date = forms.DateField(label=gettext_lazy("Date of the reversal"), widget=DATE)
    note = forms.CharField(
        label=gettext_lazy("Reason"),
        max_length=150,
        help_text=gettext_lazy("Why the voucher is reversed, for example a wrong account."),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date"].initial = timezone.localdate()

    def clean_date(self):
        date = self.cleaned_data["date"]
        year = FiscalYear.for_date(date)
        if year is None or not year.is_open:
            raise forms.ValidationError(_("There is no open financial year for that date."))
        return date


class ReportForm(forms.Form):
    """The year and dates a report covers."""

    year = forms.ModelChoiceField(
        label=gettext_lazy("Financial year"), queryset=FiscalYear.objects.all(), empty_label=None
    )
    start = forms.DateField(label=gettext_lazy("From"), required=False, widget=DATE)
    end = forms.DateField(label=gettext_lazy("To"), required=False, widget=DATE)

    def __init__(self, data=None, **kwargs):
        super().__init__(data, **kwargs)
        current = FiscalYear.current() or FiscalYear.objects.first()
        self.fields["year"].initial = current.pk if current else None

    def period(self):
        """(year, start, end) to report on, limited to the year."""
        if self.is_bound and self.is_valid():
            year = self.cleaned_data["year"]
            start = self.cleaned_data["start"] or year.start
            end = self.cleaned_data["end"] or year.end
        else:
            year = FiscalYear.objects.filter(pk=self.fields["year"].initial).first()
            if year is None:
                return None, None, None
            start, end = year.start, year.end
        return year, max(start, year.start), min(end, year.end)


def statement_languages():
    """The languages statements are kept in, and English as a translation."""
    names = dict(settings.LANGUAGES)
    keep = countries.get().STATEMENT_LANGUAGES
    return [(code, names.get(code, code)) for code in keep] + [
        ("en", _("English (a translation, not for filing)"))
    ]


def default_statement_language():
    keep = countries.get().STATEMENT_LANGUAGES
    language = (translation.get_language() or settings.LANGUAGE_CODE)[:2]
    if language in keep:
        return language
    return settings.LANGUAGE_CODE[:2] if settings.LANGUAGE_CODE[:2] in keep else keep[0]


class StatementOptions(forms.Form):
    """How a statement is shown: its language, the previous year beside it,
    and the shorter micro-entity format."""

    language = forms.ChoiceField(label=gettext_lazy("Language"), required=False)
    alone = forms.BooleanField(
        label=gettext_lazy("Without the previous year"),
        required=False,
        help_text=gettext_lazy("The previous financial year is shown beside it when it exists."),
    )
    micro = forms.BooleanField(
        label=gettext_lazy("Micro-entity format"),
        required=False,
        help_text=gettext_lazy("Leaves out the breakdowns a micro entity need not show."),
    )

    def __init__(self, data=None, **kwargs):
        super().__init__(data, **kwargs)
        self.fields["language"].choices = statement_languages()
        self.fields["language"].initial = default_statement_language()

    def options(self, micro_allowed):
        """(language, compare, micro) asked for; micro only when allowed."""
        data = self.cleaned_data if self.is_bound and self.is_valid() else {}
        language = data.get("language") or self.fields["language"].initial
        return language, not data.get("alone"), bool(data.get("micro")) and micro_allowed


class _StatementForm(StatementOptions):
    year = forms.ModelChoiceField(
        label=gettext_lazy("Financial year"), queryset=FiscalYear.objects.all(), empty_label=None
    )

    def __init__(self, data=None, **kwargs):
        super().__init__(data, **kwargs)
        current = FiscalYear.current() or FiscalYear.objects.first()
        self.fields["year"].initial = current.pk if current else None


class IncomeStatementForm(_StatementForm):
    start = forms.DateField(label=gettext_lazy("From"), required=False, widget=DATE)
    end = forms.DateField(label=gettext_lazy("To"), required=False, widget=DATE)
    field_order = ["year", "start", "end", "language", "alone", "micro"]

    period = ReportForm.period


class BalanceSheetForm(_StatementForm):
    end = forms.DateField(label=gettext_lazy("At"), required=False, widget=DATE)
    field_order = ["year", "end", "language", "alone", "micro"]

    def period(self):
        """(year, the day the balance sheet is at), within the year."""
        if self.is_bound and self.is_valid():
            year = self.cleaned_data["year"]
            end = self.cleaned_data["end"] or year.end
        else:
            year = FiscalYear.objects.filter(pk=self.fields["year"].initial).first()
            if year is None:
                return None, None
            end = year.end
        return year, min(max(end, year.start), year.end)


class VatSummaryForm(forms.Form):
    start = forms.DateField(label=gettext_lazy("From"), required=False, widget=DATE)
    end = forms.DateField(label=gettext_lazy("To"), required=False, widget=DATE)

    def __init__(self, data=None, **kwargs):
        super().__init__(data, **kwargs)
        today = timezone.localdate()
        self.fields["start"].initial = datetime.date(today.year, 1, 1)
        self.fields["end"].initial = datetime.date(today.year, 12, 31)

    def period(self):
        data = self.cleaned_data if self.is_bound and self.is_valid() else {}
        start = data.get("start") or self.fields["start"].initial
        end = data.get("end") or self.fields["end"].initial
        return (start, end) if start <= end else (end, start)


class BudgetForm(forms.Form):
    """A year's budget: an amount per income and expense account, positive
    for income expected and for costs expected. Empty means no budget."""

    def __init__(self, *args, year, **kwargs):
        super().__init__(*args, **kwargs)
        self.year = year
        budgets = {line.account_id: line for line in year.budget.all()}
        accounts = Account.objects.filter(
            kind__in=[Account.Kind.INCOME, Account.Kind.EXPENSE]
        ).filter(models.Q(active=True) | models.Q(pk__in=budgets))
        self.rows = []
        for account in accounts:
            name = f"account_{account.pk}"
            line = budgets.get(account.pk)
            self.fields[name] = forms.DecimalField(
                label=str(account),
                required=False,
                min_value=0,
                max_digits=12,
                decimal_places=2,
                initial=line.amount if line else None,
                widget=forms.NumberInput(attrs={"inputmode": "decimal", "step": "0.01"}),
            )
            self.rows.append((account, name, line))

    def income_fields(self):
        return [self[name] for account, name, _ in self.rows if account.kind == Account.Kind.INCOME]

    def expense_fields(self):
        return [
            self[name] for account, name, _ in self.rows if account.kind == Account.Kind.EXPENSE
        ]

    def save(self):
        """Save the changed lines one by one, for the audit log."""
        for account, name, line in self.rows:
            amount = self.cleaned_data.get(name)
            if amount in (None, 0):
                if line is not None:
                    line.delete()
            elif line is None:
                Budget.objects.create(year=self.year, account=account, amount=amount)
            elif line.amount != amount:
                line.amount = amount
                line.save()


class PostingSettingsForm(forms.ModelForm):
    """Where invoices and payments are booked. A series left empty is made
    when the settings are saved."""

    class Meta:
        model = PostingSettings
        fields = [
            "start",
            "receivables",
            "bank",
            "sales",
            "reminder_fees",
            "sales_vat",
            "purchase_vat",
            "vat_settlement",
            "invoice_series",
            "payment_series",
        ]
        widgets = {"start": DATE}

    NEW_SERIES = {
        "invoice_series": ("L", gettext_lazy("Sales invoices")),
        "payment_series": ("S", gettext_lazy("Payments")),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        accounts = Account.objects.filter(active=True)
        for name in PostingSettings.REQUIRED + ["purchase_vat"]:
            field = self.fields[name]
            if name in self.NEW_SERIES:
                code, label = self.NEW_SERIES[name]
                field.empty_label = _("New series: %(code)s %(name)s") % {
                    "code": code,
                    "name": label,
                }
            else:
                current = getattr(self.instance, f"{name}_id")
                field.queryset = accounts | Account.objects.filter(pk=current)

    def clean_start(self):
        start = self.cleaned_data["start"]
        if start is not None:
            year = FiscalYear.for_date(start)
            if year is None or not year.is_open:
                raise forms.ValidationError(_("Choose a day in an open financial year."))
        return start

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("start"):
            missing = [
                self.fields[name].label
                for name in PostingSettings.REQUIRED
                if name not in self.NEW_SERIES and not cleaned.get(name)
            ]
            if missing:
                raise forms.ValidationError(
                    _("Choose these accounts before posting starts: %(names)s.")
                    % {"names": ", ".join(str(name) for name in missing)}
                )
        vat = [cleaned.get(name) for name in ("sales_vat", "purchase_vat", "vat_settlement")]
        vat = [account for account in vat if account]
        if len(set(vat)) != len(vat):
            raise forms.ValidationError(
                _("Sales VAT, purchase VAT and the VAT settlement need accounts of their own.")
            )
        if cleaned.get("receivables") and cleaned.get("receivables") == cleaned.get("bank"):
            raise forms.ValidationError(_("Receivables and the bank need accounts of their own."))
        return cleaned

    def save(self, commit=True):
        for name, (code, label) in self.NEW_SERIES.items():
            if getattr(self.instance, f"{name}_id") is None:
                taken = set(VoucherSeries.objects.values_list("code", flat=True))
                free = next(
                    c for c in [code, *(f"{code}{n}" for n in range(2, 100))] if c not in taken
                )
                # Named in the organisation's language, like the vouchers.
                with translation.override(settings.LANGUAGE_CODE):
                    series = VoucherSeries.objects.create(code=free, name=str(label))
                setattr(self.instance, name, series)
        return super().save(commit)


class SalesAccountsForm(forms.Form):
    """An income account per fee line and per VAT rate; empty for the
    default sales account."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        accounts = Account.objects.filter(active=True, kind=Account.Kind.INCOME)
        rules = {(rule.fee_line_id, rule.vat_rate): rule for rule in SalesAccount.objects.all()}
        self.rows = []
        lines = api.FeeLine.objects.filter(plan__active=True).select_related("plan")
        for line in lines:
            rule = rules.get((line.pk, None))
            self._add(f"fee_{line.pk}", f"{line.plan} – {line.description}", accounts, rule)
            self.rows.append(("fee", line.pk, f"fee_{line.pk}"))
        for rate in self._rates(rules):
            rule = rules.get((None, rate))
            name = f"rate_{rate}"
            self._add(name, vat_label(VatCode.SALES, rate), accounts, rule)
            self.rows.append(("rate", rate, name))

    @staticmethod
    def _rates(rules):
        first_open = (
            FiscalYear.objects.filter(status=FiscalYear.Status.OPEN).order_by("start").first()
        )
        rates = set(countries.vat_rates(since=first_open.start if first_open else None))
        rates |= {rate for _line, rate in rules if rate is not None}
        return sorted({Decimal(rate).quantize(Decimal("0.01")) for rate in rates}, reverse=True)

    def _add(self, name, label, accounts, rule):
        queryset = accounts | Account.objects.filter(pk=rule.account_id) if rule else accounts
        self.fields[name] = forms.ModelChoiceField(
            label=label,
            queryset=queryset,
            required=False,
            empty_label=_("Default sales account"),
            initial=rule.account_id if rule else None,
        )

    def fee_fields(self):
        return [self[name] for kind, _key, name in self.rows if kind == "fee"]

    def rate_fields(self):
        return [self[name] for kind, _key, name in self.rows if kind == "rate"]

    def save(self):
        for kind, key, name in self.rows:
            account = self.cleaned_data.get(name)
            match = {"fee_line_id": key} if kind == "fee" else {"vat_rate": key}
            if account is None:
                for rule in SalesAccount.objects.filter(**match):
                    rule.delete()  # one by one, for the audit log
            else:
                rule = SalesAccount.objects.filter(**match).first() or SalesAccount(**match)
                if rule.account_id != account.pk:
                    rule.account = account
                    rule.save()


class VatRegistrationForm(forms.ModelForm):
    class Meta:
        model = VatRegistration
        fields = ["start", "end", "period"]
        widgets = {"start": DATE, "end": DATE}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["period"].required = False

    def clean_period(self):
        return self.cleaned_data["period"] or VatRegistration.Period.MONTH
