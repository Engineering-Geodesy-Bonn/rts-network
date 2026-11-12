"""Minimal web page to change the API address of the workers of this device during operation.

The address is stored in `api.json` next to the outbox, which all workers of a device share.
Every worker watches that file and switches to the new address within a second, so the page
only needs to be served by one of them: the first worker that gets the port serves it.
"""

import html
import ipaddress
import json
import logging
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from rtsworker import config
from rtsworker.client import ApiClient
from rtsworker.state import STATE

logger = logging.getLogger(__name__)

HOSTNAME = re.compile(r"^(?=.{1,253}$)[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$")
WATCH_INTERVAL = 1.0


def validate(host: str, port: str) -> tuple[str, int]:
    """Returns the cleaned address or raises ValueError with a message for the user."""
    host = host.strip()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not HOSTNAME.match(host):
            raise ValueError("The host must be an IP address or a host name.") from None
    try:
        number = int(port.strip())
    except ValueError:
        raise ValueError("The port must be a number.") from None
    if not 1 <= number <= 65535:
        raise ValueError("The port must be between 1 and 65535.")
    return host, number


class ApiSettings:
    """The API address saved on the page (overrides API_HOST/API_PORT of the environment)."""

    def __init__(self, path: str = config.API_SETTINGS_PATH, default_host: str = config.API_HOST, default_port: int = config.API_PORT):
        self.path = path
        self.default = (default_host, default_port)

    def saved(self) -> tuple[str, int] | None:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            return validate(str(data["host"]), str(data["port"]))
        except FileNotFoundError:
            return None
        except (OSError, ValueError, KeyError, TypeError) as e:
            logger.error("Ignoring invalid API settings in %s: %r", self.path, e)
            return None

    def current(self) -> tuple[str, int]:
        return self.saved() or self.default

    def save(self, host: str, port: int) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        tmp = f"{self.path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"host": host, "port": port, "saved_at": time.time()}, f)
        os.replace(tmp, self.path)  # atomic: other workers never read a half written file

    def reset(self) -> None:
        try:
            os.remove(self.path)
        except FileNotFoundError:
            pass

    def _stamp(self) -> float | None:
        try:
            return os.stat(self.path).st_mtime_ns
        except OSError:
            return None

    def watch(self, client: ApiClient, stop: threading.Event) -> None:
        """Applies the saved address to the client now and whenever the file changes."""
        stamp = object()
        while not stop.is_set():
            current = self._stamp()
            if current != stamp:
                stamp = current
                host, port = self.current()
                if (host, port) != (client.host, client.port):
                    logger.info("API address changed to %s:%d", host, port)
                    client.set_target(host, port)
            stop.wait(WATCH_INTERVAL)


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>RTS worker · {hostname}</title>
<style>
:root {{ color-scheme: light dark; --bg: #f6f7f9; --fg: #1d2330; --muted: #667085; --line: #d5d9e0; --card: #fff;
  --accent: #2f7ef5; --good: #2b9a3e; --bad: #d92d20; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg: #12151b; --fg: #e6e8ec; --muted: #98a2b3; --line: #2c323d; --card: #1a1e26; }} }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--fg); font: 15px/1.45 system-ui, sans-serif; }}
main {{ max-width: 520px; margin: 0 auto; padding: 24px 16px; }}
h1 {{ font-size: 18px; margin: 0 0 4px; }}
.sub {{ color: var(--muted); margin: 0 0 20px; font-size: 13px; }}
section {{ background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
h2 {{ font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); margin: 0 0 12px; }}
label {{ display: block; font-size: 13px; color: var(--muted); margin-bottom: 4px; }}
input {{ width: 100%; padding: 8px 10px; font: inherit; color: inherit; background: var(--bg); border: 1px solid var(--line); border-radius: 6px; }}
.row {{ display: grid; grid-template-columns: 1fr 110px; gap: 12px; margin-bottom: 14px; }}
button {{ font: inherit; padding: 8px 14px; border-radius: 6px; border: 1px solid var(--line); background: var(--card); color: inherit; cursor: pointer; }}
button.primary {{ background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 600; }}
.actions {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
dl {{ display: grid; grid-template-columns: max-content 1fr; gap: 6px 16px; margin: 0; font-size: 14px; }}
dt {{ color: var(--muted); }} dd {{ margin: 0; font-family: ui-monospace, Menlo, Consolas, monospace; word-break: break-all; }}
.ok {{ color: var(--good); font-weight: 600; }} .bad {{ color: var(--bad); font-weight: 600; }}
.msg {{ padding: 10px 12px; border-radius: 6px; margin-bottom: 16px; border: 1px solid; }}
.msg.ok {{ border-color: var(--good); }} .msg.bad {{ border-color: var(--bad); }}
.hint {{ color: var(--muted); font-size: 13px; margin: 12px 0 0; }}
</style></head>
<body><main>
<h1>RTS worker · {hostname}</h1>
<p class="sub">Changes apply to all workers of this device within a second, also during a measurement.
During a measurement only enter a new address of the same API server: another server does not know the running job.</p>
{message}
<section>
<h2>API server</h2>
<form method="post" action="/">
<div class="row">
<div><label for="host">Host</label><input id="host" name="host" value="{host}" required autocomplete="off" spellcheck="false"></div>
<div><label for="port">Port</label><input id="port" name="port" value="{port}" required inputmode="numeric"></div>
</div>
<div class="actions"><button class="primary" type="submit">Save</button></div>
</form>
<form method="post" action="/reset"><p class="hint">{source}</p>{reset}</form>
</section>
<section>
<h2>Status of this worker</h2>
<dl>
<dt>API in use</dt><dd>{in_use} {reachable}</dd>
<dt>Upload</dt><dd>{upload}</dd>
<dt>Job</dt><dd>{job}</dd>
<dt>Last error</dt><dd>{error}</dd>
<dt>Worker</dt><dd>{worker_id} · v{version}</dd>
</dl>
</section>
</main></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    settings: ApiSettings
    client: ApiClient

    def log_message(self, fmt: str, *args) -> None:
        logger.debug("%s %s", self.address_string(), fmt % args)

    def _send(self, status: int, body: str, headers: dict | None = None) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, query: str) -> None:
        self.send_response(303)
        self.send_header("Location", f"/?{query}")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _same_origin(self) -> bool:
        """Rejects form posts from other web pages (the page has no login)."""
        origin = self.headers.get("Origin")
        return not origin or origin == "null" or urlparse(origin).netloc == self.headers.get("Host")

    def do_GET(self) -> None:
        url = urlparse(self.path)
        if url.path != "/":
            self._send(404, "Not found")
            return
        query = parse_qs(url.query)
        self._send(200, self.render(saved=query.get("saved", [""])[0], error=query.get("error", [""])[0]))

    def do_POST(self) -> None:
        if not self._same_origin():
            self._send(403, "Forbidden")
            return
        url = urlparse(self.path)
        if url.path == "/reset":
            self.settings.reset()
            logger.info("API address reset to the default %s:%d", *self.settings.default)
            self._redirect("saved=reset")
            return
        if url.path != "/":
            self._send(404, "Not found")
            return
        length = min(int(self.headers.get("Content-Length") or 0), 4096)
        form = parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
        try:
            host, port = validate(form.get("host", [""])[0], form.get("port", [""])[0])
        except ValueError as e:
            self._send(400, self.render(error=str(e), host=form.get("host", [""])[0], port=form.get("port", [""])[0]))
            return
        try:
            self.settings.save(host, port)
        except OSError as e:
            self._send(500, self.render(error=f"Could not save: {e}"))
            return
        logger.info("API address set to %s:%d on the web page", host, port)
        self.client.set_target(host, port)  # this worker at once, the others via the file
        self._redirect("saved=1")

    def render(self, saved: str = "", error: str = "", host: str | None = None, port: str | None = None) -> str:
        current_host, current_port = self.settings.current()
        is_saved = self.settings.saved() is not None
        message = ""
        if error:
            message = f'<div class="msg bad">{html.escape(error)}</div>'
        elif saved == "reset":
            message = '<div class="msg ok">Reset to the address of the configuration (.env).</div>'
        elif saved:
            message = '<div class="msg ok">Saved.</div>'
        default = "{}:{}".format(*self.settings.default)
        if is_saved:
            source = f"Set on this page. The configuration (.env) has {html.escape(default)}."
            reset = '<button type="submit">Reset to configuration</button>'
        else:
            source = "From the configuration (.env)."
            reset = ""
        reachable = self.client.ping()
        state = STATE
        job = f"{state.job_type} {state.job_id[:8]}" if state.job_id else "idle"
        if state.outbox_backlog:
            upload = f"{state.outbox_backlog} measurements waiting" + ("" if state.uploader_connected else " · not connected")
        else:
            upload = "connected, nothing to send" if state.uploader_connected else "nothing to send"
        error = "–"
        if state.last_error:
            text = state.last_error if len(state.last_error) <= 160 else state.last_error[:157] + "…"
            error = f"{text} ({_age(time.time() - (state.last_error_at or time.time()))} ago)"
        return PAGE.format(
            hostname=html.escape(state.hostname),
            message=message,
            host=html.escape(host if host is not None else current_host, quote=True),
            port=html.escape(port if port is not None else str(current_port), quote=True),
            source=source,
            reset=reset,
            in_use=html.escape(f"{self.client.host}:{self.client.port}"),
            reachable='<span class="ok">reachable</span>' if reachable else '<span class="bad">not reachable</span>',
            upload=html.escape(upload),
            job=html.escape(job),
            error=html.escape(error),
            worker_id=html.escape(state.worker_id),
            version=html.escape(state.version),
        )


def _age(seconds: float) -> str:
    if seconds < 90:
        return f"{seconds:.0f} s"
    if seconds < 5400:
        return f"{seconds / 60:.0f} min"
    return f"{seconds / 3600:.1f} h"


def serve(settings: ApiSettings, client: ApiClient, port: int = config.WEB_PORT, host: str = "") -> ThreadingHTTPServer | None:
    """Serves the page in a background thread. None if the port is taken (another worker of this
    device serves it) or the page is disabled (port 0)."""
    if port <= 0:
        return None
    handler = type("BoundHandler", (Handler,), {"settings": settings, "client": client})
    try:
        server = ThreadingHTTPServer((host, port), handler)
    except OSError:
        logger.info("Settings page not served by this worker (port %d is in use, probably by another worker)", port)
        return None
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, name="web", daemon=True).start()
    logger.info("Settings page on http://%s:%d/", STATE.hostname, server.server_address[1])
    return server
