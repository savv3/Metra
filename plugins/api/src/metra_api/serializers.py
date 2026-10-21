"""What the API reads and writes. Writes are checked by Metra's own forms (see
FormBackedSerializer), so the API accepts exactly what the web pages accept."""

from django.forms.models import model_to_dict
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.plugins import api


def _plain(number):
    """12.500 as "12.5": the form counts decimals against the reading type's."""
    return format(number.normalize(), "f")


def _messages(errors):
    return [str(message) for message in errors]


class FormBackedSerializer(serializers.ModelSerializer):
    """A serializer whose writes go through a Django form.

    The incoming fields are merged with the stored record (PATCH) or with a
    new record's defaults (POST, PUT), handed to the form, and saved by it.
    ``custom_fields`` becomes the form's custom field answers. The form's
    errors come back keyed by the API's field names.
    """

    custom_fields = serializers.DictField(source="custom_data", required=False)

    def get_form(self, data, instance):
        raise NotImplementedError

    def validate(self, attrs):
        instance = self.instance
        base = instance if instance is not None and self.partial else self.Meta.model()
        names = self.Meta.form_fields
        data = model_to_dict(base, fields=names)
        data.update({name: attrs[name] for name in names if name in attrs})
        if "tags" in data:
            data["tags"] = [tag.pk for tag in data["tags"]]
        data = {name: value for name, value in data.items() if value is not None}
        form = self.get_form(data, instance, attrs)

        definitions = dict(zip(form.custom_definitions, form.custom_field_names(), strict=True))
        known = {definition.key: name for definition, name in definitions.items()}
        given = attrs.get("custom_data", {})
        unknown = sorted(set(given) - set(known))
        if unknown:
            raise serializers.ValidationError(
                {"custom_fields": {key: [_("There is no such field.")] for key in unknown}}
            )
        nested = sorted(key for key, value in given.items() if isinstance(value, dict | list))
        if nested:
            raise serializers.ValidationError(
                {"custom_fields": {key: [_("Give a single value.")] for key in nested}}
            )
        custom = dict(instance.custom_data or {}) if instance is not None and self.partial else {}
        custom.update(given)
        for key, name in known.items():
            if custom.get(key) is not None:
                data[name] = custom[key]

        if not form.is_valid():
            raise serializers.ValidationError(self.form_errors(form, known))
        self._form = form
        return attrs

    def form_errors(self, form, known):
        by_name = {name: key for key, name in known.items()}
        errors, custom = {}, {}
        for name, messages in form.errors.items():
            if name in by_name:
                custom[by_name[name]] = _messages(messages)
            elif name == "__all__":
                errors["non_field_errors"] = _messages(messages)
            else:
                errors[name] = _messages(messages)
        if custom:
            errors["custom_fields"] = custom
        return errors

    def create(self, validated_data):
        return self._form.save()

    def update(self, instance, validated_data):
        return self._form.save()


class ContactSerializer(serializers.ModelSerializer):
    """A person's role on a unit (unit-contacts)."""

    class Meta:
        model = api.UnitContact
        fields = ["id", "unit", "person", "role"]
        # The form checks that a person has each role on a unit once.
        validators = []

    def validate(self, attrs):
        form = api.UnitContactForm(
            {"person": attrs["person"].pk, "role": attrs.get("role", "contact")}, unit=attrs["unit"]
        )
        if not form.is_valid():
            errors = {
                ("non_field_errors" if name == "__all__" else name): _messages(messages)
                for name, messages in form.errors.items()
            }
            raise serializers.ValidationError(errors)
        self._form = form
        return attrs

    def create(self, validated_data):
        return self._form.save()


class UnitContactLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = api.UnitContact
        fields = ["id", "unit", "person", "role"]
        read_only_fields = fields


class UnitSerializer(FormBackedSerializer):
    """A unit. ``custom_fields`` holds its unit type's custom fields by key."""

    tags = serializers.SlugRelatedField(
        slug_field="name", many=True, queryset=api.Tag.objects.all(), required=False
    )
    contacts = UnitContactLinkSerializer(source="unit_contacts", many=True, read_only=True)

    class Meta:
        model = api.Unit
        form_fields = list(api.UnitForm._meta.fields)
        fields = [
            "id",
            "unit_type",
            *form_fields,
            "custom_fields",
            "contacts",
            "archived_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["archived_at", "created_at", "updated_at"]
        extra_kwargs = {"unit_type": {"required": False}}

    def get_form(self, data, instance, attrs):
        unit_type = attrs.get("unit_type")
        if instance is not None:
            if unit_type is not None and unit_type != instance.unit_type:
                raise serializers.ValidationError(
                    {"unit_type": [_("A unit's type cannot change.")]}
                )
            unit_type = instance.unit_type
        elif unit_type is None:
            raise serializers.ValidationError({"unit_type": [_("This field is required.")]})
        return api.UnitForm(data, instance=instance, unit_type=unit_type)


class PersonSerializer(FormBackedSerializer):
    """A person. ``custom_fields`` holds the person custom fields by key."""

    tags = serializers.SlugRelatedField(
        slug_field="name", many=True, queryset=api.Tag.objects.all(), required=False
    )
    contacts = UnitContactLinkSerializer(source="unit_contacts", many=True, read_only=True)

    class Meta:
        model = api.Person
        form_fields = list(api.PersonForm._meta.fields)
        fields = [
            "id",
            *form_fields,
            "custom_fields",
            "contacts",
            "archived_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["archived_at", "created_at", "updated_at"]

    def get_form(self, data, instance, attrs):
        return api.PersonForm(data, instance=instance)


class CustomFieldSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source="field_type")
    choices = serializers.ListField(source="choice_list", child=serializers.CharField())

    class Meta:
        model = api.CustomField
        fields = ["key", "label", "type", "choices", "required", "help_text"]
        read_only_fields = fields


class UnitTypeSerializer(serializers.ModelSerializer):
    custom_fields = CustomFieldSerializer(many=True, read_only=True)

    class Meta:
        model = api.UnitType
        fields = ["id", "name", "description", "custom_fields"]
        read_only_fields = fields


class ReadingTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = api.ReadingType
        fields = ["id", "name", "unit_type", "unit_label", "decimals", "cumulative"]
        read_only_fields = fields


class ReadingRoundSerializer(serializers.ModelSerializer):
    reading_type = ReadingTypeSerializer(read_only=True)
    # Worked out from the draft flag and the dates: draft, upcoming, open or closed.
    status = serializers.CharField(read_only=True)

    class Meta:
        model = api.ReadingRound
        fields = ["id", "reading_type", "period_label", "opens_on", "closes_on", "status"]
        read_only_fields = fields


class ReadingSerializer(serializers.ModelSerializer):
    submitted_by = serializers.SlugRelatedField(slug_field="username", read_only=True)

    class Meta:
        model = api.Reading
        fields = ["id", "round", "unit", "value", "note", "source", "submitted_by", "submitted_at"]
        read_only_fields = ["source", "submitted_by", "submitted_at"]
        # The reading type's rules and one reading per unit and round are
        # checked in validate(), with the web pages' messages.
        validators = []

    def validate(self, attrs):
        instance = self.instance
        if instance is not None:
            for name in ["round", "unit"]:
                if name in attrs and attrs[name] != getattr(instance, name):
                    raise serializers.ValidationError(
                        {name: [_("A reading cannot move; enter a new one instead.")]}
                    )
            round_, unit = instance.round, instance.unit
        else:
            round_, unit = attrs.get("round"), attrs.get("unit")
            missing = {
                name: [_("This field is required.")]
                for name, value in [("round", round_), ("unit", unit)]
                if value is None
            }
            if missing:
                raise serializers.ValidationError(missing)
            if unit.unit_type_id != round_.reading_type.unit_type_id:
                raise serializers.ValidationError(
                    {"unit": [_("This round is not read from units of this type.")]}
                )
            if api.Reading.objects.filter(round=round_, unit=unit).exists():
                raise serializers.ValidationError(
                    {"unit": [_("This unit already has a reading in this round; change it.")]}
                )
        data = {}
        if instance is not None and self.partial:
            data = {"value": _plain(instance.value), "note": instance.note}
        if "value" in attrs:
            data["value"] = _plain(attrs["value"])
        if "note" in attrs:
            data["note"] = attrs["note"]
        form = api.ReadingForm(data, instance=instance, round_=round_, unit=unit)
        if not form.is_valid():
            raise serializers.ValidationError(
                {name: _messages(messages) for name, messages in form.errors.items()}
            )
        self._form = form
        return attrs

    def save(self, **kwargs):
        form = self._form
        reading = form.save(commit=False)
        if "value" in form.changed_data or reading.pk is None:
            reading.source = api.Reading.Source.STAFF
            reading.submitted_by = self.context["request"].user
            reading.submitted_by_person = None
            reading.submitted_at = timezone.now()
        reading.save()
        self.instance = reading
        return reading


class InvoiceLineSerializer(serializers.ModelSerializer):
    net = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = api.InvoiceLine
        fields = ["description", "quantity", "unit_label", "unit_price", "vat_rate", "net"]
        read_only_fields = fields


class InvoiceSerializer(serializers.ModelSerializer):
    lines = InvoiceLineSerializer(many=True, read_only=True)

    class Meta:
        model = api.Invoice
        fields = [
            "id",
            "number",
            "kind",
            "status",
            "unit",
            "person",
            "credits",
            "period_label",
            "reference",
            "issue_date",
            "due_date",
            "total_net",
            "total_vat",
            "total",
            "issued_at",
            "lines",
        ]
        read_only_fields = fields


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = api.Payment
        fields = ["id", "invoice", "amount", "paid_on", "reference", "note", "recorded_at"]
        read_only_fields = fields
