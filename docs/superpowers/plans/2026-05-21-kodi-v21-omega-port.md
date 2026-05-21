# Kodi v21 Omega Port — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate `plugin.audio.squeezebox` from Kodi v18 Leia (Python 2.7, `xbmc.python 2.13.0`) to Kodi v21 Omega (Python 3.11, `xbmc.python 3.0.3`), replacing the vendored Python-2-only CherryPy with stdlib `wsgiref`.

**Architecture:** Two-pass conversion. Pass 1 is mechanical Py2→Py3 + Kodi API rename, file by file, one commit per file so any regression is bisectable. Pass 2 is the only structural change: rewrite `httpproxy.py` against `wsgiref` and delete `resources/lib/cherrypy/` (≈9000 vendored files). Pure-function extracts (WAV header generation, LMS UDP parsing) get unit tests because they're testable without Kodi; everything else gets manual smoke tests in a running Kodi 21.

**Tech Stack:** Python 3.11, Kodi 21 Omega addon API (`xbmc`, `xbmcgui`, `xbmcplugin`, `xbmcaddon`, `xbmcvfs`), `requests`, `script.module.simplecache`, `wsgiref` (stdlib), `pytest` for unit tests, `kodistubs` for IDE/type hints.

---

## File Structure

### Files modified (mechanical Py3 conversion)
- `addon.xml` — bump deps
- `service.py` — log levels
- `resources/lib/utils.py` — log defaults, unicode→str, `.decode` removal, subprocess attr
- `resources/lib/lmsserver.py` — imports, `.iteritems`, bytes-aware UDP discovery, latent `cmd` bug
- `resources/lib/main_service.py` — `.decode` removal, subprocess attr
- `resources/lib/plugin_content.py` — urllib imports, `.decode` removal, `.iteritems`, ListItem art API
- `resources/lib/player_monitor.py` — urllib import, ListItem art API

### Files rewritten
- `resources/lib/httpproxy.py` — wsgiref-based, bytes-safe WAV stream

### Files deleted
- `resources/lib/cherrypy/` (entire vendored tree)

### Files created
- `tests/conftest.py` — Kodi module stubs so imports don't crash at collection
- `tests/test_wav_header.py` — header bytes & sizing
- `tests/test_silent_stream.py` — chunked generator behavior
- `tests/test_lms_discovery.py` — UDP payload parsing
- `tests/test_parse_duration.py` — duration coercion
- `pytest.ini` — project config

---

## Phase 0 — Branch & baseline

### Task 0: Create feature branch

**Files:** none

- [ ] **Step 1: Verify clean working tree**

Run: `git status`
Expected: `nothing to commit, working tree clean` on `master`.

- [ ] **Step 2: Create branch**

Run: `git checkout -b port/kodi-v21-omega`
Expected: `Switched to a new branch 'port/kodi-v21-omega'`.

- [ ] **Step 3: Sanity baseline**

Run: `git log --oneline -5`
Expected: list starts with `a51768d Update README.md`.

---

## Phase 1 — Test infrastructure

### Task 1: Add pytest scaffolding with Kodi module stubs

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `pytest.ini`
- Create: `requirements-dev.txt`

The Kodi modules (`xbmc`, `xbmcaddon`, etc.) only exist inside the Kodi runtime. Tests must stub them before any code in `resources/lib/` is imported.

- [ ] **Step 1: Create `requirements-dev.txt`**

```
pytest>=8.0
kodistubs>=21.0
```

- [ ] **Step 2: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
pythonpath = resources/lib tests
addopts = -ra --strict-markers
```

- [ ] **Step 3: Create empty `tests/__init__.py`**

```python
```

- [ ] **Step 4: Create `tests/conftest.py`**

```python
"""Stub Kodi modules so resources/lib code is importable in pytest."""
import sys
import types


def _make_stub(name):
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


xbmc = _make_stub("xbmc")
xbmc.LOGDEBUG = 0
xbmc.LOGINFO = 1
xbmc.LOGWARNING = 2
xbmc.LOGERROR = 3
xbmc.LOGFATAL = 4
xbmc.PLAYLIST_MUSIC = 0
xbmc.ISO_639_1 = 0
xbmc.log = lambda msg, level=1: None
xbmc.sleep = lambda ms: None


class _Monitor:
    def waitForAbort(self, *a, **kw):
        return True

    def abortRequested(self):
        return False


xbmc.Monitor = _Monitor
xbmc.getInfoLabel = lambda *a, **kw: ""
xbmc.getCondVisibility = lambda *a, **kw: False
xbmc.getLanguage = lambda *a, **kw: "en"
xbmc.executebuiltin = lambda *a, **kw: None


class _Player:
    def __init__(self, *a, **kw):
        pass


xbmc.Player = _Player


class _PlayList:
    def __init__(self, *a, **kw):
        pass

    def getposition(self):
        return 0

    def __len__(self):
        return 0


xbmc.PlayList = _PlayList

xbmcgui = _make_stub("xbmcgui")


class _ListItem:
    def __init__(self, *a, **kw):
        pass

    def setInfo(self, *a, **kw):
        pass

    def setArt(self, *a, **kw):
        pass

    def setProperty(self, *a, **kw):
        pass

    def setContentLookup(self, *a, **kw):
        pass


xbmcgui.ListItem = _ListItem


class _Window:
    def __init__(self, *a, **kw):
        pass

    def getProperty(self, *a, **kw):
        return ""

    def setProperty(self, *a, **kw):
        pass

    def clearProperty(self, *a, **kw):
        pass


xbmcgui.Window = _Window
xbmcgui.Dialog = lambda: None

xbmcaddon = _make_stub("xbmcaddon")


class _Addon:
    def __init__(self, *a, **kw):
        pass

    def getSetting(self, *a, **kw):
        return ""

    def setSetting(self, *a, **kw):
        pass

    def getLocalizedString(self, *a, **kw):
        return ""


xbmcaddon.Addon = _Addon

xbmcplugin = _make_stub("xbmcplugin")
xbmcvfs = _make_stub("xbmcvfs")
xbmcvfs.exists = lambda *a, **kw: False

simplecache = _make_stub("simplecache")


class _SimpleCache:
    def get(self, *a, **kw):
        return None

    def set(self, *a, **kw):
        pass


simplecache.SimpleCache = _SimpleCache
```

- [ ] **Step 5: Verify pytest collects with no errors**

Run: `python -m pip install -r requirements-dev.txt && python -m pytest --collect-only`
Expected: `collected 0 items` (no test files yet) and no import errors.

- [ ] **Step 6: Commit**

```bash
git add tests/__init__.py tests/conftest.py pytest.ini requirements-dev.txt
git commit -m "test: add pytest scaffolding with Kodi module stubs"
```

---

## Phase 2 — `addon.xml` bump

### Task 2: Update addon manifest for Omega

**Files:**
- Modify: `addon.xml:2-9`

- [ ] **Step 1: Open and replace the `<requires>` block**

Replace the file contents with:

```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
	<addon id="plugin.audio.squeezebox" name="Squeezebox for Kodi" version="2.0.0" provider-name="marcelveldt">
	<requires>
		<import addon="xbmc.python" version="3.0.3"/>
		<import addon="xbmc.addon" version="19.0.0"/>
        <import addon="script.module.requests" version="2.31.0"/>
        <import addon="script.module.simplecache" version="2.0.0"/>
	</requires>
	<extension point="xbmc.python.pluginsource" library="plugin.py">
        <provides>audio</provides>
    </extension>
	<extension library="service.py" point="xbmc.service" start="login" />

	<extension point="xbmc.addon.metadata">
		<summary lang="en">Squeezelite Player for Kodi</summary>
        <description lang="en">Turn Kodi into a squeezebox player. Playback provided by squeezelite.</description>
		<language></language>
		<platform>all</platform>
		<license>Apache v2.0</license>
		<forum></forum>
		<website></website>
		<source>https://github.com/marcelveldt/plugin.audio.squeezebox</source>
		<news>v2.0.0 — Ported to Kodi 21 Omega (Python 3). Dropped script.module.six. Replaced vendored CherryPy with stdlib wsgiref.</news>
	</extension>
</addon>
```

Changes: `xbmc.python` 2.13.0→3.0.3; `xbmc.addon` 12.0.0→19.0.0; removed `script.module.six`; bumped `requests` 2.3.0→2.31.0 and `simplecache` 1.0.0→2.0.0; addon version 1.0.19→2.0.0; added `<news>`.

- [ ] **Step 2: Commit**

```bash
git add addon.xml
git commit -m "build: bump addon.xml to xbmc.python 3.0.3 for Kodi 21 Omega"
```

---

## Phase 3 — Pure-function extracts with tests

These three tasks separate the testable logic from Kodi-coupled code, so we get a real safety net for the riskiest parts.

### Task 3: Extract & test WAV header generation

**Files:**
- Create: `resources/lib/wav.py`
- Create: `tests/test_wav_header.py`

The current `httpproxy.py:_get_wave_header` produces Py2 `str` bytes that break in Py3. Extract it as a pure function operating on `bytes`, with full test coverage, before the `httpproxy.py` rewrite consumes it.

- [ ] **Step 1: Create failing test `tests/test_wav_header.py`**

```python
import struct

from wav import build_wav_header


def test_header_starts_with_riff():
    header, total_size = build_wav_header(duration=10)
    assert header[:4] == b"RIFF"
    assert header[8:12] == b"WAVE"


def test_header_format_chunk_is_pcm_stereo_44100_16bit():
    header, _ = build_wav_header(duration=10)
    fmt_chunk = header[12:36]
    assert fmt_chunk[:4] == b"fmt "
    (chunk_size, audio_format, channels, samplerate, byterate,
     blockalign, bitspersample) = struct.unpack("<LHHLLHH", fmt_chunk[4:])
    assert chunk_size == 16
    assert audio_format == 1  # PCM
    assert channels == 2
    assert samplerate == 44100
    assert bitspersample == 16
    assert byterate == 44100 * 2 * 2
    assert blockalign == 2 * 2


def test_total_size_matches_data_chunk():
    duration = 5
    header, total_size = build_wav_header(duration=duration)
    # 2 extra seconds added for crossfade
    expected_samples = 44100 * (duration + 2)
    expected_datasize = expected_samples * 2 * 2
    # total_size = 44 byte header + data
    assert total_size == 44 + expected_datasize


def test_header_returns_bytes_not_str():
    header, _ = build_wav_header(duration=1)
    assert isinstance(header, bytes)
```

- [ ] **Step 2: Run test, verify it fails**

Run: `python -m pytest tests/test_wav_header.py -v`
Expected: `ModuleNotFoundError: No module named 'wav'`.

- [ ] **Step 3: Create `resources/lib/wav.py`**

```python
"""Pure-function WAV header builder for the silent-stream HTTP proxy."""
import struct


def build_wav_header(duration):
    """Build a PCM WAV header for `duration` seconds of stereo 44.1 kHz 16-bit audio.

    Adds 2 seconds of padding to avoid Kodi crossfade truncation. Returns
    (header_bytes, total_file_size_bytes).
    """
    duration += 2
    channels = 2
    samplerate = 44100
    bitspersample = 16
    numsamples = samplerate * duration
    bytes_per_sample = bitspersample // 8
    datasize = numsamples * channels * bytes_per_sample

    fmt_chunk = struct.pack(
        "<4sLHHLLHH",
        b"fmt ",
        16,
        1,
        channels,
        samplerate,
        samplerate * channels * bytes_per_sample,
        channels * bytes_per_sample,
        bitspersample,
    )
    data_chunk = struct.pack("<4sL", b"data", int(datasize))

    riff_size = 4 + len(fmt_chunk) + len(data_chunk) + datasize
    main_header = struct.pack("<4sL4s", b"RIFF", riff_size, b"WAVE")

    header = main_header + fmt_chunk + data_chunk
    total_size = riff_size + 8  # +8 for "RIFF" + size field
    return header, total_size
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `python -m pytest tests/test_wav_header.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add resources/lib/wav.py tests/test_wav_header.py
git commit -m "refactor: extract WAV header builder as pure bytes-safe function"
```

### Task 4: Extract & test silent-stream chunk generator

**Files:**
- Modify: `resources/lib/wav.py` (add generator)
- Create: `tests/test_silent_stream.py`

- [ ] **Step 1: Create failing test `tests/test_silent_stream.py`**

```python
from wav import silent_stream_chunks


def test_yields_header_first():
    chunks = list(silent_stream_chunks(b"HEADER", payload_size=10, max_buffer=4))
    assert chunks[0] == b"HEADER"


def test_payload_is_zero_bytes_summing_to_size():
    chunks = list(silent_stream_chunks(b"HDR", payload_size=10, max_buffer=4))
    payload = b"".join(chunks[1:])
    assert len(payload) == 10
    assert payload == b"\x00" * 10


def test_chunks_respect_max_buffer():
    chunks = list(silent_stream_chunks(b"HDR", payload_size=10, max_buffer=4))
    # header + ceil(10/4) = 1 + 3 = 4
    assert len(chunks) == 4
    assert all(len(c) <= 4 for c in chunks[1:])


def test_zero_payload():
    chunks = list(silent_stream_chunks(b"HDR", payload_size=0, max_buffer=4))
    assert chunks == [b"HDR"]
```

- [ ] **Step 2: Run test, verify it fails**

Run: `python -m pytest tests/test_silent_stream.py -v`
Expected: ImportError on `silent_stream_chunks`.

- [ ] **Step 3: Add the generator to `resources/lib/wav.py`**

Append:

```python
def silent_stream_chunks(header, payload_size, max_buffer=8192):
    """Yield the WAV header followed by `payload_size` zero bytes in chunks of
    at most `max_buffer` bytes."""
    yield header
    written = 0
    zeros = b"\x00" * max_buffer
    while written < payload_size:
        remaining = payload_size - written
        if remaining >= max_buffer:
            yield zeros
            written += max_buffer
        else:
            yield b"\x00" * remaining
            written = payload_size
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `python -m pytest tests/test_silent_stream.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add resources/lib/wav.py tests/test_silent_stream.py
git commit -m "feat: add bytes-safe silent stream chunk generator"
```

### Task 5: Extract & test LMS UDP discovery parsing

**Files:**
- Create: `resources/lib/lms_discovery.py`
- Create: `tests/test_lms_discovery.py`

`LMSDiscovery.update` in `lmsserver.py:296-323` mixes socket I/O with payload parsing. Extracting the parser makes the bytes/str migration testable.

- [ ] **Step 1: Create failing test `tests/test_lms_discovery.py`**

```python
import pytest

from lms_discovery import parse_lms_response, LMS_QUERY


def test_query_is_bytes():
    assert LMS_QUERY == b"eJSON\x00"


def test_parse_extracts_port_from_json_field():
    # LMS responds with "E" followed by tag-length-value triples;
    # JSON tag is "JSON", value is the port as ASCII.
    payload = b"E" + b"JSON" + b"\x049000"
    assert parse_lms_response(payload) == 9000


def test_parse_returns_none_for_non_E_payload():
    assert parse_lms_response(b"XJSON\x049000") is None


def test_parse_returns_none_when_no_json_tag():
    assert parse_lms_response(b"E") is None


def test_parse_handles_extra_tags():
    # Real LMS responses may carry additional tags before/after JSON
    payload = b"E" + b"NAME\x06Server" + b"JSON\x049000"
    assert parse_lms_response(payload) == 9000
```

- [ ] **Step 2: Run test, verify it fails**

Run: `python -m pytest tests/test_lms_discovery.py -v`
Expected: ImportError on `lms_discovery`.

- [ ] **Step 3: Create `resources/lib/lms_discovery.py`**

```python
"""LMS UDP discovery — parse the server reply payload.

LMS broadcast protocol: client sends b"eJSON\\x00" to port 3483.
Server replies starting with b"E" followed by tag/length/value triples.
The JSON tag value is the JSON-RPC port (ASCII).
"""

LMS_QUERY = b"eJSON\x00"
LMS_PORT = 3483


def parse_lms_response(data):
    """Return the JSON-RPC port from an LMS discovery reply, or None."""
    if not data or not data.startswith(b"E"):
        return None
    idx = data.find(b"JSON")
    if idx < 0 or idx + 5 > len(data):
        return None
    length = data[idx + 4]
    start = idx + 5
    end = start + length
    if end > len(data):
        return None
    try:
        return int(data[start:end])
    except ValueError:
        return None
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `python -m pytest tests/test_lms_discovery.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add resources/lib/lms_discovery.py tests/test_lms_discovery.py
git commit -m "refactor: extract LMS UDP discovery parser as testable bytes-aware function"
```

---

## Phase 4 — Mechanical Py3 conversion (file by file)

One commit per file so regressions are bisectable.

### Task 6: Convert `resources/lib/utils.py`

**Files:**
- Modify: `resources/lib/utils.py`

Changes from current state (line refs against current master):
- L22-25: drop `simplejson` fallback
- L39: `xbmc.LOGNOTICE` default → `xbmc.LOGINFO`
- L41: `unicode` → `str`; `.encode('utf-8')` becomes optional (xbmc.log accepts str)
- L73: drop `.decode("utf-8")` on `getSetting`
- L110, L131: `subprocess._subprocess.STARTF_USESHOWWINDOW` → `subprocess.STARTF_USESHOWWINDOW`
- L122: drop `.decode("utf-8")` on `getSetting`
- L113-117: `stdout.split("\n")` works on bytes too, but `subprocess.Popen` without `text=True` returns bytes — pass `text=True` for cleaner str handling

- [ ] **Step 1: Edit imports/json block (replace lines 11-26)**

Replace:

```python
import xbmc
import xbmcvfs
import xbmcaddon
import subprocess
import os
import stat
import sys
import urllib
from traceback import format_exc
import requests

try:
    import simplejson as json
except Exception:
    import json
```

with:

```python
import xbmc
import xbmcvfs
import xbmcaddon
import subprocess
import os
import stat
import sys
import json
from traceback import format_exc

import requests
```

- [ ] **Step 2: Edit `log_msg` (replace lines 39-43)**

Replace:

```python
def log_msg(msg, loglevel=xbmc.LOGNOTICE):
    '''log message to kodi log'''
    if isinstance(msg, unicode):
        msg = msg.encode('utf-8')
    xbmc.log("%s --> %s" % (ADDON_ID, msg), level=loglevel)
```

with:

```python
def log_msg(msg, loglevel=xbmc.LOGINFO):
    '''log message to kodi log'''
    if isinstance(msg, bytes):
        msg = msg.decode('utf-8', 'replace')
    xbmc.log("%s --> %s" % (ADDON_ID, msg), level=loglevel)
```

- [ ] **Step 3: Edit `get_squeezelite_binary` setting read (line 73)**

Replace:

```python
    custom_path = addon.getSetting("squeezelite_path").decode("utf-8")
```

with:

```python
    custom_path = addon.getSetting("squeezelite_path")
```

- [ ] **Step 4: Edit `get_audiodevices` subprocess flags (line 110)**

Replace:

```python
        startupinfo.dwFlags |= subprocess._subprocess.STARTF_USESHOWWINDOW
```

with:

```python
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
```

(2 occurrences in this file — lines 110 and 131. Use Edit `replace_all=True`.)

- [ ] **Step 5: Edit subprocess decode (lines 111-117)**

Replace:

```python
    sl_exec = subprocess.Popen(args, startupinfo=startupinfo, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
    stdout, stderr = sl_exec.communicate()
    for line in stdout.split("\n"):
        line = line.strip()
        if line and not "Output devices:" in line:
            result.append(line)
    return result
```

with:

```python
    sl_exec = subprocess.Popen(args, startupinfo=startupinfo, stderr=subprocess.STDOUT,
                               stdout=subprocess.PIPE, text=True)
    stdout, _ = sl_exec.communicate()
    for line in stdout.split("\n"):
        line = line.strip()
        if line and "Output devices:" not in line:
            result.append(line)
    return result
```

- [ ] **Step 6: Edit `get_audiodevice` setting read (line 122)**

Replace:

```python
    user_device = addon.getSetting("output_device").decode("utf-8")
```

with:

```python
    user_device = addon.getSetting("output_device")
```

- [ ] **Step 7: Edit `get_audiodevice` subprocess block (lines 127-137)**

Replace:

```python
    args = [sl_binary, "-l"]
    startupinfo = None
    if xbmc.getCondVisibility("System.Platform.Windows"):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess._subprocess.STARTF_USESHOWWINDOW
    sl_exec = subprocess.Popen(args, startupinfo=startupinfo, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
    stdout, stderr = sl_exec.communicate()
    for line in get_audiodevices():
        if "default" in line:
            return line.split("-")[0].strip()
    return "default"
```

with:

```python
    for line in get_audiodevices():
        if "default" in line:
            return line.split("-")[0].strip()
    return "default"
```

(The dead `subprocess.Popen` block in `get_audiodevice` shadowed the call to `get_audiodevices()` below and never used its output — drop it.)

- [ ] **Step 8: Verify the module imports cleanly under stubs**

Run: `python -c "import sys; sys.path.insert(0, 'resources/lib'); sys.path.insert(0, 'tests'); import conftest; import utils; print('ok')"`
Expected: `ok`.

- [ ] **Step 9: Commit**

```bash
git add resources/lib/utils.py
git commit -m "port: convert utils.py to Python 3 (LOGINFO, no .decode, subprocess flag)"
```

### Task 7: Convert `resources/lib/lmsserver.py`

**Files:**
- Modify: `resources/lib/lmsserver.py`

- [ ] **Step 1: Drop dead `import thread` (line 14)**

Replace:

```python
import xbmc
from utils import log_msg, log_exception, json, process_method_on_list
import requests
import thread
import socket
import threading
import re
from simplecache import SimpleCache
```

with:

```python
import xbmc
from utils import log_msg, log_exception, process_method_on_list
import json
import requests
import socket
import threading
from simplecache import SimpleCache
```

Note: `re` was imported but never used; dropping it too.

- [ ] **Step 2: Fix `.iteritems()` (line 186)**

Replace:

```python
                    for key, value in item.iteritems():
```

with:

```python
                    for key, value in item.items():
```

- [ ] **Step 3: Fix `unicode` type check (line 209)**

Replace:

```python
        if isinstance(cmd, (str, unicode)):
```

with:

```python
        if isinstance(cmd, str):
```

- [ ] **Step 4: Fix latent `NameError` in `get_json` (line 235)**

Replace:

```python
            else:
                log_msg("Invalid or empty reponse from server - command: %s - server response: %s" %
                        (cmd, response.status_code))
        except Exception:
            log_exception(__name__, "Server is offline or connection error...")
```

with:

```python
            else:
                log_msg("Invalid or empty response from server - status: %s" % response.status_code)
        except Exception:
            log_exception(__name__, "Server is offline or connection error...")
```

(`cmd` is not in scope inside `get_json` — was a Py2 latent bug only triggered on HTTP errors. Same fix also corrects the "reponse" typo.)

- [ ] **Step 5: Replace `LMSDiscovery.update` to use the extracted parser (lines 296-323)**

Replace the entire `def update(self):` body with:

```python
    def update(self):
        """update the server entry with details"""
        from lms_discovery import parse_lms_response, LMS_QUERY, LMS_PORT
        entries = []
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(5)
        sock.bind(('', 0))
        try:
            sock.sendto(LMS_QUERY, ('<broadcast>', LMS_PORT))
            while True:
                try:
                    data, server = sock.recvfrom(1024)
                    host, _ = server
                    port = parse_lms_response(data)
                    if port is not None:
                        entries.append({'port': port, 'data': data,
                                        'from': server, 'host': host})
                except socket.timeout:
                    break
        finally:
            sock.close()
        self.entries = entries
```

- [ ] **Step 6: Run unit tests, confirm no regressions**

Run: `python -m pytest -v`
Expected: 13 passed (4 wav + 4 silent + 5 discovery).

- [ ] **Step 7: Verify import**

Run: `python -c "import sys; sys.path.insert(0, 'resources/lib'); sys.path.insert(0, 'tests'); import conftest; import lmsserver; print('ok')"`
Expected: `ok`.

- [ ] **Step 8: Commit**

```bash
git add resources/lib/lmsserver.py
git commit -m "port: convert lmsserver.py to Python 3, use extracted UDP parser, fix latent NameError"
```

### Task 8: Convert `resources/lib/main_service.py`

**Files:**
- Modify: `resources/lib/main_service.py`

- [ ] **Step 1: Fix `manual_mac` decode (line 50)**

Replace:

```python
            playerid = self.addon.getSetting("manual_mac").decode("utf-8")
```

with:

```python
            playerid = self.addon.getSetting("manual_mac")
```

- [ ] **Step 2: Fix `MusicPlayer.Title` decode (line 174)**

Replace:

```python
                elif self.lmsserver.status["title"] != xbmc.getInfoLabel("MusicPlayer.Title").decode("utf-8"):
```

with:

```python
                elif self.lmsserver.status["title"] != xbmc.getInfoLabel("MusicPlayer.Title"):
```

- [ ] **Step 3: Fix `System.FriendlyName` decode (line 197)**

Replace:

```python
        playername = xbmc.getInfoLabel("System.FriendlyName").decode("utf-8")
```

with:

```python
        playername = xbmc.getInfoLabel("System.FriendlyName")
```

- [ ] **Step 4: Fix subprocess flag (lines 210 + 229)**

Use Edit with `replace_all=True`:

Replace:

```python
                startupinfo.dwFlags |= subprocess._subprocess.STARTF_USESHOWWINDOW
```

with:

```python
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
```

(`replace_all=True` covers both occurrences in the file.)

- [ ] **Step 5: Verify import**

Run: `python -c "import sys; sys.path.insert(0, 'resources/lib'); sys.path.insert(0, 'tests'); import conftest; import main_service; print('ok')"`
Expected: `ok`.

- [ ] **Step 6: Commit**

```bash
git add resources/lib/main_service.py
git commit -m "port: convert main_service.py to Python 3"
```

### Task 9: Convert `resources/lib/plugin_content.py`

**Files:**
- Modify: `resources/lib/plugin_content.py`

This is the biggest file (~37 KB) but the changes are all mechanical: imports, decode removal, iteritems, listitem art API.

- [ ] **Step 1: Replace imports block (lines 11-21)**

Replace:

```python
import xbmc
import xbmcplugin
import xbmcgui
import xbmcaddon
from utils import log_msg, KODI_VERSION, log_exception, ADDON_ID, parse_duration
import urlparse
from urllib import quote_plus
import sys
import os
from operator import itemgetter
from lmsserver import LMSServer, TAGS_BASIC, TAGS_FULL, TAGS_ALBUM
```

with:

```python
import sys
import os
from operator import itemgetter
from urllib.parse import parse_qsl, quote_plus

import xbmc
import xbmcplugin
import xbmcgui
import xbmcaddon

from utils import log_msg, KODI_VERSION, log_exception, ADDON_ID, parse_duration
from lmsserver import LMSServer, TAGS_BASIC, TAGS_FULL, TAGS_ALBUM
```

- [ ] **Step 2: Remove `.decode("utf-8")` from `getProperty` reads (lines 38-40)**

Replace:

```python
        lmsplayerid = win.getProperty("lmsplayerid").decode("utf-8")
        lmshost = win.getProperty("lmshost").decode("utf-8")
        lmsport = win.getProperty("lmsport").decode("utf-8")
```

with:

```python
        lmsplayerid = win.getProperty("lmsplayerid")
        lmshost = win.getProperty("lmshost")
        lmsport = win.getProperty("lmsport")
```

- [ ] **Step 3: Fix `parse_qsl` call (line 53)**

Replace:

```python
                self.params = dict(urlparse.parse_qsl(sys.argv[2].replace('?', '').decode("utf-8")))
```

with:

```python
                self.params = dict(parse_qsl(sys.argv[2].replace('?', '')))
```

- [ ] **Step 4: Convert all `.iteritems()` to `.items()`**

Use Edit with `replace_all=True`:

Replace:

```python
.iteritems()
```

with:

```python
.items()
```

(4 occurrences: lines 274, 299, 428, 596.)

- [ ] **Step 5: Replace `setIconImage` / `setThumbnailImage` blocks**

Three blocks in this file follow the same pattern. Locate each pair and replace them with `setArt`.

Block 1 (around line 569-570):

```python
        listitem.setIconImage(thumb)
        listitem.setThumbnailImage(thumb)
```

→

```python
        listitem.setArt({"icon": thumb, "thumb": thumb})
```

Block 2 (around line 616-617):

```python
        listitem.setIconImage(thumb)
        listitem.setThumbnailImage(thumb)
```

→

```python
        listitem.setArt({"icon": thumb, "thumb": thumb})
```

Block 3 (around line 657-658):

```python
        listitem.setIconImage(lms_item["thumb"])
        listitem.setThumbnailImage(lms_item["thumb"])
```

→

```python
        listitem.setArt({"icon": lms_item["thumb"], "thumb": lms_item["thumb"]})
```

- [ ] **Step 6: Fix `ListItem(label, iconImage=icon)` ctor (line 703)**

Replace:

```python
    def create_generic_listitem(self, label, icon, cmd, is_folder=True, contextmenu=None):
        listitem = xbmcgui.ListItem(label, iconImage=icon)
```

with:

```python
    def create_generic_listitem(self, label, icon, cmd, is_folder=True, contextmenu=None):
        listitem = xbmcgui.ListItem(label)
        listitem.setArt({"icon": icon, "thumb": icon})
```

(The `iconImage` keyword was removed from the `ListItem` constructor in Matrix.)

- [ ] **Step 7: Verify import**

Run: `python -c "import sys; sys.argv = ['plugin.py', '1', '?']; sys.path.insert(0, 'resources/lib'); sys.path.insert(0, 'tests'); import conftest; import plugin_content; print('ok')"`
Expected: `ok`.

- [ ] **Step 8: Verify no stragglers in this file**

Run: `grep -nE "(\.decode\(|\.iteritems\(|unicode|urlparse|setIconImage|setThumbnailImage|iconImage=|_subprocess)" resources/lib/plugin_content.py`
Expected: empty output.

- [ ] **Step 9: Commit**

```bash
git add resources/lib/plugin_content.py
git commit -m "port: convert plugin_content.py to Python 3 (urllib.parse, setArt, items)"
```

### Task 10: Convert `resources/lib/player_monitor.py`

**Files:**
- Modify: `resources/lib/player_monitor.py`

- [ ] **Step 1: Fix urllib import (line 14)**

Replace:

```python
from utils import log_msg, log_exception, parse_duration
import xbmc
import xbmcgui
from urllib import quote_plus
```

with:

```python
from urllib.parse import quote_plus

import xbmc
import xbmcgui

from utils import log_msg, log_exception, parse_duration
```

- [ ] **Step 2: Replace `setIconImage` / `setThumbnailImage` (lines 113-115)**

Replace:

```python
        listitem.setArt({"thumb": lms_song["thumb"]})
        listitem.setIconImage(lms_song["thumb"])
        listitem.setThumbnailImage(lms_song["thumb"])
```

with:

```python
        listitem.setArt({"icon": lms_song["thumb"], "thumb": lms_song["thumb"]})
```

- [ ] **Step 3: Fix `exit = True` no-op (line 33)**

Replace:

```python
    def close(self):
        '''cleanup on exit'''
        exit = True
        del self.playlist
```

with:

```python
    def close(self):
        '''cleanup on exit'''
        self.exit = True
        del self.playlist
```

(Latent bug: `exit = True` assigned a local that was immediately discarded.)

- [ ] **Step 4: Verify import**

Run: `python -c "import sys; sys.path.insert(0, 'resources/lib'); sys.path.insert(0, 'tests'); import conftest; import player_monitor; print('ok')"`
Expected: `ok`.

- [ ] **Step 5: Commit**

```bash
git add resources/lib/player_monitor.py
git commit -m "port: convert player_monitor.py to Python 3 and fix close() no-op"
```

### Task 11: Convert `service.py` (root entry point)

**Files:**
- Modify: `service.py`

- [ ] **Step 1: Fix log levels (lines 36 + 39)**

Use Edit with `replace_all=True`:

Replace:

```python
xbmc.LOGNOTICE
```

with:

```python
xbmc.LOGINFO
```

- [ ] **Step 2: Verify the file still parses**

Run: `python -c "import ast; ast.parse(open('service.py').read()); print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add service.py
git commit -m "port: replace removed LOGNOTICE with LOGINFO in service entry"
```

### Task 12: Verify nothing else uses Py2 idioms

**Files:** none (read-only check)

- [ ] **Step 1: Sweep for stragglers across the whole repo**

Run:

```bash
grep -rnE "(\.decode\(|\.iteritems\(|\bunicode\b|LOGNOTICE|LOGSEVERE|StringIO|^import thread$|^from urlparse|^import urlparse$|from urllib import|_subprocess\.STARTF|setIconImage|setThumbnailImage|simplejson|\bxrange\b|iconImage=)" resources/lib/*.py *.py
```

Expected: only matches in `resources/lib/cherrypy/` (which we delete in Phase 5) and `resources/lib/httpproxy.py` (which we rewrite next). No matches in our own code.

- [ ] **Step 2: Run the test suite**

Run: `python -m pytest -v`
Expected: 13 passed.

(No commit — this task is verification only.)

---

## Phase 5 — Replace CherryPy with `wsgiref`

### Task 13: Rewrite `httpproxy.py` against stdlib

**Files:**
- Modify: `resources/lib/httpproxy.py` (complete rewrite)

The new module reuses `wav.build_wav_header` and `wav.silent_stream_chunks` from Task 3-4 and exposes the same surface as before (`ProxyRunner(host, allow_ranges)`, `.start()`, `.stop()`, `.get_port()`) so `service.py` doesn't change.

- [ ] **Step 1: Write the full replacement**

Replace the entire contents of `resources/lib/httpproxy.py` with:

```python
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


class _SilentStreamApp:
    """WSGI app: GET/HEAD /track/<duration|"radio"> → silent WAV."""

    def __init__(self, allowed_ips):
        self.allowed_ips = set(allowed_ips)

    def __call__(self, environ, start_response):
        method = environ["REQUEST_METHOD"].upper()
        remote = environ.get("REMOTE_ADDR", "")
        if remote not in self.allowed_ips:
            start_response("403 Forbidden", [("Content-Type", "text/plain")])
            return [b"forbidden"]
        if method not in ("GET", "HEAD"):
            start_response("405 Method Not Allowed", [("Content-Type", "text/plain")])
            return [b"method not allowed"]

        # Path is like /track/<duration> or /track/radio
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
        range_header = environ.get("HTTP_RANGE", "")

        if is_radio:
            headers = [
                ("Content-Type", "audio/x-wav"),
                ("Connection", "close"),
            ]
            status = "200 OK"
            if method == "HEAD":
                start_response(status, headers)
                return [b""]
            start_response(status, headers)
            return silent_stream_chunks(header, payload_size)

        # File-style: support Range requests for Kodi seeking.
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
        # For our zero-payload stream the "byte slice" is just `length` zero bytes;
        # the WAV header sits in the first 44 bytes of the virtual file.
        return _range_chunks(header, total_size, start, end)


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


class ProxyRunner(threading.Thread):
    """Background WSGI server. Signature matches the previous CherryPy version."""

    def __init__(self, host="127.0.0.1", try_ports=range(51100, 51150),
                 allowed_ips=("127.0.0.1",), allow_ranges=True):
        super().__init__(daemon=True)
        self._host = host
        self._port = _find_free_port(host, list(try_ports))
        self._app = _SilentStreamApp(allowed_ips)
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
        # make_server() is synchronous — server is ready as soon as __init__ returns
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
```

- [ ] **Step 2: Add an end-to-end test using a real socket**

Create `tests/test_httpproxy.py`:

```python
import socket
import time
from urllib.request import Request, urlopen

import pytest

from httpproxy import ProxyRunner


@pytest.fixture
def runner():
    r = ProxyRunner(host="127.0.0.1", try_ports=range(52000, 52050))
    r.start()
    # wsgiref make_server binds in __init__, so it's ready immediately
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
    with pytest.raises(Exception) as exc_info:
        _get(runner, "/track/3", method="POST")
    # urllib raises HTTPError on 4xx
    assert "405" in str(exc_info.value)


def test_unknown_path_404(runner):
    with pytest.raises(Exception) as exc_info:
        _get(runner, "/notatrack/3")
    assert "404" in str(exc_info.value)
```

- [ ] **Step 3: Run new tests**

Run: `python -m pytest tests/test_httpproxy.py -v`
Expected: 6 passed.

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest -v`
Expected: 19 passed (13 from prior + 6 new).

- [ ] **Step 5: Commit**

```bash
git add resources/lib/httpproxy.py tests/test_httpproxy.py
git commit -m "feat: replace vendored CherryPy with stdlib wsgiref in httpproxy"
```

### Task 14: Delete vendored CherryPy

**Files:**
- Delete: `resources/lib/cherrypy/` (entire tree)

- [ ] **Step 1: Sanity-check no other module imports cherrypy**

Run: `grep -rn "import cherrypy\|from cherrypy" resources/lib/ --include='*.py' | grep -v resources/lib/cherrypy`
Expected: empty output.

- [ ] **Step 2: Delete the tree**

Run: `git rm -r resources/lib/cherrypy`
Expected: many "rm 'resources/lib/cherrypy/..." lines.

- [ ] **Step 3: Verify tests still pass**

Run: `python -m pytest -v`
Expected: 19 passed.

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: remove vendored CherryPy (replaced by wsgiref)"
```

---

## Phase 6 — Manual validation in Kodi v21 Omega

These tasks require a running Kodi v21 instance and an LMS server reachable on the LAN. They are **manual smoke tests** with explicit pass/fail criteria.

### Task 15: Package and install

**Files:** none

- [ ] **Step 1: Create install zip**

Run:

```bash
cd /data/projets/perso
zip -r plugin.audio.squeezebox.zip plugin.audio.squeezebox \
  -x 'plugin.audio.squeezebox/.git/*' \
  -x 'plugin.audio.squeezebox/docs/*' \
  -x 'plugin.audio.squeezebox/tests/*' \
  -x 'plugin.audio.squeezebox/pytest.ini' \
  -x 'plugin.audio.squeezebox/requirements-dev.txt' \
  -x '*.pyc' -x '*.pyo' -x '*/__pycache__/*'
```

Expected: `plugin.audio.squeezebox.zip` created (≈30 MB without CherryPy).

- [ ] **Step 2: Install in Kodi 21**

In Kodi: Settings → Add-ons → Install from zip → select the file. Confirm dependency resolution succeeds (`script.module.requests 2.31+`, `script.module.simplecache 2.0+`).

Expected: addon installs without errors, appears in Music add-ons.

### Task 16: Service startup smoke test

- [ ] **Step 1: Restart Kodi to trigger `xbmc.service` start at `login`**

- [ ] **Step 2: Tail `kodi.log`**

On Linux: `tail -f ~/.kodi/temp/kodi.log | grep plugin.audio.squeezebox`

Expected log lines (within ~30s):
- `plugin.audio.squeezebox --> started webproxy at port 511XX`
- `plugin.audio.squeezebox --> Detected Mac-Address: XX:XX:...`
- `plugin.audio.squeezebox --> LMS server discovered - host: ... - port: 9000`
- `plugin.audio.squeezebox --> Start Monitoring events for playerid ...`

Pass/fail: presence of all four lines. Any Python traceback = fail; investigate before continuing.

### Task 17: Plugin entry smoke test

- [ ] **Step 1: Browse the plugin**

Open Music → Add-ons → Squeezelite Player for Kodi.

Expected: top-level menu shows entries pulled from LMS (Albums / Artists / Playlists / Radios / Favorites / Apps).

- [ ] **Step 2: Drill into Albums**

Expected: list of albums with artwork. No errors in `kodi.log`.

### Task 18: Playback smoke test

- [ ] **Step 1: Start a track from the Albums view**

Expected:
- Kodi's "Now Playing" screen appears with artwork.
- Audio is heard from the system's default ALSA / Windows output.
- `kodi.log` shows `play started by lms server` followed by HTTP requests to `127.0.0.1:511XX/track/<duration>`.

- [ ] **Step 2: Pause / resume**

Press pause on the Kodi UI. Expected: LMS reports pause within ~1s and Kodi reflects it. Resume similarly.

- [ ] **Step 3: Seek**

Drag the timeline to the middle of the track. Expected: audio jumps; `kodi.log` shows `seek requested by lms server` or the Kodi-side equivalent.

- [ ] **Step 4: Next/previous**

Skip to next track. Expected: playlist advances on both sides without a stall.

- [ ] **Step 5: Stop**

Stop playback. Expected: silent stream closes, LMS player reports stop.

### Task 19: Edge-case smoke tests

- [ ] **Step 1: Internet radio stream**

Pick a radio favorite, start it. Expected: audio plays, `kodi.log` shows requests to `/track/radio`.

- [ ] **Step 2: Video preemption**

Start a video file in Kodi while the LMS player is active. Expected: `kodi.log` shows `Kodi started playing video - disabled the LMS player`. Stop the video → LMS player powers back on.

- [ ] **Step 3: LMS server unreachable**

Stop the LMS server, restart Kodi. Expected: addon logs the discovery loop quietly without crashing.

### Task 20: Settings & manual-config paths

- [ ] **Step 1: Manual MAC**

Open addon settings → enable "Disable auto MAC detection" → set a fake MAC. Restart Kodi. Expected: log shows the manual MAC used.

- [ ] **Step 2: Manual LMS host**

Open addon settings → enable "Disable auto LMS detection" → set host/port. Restart Kodi. Expected: connection happens to the manual address.

- [ ] **Step 3: Output device picker (Linux/Windows/macOS)**

Open addon settings → "Select output device". Expected: dialog lists ALSA / PortAudio devices; selecting one writes to `output_device`.

---

## Phase 7 — Documentation and release polish

### Task 21: Update README and CLAUDE.md

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: README — add migration note at top**

Insert after the existing repo title line:

```markdown
> **v2.0** — ported to Kodi 21 Omega (Python 3). Older Kodi versions (≤20 Nexus) are no longer supported; install v1.0.19 instead.
```

- [ ] **Step 2: README — bump tested versions**

Replace:

```
I've tested it with LMS server version 7.9 myself.
```

with:

```
Tested against LMS 8.x and Kodi 21 Omega.
```

- [ ] **Step 3: CLAUDE.md — update the Python constraint section**

In `CLAUDE.md`, replace the `## Runtime / language constraint` section title and body to reflect Py3 / Kodi 21. (Open the file; rewrite that section so it documents the new state: Python 3.11, `xbmc.python 3.0.3`, no `.decode` on Kodi APIs, etc.)

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: document v2.0 Kodi 21 Omega support"
```

### Task 22: Final dry-run

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest -v`
Expected: 19 passed.

- [ ] **Step 2: Final straggler grep**

Run:

```bash
grep -rnE "(\.decode\(\"utf-8\"\)|\.iteritems\(\)|\bunicode\b|LOGNOTICE|LOGSEVERE|StringIO\.|^import thread$|^import urlparse$|from urllib import quote_plus|_subprocess\.STARTF|setIconImage|setThumbnailImage|simplejson|iconImage=)" resources/lib/*.py *.py
```

Expected: empty output.

- [ ] **Step 3: Confirm no `cherrypy/` remains**

Run: `ls resources/lib/cherrypy 2>&1 || echo "absent"`
Expected: `absent`.

- [ ] **Step 4: Open PR / push branch**

Run: `git push -u origin port/kodi-v21-omega`

(Or merge to master once smoke tests on Kodi 21 are green — at the maintainer's discretion.)

---

## Out of scope (deferred)

These were identified during analysis but **not in this plan**. Open follow-up issues if needed:

1. **`squeezelite-aarch64` (ARM64) binary** — currently only `squeezelite-arm` (armv6/7) is bundled. Pi 4/5 on 64-bit OS needs an arm64 build. Adding it is a single drop-in file + a branch in `utils.get_squeezelite_binary`.
2. **macOS Apple Silicon native binary** — current `squeezelite` may run via Rosetta. Universal2 build is a future polish.
3. **`getMusicInfoTag()` migration** — `listitem.setInfo("music", {...})` works in v21 but is deprecated. Migration is non-trivial (~50 call sites) and out of scope for this port.
4. **Typed setting accessors** — moving `getSetting() == "true"` to `getSettingBool()` is nicer but not required.
5. **Authentication for LMS** — README notes this is unimplemented. Still unimplemented after this port.
6. **Android "fake OSD"** — there's a `TODO` in `main_service.monitor_lms`. Out of scope.
