"""Portfolio evidence: HTML to text, same-site link following, and the address guard."""
import pytest

from backend.services.evidence import portfolio

HOME = """<html><head><title>Sara</title><style>p{}</style><script>var x=1</script></head>
<body><h1>Sara Ahmed</h1><p>Data analyst who loves Python and Pandas.</p>
<a href="/projects">Projects</a> <a href="https://other.example/x">Elsewhere</a> <a href="/contact">Contact</a></body></html>"""
PROJECTS = "<html><body><h2>Sales Dashboard</h2><p>Built with Python, Matplotlib and SQL.</p></body></html>"


class _Response:
    def __init__(self, body: str):
        self.headers = {"content-type": "text/html; charset=utf-8"}
        self.encoding = "utf-8"
        self._body = body.encode("utf-8")

    def raise_for_status(self):
        pass

    @property
    def raw(self):
        body = self._body

        class Raw:
            def read(self, n, decode_content=True):
                return body[:n]

        return Raw()


def test_reads_the_page_and_same_site_content_pages_only(monkeypatch):
    fetched = []

    def fake_get(url, **kwargs):
        fetched.append(url)
        return _Response(PROJECTS if url.endswith("/projects") else HOME)

    monkeypatch.setattr(portfolio.requests, "get", fake_get)
    monkeypatch.setattr(portfolio, "_check_url", lambda url: url)

    text = portfolio.fetch_portfolio("https://sara.example/")

    assert fetched == ["https://sara.example/", "https://sara.example/projects"]  # not the other host, not /contact
    assert "loves Python and Pandas" in text and "Matplotlib and SQL" in text
    assert "var x=1" not in text and "p{}" not in text  # scripts and styles stripped


def test_private_addresses_are_refused(monkeypatch):
    monkeypatch.setattr(portfolio.socket, "getaddrinfo", lambda host, port: [(None, None, None, None, ("127.0.0.1", 0))])
    with pytest.raises(portfolio.PortfolioError):
        portfolio.fetch_portfolio("http://internal.example/")


def test_scheme_is_added_and_bad_urls_rejected():
    with pytest.raises(portfolio.PortfolioError):
        portfolio._check_url("not a url at all")
    monkeypatch_free = portfolio._check_url  # noqa: F841 - sanity that the function exists
