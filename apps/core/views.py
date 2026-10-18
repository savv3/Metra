from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render


def home(request):
    if request.user.is_authenticated:
        return redirect("register:unit_list")
    return render(request, "core/home.html")


def healthz(request):
    """Used by the Docker health check: the app is up and can reach its database."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})
