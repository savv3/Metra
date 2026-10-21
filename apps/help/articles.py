"""Help articles: Markdown files, one per language, in ``articles/<language>/``.

Each file starts with ``# Title``. Plugins add their own folders (with the
same layout) through ``api.add_help_articles``. An article missing in the
reader's language is shown in English, then Swedish.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import markdown
from django.utils.safestring import mark_safe
from django.utils.translation import get_language

from apps.plugins.hooks import HELP_ARTICLES, hooks

FOLDER = Path(__file__).parent / "articles"
# The core articles, in the order the help index lists them.
ORDER = [
    "getting-started",
    "register",
    "readings",
    "messages",
    "invoicing",
    "backups",
    "notifications",
    "roles",
]
FALLBACK = ["en", "sv"]
# Which article fits a page, by the page's URL namespace.
PAGES = {
    "core": "getting-started",
    "setup": "getting-started",
    "register": "register",
    "readings": "readings",
    "messaging": "messages",
    "invoicing": "invoicing",
    "backups": "backups",
    "accounts": "roles",
    "notifications": "notifications",
}
SLUG = re.compile(r"^[a-z0-9-]+$")


@dataclass
class Article:
    slug: str
    language: str  # the language it is written in, which may be a fallback
    title: str
    text: str  # Markdown, without the title line

    @property
    def html(self):
        # Articles come from the repository and installed plugins, never from users.
        return mark_safe(markdown.markdown(self.text, extensions=["tables"]))  # noqa: S308


@dataclass
class Snippet:
    article: Article
    text: str = ""
    in_title: bool = False


@dataclass
class Library:
    folders: list = field(default_factory=list)
    order: list = field(default_factory=list)
    pages: dict = field(default_factory=dict)


def library():
    """The core articles plus those plugins add."""
    lib = Library([FOLDER], list(ORDER), dict(PAGES))
    for extra in hooks.get(HELP_ARTICLES):
        lib.folders.append(Path(extra.folder))
        lib.order += [slug for slug in extra.order if slug not in lib.order]
        lib.pages.update(extra.pages)
    return lib


def _read(path, slug, language):
    lines = path.read_text(encoding="utf-8").splitlines()
    title = lines[0].removeprefix("# ").strip() if lines else slug
    return Article(slug, language, title, "\n".join(lines[1:]).strip())


def get(slug, language=None):
    """The article in ``language`` (or the active one), else a fallback; None if unknown."""
    if not SLUG.match(slug):
        return None
    language = (language or get_language() or "sv")[:2]
    for lang in [language, *FALLBACK]:
        for folder in library().folders:
            path = folder / lang / f"{slug}.md"
            if path.is_file():
                return _read(path, slug, lang)
    return None


def all_articles(language=None):
    return [a for a in (get(slug, language) for slug in library().order) if a]


def plain(text):
    """Markdown without its markup, for search snippets."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return re.sub(r"[*_`#>|]", "", text)


def search(query, language=None):
    """Articles matching every word of ``query``, title matches first."""
    words = [w for w in query.lower().split() if w]
    if not words:
        return []
    found = []
    for article in all_articles(language):
        body = plain(article.text)
        haystack = f"{article.title}\n{body}".lower()
        if not all(word in haystack for word in words):
            continue
        at = body.lower().find(words[0])
        start = max(at - 60, 0) if at >= 0 else 0
        excerpt = " ".join(body[start : start + 180].split())
        found.append(
            Snippet(
                article, ("…" if start else "") + excerpt + "…", words[0] in article.title.lower()
            )
        )
    return sorted(found, key=lambda s: not s.in_title)


def for_page(namespace):
    """The slug of the article that fits a page, or None for the help index."""
    return library().pages.get(namespace)
