import io
import socket
from email.message import Message

import pytest

from legal.connectors.base import SourceTarget
from legal.connectors.http_fetcher import OfficialSourceFetcher, OfficialSourceFetchError


def target(url="https://www.courts.maine.gov/rules/example", *,
           source_class="court_rules_index", jurisdiction="maine", mime="text/plain"):
    return SourceTarget("fictional-source", source_class, jurisdiction, url, "fixture", mime)


class Response(io.BytesIO):
    def __init__(self, url, body=b"test", *, status=200, **headers):
        super().__init__(body)
        self.url = url
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = "text/plain"
        for field, value in headers.items():
            self.headers[field.replace("_", "-")] = value

    def geturl(self):
        return self.url

    def read1(self, size=-1):
        return self.read(min(size, 4))


@pytest.fixture
def transport(monkeypatch):
    fetcher = OfficialSourceFetcher(
        max_response_bytes=4, min_delay_seconds=0, max_retries=0,
        respect_robots_txt=False, strict_content_type=True,
    )
    calls, routes = [], {}

    def open_request(request):
        calls.append(request.full_url)
        return routes[request.full_url]()

    monkeypatch.setattr(fetcher, "_open", open_request)
    return fetcher, calls, routes


@pytest.mark.parametrize("url", [
    "http://www.courts.maine.gov/rules/example",
    "https://www.courts.maine.gov:8443/rules/example",
    "https://user@www.courts.maine.gov/rules/example",
    "https://legislature.maine.gov/rules/example",
    "https://unreviewed.maine.gov/rules/example",
    "https://127.0.0.1/rules/example",
    "https://www.courts.maine.gov\\@attacker.invalid/rules/example",
])
def test_destination_is_checked_before_any_request(transport, url):
    fetcher, calls, _ = transport
    fetcher.respect_robots_txt = True
    with pytest.raises(OfficialSourceFetchError) as error:
        fetcher.fetch(target(url))
    assert error.value.code == "source_destination_refused"
    assert calls == []


def test_relative_redirect_is_followed_and_chain_is_recorded(transport):
    fetcher, calls, routes = transport
    source = target()
    final = "https://www.courts.maine.gov/rules/new"
    routes[source.url] = lambda: Response(source.url, status=302, Location="new")
    routes[final] = lambda: Response(final)
    result = fetcher.fetch(source)
    assert result.content == b"test"
    assert result.final_url == final
    assert result.fetch_metadata["redirect_chain"] == [final]
    assert calls == [source.url, final]


@pytest.mark.parametrize("robots", [False, True])
def test_redirect_escape_refused_for_sources_and_robots(transport, robots):
    fetcher, calls, routes = transport
    fetcher.respect_robots_txt = robots
    source = target()
    initial = "https://www.courts.maine.gov/robots.txt" if robots else source.url
    routes[initial] = lambda: Response(initial, status=302, Location="https://attacker.invalid/")
    with pytest.raises(OfficialSourceFetchError):
        fetcher.fetch(source)
    assert calls == [initial]


@pytest.mark.parametrize("length", [None, "4"])
def test_reads_one_extra_byte_even_when_length_claims_exact_cap(transport, length):
    fetcher, _, routes = transport
    source = target()
    headers = {"Content_Length": length} if length is not None else {}
    routes[source.url] = lambda: Response(source.url, b"tests", **headers)
    with pytest.raises(OfficialSourceFetchError) as error:
        fetcher.fetch(source)
    assert error.value.attempts[-1].status == "response_too_large"


def test_exact_cap_and_approved_federal_source_are_usable(transport):
    fetcher, calls, routes = transport
    source = target("https://uscode.house.gov/view.xhtml", source_class="federal_family_law", jurisdiction="federal")
    routes[source.url] = lambda: Response(source.url, Content_Length="4")
    assert fetcher.fetch(source).content == b"test"
    assert calls == [source.url]


def test_pdf_header_cannot_disguise_html(transport):
    fetcher, _, routes = transport
    fetcher.max_response_bytes = 128
    source = target(mime="application/pdf")

    def response():
        value = Response(source.url, b"<html>Error</html>")
        value.headers.replace_header("Content-Type", "application/pdf")
        return value

    routes[source.url] = response
    with pytest.raises(OfficialSourceFetchError) as error:
        fetcher.fetch(source)
    assert error.value.attempts[-1].status == "content_type_mismatch"


@pytest.mark.parametrize("status,headers,code", [
    (206, {}, "source_response_status_refused"),
    (200, {"Content_Encoding": "gzip"}, "source_content_encoding_refused"),
    (200, {"Content_Length": "3"}, "source_content_length_mismatch"),
    (200, {"Content_Length": "4", "Transfer_Encoding": "chunked"}, "source_content_length_invalid"),
])
def test_refuses_partial_encoded_or_inconsistently_framed_source(transport, status, headers, code):
    fetcher, _, routes = transport
    source = target()
    routes[source.url] = lambda: Response(source.url, status=status, **headers)
    with pytest.raises(OfficialSourceFetchError) as error:
        fetcher.fetch(source)
    assert error.value.attempts[-1].status == code


def test_socket_dials_resolved_numeric_address_and_blocks_nonpublic_dns(monkeypatch):
    from legal.connectors.http_fetcher import _connect_public_address

    opened = []

    class Socket:
        def settimeout(self, timeout):
            assert 0 < timeout <= 2

        def connect(self, address):
            opened.append(address)

    monkeypatch.setattr(socket, "socket", lambda *args: Socket())
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
    ])
    _connect_public_address(("www.courts.maine.gov", 443), 2)
    assert opened == [("93.184.216.34", 443)]
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
    ])
    with pytest.raises(OSError, match="nonpublic"):
        _connect_public_address(("www.courts.maine.gov", 443), 2)
    assert len(opened) == 1
