from decimal import Decimal

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.readings.models import ReadingRound

from .models import FeePlan, Invoice, InvoiceLine, InvoiceRun


class RunForm(forms.ModelForm):
    class Meta:
        model = InvoiceRun
        fields = ["period_label", "plans", "rounds"]
        widgets = {
            "plans": forms.CheckboxSelectMultiple,
            "rounds": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plans"].queryset = FeePlan.objects.filter(active=True)
        self.fields["plans"].initial = list(self.fields["plans"].queryset)
        self.fields["rounds"].queryset = ReadingRound.objects.select_related("reading_type")

    def clean(self):
        cleaned = super().clean()
        rounds = cleaned.get("rounds") or []
        types = [r.reading_type_id for r in rounds]
        if len(types) != len(set(types)):
            raise forms.ValidationError(_("Choose at most one round per reading type."))
        return cleaned


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["note"]
        widgets = {"note": forms.Textarea(attrs={"rows": 2})}


class LineForm(forms.ModelForm):
    class Meta:
        model = InvoiceLine
        fields = ["description", "quantity", "unit_label", "unit_price", "vat_rate"]
        widgets = {
            "quantity": forms.TextInput(attrs={"inputmode": "decimal", "size": 8}),
            "unit_price": forms.TextInput(attrs={"inputmode": "decimal", "size": 10}),
            "vat_rate": forms.TextInput(attrs={"inputmode": "decimal", "size": 5}),
            "unit_label": forms.TextInput(attrs={"size": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ["quantity", "unit_price", "vat_rate"]:
            self.fields[name].localize = True
            self.fields[name].widget.is_localized = True
            # Show 1 and 120, not the database's 1.000 and 120.0000.
            value = self.initial.get(name)
            if isinstance(value, Decimal):
                self.initial[name] = Decimal(format(value.normalize(), "f"))


LineFormSet = forms.inlineformset_factory(
    Invoice, InvoiceLine, form=LineForm, extra=1, can_delete=True
)
