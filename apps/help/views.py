from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.utils.translation import get_language

from . import articles


# Help is for everyone who works in Metra, whatever their role, and holds no
# register data, so a login is the only check.
@login_required
def index(request):
    query = request.GET.get("q", "").strip()
    context = {"articles": articles.all_articles(), "query": query}
    if query:
        context["results"] = articles.search(query)
    return render(request, "help/index.html", context)


@login_required
def article(request, slug):
    found = articles.get(slug)
    if found is None:
        raise Http404
    context = {
        "article": found,
        "articles": articles.all_articles(),
        "fallback": found.language != (get_language() or "sv")[:2],
    }
    return render(request, "help/article.html", context)
