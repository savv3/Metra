from django import template

register = template.Library()


@register.inclusion_tag("messaging/_send_forms.html", takes_context=True)
def round_send_forms(context, round_):
    from ..views import channel_status

    return {
        "round": round_,
        "channels": channel_status(),
        "perms": context.get("perms"),
        "csrf_token": context.get("csrf_token"),
    }


@register.inclusion_tag("messaging/_person_newsletter.html", takes_context=True)
def person_newsletter(context, person):
    """The person's newsletter consent, with a form for staff to record a new one."""
    from ..forms import ConsentForm
    from ..models import ConsentRecord

    user = context["request"].user
    if not user.has_perm("register.view_person"):
        return {"show": False}
    history = list(ConsentRecord.objects.filter(person=person).select_related("recorded_by")[:20])
    current = history[0] if history else None
    return {
        "show": True,
        "person": person,
        "current": current,
        "history": history,
        "form": ConsentForm(initial={"subscribed": "1" if current and current.subscribed else "0"}),
        "perms": context.get("perms"),
        "csrf_token": context.get("csrf_token"),
    }


UNIT_MESSAGES_SHOWN = 20


@register.inclusion_tag("messaging/_unit_messages.html", takes_context=True)
def unit_messages(context, unit):
    """Recent messages to the unit's contacts, with a button to write a new one."""
    from ..models import Message

    user = context["request"].user
    if not user.has_perm("messaging.view_message"):
        return {"show": False}
    unit_messages = (
        Message.objects.filter(unit=unit)
        .select_related("person", "batch")
        .order_by("-created_at", "-pk")[:UNIT_MESSAGES_SHOWN]
    )
    return {
        "show": True,
        "unit": unit,
        "unit_messages": unit_messages,
        "can_send": user.has_perm("messaging.send_unit_message") and not unit.is_archived,
    }
