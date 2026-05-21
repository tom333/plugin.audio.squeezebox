# -*- coding: utf-8 -*-
"""HTTP proxy that serves a silent PCM WAV stream to Kodi.

Uses stdlib wsgiref instead of CherryPy. Bound to 127.0.0.1 and only
serves GET/HEAD from allowed IPs.
"""
import socket
import threading
from wsgiref.simple_server import make_server, WSGIRequestHandler

from utils import log_msg
from wav import build_wav_header, silent_stream_chunks


class HTTPProxyError(Exception):
    pass


class _QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        pass


def _find_free_port(host, port_list):
    for port in port_list:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind((host, port))
            s.close()
            return port
        except OSError:
            s.close()
            continue
    raise HTTPProxyError("Cannot find a free port. Tried: %s" %
                         ",".join(str(p) for p in port_list))


def _parse_range(header_value, filesize):
    """Return (start, end, length) for a Range header, or None if absent/invalid."""
    if not header_value or not header_value.startswith("bytes="):
        return None
    spec = header_value[len("bytes="):]
    start_s, _, end_s = spec.partition("-")
    try:
        start = int(start_s) if start_s else 0
    except ValueError:
        return None
    try:
        end = int(end_s) if end_s else filesize - 1
    except ValueError:
        end = filesize - 1
    if start < 0 or start >= filesize:
        return None
    end = min(end, filesize - 1)
    return start, end, end - start + 1


def _range_chunks(header, total_size, start, end):
    """Yield bytes [start:end+1] of (header + zero-payload of total_size - len(header))."""
    header_len = len(header)
    cursor = start
    if cursor < header_len:
        slice_end = min(end + 1, header_len)
        yield header[cursor:slice_end]
        cursor = slice_end
    if cursor <= end:
        remaining = end - cursor + 1
        chunk = b"\x00" * min(remaining, 8192)
        while remaining > 0:
            if remaining >= len(chunk):
                yield chunk
                remaining -= len(chunk)
            else:
                yield b"\x00" * remaining
                remaining = 0


class _SilentStreamApp:
    """WSGI app: GET/HEAD /track/<duration|"radio"> → silent WAV."""

    def __init__(self, allowed_ips, allow_ranges=True):
        self.allowed_ips = set(allowed_ips)
        self.allow_ranges = allow_ranges

    def __call__(self, environ, start_response):
        method = environ["REQUEST_METHOD"].upper()
        remote = environ.get("REMOTE_ADDR", "")
        if remote not in self.allowed_ips:
            start_response("403 Forbidden", [("Content-Type", "text/plain")])
            return [b"forbidden"]
        if method not in ("GET", "HEAD"):
            start_response("405 Method Not Allowed", [("Content-Type", "text/plain")])
            return [b"method not allowed"]

        path = environ.get("PATH_INFO", "").strip("/")
        parts = path.split("/")
        if len(parts) != 2 or parts[0] != "track":
            start_response("404 Not Found", [("Content-Type", "text/plain")])
            return [b"not found"]

        track_id = parts[1]
        try:
            duration = int(track_id)
            is_radio = False
        except ValueError:
            duration = 3600
            is_radio = True

        header, total_size = build_wav_header(duration)
        payload_size = total_size - len(header)
        range_header = environ.get("HTTP_RANGE", "") if self.allow_ranges else ""

        if is_radio:
            # Note: 'Connection' is a hop-by-hop header and forbidden by
            # wsgiref; the server manages connection close itself.
            headers = [
                ("Content-Type", "audio/x-wav"),
            ]
            if method == "HEAD":
                start_response("200 OK", headers)
                return [b""]
            start_response("200 OK", headers)
            return silent_stream_chunks(header, payload_size)

        rng = _parse_range(range_header, total_size) if range_header else None
        if rng is None:
            headers = [
                ("Content-Type", "audio/x-wav"),
                ("Content-Length", str(total_size)),
                ("Accept-Ranges", "bytes"),
            ]
            if method == "HEAD":
                start_response("200 OK", headers)
                return [b""]
            start_response("200 OK", headers)
            return silent_stream_chunks(header, payload_size)

        start, end, length = rng
        headers = [
            ("Content-Type", "audio/x-wav"),
            ("Content-Length", str(length)),
            ("Accept-Ranges", "bytes"),
            ("Content-Range", "bytes %d-%d/%d" % (start, end, total_size)),
        ]
        if method == "HEAD":
            start_response("206 Partial Content", headers)
            return [b""]
        start_response("206 Partial Content", headers)
        return _range_chunks(header, total_size, start, end)


class ProxyRunner(threading.Thread):
    """Background WSGI server. Signature matches the previous CherryPy version."""

    def __init__(self, host="127.0.0.1", try_ports=range(51100, 51150),
                 allowed_ips=("127.0.0.1",), allow_ranges=True):
        super().__init__(daemon=True)
        self._host = host
        self._port = _find_free_port(host, list(try_ports))
        self._app = _SilentStreamApp(allowed_ips, allow_ranges=allow_ranges)
        self._server = make_server(host, self._port, self._app,
                                   handler_class=_QuietHandler)

    def run(self):
        try:
            self._server.serve_forever(poll_interval=0.5)
        except Exception as exc:
            log_msg("ProxyRunner error: %s" % exc)

    def get_port(self):
        return self._port

    def get_host(self):
        return self._host

    def ready_wait(self):
        return

    def stop(self):
        try:
            self._server.shutdown()
        except Exception:
            pass
        try:
            self._server.server_close()
        except Exception:
            pass
        self.join(1)
