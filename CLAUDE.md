# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Kodi audio addon (`plugin.audio.squeezebox`) that turns Kodi into a Logitech Media Server (LMS) / Squeezebox player. Distributed as a zip via the maintainer's Kodi addon repository — there is no build/lint/test pipeline in this repo. Iteration loop is: edit → repackage into Kodi → check the Kodi log.

## Runtime / language constraint

**This is a Python 3.11 codebase** targeting Kodi 21 Omega (`xbmc.python 3.0.3`). The v2.0 port (May 2026) converted everything from Py2/Leia to Py3/Omega. Older Py2 idioms are gone:

- `unicode` → `str`. `iteritems()` → `items()`. `StringIO` → `BytesIO` or stdlib `bytes`.
- `urlparse` / `urllib` → `urllib.parse`.
- `xbmc.LOGNOTICE` (removed in Kodi 19) → `xbmc.LOGINFO`.
- `subprocess._subprocess.STARTF_USESHOWWINDOW` → `subprocess.STARTF_USESHOWWINDOW` (top-level).
- `xbmcgui.ListItem.setIconImage` / `setThumbnailImage` / `iconImage=` ctor kwarg → `setArt({"icon": ..., "thumb": ...})`.
- **`.decode("utf-8")` on `addon.getSetting()`, `xbmc.getInfoLabel()`, `window.getProperty()`, `sys.argv[2]`, etc. is gone** — these APIs return `str` directly in Py3.
- Vendored CherryPy replaced by stdlib `wsgiref` in `resources/lib/httpproxy.py`. `script.module.six` removed from `addon.xml`.

The `xbmc*` modules (`xbmc`, `xbmcaddon`, `xbmcgui`, `xbmcplugin`, `xbmcvfs`) only exist inside Kodi's embedded interpreter. Tests stub them via `tests/conftest.py` so `resources/lib/` is importable under pytest.

Use `xbmc.log(..., level=xbmc.LOGDEBUG|LOGINFO|LOGWARNING|...)` via the `log_msg` / `log_exception` helpers in `utils.py`.

## Architecture: the silent-stream trick

The core idea (explained in README) is that Kodi plays a **fake silent WAV stream** while **Squeezelite** actually pushes audio to the sound device. The plugin keeps both sides in sync so Kodi's "Now Playing" UI reflects the LMS state.

Two Kodi extension points run simultaneously (declared in `addon.xml`):

1. **`service.py`** → `xbmc.service` (started at Kodi `login`). Long-running background thread.
2. **`plugin.py`** → `xbmc.python.pluginsource` providing `audio`. Re-invoked on every directory navigation under `plugin://plugin.audio.squeezebox/...`.

Both add `resources/lib/` to `sys.path` before importing.

### service.py runtime graph

`service.py` spins up two things and idles in a `waitForAbort` loop until Kodi exits:

- **`ProxyRunner`** (`resources/lib/httpproxy.py`): a stdlib `wsgiref` WSGI server bound to `127.0.0.1` on the first free port in `51100–51150`. The `_SilentStreamApp` handler synthesizes a silent PCM WAV header + zeroed samples sized to the current track's duration. Radio streams use a hardcoded 3600 s duration. Requests are restricted to `127.0.0.1` and `GET`/`HEAD` only.
- **`MainService`** thread (`resources/lib/main_service.py`):
  - Resolves a player ID from the host MAC (`utils.get_mac` polls `Network.MacAddress` for up to ~360 s), or the manual MAC setting.
  - Discovers an LMS via UDP broadcast on port 3483 (`LMSDiscovery` in `lmsserver.py`, payload `b"eJSON\0"`), or uses manual `lms_hostname`/`lms_port`.
  - Spawns the correct **squeezelite binary** for the platform (`utils.get_squeezelite_binary` picks from `resources/lib/bin/{win32,osx,linux}/...`, chmods +x, and `kill_squeezelite` first wipes any stale processes). LibreELEC uses the system-provided squeezelite from `virtual.multimedia-tools`.
  - Publishes `lmshost`, `lmsport`, `lmsplayerid` as **properties on Kodi's global window 10000** so `plugin.py` (a separate process invocation) can pick them up. `lmsexit=true` signals shutdown.
  - Polls LMS status every 1 s in `monitor_lms` and reconciles bidirectionally with the Kodi player (see below).

### plugin.py runtime

Kodi calls `plugin.py` fresh for every navigation. `PluginContent.__init__` reads window 10000 to get LMS coords, instantiates a new `LMSServer`, then dispatches on `params["action"]` to a method on `PluginContent` (e.g. `albums`, `artists`, `tracks`, `playlists`, `currentplaylist`, `favorites`, `command`, `select_output`). Dispatch is by `hasattr(self.__class__, action)` — so **action names are method names**. Listings are built with `xbmcplugin.addDirectoryItem` and terminated by `xbmcplugin.endOfDirectory`.

### State synchronization (the tricky part)

`main_service.MainService.monitor_lms` is the reconciliation loop. It runs every 1 s and decides what to push to Kodi based on LMS state. `player_monitor.KodiPlayer` (subclass of `xbmc.Player`) fires events in the opposite direction (`onPlayBackPaused`, `onPlayBackStopped`, `onPlayBackStarted`, `onPlayBackSeek`) that translate into LMS commands.

Two booleans gate this loop and **must be respected** when adding behavior to avoid feedback storms:

- `LMSServer._state_changing` — true while `send_command` is waiting for LMS to ack a change. `monitor_lms` skips reconciliation when set.
- `KodiPlayer.is_busy` — true while the Kodi side is mid-action (e.g. seeking). `monitor_lms` also skips while set.

Other coordination flags:

- `KodiPlayer.is_playing` — distinguishes "Kodi is playing our silent stream" from "Kodi is playing video / something else". Set by checking `MusicPlayer.Property(sl_path)` (each listitem stamps its LMS URL into property `sl_path` so we can tell our items apart).
- `MainService._temp_power_off` — when Kodi starts playing **video**, the LMS player is powered off; powered back on when video ends.

When updating the playlist, `KodiPlayer.update_playlist` rebuilds Kodi's `PLAYLIST_MUSIC` from `LMSServer.cur_playlist()`. Listitems point at `http://127.0.0.1:<webport>/track/<duration_or_"radio">` — the silent-stream URL — while also stashing `original_listitem_url` to a `plugin://...?action=command&params=playlist+index+N` so right-click "play from here" works.

### LMS JSON-RPC

`LMSServer.send_request` posts `slim.request` to `http://<host>:<port>/jsonrpc.js`. The cmd is space-split (with `[SP]` as an escape for embedded spaces, used when building actionstr params). Tag selectors control returned fields: `TAGS_FULL` / `TAGS_BASIC` / `TAGS_ALBUM`. Per-track detail enrichment goes through `trackdetails()`, which caches by `(id, title)` with `lastUpdated` as a checksum via `script.module.simplecache`.

`get_thumb` walks a long list of LMS artwork hints and rewrites relative URLs against the server base — keep this fallback chain in mind when LMS art is missing.

### Inter-process state via window properties

Because `plugin.py` is re-invoked per navigation and runs in a **different process** from `service.py`, the two sides communicate exclusively through Kodi global state:
- Window 10000 properties (`lmshost`, `lmsport`, `lmsplayerid`, `lmsexit`).
- Listitem properties (`sl_path`, `original_listitem_url`, `do_not_analyze`).

There is no shared Python module state between them.

## Dependencies

Declared in `addon.xml`:
- `xbmc.python 3.0.3`, `xbmc.addon 19.0.0` (Kodi Matrix+ API, addon targets Omega / v21).
- `script.module.requests`, `script.module.simplecache` — provided by Kodi's addon system, not pip. (`script.module.six` was dropped in the v2.0 port.)

Vendored under `resources/lib/`:
- **`bin/`** — Squeezelite binaries for `win32`, `osx`, `linux` (incl. `squeezelite-arm` for RPi, `-i64`/`-x86` for Linux x86/x64, plus Windows DLLs).

The HTTP proxy uses stdlib `wsgiref` directly — there is no vendored web framework anymore (CherryPy was removed in v2.0).

## Localization

Strings live in `resources/language/resource.language.{en_gb,nl_nl}/strings.po`. Numeric IDs (e.g. `32000`, `32209`) referenced from `settings.xml` and via `self.addon.getLocalizedString(...)` / `xbmc.getLocalizedString(...)` in code. When adding user-facing text, add the string to both `.po` files (or at minimum `en_gb`).

`settings.xml` uses Kodi's relative-visibility syntax `eq(-1,true)` / `eq(-2,true)` (means "previous / second-previous setting is true") — keep adjacent settings in their declared order or the visibility chain breaks.

## Platform quirks worth knowing

- **Android / iOS**: no bundled Squeezelite — users install a separate Squeezeplayer app, and the addon expects to be told the MAC manually (`disable_auto_mac` + `manual_mac`). The Android branch in `monitor_lms` already skips reconciliation when the addon's playerid matches the local MAC (TODO comment: "implement fake OSD for android").
- **Windows**: subprocess spawns use `STARTUPINFO` with `STARTF_USESHOWWINDOW` to suppress console windows; `kill_squeezelite` uses `taskkill` for both `squeezelite-win.exe` and `squeezelite.exe`.
- **LibreELEC**: uses the system Squeezelite from `virtual.multimedia-tools` addon instead of the bundled binary.
