import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest

from rtsworker import web
from rtsworker.client import ApiClient
from rtsworker.web import ApiSettings, validate


@pytest.fixture
def page(tmp_path):
    settings = ApiSettings(str(tmp_path / "api.json"), "127.0.0.1", 9)
    client = ApiClient(*settings.current(), timeout=0.5)
    client.ping = lambda host=None: False  # the page shows whether the API answers
    server = web.serve(settings, client, port=_free_port(), host="127.0.0.1")
    yield settings, client, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def post(url: str, data: dict, headers: dict | None = None):
    request = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), headers=headers or {}, method="POST")
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def test_validate():
    assert validate(" 192.168.0.5 ", "8000") == ("192.168.0.5", 8000)
    assert validate("rts-api.local", "80") == ("rts-api.local", 80)
    for host, port in [("", "8000"), ("a b", "8000"), ("http://x", "8000"), ("x", "0"), ("x", "70000"), ("x", "abc")]:
        with pytest.raises(ValueError):
            validate(host, port)


def test_page_saves_and_resets(page):
    settings, client, url = page
    status, body = urllib.request.urlopen(url).status, urllib.request.urlopen(url).read().decode()
    assert status == 200 and 'value="127.0.0.1"' in body and "From the configuration" in body

    status, body = post(url + "/", {"host": "192.168.1.20", "port": "8001"})
    assert status == 200 and "Saved." in body  # redirected to the page
    assert json.load(open(settings.path))["host"] == "192.168.1.20"
    assert (client.host, client.port) == ("192.168.1.20", 8001)
    assert client.stream_url == "ws://192.168.1.20:8001/worker/stream"

    status, body = post(url + "/reset", {})
    assert status == 200 and settings.saved() is None and 'value="127.0.0.1"' in body


def test_page_rejects_invalid_and_foreign_posts(page):
    settings, client, url = page
    status, body = post(url + "/", {"host": "<script>", "port": "8000"})
    assert status == 400 and "IP address or a host name" in body and "<script>" not in body
    status, _ = post(url + "/", {"host": "1.2.3.4", "port": "8000"}, {"Origin": "http://evil.example"})
    assert status == 403
    assert settings.saved() is None and client.host == "127.0.0.1"


def test_other_workers_follow_the_file(tmp_path):
    settings = ApiSettings(str(tmp_path / "api.json"), "10.0.0.1", 8000)
    client = ApiClient(*settings.current())
    stop = threading.Event()
    web.WATCH_INTERVAL = 0.05
    threading.Thread(target=settings.watch, args=(client, stop), daemon=True).start()
    ApiSettings(settings.path).save("10.0.0.9", 9000)  # written by the worker that serves the page
    deadline = time.time() + 2
    while (client.host, client.port) != ("10.0.0.9", 9000):
        assert time.time() < deadline
        time.sleep(0.02)
    settings.reset()
    while client.host != "10.0.0.1":
        assert time.time() < deadline
        time.sleep(0.02)
    stop.set()
