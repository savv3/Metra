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
