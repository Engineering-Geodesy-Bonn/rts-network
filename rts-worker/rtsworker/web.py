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
<meta name="theme-color" content="#1a1f26">
<title>RTS worker · {hostname}</title>
<style>
/* Colors and elements of the RTS dashboard (rts-dashboard/src/app.css) */
:root {{ --bg: #eceef1; --surface: #ffffff; --surface-2: #f5f6f8; --line: #d8dce2; --line-strong: #c3c9d1;
  --fg: #14181d; --muted: #5a6470; --accent: #1d5fc9; --accent-fg: #ffffff; --good: #137547; --bad: #c0261a;
  --good-soft: #e3f3ea; --bad-soft: #fbe6e3; --bar: #1a1f26; --bar-fg: #e9ecef; --bar-muted: #98a2ad; color-scheme: light;
  --mono: 'JetBrains Mono', 'SF Mono', ui-monospace, Menlo, Consolas, 'Liberation Mono', monospace; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg: #0d1014; --surface: #151a20; --surface-2: #1b2128; --line: #283039;
  --line-strong: #36404b; --fg: #e6e9ed; --muted: #98a2ad; --accent: #5b9bff; --accent-fg: #0d1014; --good: #49c07a;
  --bad: #f1675a; --good-soft: #112619; --bad-soft: #2f1512; --bar: #090b0e; --bar-fg: #e6e9ed; --bar-muted: #8a949f;
  color-scheme: dark; }} }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--fg); font: 14px/1.45 system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif; }}
.label {{ font-size: 11px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); }}
.num {{ font-family: var(--mono); font-variant-numeric: tabular-nums; font-size: .93em; letter-spacing: -.01em; }}
header {{ background: var(--bar); color: var(--bar-fg); padding-top: env(safe-area-inset-top); }}
header div {{ max-width: 640px; margin: 0 auto; height: 44px; display: flex; align-items: center; gap: 12px; padding: 0 16px; }}
header .label, header .sep {{ color: var(--bar-muted); }}
header b {{ font-size: 13px; }}
main {{ max-width: 640px; margin: 0 auto; padding: 16px; display: grid; gap: 16px; }}
.intro {{ color: var(--muted); font-size: 13px; margin: 0; }}
.panel {{ background: var(--surface); border: 1px solid var(--line); border-radius: 6px; overflow: hidden; }}
.panel > h2 {{ margin: 0; min-height: 40px; display: flex; align-items: center; padding: 6px 12px; background: var(--surface-2); border-bottom: 1px solid var(--line); }}
.body {{ padding: 12px; }}
.row {{ display: grid; grid-template-columns: 1fr 120px; gap: 12px; margin-bottom: 12px; }}
label > span {{ display: block; margin-bottom: 4px; }}
input {{ width: 100%; background: var(--surface); color: var(--fg); border: 1px solid var(--line-strong); border-radius: 5px; padding: .4rem .55rem; font-size: 14px; }}
input:focus {{ outline: 2px solid var(--accent); outline-offset: -1px; }}
#port {{ font-family: var(--mono); }}
.actions {{ display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }}
button {{ height: 32px; padding: 0 12px; font: 500 13px system-ui, sans-serif; border-radius: 5px; border: 1px solid var(--line-strong); background: var(--surface); color: var(--fg); cursor: pointer; }}
button:hover {{ background: var(--surface-2); }}
button.primary {{ background: var(--accent); border-color: transparent; color: var(--accent-fg); }}
button.primary:hover {{ filter: brightness(1.1); }}
.hint {{ color: var(--muted); font-size: 12px; margin: 0; }}
.source {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--line); }}
.source button {{ margin-left: auto; }}
dl {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1px; background: var(--line); margin: 0; }}
dl > div {{ background: var(--surface); padding: 8px 12px; min-width: 0; }}
dl > div.wide {{ grid-column: 1 / -1; }}
dd {{ margin: 2px 0 0; overflow-wrap: anywhere; }}
.tag {{ display: inline-block; border-radius: 3px; padding: 1px 6px; font: 600 11px system-ui, sans-serif; letter-spacing: .04em; text-transform: uppercase; white-space: nowrap; vertical-align: 1px; }}
.tag.ok {{ background: var(--good-soft); color: var(--good); }}
.tag.bad {{ background: var(--bad-soft); color: var(--bad); }}
.msg {{ margin: 0; padding: 8px 12px; border-radius: 5px; font-size: 13px; }}
.msg.ok {{ background: var(--good-soft); color: var(--good); }}
.msg.bad {{ background: var(--bad-soft); color: var(--bad); }}
@media (max-width: 480px) {{ .row {{ grid-template-columns: 1fr 96px; }} dl {{ grid-template-columns: 1fr; }} }}
</style></head>
<body>
<header><div><span class="label">RTS Network</span><span class="sep">/</span><b>Worker · {hostname}</b></div></header>
<main>
{message}
<section class="panel">
<h2 class="label">API server</h2>
<div class="body">
<form method="post" action="/">
<div class="row">
<label><span class="label">Host</span><input id="host" name="host" value="{host}" required autocomplete="off" spellcheck="false"></label>
<label><span class="label">Port</span><input id="port" name="port" value="{port}" required inputmode="numeric"></label>
</div>
<div class="actions"><button class="primary" type="submit">Save</button></div>
</form>
<form method="post" action="/reset" class="source"><p class="hint">{source}</p>{reset}</form>
</div>
</section>
<p class="intro">Changes apply to all workers of this Raspberry Pi within a second, also during a measurement.
During a measurement only enter a new address of the same API server: another server does not know the running job.</p>
<section class="panel">
<h2 class="label">This worker</h2>
<dl>
<div><dt class="label">API in use</dt><dd><span class="num">{in_use}</span> {reachable}</dd></div>
<div><dt class="label">Upload</dt><dd>{upload}</dd></div>
<div><dt class="label">Job</dt><dd>{job}</dd></div>
<div><dt class="label">Version</dt><dd class="num">v{version}</dd></div>
<div class="wide"><dt class="label">Last error</dt><dd>{error}</dd></div>
<div class="wide"><dt class="label">Worker ID</dt><dd class="num">{worker_id}</dd></div>
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
            reachable='<span class="tag ok">reachable</span>' if reachable else '<span class="tag bad">not reachable</span>',
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
