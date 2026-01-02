import re
from typing import Optional


_WS_RE = re.compile(r"\s+")
_YEAR_SUFFIX_RE = re.compile(r"[,\.]\s*(?P<year>(?:19|20)\d{2})(?:\s*,\s*(?P<num>\d+))?\s*$")


def normalize_scholar_paper_title(raw: Optional[str]) -> str:
    """
    Normalize a paper title scraped from Google Scholar.

    Scholar sometimes returns citation-like strings as "titles", e.g.:
      "GE Hinton Imagenet classification with deep convolutional neural networks., 2012, 25"

    For UI cards we want the real title part:
      "Imagenet classification with deep convolutional neural networks"
    """

    text = str(raw or "").strip()
    if not text:
        return ""

    text = _WS_RE.sub(" ", text)
    m = _YEAR_SUFFIX_RE.search(text)
    if not m:
        return text

    before = text[: m.start()].strip()
    tokens = before.split()
    if len(tokens) < 3:
        return text

    def _is_initial(token: str) -> bool:
        return token.isalpha() and token.isupper() and len(token) == 1

    def _is_initials(token: str) -> bool:
        return token.isalpha() and token.isupper() and 1 <= len(token) <= 3

    def _is_capitalized(token: str) -> bool:
        return bool(token) and token[0].isupper()

    author_tokens = 0
    if len(tokens) >= 3 and _is_initial(tokens[0]) and _is_initial(tokens[1]) and _is_capitalized(tokens[2]):
        author_tokens = 3
    elif _is_initials(tokens[0]) and _is_capitalized(tokens[1]):
        author_tokens = 2
    elif _is_capitalized(tokens[0]) and _is_capitalized(tokens[1]):
        author_tokens = 2

    if author_tokens <= 0 or len(tokens) <= author_tokens:
        return text

    candidate = " ".join(tokens[author_tokens:]).strip().strip(" .,:;")
    if len(candidate) < 8:
        return text
    return candidate

