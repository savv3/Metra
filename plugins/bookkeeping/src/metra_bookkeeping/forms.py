import datetime
from pathlib import Path

from django import forms
from django.template.defaultfilters import filesizeformat
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from . import countries
from .models import Account, FiscalYear, Voucher, VoucherLine, VoucherSeries

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
        fields = ["start", "end", "length_reason"]
        widgets = {"start": DATE, "end": DATE}


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
        fields = ["number", "name", "kind", "active"]

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


class VoucherLineForm(forms.ModelForm):
    class Meta:
        model = VoucherLine
        fields = ["account", "description", "debit", "credit"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
