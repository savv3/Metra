from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render

from apps.register.models import Unit


@login_required
@permission_required("register.view_unit", raise_exception=True)
def index(request):
    return render(
        request, "metra_example_plugin/index.html", {"units": Unit.objects.active().count()}
    )
