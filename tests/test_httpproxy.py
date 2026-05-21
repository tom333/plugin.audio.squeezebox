import pytest
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from httpproxy import ProxyRunner


@pytest.fixture
def runner():
    r = ProxyRunner(host="127.0.0.1", try_ports=range(52000, 52050))
    r.start()
    yield r
    r.stop()


def _get(runner, path, headers=None, method="GET"):
    url = "http://127.0.0.1:%d%s" % (runner.get_port(), path)
    req = Request(url, headers=headers or {}, method=method)
    return urlopen(req, timeout=5)


def test_get_track_returns_wav_header(runner):
    resp = _get(runner, "/track/3")
    body = resp.read(12)
    assert body[:4] == b"RIFF"
    assert body[8:12] == b"WAVE"


def test_head_track_returns_content_length(runner):
    resp = _get(runner, "/track/10", method="HEAD")
    assert resp.status == 200
    assert int(resp.headers["Content-Length"]) > 44


def test_range_request_returns_206(runner):
    resp = _get(runner, "/track/3", headers={"Range": "bytes=0-10"})
    assert resp.status == 206
    assert resp.headers["Content-Range"].startswith("bytes 0-10/")


def test_radio_endpoint(runner):
    resp = _get(runner, "/track/radio")
    body = resp.read(4)
    assert body == b"RIFF"


def test_disallowed_method_405(runner):
    with pytest.raises(HTTPError) as exc_info:
        _get(runner, "/track/3", method="POST")
    assert exc_info.value.code == 405


def test_unknown_path_404(runner):
    with pytest.raises(HTTPError) as exc_info:
        _get(runner, "/notatrack/3")
    assert exc_info.value.code == 404
