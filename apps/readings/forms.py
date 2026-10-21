from django import forms
from django.utils.translation import gettext_lazy as _

from apps.register.forms import DATE_WIDGET

from .models import Reading, ReadingRound, ReadingType


class RoundForm(forms.ModelForm):
    class Meta:
        model = ReadingRound
        fields = ["reading_type", "period_label", "opens_on", "closes_on", "is_draft"]
        widgets = {"opens_on": DATE_WIDGET, "closes_on": DATE_WIDGET}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        types = ReadingType.objects.active()
        if self.instance.pk:
            # A round keeps its type: its readings were taken for that type.
            types = ReadingType.objects.filter(pk=self.instance.reading_type_id)
            self.fields["reading_type"].disabled = True
        self.fields["reading_type"].queryset = types
        if types.count() == 1:
            self.fields["reading_type"].initial = types.first()


def value_field(reading_type, **kwargs):
    """A number field with the reading type's decimals; accepts 12,5 as well as 12.5."""
    label = _("Reading")
    if reading_type.unit_label:
        label = f"{label} ({reading_type.unit_label})"
    return forms.DecimalField(
        label=label,
        min_value=0,
        max_digits=15,
        decimal_places=reading_type.decimals,
        localize=True,
        widget=forms.TextInput(attrs={"inputmode": "decimal", "autocomplete": "off"}),
        **kwargs,
    )


class ReadingForm(forms.ModelForm):
    """Staff enter or correct one unit's reading in a round."""

    class Meta:
        model = Reading
        fields = ["value", "note"]
        widgets = {"note": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, round_, unit, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.round = round_
        self.instance.unit = unit
        self.fields["value"] = value_field(round_.reading_type)
