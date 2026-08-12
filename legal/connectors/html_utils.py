from __future__ import annotations

from html.parser import HTMLParser

from legal.corpus.source_normalizer import normalize_url, normalize_whitespace


class LinkCollector(HTMLParser):
    def __init__(self, *, base_url: str | None = None) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: list[dict[str, str]] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            attrs_dict = {key.lower(): value for key, value in attrs if value is not None}
            href = attrs_dict.get("href")
            if href:
                self._current_href = normalize_url(href, self.base_url)
                self._current_text = []

    def handle_data(self, data: str) -> None:
        self.text_parts.append(data)
        if self._current_href is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._current_href is not None:
            self.links.append(
                {
                    "href": self._current_href,
                    "text": normalize_whitespace(" ".join(self._current_text)),
                }
            )
            self._current_href = None
            self._current_text = []

    @property
    def visible_text(self) -> str:
        return normalize_whitespace(" ".join(self.text_parts))


def collect_links_and_text(html: str, *, base_url: str | None = None) -> tuple[list[dict[str, str]], str]:
    parser = LinkCollector(base_url=base_url)
    parser.feed(html)
    return parser.links, parser.visible_text
