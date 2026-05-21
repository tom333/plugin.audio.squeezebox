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
