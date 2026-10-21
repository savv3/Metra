from . import unitwords


def unit_words(request):
    """``single_unit_type``, ``unit_word_singular`` and ``unit_word_plural``
    for templates. Callables, so pages that do not use them cost no query."""
    return {
        "single_unit_type": lambda: unitwords.words(request)["single_unit_type"],
        "unit_word_singular": lambda: unitwords.words(request)["singular"],
        "unit_word_plural": lambda: unitwords.words(request)["plural"],
    }
