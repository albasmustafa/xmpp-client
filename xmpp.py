"""
deneme.py — Modern Tkinter XMPP İstemcisi
Kurulum: pip install slixmpp

Thread modeli (önemli):
  • Tk ana thread'i: tüm widget işlemleri ve `MainWindow._poll` ile
    `gui_q` kuyruğunun tüketimi.
  • XMPP thread'i: `start()` içinde ayrı asyncio döngüsü; ağ olayları
    yalnızca `gui_q.put(("kind", data))` ile GUI'ye iletilir.
  • Arka plan işleri (indirme, ses kaydı, oynatma, GIF arama, REST API):
    daemon thread'ler; GUI güncellemeleri mutlaka `root.after(0, ...)`
    üzerinden yapılır.
  • Kural: XMPP/worker thread'inden Tk widget'ına asla doğrudan
    dokunulmaz; veri kuyruğa konur, GUI thread'i işler.
"""

import asyncio
import io
import json
import os

# Flatpak ortamında host portaudio kütüphanesini bul
if os.path.isdir("/run/host/usr/lib"):
    os.environ.setdefault("LD_LIBRARY_PATH",
        "/run/host/usr/lib:" + os.environ.get("LD_LIBRARY_PATH", ""))
import base64
import http.server
import queue
import re
import socket
import sqlite3
import struct
import subprocess as _sp
import tempfile
import threading
import time
import tkinter as tk
import urllib.parse
import urllib.request
import wave
import weakref
import xml.etree.ElementTree as ET
from collections import OrderedDict, deque
from concurrent.futures import TimeoutError as _FutureTimeoutError
from datetime import datetime
from tkinter import messagebox, simpledialog, ttk

from slixmpp.xmlstream.handler import CoroutineCallback
from slixmpp.xmlstream.matcher import StanzaPath

import jingle_ft
from jingle_ft import JingleFTManager
from ui import profile as _ui_profile
from ui import rooms as _ui_rooms_menu
from ui import sidebar as _ui_sidebar
from ui.chat import ChatShell as _ChatShell
from ui.chat import actions as _actions_ui
from ui.chat import audio as _audio_ui
from ui.chat import history as _history_ui
from ui.chat import identity as _identity
from ui.chat import media as _media_ui
from ui.chat import reactions as _reactions_ui
from ui.chat import render as _render
from ui.chat import typing as _typing_ui
from ui.chat.composer import ComposerView as _ComposerView
from ui.chat.suggest import SuggestionBar as _SuggestionBar
from ui.dialogs import ai as _ui_ai
from ui.dialogs import chat_actions as _ui_chat_actions
from ui.dialogs import chat_options as _ui_chat_options
from ui.dialogs import contact as _ui_contact
from ui.dialogs import presence as _ui_presence
from ui.dialogs import rooms as _ui_rooms
from ui.dialogs import settings as _ui_settings
from ui.dialogs import simple as _ui_simple
from ui.timers import after_alive as _after_alive
from xmppcore import aesgcm as _aesgcm
from xmppcore import agent as _agent
from xmppcore import ai as _ai
from xmppcore import questions as _questions
from xmppcore import sensitive as _sensitive
from xmppcore import tts as _tts
from xmppcore.archive import ArchiveMixin
from xmppcore.config import (
    _account_password,
    _auto_login_enabled,
    _encode_pw,
    _load_config,
    _save_config,
    _saved_login,
    _store_login,
    _verify_pin,
)
from xmppcore.config import _decode_pw as _decode_pw
from xmppcore.config import _get_fernet_key as _get_fernet_key

# ── Faz 1 yaprak modülleri (facade yeniden dışa aktarımı) ────────────────────
from xmppcore.constants import _CONFIG_PATH, _log
from xmppcore.constants import _DB_PATH as _DB_PATH
from xmppcore.format import (
    _bookmark_add,
    _fill_search_form,
    _parse_geometry,
    _parse_room_search,
    _parse_tenor_results,
    _reaction_tooltip,
    _reply_preview,
    _to_int,
    _toggle_reaction_set,
)
from xmppcore.format import _room_result_line as _room_result_line
from xmppcore.helpers import (
    _CORRECTION,
    _add_origin_id,
    _get_xep,
    _has_child,
    _new_msg_id,
    _normalize_room_jid,
    _normalize_user_jid,
    _spawn_task,
    _square_avatar_png,
    _stanza_msg_id,
    _strip_quoted_fallback,
)
from xmppcore.helpers import _stanza_is_encrypted as _stanza_is_encrypted
from xmppcore.i18n import _STRINGS
from xmppcore.messages import MessagesMixin
from xmppcore.muc import MucMixin
from xmppcore.muc import _room_kind_ok as _muc_room_kind_ok
from xmppcore.presence import PresenceMixin
from xmppcore.proxy import open_tunnel as _open_proxy_tunnel
from xmppcore.proxy import proxy_from_form as _proxy_from_form
from xmppcore.proxy import proxy_settings as _proxy_settings
from xmppcore.storage import (
    _db_ai_cache_get,
    _db_ai_cache_set,
    _db_ai_context,
    _db_ai_embedding_chunk,
    _db_ai_pending,
    _db_ai_pending_count,
    _db_ai_store_embeddings,
    _db_clear_all,
    _db_clear_chat,
    _db_clear_my_reactions,
    _db_clear_reactions_mid,
    _db_load_msgs,
    _db_save_reaction,
    _db_store_msg,
    _db_unanswered,
    _db_update_msg_body,
    _db_update_msg_reply,
)
from xmppcore.storage import _db_load_reactions as _db_load_reactions
from xmppcore.storage import _db_search_msgs as _db_search_msgs
from xmppcore.storage import _get_db as _get_db
from xmppcore.theme import _THEMES
from xmppcore.transfers import TransferMixin

_db_conn: sqlite3.Connection | None = None

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ── Ses kayıt desteği ────────────────────────────────────────────────────────
_HAS_PYAUDIO = False
try:
    import pyaudio
    _HAS_PYAUDIO = True
except ImportError:
    pass

_HAS_DND = False
try:
    import tkinterdnd2  # noqa: F401
    _HAS_DND = True
except ImportError:
    pass














def _room_result_details(item: dict) -> str:
    """Seçili odanın ayrıntı satırı (açıklama + rozetler)."""
    addr = item.get("address", "")
    bits = []
    nusers = _to_int(item.get("nusers"))
    if nusers:
        bits.append(f"👤 {nusers}")
    lang = item.get("language", "")
    if lang:
        bits.append(f"🌐 {lang}")
    if item.get("is_public") is False:
        bits.append(f"🔒 {_t('private_room')}")
    desc = (item.get("description") or "").strip()
    line = " · ".join(bits)
    if desc and line:
        return f"{line}\n{desc}"
    return line or desc or addr










def _safe_open_url(url: str):
    """URL'yi shell enjeksiyonu riski olmadan aç."""
    try:
        _sp.Popen(["xdg-open", url], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
    except Exception:
        _log.warning("URL açılamadı: %s", url, exc_info=True)


def _safe_grab_set(window, retries: int = 40, delay_ms: int = 25):
    """`grab_set`'i pencere görünür olana kadar ertele.

    Yeni Toplevel'ler (özellikle Wayland / asenkron pencere
    yöneticilerinde) henüz görünür değilken grab alınamaz ve Tk
    "grab failed: window not viewable" hatası verir. Bu yardımcı kısa
    aralıklarla dener, pencere kapanırsa sessizce vazgeçer.
    """
    root_getter = getattr(window, "_root", None)
    scheduler = root_getter() if callable(root_getter) else window

    def _try(remaining: int):
        try:
            if not window.winfo_exists():
                return
            if window.winfo_viewable():
                window.grab_set()
                return
        except Exception:
            return
        if remaining > 0:
            try:
                scheduler.after(delay_ms, _try, remaining - 1)
            except Exception:
                pass

    _try(retries)


def _ipv6_available() -> bool:
    """Yerel IPv6 rotası var mı? (UDP connect paket göndermez, hızlıdır)"""
    if not socket.has_ipv6:
        return False
    try:
        s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        try:
            s.connect(("2001:4860:4860::8888", 53, 0, 0))
            return True
        finally:
            s.close()
    except OSError:
        return False


def _prefer_ipv4(records: list, ipv6_ok: bool) -> list:
    """IPv6 yolu yoksa IPv6 kayıtlarını ele; varsa IPv4'leri öne al.

    Kayıtlar (service, host, address, port) demetleridir. IPv6 rotası
    olmayan ağlarda IPv6 denemeleri "Network is unreachable" ile
    başarısız olup gecikme yaratır; bu yardımcı sırayı düzeltir.
    """
    if not ipv6_ok:
        v4 = [r for r in records if ":" not in str(r[2])]
        if v4:
            return v4
    return sorted(records, key=lambda r: 1 if ":" in str(r[2]) else 0)


def _cleanup_temp_files(paths):
    """Verilen geçici dosyaları sessizce sil."""
    for p in list(paths):
        try:
            if p and os.path.isfile(p):
                os.remove(p)
        except OSError:
            _log.warning("Geçici dosya silinemedi: %s", p, exc_info=True)


class _WorkerShutdown(Exception):
    """Kapanış: worker artefakt sahipliğini bırakıp sessizce çıkar."""


_API_BODY_MAX = 1024 * 1024
_API_REQUEST_TIMEOUT = 5
_API_SEND_TIMEOUT = 5


# ── Avatar cache ──────────────────────────────────────────────────────────────
from xmppcore.constants import _AVATAR_DIR as _AVATAR_DIR  # noqa: E402  (dizini oluşturur)


def _avatar_cache_path(bare_jid: str) -> str:
    safe = bare_jid.replace("@", "_at_").replace(".", "_")
    return os.path.join(_AVATAR_DIR, safe)

def _save_avatar_cache(bare_jid: str, data: bytes):
    try:
        path = _avatar_cache_path(bare_jid)
        with open(path, "wb") as f:
            f.write(data)
    except Exception:
        pass

def _load_avatar_cache(bare_jid: str) -> bytes | None:
    try:
        path = _avatar_cache_path(bare_jid)
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
    except Exception:
        pass
    return None

# Resim URL'si tespit deseni (aesgcm:// = OMEMO ile şifreli medya, XEP-0454)
_AESGCM_KEY_RE = r'#(?:[0-9a-fA-F]{96}|[0-9a-fA-F]{88})(?![0-9a-fA-F])'
_IMG_URL_RE = re.compile(
    r'(https?://\S+\.(?:png|jpe?g|gif|webp|bmp|svg)(?:\?\S*)?'
    r'|aesgcm://[^\s#]+\.(?:png|jpe?g|gif|webp|bmp)' + _AESGCM_KEY_RE + ')',
    re.IGNORECASE,
)

# Ses dosyası URL'si tespit deseni (sesli mesajlar mobilden aesgcm:// gelir)
_AUDIO_URL_RE = re.compile(
    r'(https?://\S+\.(?:wav|ogg|opus|mp3|m4a|flac|aac|webm)(?:\?\S*)?'
    r'|aesgcm://[^\s#]+\.(?:wav|ogg|opus|mp3|m4a|flac|aac|webm)'
    + _AESGCM_KEY_RE + ')',
    re.IGNORECASE,
)

# ── Renk paleti — Ultra Modern Glassmorphism ─────────────────────────────────
BG        = "#06060c"   # ultra derin siyah (OLED dostu)
BG_PANEL  = "#0c0c18"   # sidebar — koyu lacivert
BG_CARD   = "#13132a"   # kart yüzeyi (cam efekt taban)
BG_CHAT   = "#080810"   # sohbet zemini (neredeyse saf siyah)
BG_INPUT  = "#181830"   # giriş alanı (belirgin)
BG_HOVER  = "#22224a"   # hover — parlak mor gölge
BG_ME     = "#7c3aed"   # gönderilen balonlar (violet-600)
BG_THEM   = "#18183a"   # alınan balonlar (cam efektli)
ACCENT    = "#c4b5fd"   # birincil vurgu (violet-300)
ACCENT2   = "#8b5cf6"   # ikincil vurgu (violet-500)
ACCENT_G  = "#34d399"   # yeşilimsi vurgu (emerald-400)
FG        = "#f1f5f9"   # ana metin (slate-100)
FG_DIM    = "#64748b"   # soluk metin (slate-500)
FG_ME     = "#ffffff"   # benim balonumdaki metin
SEL_BG    = "#4c1d95"   # liste seçimi (violet-900)
SEL_FG    = "#ffffff"
BORDER    = "#1e1b4b"   # ince kenarlık (indigo-950)
SHADOW    = "#020207"   # gölge efekti
RED       = "#f43f5e"   # hata / dnd (rose-500)
ONLINE    = "#10b981"   # emerald-500
AWAY      = "#f59e0b"   # amber-500
GLOW      = "#7c3aed"   # neon glow efekti (Tk 8 haneli RGBA desteklemez)

# Linux uyumlu font zinciri

def _pick_font():
    for f in ("Cantarell", "Noto Sans", "Liberation Sans", "DejaVu Sans", "Segoe UI"):
        try:
            r = _sp.run(["fc-list", f], capture_output=True, text=True, timeout=2)
            if r.stdout.strip():
                return f
        except Exception:
            pass
    return "TkDefaultFont"

FONT      = _pick_font()
FONT_MONO = "monospace"

# ── Bildirim desteği ─────────────────────────────────────────────────────────
_HAS_NOTIFY = False
try:
    import subprocess as _notify_sp
    _notify_sp.run(["notify-send", "--version"], capture_output=True, timeout=2)
    _HAS_NOTIFY = True
except Exception:
    pass

def _desktop_notify(title: str, body: str, icon: str = "dialog-information"):
    if _HAS_NOTIFY:
        try:
            process = _notify_sp.Popen(["notify-send", "-a", "XMPP Client",
                                        "-i", icon, title, body],
                                       stdout=_notify_sp.DEVNULL, stderr=_notify_sp.DEVNULL)
            threading.Thread(target=process.wait, daemon=True).start()
        except Exception:
            pass

# ── Bildirim sesi ────────────────────────────────────────────────────────────
_current_lang = "tr"

def _t(key: str) -> str:
    """Çeviri fonksiyonu."""
    return _STRINGS.get(_current_lang, _STRINGS["tr"]).get(key, key)


def _sidebar_menu_spec(has_active_chat: bool) -> list[tuple]:
    """Gajim tarzı ☰ ana menüsünün bölümlü yapısı (saf veri).

    Öğe türleri:
      ("section", başlık)          → devre dışı bölüm başlığı
      ("item",    etiket, anahtar) → tıklanabilir komut
      ("sep",)                     → ayırıcı

    GUI katmanı anahtarları gerçek metotlara eşler; bu fonksiyon Tk
    gerektirmediğinden doğrudan test edilebilir.
    """
    spec: list[tuple] = [
        ("section", _t("contacts")),
        ("item", f"🔍  {_t('user_search')}", "search_users"),
        ("item", f"🏷  {_t('groups')}", "groups"),
        ("sep",),
        ("section", _t("rooms")),
        ("item", f"🧭  {_t('discover_rooms')}", "discover_rooms"),
        ("item", f"📑  {_t('bookmarks')}", "bookmarks"),
        ("sep",),
        ("section", _t("advanced")),
    ]
    if has_active_chat:
        spec.append(("item", f"🎭  {_t('sticker_gif')}", "gif"))
    spec += [
        ("item", f"🔎  {_t('msg_search')}", "msg_search"),
        ("item", f"📋  {_t('log')}", "log"),
        ("item", f"🌐  {_t('rest_api')}", "rest_api"),
        ("item", f"🔄  {_t('reconnect')}", "reconnect"),
        ("item", f"🎨  {_t('theme')}", "theme"),
        ("sep",),
        ("item", f"⚙  {_t('settings')}", "settings"),
    ]
    return spec


def _chat_header_menu_spec(*, is_room: bool, compact: bool) -> list[tuple]:
    """Sohbet başlığı ⋮ menüsünün yapısı (saf veri; Tk gerektirmez).

    Öğe türleri:
      ("item", etiket, anahtar)       → komut (MainWindow anahtarı eşler)
      ("menu", etiket, [alt öğeler])  → alt menü
      ("ai",)                         → ✨ AI alt menüsü (dinamik)
      ("sep",)                        → ayırıcı
    Sık kullanılanlar üst düzeyde; gerisi konu başlıklı alt menülerde.
    """
    chat = [
        ("item", "⏱ Kaybolan Mesajlar", "disappearing"),
        ("item", "📜 Daha Eski Mesajları Yükle (MAM)", "load_older"),
        ("item", "⏰ Mesaj Zamanla", "schedule"),
        ("item", "📤 Sohbeti Dışa Aktar", "export"),
        ("item", "🗑 Geçmişi Sil", "clear_history"),
    ]
    if is_room:
        chat += [("sep",), ("item", "🔧 Oda Yönetimi", "room_admin")]
    return [
        ("item", "👤 Profil", "profile"),
        ("item", "🔎 Mesaj Ara", "search"),
        ("item", "📌 Sabitlenmiş Mesajlar", "pinned"),
        ("ai",),
        ("sep",),
        ("menu", "💬 Sohbet", chat),
        ("menu", "📤 Paylaşım", [
            ("item", "📍 Konum Paylaş", "location"),
            ("item", "📊 Anket Oluştur", "poll"),
            ("item", "📖 Hikaye Paylaş", "story"),
            ("item", "📢 Toplu Mesaj", "broadcast"),
        ]),
        ("menu", "🔒 Güvenlik", [
            ("item", "🔒 OMEMO Parmak İzleri", "omemo_fp"),
            ("item", "🔐 OMEMO QR Doğrulama", "omemo_qr"),
            ("item", "🚫 Engelli Kişiler", "blocking"),
        ]),
        ("menu", "🪟 Görünüm", [
            ("item", "📺 Yeni Sekmede Aç", "tab"),
            ("item", "📺 Bölünmüş Ekran", "split"),
            ("item", "🖼 Arka Plan Değiştir", "wallpaper"),
            ("item", "📐 Rahat Moda Geç" if compact else "📐 Kompakt Moda Geç",
             "compact"),
        ]),
        ("menu", "⚙ Diğer", [
            ("item", "💬 Durum Mesajı", "status_msg"),
            ("item", "💾 Yedekleme / Geri Yükleme", "backup"),
            ("item", "⌨ Klavye Kısayolları", "shortcuts"),
        ]),
    ]


_LAST_THEME: dict = {}
_COLOR_REMAP: dict = {}  # eski renk → yeni renk (canlı tema yenileme için)


def _theme_choices() -> list:
    """Seçilebilir tüm tema adlarını döndür."""
    return list(_THEMES.keys())


def _apply_color_theme(theme_name: str):
    """Tema renklerini global değişkenlere uygula ve renk eşlemesini kaydet."""
    global _LAST_THEME, _COLOR_REMAP
    theme = _THEMES.get(theme_name, _THEMES["koyu"])
    remap = {}
    for key, val in theme.items():
        old = _LAST_THEME.get(key)
        if old and old != val:
            remap.setdefault(old, val)
    _COLOR_REMAP = remap
    _LAST_THEME = dict(theme)
    g = globals()
    for key, val in theme.items():
        g[key] = val

# ── Emoji paleti verileri ────────────────────────────────────────────────────
_EMOJI_CATEGORIES = {
    "Yüzler": "😀😃😄😁😆😅🤣😂🙂😊😇🥰😍🤩😘😗😋😛😜🤪😝🤑🤗🤭🤫🤔🤐🤨😐😑😶😏😒🙄😬🤥😌😔😪🤤😴😷🤒🤕🤢🤮🤧🥵🥶🥴😵🤯🤠🥳🥸😎🤓🧐😕😟🙁😮😯😲😳🥺😦😧😨😰😥😢😭😱😖😣😞😓😩😫🥱😤😡😠🤬",
    "El": "👋🤚🖐✋🖖👌🤌🤏✌🤞🤟🤘🤙👈👉👆🖕👇☝👍👎✊👊🤛🤜👏🙌👐🤲🤝🙏✍💅🤳💪",
    "Kalp": "❤🧡💛💚💙💜🖤🤍🤎💔❣💕💞💓💗💖💘💝",
    "Nesne": "🎁🎀🎉🎊🎈🎃🎄✨🎆🎇📱💻🖥🖨📷📹🎥📞☎📧📬📦🏷🔑🗝🔒🔓",
    "Yiyecek": "🍎🍐🍊🍋🍌🍉🍇🍓🫐🍈🍒🍑🥭🍍🥥🥝🍅🫒🥑🥦🥬🥒🌶🫑🌽🥕🫘🧄🧅🥔🍠🥐🥖🫓🥨🥯🧀🥚🍳🥓🥩🍗🍖🌭🍔🍟🍕🫔🌮🌯🫔🥗🥘🫕🥫🍝🍜🍲🍛🍣🍱🥟🦪🍤🍙🍚🍘🍥🥠🥮🍢🍡🍧🍨🍦🥧🧁🍰🎂🍮🍭🍬🍫🍿🍩🍪🌰🥜",
    "Doğa": "🌍🌎🌏🌐🗺🌋🏔⛰🗻🏕🏖🏜🏝🌅🌄🌠🎑🏞🌉🌃🌆🌇🌌🌁⛅🌤🌥🌦🌧⛈🌩🌨❄☃🌬🌈🌊🔥",
}

# ── URL Önizleme yardımcıları ────────────────────────────────────────────────
_URL_RE = re.compile(r'(https?://[^\s<>"]+)')

# ── Sınırlı ağ okuması (Security Hotfix 1) ──────────────────────────────────
# Uzak sunucu kontrollü URL'lerden belleğe alınacak gövde boyutu tavanları.
_NET_IMG_MAX = 8 * 1024 * 1024        # satır içi görüntü
_NET_IMG_FULL_MAX = 16 * 1024 * 1024  # tam ekran görüntü
_NET_AUDIO_MAX = 25 * 1024 * 1024     # ses mesajı
_NET_GIF_THUMB_MAX = 2 * 1024 * 1024  # GIF küçük önizleme
_NET_JSON_MAX = 4 * 1024 * 1024       # JSON arama yanıtları
_NET_AESGCM_FILE_MAX = 100 * 1024 * 1024  # şifreli dosya (video, belge)
_MEDIA_WORKER_CAP = 6                 # eşzamanlı remote-media worker tavanı
_MAX_INLINE_IMAGES = 6                # mesaj başına zengin görsel tavanı (2E)
_MAX_INLINE_AUDIO = 3                 # mesaj başına zengin ses tavanı (2E)
_MEDIA_CACHE_MAX = 64                 # (kind, url) → sonuç girdisi tavanı


def _read_bounded(resp, max_bytes):
    """HTTP response gövdesini en çok max_bytes oku; aşarsa hata ver.

    Content-Length geçerli bir tamsayıysa ve tavanı aşıyorsa hiç okumadan
    hata verir. Başlık eksik/bozuksa buna güvenilmez: asıl zorlama her
    durumda resp.read(max_bytes + 1) ile yapılır; sınırsız akışta bile
    okunan veri max_bytes + 1'i geçemez.
    """
    try:
        cl = resp.headers.get("Content-Length")
    except Exception:
        cl = None
    if cl:
        try:
            declared = int(str(cl).strip())
        except (TypeError, ValueError):
            declared = None  # bozuk başlığa güvenme; bounded read zorlar
        if declared is not None and declared > max_bytes:
            raise ValueError(
                f"HTTP response exceeds size limit "
                f"(Content-Length={declared} > {max_bytes})")
    data = resp.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(
            f"HTTP response exceeds size limit (> {max_bytes} bytes)")
    return data


def _fetch_url_bytes(url, max_bytes, timeout=15):
    """URL içeriğini sınırlı oku. aesgcm:// (OMEMO ile şifreli medya,
    XEP-0454) https üzerinden indirilip çözülür; bozuksa InvalidTag."""
    media = _aesgcm.parse(url)
    req = urllib.request.Request(media[0] if media else url, headers={
        "User-Agent": "Mozilla/5.0",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = _read_bounded(resp, max_bytes)
    return _aesgcm.decrypt(raw, media[1], media[2]) if media else raw


def _aesgcm_file_urls(body: str, exclude) -> list[str]:
    """Gövdedeki resim/ses dışı şifreli dosya bağlantıları (video, belge)."""
    out = []
    for url in _aesgcm.URL_RE.findall(body or ""):
        if url not in exclude and url not in out:
            out.append(url)
    return out


def _fetch_url_preview(url: str) -> dict:
    """URL'den başlık ve açıklama çek (basit HTML parse)."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0", "Accept": "text/html"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            ct = resp.headers.get("Content-Type", "")
            if "html" not in ct:
                return {}
            html = resp.read(16384).decode("utf-8", errors="replace")
        title = ""
        desc = ""
        m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
        if m:
            title = m.group(1).strip()[:120]
        m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)', html, re.IGNORECASE)
        if not m:
            m = re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)', html, re.IGNORECASE)
        if m:
            desc = m.group(1).strip()[:200]
        img = ""
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html, re.IGNORECASE)
        if m:
            img = m.group(1).strip()
        return {"title": title, "desc": desc, "image": img}
    except Exception:
        return {}


# ── Yardımcı UI fonksiyonları ────────────────────────────────────────────────
def _rounded_rect(canvas, x1, y1, x2, y2, r, **kw):
    """Canvas'ta yuvarlatılmış dikdörtgen çizer."""
    pts = [
        x1 + r, y1,
        x2 - r, y1,
        x2,     y1,
        x2,     y1 + r,
        x2,     y2 - r,
        x2,     y2,
        x2 - r, y2,
        x1 + r, y2,
        x1,     y2,
        x1,     y2 - r,
        x1,     y1 + r,
        x1,     y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kw)


def _add_tooltip(widget, text: str):
    """Hover'da görünen sade balon (ikon-only butonlar için)."""
    state = {"win": None}

    def _show(_=None):
        if state["win"] is not None:
            return
        try:
            x = widget.winfo_rootx()
            y = widget.winfo_rooty() - 26
            win = tk.Toplevel(widget)
            win.wm_overrideredirect(True)
            win.wm_geometry(f"+{x}+{y}")
            tk.Label(win, text=text, bg=BG_CARD, fg=FG, font=(FONT, 8),
                     padx=8, pady=3, bd=0).pack()
            state["win"] = win
        except Exception:
            state["win"] = None

    def _hide(_=None):
        if state["win"] is not None:
            try:
                state["win"].destroy()
            except Exception:
                pass
            state["win"] = None

    widget.bind("<Enter>", _show, "+")
    widget.bind("<Leave>", _hide, "+")
    widget.bind("<Destroy>", _hide, "+")


def _avatar(parent, size, letter, color=None, bg=None, photo_data=None,
            _photo_refs=None):
    """Yeniden kullanılabilir Canvas daire avatar. photo_data varsa fotoğraf gösterir."""
    color = color or ACCENT2
    bg = bg or BG_PANEL
    c = tk.Canvas(parent, width=size, height=size,
                  bg=bg, highlightthickness=0)
    if photo_data and HAS_PIL:
        try:
            img = Image.open(io.BytesIO(photo_data))
            try:
                from PIL import ImageDraw, ImageOps
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass
            img = img.resize((size, size), Image.LANCZOS)
            # Dairesel maske
            try:
                from PIL import ImageDraw
                mask = Image.new("L", (size, size), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
                img.putalpha(mask)
            except Exception:
                pass
            photo = ImageTk.PhotoImage(img)
            c.create_image(size // 2, size // 2, image=photo)
            c._avatar_photo = photo  # GC koruması
            if _photo_refs is not None:
                _photo_refs.append(photo)
            return c
        except Exception:
            pass
    # Fallback: harf avatarı
    pad = 1
    c.create_oval(pad, pad, size - pad, size - pad, fill=color, outline="")
    fs = max(8, size // 3)
    c.create_text(size // 2, size // 2, text=letter.upper() if letter else "?",
                  fill=FG_ME, font=(FONT, fs, "bold"))
    return c


def _chat_theme() -> dict:
    """Chat UI katmanları için canlı tema değerleri (construction anında)."""
    return {
        "BG_CHAT": BG_CHAT, "BG_CARD": BG_CARD, "BG_HOVER": BG_HOVER,
        "BG_THEM": BG_THEM, "BG_ME": BG_ME, "BORDER": BORDER, "FG": FG,
        "FG_DIM": FG_DIM, "FG_ME": FG_ME, "ACCENT": ACCENT,
        "ACCENT2": ACCENT2, "ACCENT_G": ACCENT_G, "GLOW": GLOW,
        "RED": RED, "SHADOW": SHADOW, "FONT": FONT, "BG": BG,
        "SEL_BG": SEL_BG, "SEL_FG": SEL_FG,
    }


def _parse_msg_date(time_str):
    """Desteklenen zaman formatlarını date'e çevir; bozuk/eksik → None."""
    if not time_str:
        return None
    s = str(time_str).strip()
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        try:
            datetime.strptime(s, "%H:%M")
            return datetime.now().date()
        except ValueError:
            return None
    # Saf saat (ör. "10:30") 1900-01-01 varsayılan tarihiyle gelir → bugün say
    if dt.year == 1900:
        return datetime.now().date()
    return dt.date()


def _date_separator_label(day_key, today_key, msg_date):
    """Tarih ayırıcı etiketi: bugün → 'Bugün', aksi → mevcut intended format."""
    if day_key == today_key:
        return _t("today")
    return msg_date.strftime("%d %B %Y")


class PlaceholderEntry(ttk.Entry):
    """Placeholder destekli modern Entry."""
    def __init__(self, master, placeholder="", textvariable=None, **kw):
        self._ph = placeholder
        self._var = textvariable or tk.StringVar()
        super().__init__(master, textvariable=self._var, **kw)
        self._showing_ph = False
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
        if not self._var.get():
            self._show_placeholder()

    def _show_placeholder(self):
        self._showing_ph = True
        self._var.set(self._ph)
        self.configure(foreground=FG_DIM)

    def _on_focus_in(self, _=None):
        if self._showing_ph:
            self._var.set("")
            self.configure(foreground=FG)
            self._showing_ph = False

    def _on_focus_out(self, _=None):
        if not self._var.get():
            self._show_placeholder()

    def get_value(self):
        return "" if self._showing_ph else self._var.get()


def _apply_theme():
    s = ttk.Style()
    s.theme_use("clam")

    s.configure(".",           background=BG, foreground=FG,
                font=(FONT, 9))
    s.configure("TFrame",     background=BG)
    s.configure("TLabel",     background=BG, foreground=FG)
    s.configure("TLabelframe",       background=BG)
    s.configure("TLabelframe.Label", background=BG, foreground=FG,
                font=(FONT, 9, "bold"))

    # ── Birincil buton (gradient hissi + yumuşak köşe) ──
    s.configure("TButton",
                background=ACCENT2, foreground=FG_ME,
                borderwidth=0, padding=(20, 11),
                font=(FONT, 10, "bold"), focuscolor="")
    s.map("TButton",
          background=[("active", ACCENT), ("pressed", "#6d28d9")],
          foreground=[("active", FG_ME)])

    # ── İkincil / küçük buton ──
    s.configure("Small.TButton",
                background=BG_HOVER, foreground=FG,
                borderwidth=0, padding=(10, 6),
                font=(FONT, 9), focuscolor="")
    s.map("Small.TButton",
          background=[("active", SEL_BG), ("pressed", SEL_BG)],
          foreground=[("active", FG_ME)])

    # ── Hayalet buton (şeffaf arka plan) ──
    s.configure("Ghost.TButton",
                background=BG_PANEL, foreground=ACCENT,
                borderwidth=0, padding=(14, 9),
                font=(FONT, 9), focuscolor="")
    s.map("Ghost.TButton",
          background=[("active", BG_HOVER), ("pressed", BG_HOVER)],
          foreground=[("active", FG_ME)])

    # ── Tehlike butonu (kırmızı) ──
    s.configure("Danger.TButton",
                background="#881337", foreground="#fecdd3",
                borderwidth=0, padding=(20, 11),
                font=(FONT, 10, "bold"), focuscolor="")
    s.map("Danger.TButton",
          background=[("active", RED), ("pressed", "#9f1239")],
          foreground=[("active", FG_ME)])

    # ── Giriş alanı (daha belirgin kenarlık hissi) ──
    s.configure("TEntry",
                fieldbackground=BG_INPUT, foreground=FG,
                insertcolor=ACCENT, borderwidth=1,
                bordercolor=BORDER, lightcolor=BORDER,
                darkcolor=BORDER, padding=7)
    # Modern entry (büyük padding + focus rengi)
    s.configure("Modern.TEntry",
                fieldbackground=BG_HOVER, foreground=FG,
                insertcolor=ACCENT, borderwidth=2,
                bordercolor=BORDER, lightcolor=BORDER,
                darkcolor=BORDER, padding=10)
    s.map("Modern.TEntry",
          bordercolor=[("focus", ACCENT2)],
          lightcolor=[("focus", ACCENT2)])

    s.configure("TCombobox",
                fieldbackground=BG_INPUT, foreground=FG,
                selectbackground=SEL_BG, selectforeground=SEL_FG,
                bordercolor=BORDER, lightcolor=BORDER,
                darkcolor=BORDER, padding=5)
    s.map("TCombobox",
          fieldbackground=[("readonly", BG_INPUT)],
          bordercolor=[("focus", ACCENT2)])

    s.configure("Panel.TFrame",  background=BG_PANEL)
    s.configure("Panel.TLabel",  background=BG_PANEL, foreground=FG)
    s.configure("Input.TFrame",  background=BG_INPUT)

    # ── Notebook (sekmeler — alt çizgi vurgusu) ──
    s.configure("TNotebook",     background=BG_PANEL, borderwidth=0,
                tabmargins=(2, 6, 0, 0))
    s.configure("TNotebook.Tab", background=BG_INPUT, foreground=FG_DIM,
                padding=(22, 12), font=(FONT, 9, "bold"))
    s.map("TNotebook.Tab",
          background=[("selected", BG_PANEL), ("active", BG_HOVER)],
          foreground=[("selected", ACCENT), ("active", FG)])

    # ── Scrollbar (ince, yuvarlak, modern) ──
    s.configure("Vertical.TScrollbar",
                background=BORDER, troughcolor=BG,
                borderwidth=0, arrowsize=0, width=4)
    s.map("Vertical.TScrollbar",
          background=[("active", ACCENT2), ("pressed", ACCENT2)])

    # ── Checkbutton ──
    s.configure("TCheckbutton",
                background=BG_PANEL, foreground=FG_DIM,
                focuscolor="", font=(FONT, 8))
    s.map("TCheckbutton",
          background=[("active", BG_PANEL)],
          foreground=[("active", FG)])

    s.layout("SidebarFilter.TRadiobutton", s.layout("Toolbutton"))
    s.configure("SidebarFilter.TRadiobutton",
                background=BG_PANEL, foreground=FG_DIM, borderwidth=0,
                padding=(5, 4), font=(FONT, 8), relief="flat")
    s.map("SidebarFilter.TRadiobutton",
          background=[("selected", BG_HOVER), ("active", BG_HOVER)],
          foreground=[("selected", ACCENT), ("active", FG)])

    # ── Progressbar ──
    s.configure("TProgressbar",
                background=ACCENT2, troughcolor=BG_HOVER,
                borderwidth=0, thickness=4)


try:
    from slixmpp import ClientXMPP
except ImportError:
    import sys
    print("slixmpp kurulu değil → pip install slixmpp")
    sys.exit(1)

# ── GPG uyumluluk yaması ─────────────────────────────────────────────────────
# slixmpp'in gnupg modülü yeni GPG durum mesajlarını (INV_SGNR vb.) tanımıyor.
# _read_response içindeki handle_status çağrısını sarmalayarak ValueError'ları yutuyoruz.
try:
    from slixmpp.thirdparty import gnupg as _gnupg
    _orig_read_response = _gnupg.GPG._read_response
    def _patched_read_response(self, stream, result):
        lines = []
        while True:
            line = stream.readline()
            if len(line) == 0:
                break
            lines.append(line)
            line = line.rstrip()
            if self.verbose:
                print(line)
            if line[0:9] == '[GNUPG:] ':
                line = line[9:]
                L = line.split(None, 1)
                keyword = L[0]
                value = L[1] if len(L) > 1 else ""
                try:
                    result.handle_status(keyword, value)
                except ValueError:
                    pass
        result.stderr = ''.join(lines)
    _gnupg.GPG._read_response = _patched_read_response
except Exception:
    pass

# ── OMEMO desteği ────────────────────────────────────────────────────────────
HAS_OMEMO = False
try:
    import pathlib

    from omemo.storage import Just, Maybe, Nothing
    from omemo.storage import Storage as _OmemoStorage
    from omemo.types import DeviceInformation
    from omemo.types import JSONType as _JSONType
    from slixmpp.plugins import register_plugin as _slx_register_plugin
    from slixmpp_omemo import XEP_0384 as _XEP_0384_Base
    from slixmpp_omemo import TrustLevel

    _OMEMO_DIR = pathlib.Path(os.path.expanduser("~/.xmpp_omemo"))
    _OMEMO_DIR.mkdir(parents=True, exist_ok=True)

    class _OmemoStorageImpl(_OmemoStorage):
        """JSON dosya tabanlı OMEMO anahtar deposu."""
        def __init__(self, path: pathlib.Path) -> None:
            super().__init__()
            self._path = path
            self._data: dict[str, _JSONType] = {}
            try:
                self._data = json.loads(path.read_text("utf-8"))
            except Exception:
                pass

        async def _load(self, key: str) -> Maybe[_JSONType]:
            return Just(self._data[key]) if key in self._data else Nothing()

        async def _store(self, key: str, value: _JSONType) -> None:
            self._data[key] = value
            self._path.write_text(json.dumps(self._data), "utf-8")

        async def _delete(self, key: str) -> None:
            self._data.pop(key, None)
            self._path.write_text(json.dumps(self._data), "utf-8")

    class XEP_0384Impl(_XEP_0384_Base):
        """Somut OMEMO plugin uygulaması — BTBV (Blind Trust) açık."""
        default_config = {
            "data_dir": str(_OMEMO_DIR),
            "fallback_message": "Bu mesaj OMEMO ile şifrelenmiştir.",
        }

        def plugin_init(self) -> None:
            self._data_dir = pathlib.Path(
                self.config.get("data_dir", str(_OMEMO_DIR)))
            self._data_dir.mkdir(parents=True, exist_ok=True)
            self._storage: _OmemoStorage | None = None
            self._storage_jid: str | None = None
            super().plugin_init()

        @property
        def storage(self) -> _OmemoStorage:
            # boundjid ancak oturum bağlandıktan sonra dolu olur; bu yüzden
            # depo dosyası tembel olarak oluşturulur.
            jid_safe = (self.xmpp.boundjid.bare
                        .replace("@", "_at_").replace(".", "_")) or "varsayilan"
            if self._storage is None or self._storage_jid != jid_safe:
                self._storage = _OmemoStorageImpl(
                    self._data_dir / f"{jid_safe}.json")
                self._storage_jid = jid_safe
            return self._storage

        @property
        def _btbv_enabled(self) -> bool:
            return True

        async def _devices_blindly_trusted(
            self, blindly_trusted: frozenset[DeviceInformation],
            identifier: str | None,
        ) -> None:
            pass  # BTBV — otomatik güven

        async def _prompt_manual_trust(
            self, manually_trusted: frozenset[DeviceInformation],
            identifier: str | None,
        ) -> None:
            # BTBV açık olduğundan burası normalde çağrılmaz
            sm = await self.get_session_manager()
            for dev in manually_trusted:
                await sm.set_trust(
                    dev.bare_jid, dev.identity_key,
                    TrustLevel.TRUSTED.value,
                )

    _slx_register_plugin(XEP_0384Impl)
    HAS_OMEMO = True
except ImportError:
    pass


# ══════════════════════════════════════════════════════════════════════════════
# XMPP İstemcisi
# ══════════════════════════════════════════════════════════════════════════════

class XMPPBot(PresenceMixin, MessagesMixin, MucMixin, ArchiveMixin,
              TransferMixin, ClientXMPP):
    # [2P-BUG B] Transiyan (geçici) OMEMO hata belirteçleri: oturum/bundle
    # hazır-değil sınıfı hatalar SINIRLI retry edilir; kriptografik/trust
    # kalıcı hatalar (ör. "Device is not trusted") retry edilmez, explicit
    # failure olarak yüzeylenir.
    _OMEMO_RETRYABLE = ("session", "no_session", "prepare", "bundle",
                        "keyexchange", "prekey")

    def __init__(self, jid, password, gui_q):
        super().__init__(jid, password)
        self.gui_q    = gui_q
        self.my_nicks: dict[str, str] = {}   # room → nick
        self._connected_ok = False           # session_start geldi mi?
        self._closing = False
        self._reconnect_stop = threading.Event()
        self.omemo_ready = False
        # Gönderdiğimiz mesajların kimlikleri: odadaki yansımayı aynı hesabın
        # başka cihazından (telefon) gelen mesajdan ayırmak için (MucMixin)
        self._sent_ids: deque = deque(maxlen=1000)
        self.add_filter("out", self._remember_sent_id)
        self._register_xeps()
        self._register_handlers()
        self.ft = JingleFTManager(self, gui_q)
        self.register_handler(CoroutineCallback(
            "Jingle FT", StanzaPath("iq@type=set/jingle"),
            self.ft.handle_jingle_iq))
        self.add_event_handler("session_bind", self._on_session_bind_jingle)

    def connect(self, host=None, port=None):
        """Yeniden bağlantıda girişte seçilmiş sunucu adresini koru."""
        if getattr(self, "_closing", False) or getattr(self, "_auth_failed", False):
            return None
        if host is None and port is None:
            address = getattr(self, "custom_address", None)
            if address:
                host, port = address
        return super().connect(host=host, port=port)

    async def _close_connection(self):
        """Çevrimdışı presence ve stream kapanışı bitince döngüyü durdur."""
        self._closing = True
        stop = getattr(self, "_reconnect_stop", None)
        if stop is not None:
            stop.set()
        try:
            self.cancel_connection_attempt()
            if self.is_connected():
                self.send_presence(ptype="unavailable")
            await self.disconnect(wait=1)
        except Exception:
            _log.warning("XMPP bağlantısı kapatılamadı", exc_info=True)
        finally:
            try:
                self.abort()
            finally:
                self.loop.stop()

    def _omemo_enabled(self) -> bool:
        """OMEMO kütüphanesi yüklenebilir mi? (tek doğruluk kaynağı: bu modül)"""
        return HAS_OMEMO

    # ── Plugin kayıt ──────────────────────────────────────────────────────────
    def _safe_reg(self, name):
        import io
        import sys
        old = sys.stderr
        sys.stderr = io.StringIO()
        try:
            self.register_plugin(name)
        except Exception:
            pass
        finally:
            sys.stderr = old

    def _register_xeps(self):
        for xep in [
            # ── Temel & Keşif ──────────────────────────────────────────────
            "xep_0030",  # Service Discovery
            "xep_0092",  # Software Version
            "xep_0115",  # Entity Capabilities
            "xep_0128",  # Service Discovery Extensions
            "xep_0199",  # XMPP Ping
            "xep_0202",  # Entity Time
            "xep_0203",  # Delayed Delivery

            # ── Form & Kayıt ──────────────────────────────────────────────
            "xep_0004",  # Data Forms
            "xep_0050",  # Ad-Hoc Commands
            "xep_0055",  # Jabber Search
            "xep_0077",  # In-Band Registration
            "xep_0122",  # Data Forms Validation

            # ── Mesajlaşma ─────────────────────────────────────────────────
            "xep_0066",  # Out of Band Data
            "xep_0071",  # XHTML-IM
            "xep_0085",  # Chat State Notifications
            "xep_0184",  # Message Delivery Receipts
            "xep_0224",  # Attention
            "xep_0231",  # Bits of Binary
            "xep_0249",  # Direct MUC Invitations
            "xep_0280",  # Message Carbons
            "xep_0308",  # Last Message Correction
            "xep_0333",  # Chat Markers
            "xep_0334",  # Message Processing Hints
            "xep_0359",  # Unique and Stable Stanza IDs
            "xep_0422",  # Message Fastening
            "xep_0424",  # Message Retraction
            "xep_0444",  # Message Reactions
            "xep_0461",  # Message Replies

            # ── Mesaj Arşivi ───────────────────────────────────────────────
            "xep_0059",  # Result Set Management
            "xep_0297",  # Stanza Forwarding
            "xep_0313",  # Message Archive Management (MAM)

            # ── Şifreleme ──────────────────────────────────────────────────
            "xep_0027",  # Current Jabber OpenPGP Usage
            "xep_0380",  # Explicit Message Encryption
            "xep_0300",  # Cryptographic Hash Functions
            # xep_0384 (OMEMO) ayrı kaydedilir

            # ── Kişiler & Profil ───────────────────────────────────────────
            "xep_0012",  # Last Activity
            "xep_0054",  # vcard-temp
            "xep_0084",  # User Avatar (PEP)
            "xep_0153",  # vCard-Based Avatars
            "xep_0172",  # User Nickname
            "xep_0191",  # Blocking Command
            "xep_0292",  # vCard4 Over XMPP

            # ── Grup Sohbet (MUC) ──────────────────────────────────────────
            "xep_0045",  # Multi-User Chat
            "xep_0048",  # Bookmarks
            "xep_0402",  # PEP Native Bookmarks
            "xep_0410",  # MUC Self-Ping
            "xep_0421",  # Anonymous Unique Occupant IDs

            # ── PubSub & PEP ──────────────────────────────────────────────
            "xep_0060",  # Publish-Subscribe
            "xep_0163",  # Personal Eventing Protocol (PEP)

            # ── Durum / Konum / Aktivite ───────────────────────────────────
            "xep_0080",  # User Location
            "xep_0107",  # User Mood
            "xep_0108",  # User Activity
            "xep_0118",  # User Tune
            "xep_0256",  # Last Activity in Presence
            "xep_0319",  # Last User Interaction

            # ── Dosya Transferi ────────────────────────────────────────────
            "xep_0047",  # In-Band Bytestreams
            "xep_0065",  # SOCKS5 Bytestreams
            "xep_0096",  # SI File Transfer
            "xep_0234",  # Jingle File Transfer
            "xep_0363",  # HTTP File Upload

            # ── Bağlantı & Mobil ───────────────────────────────────────────
            "xep_0198",  # Stream Management
            "xep_0352",  # Client State Indication
        ]:
            self._safe_reg(xep)

        # OMEMO plugin — ayrı kayıt
        if HAS_OMEMO:
            try:
                self.register_plugin(
                    "xep_0384",
                    {"data_dir": str(_OMEMO_DIR)},
                )
            except Exception as e:
                self._omemo_reg_error = str(e)
                self.gui_q.put(("sys_msg",
                    f"⚠ OMEMO plugin kaydı başarısız: {e}"))

    # ── Event handler kayıt ───────────────────────────────────────────────────
    def _register_handlers(self):
        self.add_event_handler("session_start",         self._on_start)
        self.add_event_handler("message",               self._on_message)
        self.add_event_handler("groupchat_message",     self._on_gc_message)
        self.add_event_handler("changed_status",        self._on_presence)
        self.add_event_handler("failed_auth",           self._on_auth_fail)
        self.add_event_handler("disconnected",          self._on_disconnect)
        self.add_event_handler("chatstate_composing",   self._on_typing_start)
        self.add_event_handler("chatstate_paused",      self._on_typing_stop)
        self.add_event_handler("chatstate_active",      self._on_typing_stop)
        self.add_event_handler("chatstate_gone",        self._on_typing_stop)
        self.add_event_handler("chatstate_inactive",    self._on_typing_stop)
        self.add_event_handler("groupchat_invite",      self._on_muc_invite)
        self.add_event_handler("groupchat_direct_invite", self._on_muc_invite)
        self.add_event_handler("groupchat_presence",    self._on_muc_presence)
        self.add_event_handler("groupchat_subject",     self._on_muc_subject)
        self.add_event_handler("presence_subscribe",    self._on_subscribe_req)
        self.add_event_handler("presence_subscribed",   self._on_subscribed)
        self.add_event_handler("presence_unsubscribed", self._on_unsubscribed)
        self.add_event_handler("connected",             self._on_tcp_connected)
        self.add_event_handler("connection_failed",     self._on_conn_fail)
        self.add_event_handler("encrypted_message",    self._on_pgp_message)
        if HAS_OMEMO:
            self.add_event_handler("omemo_initialized", self._on_omemo_ready)
        self.add_event_handler("marker_displayed", self._on_marker_displayed)
        self.add_event_handler("message_correction", self._on_message_correction)
        self.add_event_handler("message_retract", self._on_message_retract)
        self.add_event_handler("reactions", self._on_reactions)
        # XEP-0280: aynı hesabın diğer cihazlarının (telefon) kopyaları
        self.add_event_handler("carbon_sent", self._on_carbon_sent)
        self.add_event_handler("carbon_received", self._on_carbon_received)

    # ── Session ───────────────────────────────────────────────────────────────
    async def _on_start(self, _):
        self._connected_ok = True
        # XEP-0027: presence imzalama filtresini kaldır (kendi key olmadan hata veriyor)
        # Kendi anahtarımız ayarlandığında _setup_own_pgp_key tekrar ekler
        try:
            self.del_filter('out', _get_xep(self, "xep_0027")._sign_presence)
        except Exception:
            pass
        await self.get_roster()
        self.send_presence()
        try:
            await _get_xep(self, "xep_0280").enable()
        except Exception:
            pass
        # PGP: kendi anahtarımızı bul ve ayarla
        self._setup_own_pgp_key()
        self._reconnect_delay = 2  # Başarılı bağlantıda sıfırla
        self._auth_failed = False
        roster = {str(jid): self.client_roster[jid]["name"] or str(jid)
                  for jid in self.client_roster}
        self.gui_q.put(("connected", roster))
        # Kendi oda servisimizi keşfet (ör. yax.im → chat.yax.im); bloklamaz
        _spawn_task(self, self._find_muc_service())
        # OMEMO hazırlık kontrolü (10s sonra hâlâ hazır değilse uyar)
        if HAS_OMEMO:
            _spawn_task(self, self._check_omemo_readiness())

    async def _check_omemo_readiness(self):
        """OMEMO başlatma sonucunu bekle ve hata varsa raporla."""
        await asyncio.sleep(15)
        if not self.omemo_ready:
            try:
                xep = _get_xep(self, "xep_0384")
                # get_session_manager tekrar dene — belki hâlâ çalışıyor
                await asyncio.wait_for(xep.get_session_manager(), timeout=10)
                # Başarılı olduysa event zaten tetiklendi
            except asyncio.TimeoutError:
                self.gui_q.put(("sys_msg",
                    "⚠ OMEMO başlatma zaman aşımına uğradı. "
                    "Sunucu PEP/PubSub desteklemeyebilir."))
            except Exception as e:
                self.gui_q.put(("sys_msg",
                    f"⚠ OMEMO başlatma hatası: {e}"))

    def _on_omemo_ready(self, _):
        self.omemo_ready = True
        self.gui_q.put(("sys_msg", "🔐 OMEMO şifreleme hazır"))

    async def _decrypt_and_deliver(self, msg, mtype, own_to=None):
        """OMEMO mesajını çöz ve GUI'ye ilet. `own_to` verilirse mesaj başka
        cihazımızdan o kişiye gönderilmiş kopyadır (carbon) ve bizim
        mesajımız olarak (own_msg) iletilir.

        [2P-BUG B] 'Bazen çözülmüyor' kanıtı: oturum/bundle hazır-değil
        gibi GEÇİCİ hatalar tek denemede kalıcı kayba dönüşüyordu (yalnız
        sys_msg). Şimdi: transiyan hatalarda SINIRLI yeniden deneme (3
        deneme, artan bounded backoff, asyncio — Tk bloklamaz; tek pending
        görev/stanza — çift plaintext yok); kalıcı kriptografik hatalar
        retry edilmeden tek explicit sys_msg ile yüzeylenir.
        """
        stanza_id = _stanza_msg_id(msg) or ""
        pending = getattr(self, "_omemo_decrypt_pending", None)
        if pending is None:
            pending = set()
            self._omemo_decrypt_pending = pending
        if stanza_id and stanza_id in pending:
            return
        if stanza_id:
            pending.add(stanza_id)
        try:
            last_error = None
            for attempt in range(1, 4):
                try:
                    xep = _get_xep(self, "xep_0384")
                    plaintext_msg, _device_info = await xep.decrypt_message(msg)
                    body = plaintext_msg["body"] or ""
                    if not body:
                        return
                    # Şifreli düzeltme (XEP-0308): <replace> şifresiz kısımda
                    # durur; çözülen metin orijinal mesaja uygulanır
                    orig_id = ""
                    if _has_child(msg.xml, _CORRECTION):
                        try:
                            orig_id = str(msg["replace"]["id"] or "")
                        except Exception:
                            orig_id = ""
                    if orig_id:
                        self.gui_q.put(("msg_correction", {
                            "from": str(msg["from"].bare),
                            "orig_id": orig_id,
                            "body": (body if mtype == "groupchat"
                                     else _strip_quoted_fallback(msg, body)),
                            "nick": str(msg["from"].resource or msg["from"].user),
                        }))
                        return
                    if mtype == "groupchat":
                        sender = str(msg["from"].resource)
                        room = str(msg["from"].bare)
                        own = self._muc_own_message(msg, room, sender)
                        if own == "echo":
                            return
                        if own == "other":
                            self.gui_q.put(("own_msg", {
                                "to": room,
                                "body": body,
                                "oob": "",
                                "encrypted": "omemo",
                                "mid": _stanza_msg_id(msg),
                                "reply": self._reply_info(msg),
                            }))
                            return
                        self.gui_q.put(("msg", {
                            "from": room,
                            "nick": sender,
                            "body": body,
                            "type": "groupchat",
                            "oob":  "",
                            "encrypted": "omemo",
                            "mid": _stanza_msg_id(msg),
                            "reply": self._reply_info(msg),
                        }))
                    elif own_to:
                        self.gui_q.put(("own_msg", {
                            "to": own_to,
                            "body": _strip_quoted_fallback(msg, body),
                            "oob": "",
                            "encrypted": "omemo",
                            "mid": _stanza_msg_id(msg),
                            "reply": self._reply_info(msg),
                        }))
                    else:
                        self.gui_q.put(("msg", {
                            "from": str(msg["from"].bare),
                            "nick": str(msg["from"].user),
                            "body": _strip_quoted_fallback(msg, body),
                            "type": "chat",
                            "oob":  "",
                            "encrypted": "omemo",
                            "mid": _stanza_msg_id(msg),
                            "reply": self._reply_info(msg),
                        }))
                    return
                except Exception as e:
                    last_error = e
                    marker = (str(e) + type(e).__name__).lower()
                    if attempt >= 3 or not any(
                            t in marker for t in self._OMEMO_RETRYABLE):
                        break                       # kalıcı: retry yok
                    await asyncio.sleep(0.1 * attempt)   # bounded backoff
            self.gui_q.put(("sys_msg",
                            f"⚠ OMEMO çözme hatası: {last_error}"))
        finally:
            if stanza_id and stanza_id in pending:
                pending.discard(stanza_id)

    # ── PGP ──────────────────────────────────────────────────────────────────
    def _on_pgp_message(self, msg):
        """XEP-0027 şifreli mesaj alındı — çöz ve GUI'ye ilet."""
        try:
            # msg["encrypted"] → get_encrypted() → otomatik decrypt yapar
            plaintext = msg["encrypted"]
            if isinstance(plaintext, bytes):
                plaintext = plaintext.decode("utf-8", errors="replace")
            if not plaintext:
                # Decrypt başarısız — ham XML text'i dene
                raw = msg.xml.find("{jabber:x:encrypted}x")
                if raw is not None and raw.text:
                    xep = _get_xep(self, "xep_0027")
                    plaintext = xep.decrypt(raw.text)
                    if isinstance(plaintext, bytes):
                        plaintext = plaintext.decode("utf-8", errors="replace")
            if not plaintext:
                self.gui_q.put(("sys_msg", "⚠ PGP mesajı çözülemedi (anahtar eksik?)"))
                return
            mtype = msg["type"]
            if mtype == "groupchat":
                sender = str(msg["from"].resource)
                room = str(msg["from"].bare)
                if sender == self.my_nicks.get(room, ""):
                    return
                self.gui_q.put(("msg", {
                    "from": room,
                    "nick": sender,
                    "body": _strip_quoted_fallback(msg, plaintext),
                    "type": "groupchat",
                    "oob": "",
                    "encrypted": "pgp",
                    "mid": _stanza_msg_id(msg),
                    "reply": self._reply_info(msg),
                }))
            else:
                self.gui_q.put(("msg", {
                    "from": str(msg["from"].bare),
                    "nick": str(msg["from"].user),
                    "body": _strip_quoted_fallback(msg, plaintext),
                    "type": "chat",
                    "oob": "",
                    "encrypted": "pgp",
                    "mid": _stanza_msg_id(msg),
                    "reply": self._reply_info(msg),
                }))
        except Exception as e:
            self.gui_q.put(("sys_msg", f"⚠ PGP çözme hatası: {e}"))

    def _setup_own_pgp_key(self):
        """Kendi JID'imiz için GPG anahtarını bul ve ayarla."""
        try:
            xep = _get_xep(self, "xep_0027")
            bare = str(self.boundjid.bare)
            # 1) Config'den
            cfg = _load_config()
            pgp_map = cfg.get("pgp_keymap", {})
            if bare in pgp_map:
                xep.set_keyid(jid=bare, keyid=pgp_map[bare])
                # Presence imzalama filtresini geri ekle
                self.add_filter('out', xep._sign_presence)
                self.gui_q.put(("sys_msg", "🔑 PGP anahtar ayarlandı (config)"))
                return
            # 2) GPG secret key'lerden JID ile eşleşen
            for key in xep.gpg.list_keys(True):  # True = secret keys
                for uid in key.get("uids", []):
                    if bare.lower() in uid.lower():
                        keyid = key["keyid"]
                        xep.set_keyid(jid=bare, keyid=keyid)
                        self.add_filter('out', xep._sign_presence)
                        self.gui_q.put(("sys_msg",
                            f"🔑 PGP anahtar otomatik eşleştirildi: {keyid[-8:]}"))
                        return
            # 3) İlk secret key'i kullan (tek key varsa)
            secret_keys = xep.gpg.list_keys(True)
            if len(secret_keys) == 1:
                keyid = secret_keys[0]["keyid"]
                xep.set_keyid(jid=bare, keyid=keyid)
                self.add_filter('out', xep._sign_presence)
                self.gui_q.put(("sys_msg",
                    f"🔑 PGP: tek secret key kullanılıyor: {keyid[-8:]}"))
                return
        except Exception:
            pass

    def pgp_available(self) -> bool:
        """PGP (GPG) kullanılabilir mi?"""
        try:
            xep = _get_xep(self, "xep_0027")
            keys = xep.gpg.list_keys()
            return len(keys) > 0
        except Exception:
            return False

    def pgp_list_keys(self) -> list:
        """Mevcut GPG anahtarlarını döndür."""
        try:
            xep = _get_xep(self, "xep_0027")
            return [{"keyid": k["keyid"][-8:],
                     "uids": k.get("uids", [])}
                    for k in xep.gpg.list_keys()]
        except Exception:
            return []

    def _on_tcp_connected(self, _):
        self.gui_q.put(("sys_msg", "Sunucuya bağlandı, oturum açılıyor…"))

    def _on_conn_fail(self, err):
        detail = str(err) if err else ""
        addr = getattr(self, "custom_address", None)
        self.gui_q.put(("conn_failed", {
            "error": detail,
            "domain": str(getattr(self, "default_domain", "") or ""),
            "port": getattr(self, "default_port", 5222),
            "address": f"{addr[0]}:{addr[1]}" if addr else "",
        }))

    async def get_dns_records(self, domain, port=None):
        """SRV kayıtlarını al; IPv4'ü öne al / IPv6 yoksa ele.

        slixmpp kayıtları getaddrinfo sırasıyla dener; IPv6 rotası
        olmayan ağlarda ilk denemeler "Network is unreachable" ile
        zaman kaybettirir. Bu sarmalayıcı sırayı yerel duruma göre
        düzeltir.
        """
        if self._current_proxy():
            # Proxy (ör. Tor) etkinken yerel SRV/DNS sorgusu yapılmaz: ad
            # proxy'de çözülür, alan adı yerel çözücüye sızmaz
            return [("", domain, domain, port or self.default_port)]
        records = await super().get_dns_records(domain, port)
        return _prefer_ipv4(records, _ipv6_available())

    def _current_proxy(self):
        """Ayarlardaki geçerli proxy (her bağlantı denemesinde okunur)."""
        return _proxy_settings(_load_config())

    async def _attempt_connection(self, host, port, tls, server_hostname):
        """Proxy ayarlıysa bağlantıyı tünel üstünden kur (slixmpp'nin
        kendi denemesiyle aynı sözleşme: True/False, connection_failed)."""
        proxy = self._current_proxy()
        if not proxy:
            return await super()._attempt_connection(
                host, port, tls, server_hostname)
        self.event_when_connected = "connected"
        self._connect_loop_wait += 1
        if self._current_connection_attempt is None:
            return False
        ssl_context = self.get_ssl_context() if tls else None
        try:
            sock = await _open_proxy_tunnel(self.loop, proxy, host, port)
            await self.loop.create_connection(
                lambda: self, sock=sock, ssl=ssl_context,
                server_hostname=server_hostname if tls else None)
        except OSError as e:
            _log.warning("Proxy (%s %s:%s) üzerinden bağlanılamadı: %s",
                         proxy["type"], proxy["host"], proxy["port"], e)
            self.event("connection_failed", e)
            return False
        self._connect_loop_wait = 0
        return True

    def _on_auth_fail(self, _):
        # Otomatik yeniden bağlanmayı kapat: şifre yanlışsa denemek anlamsız.
        self._auth_failed = True
        self.gui_q.put(("auth_failed",
            "Giriş başarısız: JID veya şifre yanlış."))
        self.disconnect()

    def _on_disconnect(self, _):
        self.omemo_ready = False
        self._connected_ok = False
        self.gui_q.put(("disconnected", None))
        # Otomatik reconnect — üstel geri çekilme
        if getattr(self, "_closing", False):
            return
        if getattr(self, '_reconnect_pending', False):
            return
        if not getattr(self, '_auth_failed', False):
            delay = getattr(self, '_reconnect_delay', 2)
            self.gui_q.put(("sys_msg", f"⟳ {delay}s sonra yeniden bağlanılıyor…"))
            self._reconnect_pending = True
            def _do_reconnect():
                try:
                    stop = getattr(self, "_reconnect_stop", None)
                    if stop is not None:
                        if stop.wait(delay):
                            return
                    else:
                        time.sleep(delay)
                    if (getattr(self, "_closing", False)
                            or getattr(self, "_auth_failed", False)):
                        return
                    self.loop.call_soon_threadsafe(self.connect)
                except Exception:
                    _log.warning("Yeniden bağlanma planlanamadı", exc_info=True)
                finally:
                    self._reconnect_pending = False
            self._reconnect_delay = min(delay * 2, 120)  # max 2dk
            threading.Thread(target=_do_reconnect, daemon=True).start()

    def _dispatch_loop(self, fn):
        """fn'i XMPP loop thread'inde çalıştır; loop yoksa doğrudan.

        GUI thread'inden yapılan senkron send() çağrıları
        (waiting_queue.put_nowait / iq Future) loop'a taşınır; public
        imzalar korunur. Loop yoksa davranış eski haliyle kalır.
        """
        loop = getattr(self, "loop", None)
        if loop is None:
            fn()
            return
        try:
            if asyncio.get_running_loop() is loop:
                fn()
                return
        except RuntimeError:
            pass
        loop.call_soon_threadsafe(fn)

    def _send_pgp(self, to, body, mtype, mid=None):
        """XEP-0027 PGP şifreli mesaj gönder."""
        try:
            xep = _get_xep(self, "xep_0027")
            # keyid ayarlı mı kontrol et — yoksa otomatik eşleştirmeyi dene
            keyid = xep.get_keyid(to)
            if not keyid:
                keyid = self._pgp_auto_keyid(to)
            if not keyid:
                self.gui_q.put(("error",
                    f"PGP: {to} için GPG anahtarı bulunamadı. "
                    "Ayarlar → Şifreleme'den anahtar eşleştirin."))
                return
            # Doğrudan gpg.encrypt ile şifrele (keyid = fingerprint/uid)
            enc = xep.gpg.encrypt(body, keyid)
            if not enc.ok:
                self.gui_q.put(("error",
                    f"PGP şifreleme başarısız: {enc.status}"))
                return
            # Ham şifreli veriyi PGP stanza'ya yerleştir.
            # _extract_data slixmpp'in kendi yardımcısı; yoksa armoru ham kullan.
            try:
                from slixmpp.plugins.xep_0027.gpg import _extract_data
                enc_data = _extract_data(enc.data, 'MESSAGE')
            except ImportError:
                enc_data = enc.data
            if not enc_data:
                self.gui_q.put(("error", "PGP: Şifreli veri çıkarılamadı"))
                return
            msg = self.make_message(mto=to, mtype=mtype)
            _add_origin_id(msg, mid)
            msg["body"] = "Bu mesaj PGP ile şifrelenmiştir."
            # Encrypted stanza XML'ine doğrudan yaz
            enc_xml = msg.xml.find("{jabber:x:encrypted}x")
            if enc_xml is None:
                enc_xml = ET.SubElement(msg.xml,
                    "{jabber:x:encrypted}x")
            enc_xml.text = enc_data
            msg.send()
        except Exception as e:
            self.gui_q.put(("error", f"PGP gönderme hatası: {e}"))

    def _pgp_auto_keyid(self, jid):
        """JID için GPG anahtarını otomatik bulmaya çalış."""
        try:
            xep = _get_xep(self, "xep_0027")
            bare = str(jid).split("/")[0]
            # 1) Config'deki eşleştirmelerden bak
            cfg = _load_config()
            pgp_map = cfg.get("pgp_keymap", {})
            if bare in pgp_map:
                keyid = pgp_map[bare]
                xep.set_keyid(jid=bare, keyid=keyid)
                return keyid
            # 2) GPG anahtarlarında JID'nin bare adresiyle eşleşen uid ara
            for key in xep.gpg.list_keys():
                for uid in key.get("uids", []):
                    if bare.lower() in uid.lower():
                        keyid = key["keyid"]
                        xep.set_keyid(jid=bare, keyid=keyid)
                        return keyid
        except Exception:
            pass
        return None

    async def _send_omemo(self, to, body, mtype, reply_id=None, reply_body=None,
                          mid=None, reply_to_jid=None):
        """[2P-BUG A] Hızlı ardışık OMEMO gönderimde eşzamanlı encrypt
        hazırlık yarışı (SessionManager) mesajların DÜŞMESİNE yol açıyordu.

        Sıra koruyarak serileştirme: asyncio.Lock FIFO bekler — 'ignore
        while busy' değil; her gönderim kendi sabit body/mid state'ine
        sahiptir ve hiçbiri düşmez. Test: test_2p_consecutive_send.py
        yarış modeli.
        """
        lock = getattr(self, "_omemo_send_lock", None)
        if lock is None:
            lock = asyncio.Lock()
            self._omemo_send_lock = lock
        async with lock:
            await self._send_omemo_locked(to, body, mtype, reply_id,
                                          reply_body, mid, reply_to_jid)

    async def _send_omemo_locked(self, to, body, mtype, reply_id=None,
                                 reply_body=None, mid=None,
                                 reply_to_jid=None):
        """OMEMO şifreli mesaj gönder. reply_id/body verilirse yanıt bilgisi
        şifreli yüke eklenir (XEP-0461 + XEP-0428 fallback)."""
        from slixmpp import JID
        xep = _get_xep(self, "xep_0384")
        stanza = self.make_message(mto=to, mtype=mtype)
        stanza["body"] = body
        stanza.set_to(to)
        stanza.set_from(self.boundjid)
        sent_mid = _add_origin_id(stanza, mid)
        if reply_id:
            reply_el = ET.SubElement(stanza.xml, "{urn:xmpp:reply:0}reply")
            reply_el.set("to", reply_to_jid or to)
            reply_el.set("id", reply_id)
            fallback = ET.SubElement(stanza.xml,
                                     "{urn:xmpp:fallback:0}fallback")
            fallback.set("for", "urn:xmpp:reply:0")
            if reply_body:
                ET.SubElement(fallback, "body").text = reply_body[:200]

        # Alıcıları belirle
        recipients: set = set()
        if mtype == "groupchat":
            # MUC OMEMO: oda üyelerinin gerçek JID'lerini topla
            try:
                muc = _get_xep(self, "xep_0045")
                roster = muc.get_roster(JID(to))
                for nick in roster:
                    try:
                        real_jid = muc.get_jid_property(JID(to), nick, "jid")
                        if real_jid:
                            recipients.add(JID(real_jid))
                    except Exception:
                        pass
            except Exception:
                pass
            if not recipients:
                self.gui_q.put(("error",
                    "OMEMO: Oda üyelerinin JID'leri alınamadı "
                    "(oda anonim olabilir). Düz metin gönderiliyor."))
                self.send_message(mto=to, mbody=body, mtype=mtype)
                return
        else:
            recipients.add(JID(to))

        # Kendi cihazlarımıza da şifrele
        recipients.add(self.boundjid)

        # Cihaz listelerini ve bundle'ları tazele — ilk gönderimde
        # PEP önbelleği henüz dolmamış olabilir.
        try:
            await xep.refresh_device_lists(recipients, force_download=True)
        except Exception:
            pass

        try:
            encrypted, errors = await xep.encrypt_message(stanza, recipients)
        except Exception as e:
            err_str = str(e)
            if "device" in err_str.lower() or "bundle" in err_str.lower():
                self.gui_q.put(("error",
                    f"OMEMO: Alıcının cihaz bilgileri alınamadı.\n"
                    f"Karşı tarafın OMEMO destekli bir istemci kullanması gerekiyor.\n"
                    f"Detay: {err_str[:200]}"))
            else:
                self.gui_q.put(("error", f"OMEMO şifreleme hatası: {err_str[:200]}"))
            return

        if errors:
            for err in errors:
                self.gui_q.put(("sys_msg",
                    f"⚠ OMEMO uyarı: {err}"))

        if encrypted is None:
            self.gui_q.put(("error",
                "OMEMO şifreleme başarısız — düz metin gönderiliyor"))
            if mtype == "groupchat":
                self.send_message(mto=to, mbody=body, mtype=mtype)
            else:
                msg = self.make_message(mto=to, mbody=body, mtype=mtype)
                _add_origin_id(msg, mid)
                msg.send()
            return

        # XEP-0380: Explicit Message Encryption göstergesi
        try:
            namespaces = xep.is_encrypted(encrypted)
            if namespaces:
                ns = sorted(namespaces)[0]
                encrypted["eme"]["namespace"] = ns
                encrypted["eme"]["name"] = _get_xep(self, "xep_0380").mechanisms.get(
                    ns, "OMEMO")
        except Exception:
            pass

        encrypted.send()
        self.gui_q.put(("sent_mid", {"to": to, "mid": sent_mid}))

    def omemo_device_info(self, callback):
        """OMEMO cihaz bilgilerini arka planda al, callback(info_dict) çağır."""
        if not HAS_OMEMO or not self.omemo_ready:
            callback(None)
            return
        async def _get():
            try:
                xep = _get_xep(self, "xep_0384")
                sm = await xep.get_session_manager()
                own, others = await sm.get_own_device_information()
                fp = sm.format_identity_key(own.identity_key)
                info = {
                    "device_id": own.device_id,
                    "fingerprint": " ".join(fp),
                    "trust": own.trust_level_name,
                    "other_devices": [],
                }
                for dev in others:
                    dfp = sm.format_identity_key(dev.identity_key)
                    info["other_devices"].append({
                        "device_id": dev.device_id,
                        "fingerprint": " ".join(dfp),
                        "trust": dev.trust_level_name,
                        "active": any(a for _, a in dev.active),
                    })
                callback(info)
            except Exception as e:
                callback({"error": str(e)})
        asyncio.run_coroutine_threadsafe(_get(), self.loop)

    # ── Avatar ────────────────────────────────────────────────────────────────
    def fetch_avatar(self, jid, callback):
        """JID'nin avatarını al. callback(jid, bytes|None) çağrılır."""
        asyncio.run_coroutine_threadsafe(
            self._fetch_avatar(jid, callback), self.loop)

    async def _fetch_avatar(self, jid, callback):
        bare = str(jid).split("/")[0]
        # Önce cache'e bak
        cached = _load_avatar_cache(bare)
        if cached:
            callback(bare, cached)
            return
        # XEP-0054 vCard'dan PHOTO al
        try:
            result = await _get_xep(self, "xep_0054").get_vcard(jid=bare, timeout=10)
            vcard = result["vcard_temp"]
            photo_xml = vcard.xml.find("{vcard-temp}PHOTO")
            if photo_xml is not None:
                binval = photo_xml.find("{vcard-temp}BINVAL")
                if binval is not None and binval.text:
                    data = base64.b64decode(binval.text)
                    if data:
                        _save_avatar_cache(bare, data)
                        callback(bare, data)
                        return
        except Exception:
            pass
        callback(bare, None)

    def publish_avatar(self, photo_bytes, mime="image/png", callback=None):
        """Kendi profil fotoğrafını yayınla (vCard + PEP)."""
        asyncio.run_coroutine_threadsafe(
            self._publish_avatar(photo_bytes, mime, callback), self.loop)

    async def _publish_avatar(self, photo_bytes, mime, callback):
        try:
            # XEP-0054: vCard'a PHOTO ekle
            try:
                result = await _get_xep(self, "xep_0054").get_vcard(timeout=10)
                vcard = result["vcard_temp"]
            except Exception:
                vcard = _get_xep(self, "xep_0054").make_vcard()
            # Mevcut PHOTO'yu sil ve yeniden ekle
            for old in vcard.xml.findall("{vcard-temp}PHOTO"):
                vcard.xml.remove(old)
            photo_el = ET.SubElement(vcard.xml, "{vcard-temp}PHOTO")
            type_el = ET.SubElement(photo_el, "{vcard-temp}TYPE")
            type_el.text = mime
            binval_el = ET.SubElement(photo_el, "{vcard-temp}BINVAL")
            binval_el.text = base64.b64encode(photo_bytes).decode("ascii")
            await _get_xep(self, "xep_0054").publish_vcard(vcard)

            # XEP-0084: PEP Avatar
            try:
                xep84 = _get_xep(self, "xep_0084")
                await asyncio.wait_for(xep84.publish_avatar(photo_bytes), 20)
                # Meta veriyi de yayınla
                img = Image.open(io.BytesIO(photo_bytes))
                avatar_id = xep84.generate_id(photo_bytes)
                # Öznitelikler str olmalı: slixmpp yalnız 'bytes'ı çevirir; int
                # width/height serileştirmede TypeError atar, Future hiç
                # tamamlanmaz ve await sonsuza dek asılı kalırdı.
                await asyncio.wait_for(xep84.publish_avatar_metadata([{
                    "id": avatar_id,
                    "type": mime,
                    "bytes": str(len(photo_bytes)),
                    "width": str(img.width),
                    "height": str(img.height),
                }]), 20)
            except Exception:
                pass  # PEP desteklenmeyebilir

            # XEP-0153: vCard avatar hash'ini presence'a ekle
            try:
                await asyncio.wait_for(
                    _get_xep(self, "xep_0153").set_avatar(avatar=photo_bytes, mtype=mime), 20)
            except Exception:
                pass

            # Kendi cache'imizi güncelle
            _save_avatar_cache(self.boundjid.bare, photo_bytes)
            self.gui_q.put(("sys_msg", "✓ Profil fotoğrafı güncellendi"))
            if callback:
                callback(True)
        except Exception as e:
            self.gui_q.put(("sys_msg", f"⚠ Avatar yayınlanamadı: {e}"))
            if callback:
                callback(False)

    def fetch_all_avatars(self, jids, callback):
        """Tüm kişilerin avatarlarını arka planda al."""
        for jid in jids:
            self.fetch_avatar(jid, callback)

    # ── Kişi yönetimi ─────────────────────────────────────────────────────────
    def add_contact(self, jid):
        asyncio.run_coroutine_threadsafe(self._add_contact(jid), self.loop)

    async def _add_contact(self, jid):
        try:
            # Roster.subscribe zaten 'subscribe' presence'ı gönderir;
            # ikinci kez göndermek çift isteğe yol açar.
            self.client_roster.subscribe(jid)
            self.gui_q.put(("sys_msg", f"İstek gönderildi → {jid}"))
        except Exception as e:
            self.gui_q.put(("error", f"Kişi eklenemedi: {e}"))

    def remove_contact(self, jid):
        asyncio.run_coroutine_threadsafe(self._remove_contact(jid), self.loop)

    async def _remove_contact(self, jid):
        try:
            # Roster.remove hem aboneliği iptal eder hem sunucuya
            # subscription='remove' roster güncellemesi gönderir.
            self.client_roster.remove(jid)
            self.gui_q.put(("contact_removed", jid))
            self.gui_q.put(("sys_msg", f"✓ Kişi kaldırıldı: {jid}"))
        except Exception as e:
            self.gui_q.put(("error", f"Kişi kaldırılamadı: {e}"))

    # ── Kullanıcı Arama (XEP-0055) ──────────────────────────────────────────
    def search_users(self, server, query):
        asyncio.run_coroutine_threadsafe(
            self._search_users(server, query), self.loop)

    async def _search_users(self, server, query):
        try:
            xep = _get_xep(self, "xep_0055")
            form = await xep.get_search_form(jid=server)
            fields = form["search"]["form"].get_fields()
            # Sorguyu en uygun alana yerleştir (nick/first/last...)
            _fill_search_form(fields, query)
            form["search"]["form"]["type"] = "submit"
            results = await xep.search(jid=server, form=form["search"]["form"])
            items = []
            try:
                for item in results["search"]["items"]:
                    row = {}
                    for fld in item["fields"]:
                        row[fld["var"]] = fld["value"]
                    items.append(row)
            except Exception:
                pass
            self.gui_q.put(("search_results", {"server": server, "items": items}))
        except Exception as e:
            self.gui_q.put(("search_results", {"server": server, "items": [],
                             "error": str(e)}))

    # ── Kişi Engelleme (XEP-0191) ────────────────────────────────────────────
    def block_contact(self, jid):
        asyncio.run_coroutine_threadsafe(self._block_contact(jid), self.loop)

    async def _block_contact(self, jid):
        try:
            await _get_xep(self, "xep_0191").block(jid)
            self.gui_q.put(("sys_msg", f"🚫 {jid} engellendi"))
        except Exception as e:
            self.gui_q.put(("error", f"Engelleme hatası: {e}"))

    def unblock_contact(self, jid):
        asyncio.run_coroutine_threadsafe(self._unblock_contact(jid), self.loop)

    async def _unblock_contact(self, jid):
        try:
            await _get_xep(self, "xep_0191").unblock(jid)
            self.gui_q.put(("sys_msg", f"✓ {jid} engeli kaldırıldı"))
        except Exception as e:
            self.gui_q.put(("error", f"Engel kaldırma hatası: {e}"))

    def get_blocked_list(self, callback):
        asyncio.run_coroutine_threadsafe(
            self._get_blocked_list(callback), self.loop)

    async def _get_blocked_list(self, callback):
        try:
            result = await _get_xep(self, "xep_0191").get_blocked()
            items = []
            for item in result["blocklist"]["items"]:
                try:
                    items.append(str(item["jid"]))
                except (TypeError, KeyError):
                    items.append(str(item))
            # Callback'i GUI thread'ine taşı (Tk güvenliği)
            self.gui_q.put(("blocked_list", {"items": items, "cb": callback}))
        except Exception as e:
            self.gui_q.put(("error", f"Engel listesi hatası: {e}"))

    # ── Durum Mesajı ──────────────────────────────────────────────────────────
    def set_status_message(self, status_text, show="chat"):
        """Özel durum mesajı yayınla."""
        def _do():
            try:
                self.send_presence(pstatus=status_text, pshow=show)
            except Exception:
                pass
        self._dispatch_loop(_do)

    # ── Konum Paylaşma (XEP-0080) ────────────────────────────────────────────
    def publish_location(self, lat, lon, description=""):
        asyncio.run_coroutine_threadsafe(
            self._publish_location(lat, lon, description), self.loop)

    async def _publish_location(self, lat, lon, description):
        try:
            xep = _get_xep(self, "xep_0080")
            await xep.publish_location(lat=lat, lon=lon, description=description)
            self.gui_q.put(("sys_msg", "📍 Konum paylaşıldı"))
        except Exception as e:
            self.gui_q.put(("error", f"Konum paylaşma hatası: {e}"))

    def publish_mood(self, mood, text=""):
        """Ruh hâli yayınla (XEP-0107); ağ işi döngü thread'inde."""
        asyncio.run_coroutine_threadsafe(
            self._publish_mood(mood, text), self.loop)

    async def _publish_mood(self, mood, text):
        try:
            await _get_xep(self, "xep_0107").publish_mood(mood, text or None)
        except Exception as e:
            self.gui_q.put(("error", f"Ruh hâli paylaşılamadı: {e}"))

    def stop_location(self):
        asyncio.run_coroutine_threadsafe(self._stop_location(), self.loop)

    async def _stop_location(self):
        try:
            await _get_xep(self, "xep_0080").stop()
            self.gui_q.put(("sys_msg", "📍 Konum paylaşımı durduruldu"))
        except Exception as e:
            self.gui_q.put(("error", f"Konum durdurma hatası: {e}"))

    # ── vCard Profil Bilgisi ──────────────────────────────────────────────────
    def get_vcard(self, jid, callback):
        asyncio.run_coroutine_threadsafe(
            self._get_vcard(jid, callback), self.loop)

    async def _get_vcard(self, jid, callback):
        try:
            result = await _get_xep(self, "xep_0054").get_vcard(jid, timeout=10)
            vcard = result["vcard_temp"]
            info = {
                "fn": str(vcard["FN"] or ""),
                "nickname": str(vcard["NICKNAME"] or ""),
                "email": "",
                "url": "",
                "bday": "",
            }
            try:
                info["email"] = str(vcard["EMAIL"]["USERID"] or "")
            except Exception:
                pass
            try:
                info["url"] = str(vcard["URL"] or "")
            except Exception:
                pass
            try:
                info["bday"] = str(vcard["BDAY"] or "")
            except Exception:
                pass
            self.gui_q.put(("vcard", {"jid": jid, "info": info, "cb": callback}))
        except Exception as e:
            self.gui_q.put(("vcard", {"jid": jid, "info": None,
                                      "error": str(e), "cb": callback}))

    # ── OMEMO Parmak İzleri ───────────────────────────────────────────────────
    def get_omemo_fingerprints(self, jid, callback):
        if not HAS_OMEMO or not self.omemo_ready:
            callback({"error": "OMEMO hazır değil"})
            return
        asyncio.run_coroutine_threadsafe(
            self._get_omemo_fps(jid, callback), self.loop)

    async def _get_omemo_fps(self, jid, callback):
        try:
            xep = _get_xep(self, "xep_0384")
            sm = await xep.get_session_manager()
            devices = await sm.get_device_information(jid)
            fps = []
            for dev in devices:
                fp = sm.format_identity_key(dev.identity_key)
                fps.append({
                    "device_id": dev.device_id,
                    "fingerprint": " ".join(fp),
                    "trust": dev.trust_level_name,
                    "active": any(active for _, active in dev.active),
                })
            self.gui_q.put(("omemo_fps", {"jid": jid, "fps": fps, "cb": callback}))
        except Exception as e:
            self.gui_q.put(("omemo_fps", {"jid": jid, "fps": [],
                                           "error": str(e), "cb": callback}))

    # ── Jingle dosya transferi (XEP-0166/0234/0261) ─────────────────────────
    def _on_session_bind_jingle(self, jid):
        """Bind sonrası Jingle yeteneklerini duyur (full JID düğümüne)."""
        for feat in ("urn:xmpp:jingle:1", "urn:xmpp:jingle:apps:file-transfer:5",
                     "urn:xmpp:jingle:transports:ibb:1"):
            try:
                _get_xep(self, "xep_0030").add_feature(feat)
            except Exception:
                _log.warning("Disco feature eklenemedi: %s", feat, exc_info=True)

    def _on_jingle_future(self, fut):
        """Arka plan jingle görevi hata ile biterse GUI'ye bildir."""
        try:
            fut.result()
        except Exception as e:
            try:
                self.gui_q.put(("ft_error", {
                    "sid": "", "error": str(e),
                    "name": getattr(fut, "fname", ""),
                    "peer": getattr(fut, "peer", "")}))
            except Exception:
                pass

    def jingle_send(self, to, filepath, block_size=None):
        fut = asyncio.run_coroutine_threadsafe(
            self.ft.start_send(to, filepath, block_size), self.loop)
        fut.peer = to
        fut.fname = os.path.basename(filepath)
        fut.add_done_callback(self._on_jingle_future)
        return fut

    def jingle_accept(self, sid, save_path):
        fut = asyncio.run_coroutine_threadsafe(
            self.ft.accept(sid, save_path), self.loop)
        fut.add_done_callback(self._on_jingle_future)
        return fut

    def jingle_decline(self, sid):
        fut = asyncio.run_coroutine_threadsafe(self.ft.decline(sid), self.loop)
        fut.add_done_callback(self._on_jingle_future)
        return fut

    def jingle_cancel(self, sid):
        fut = asyncio.run_coroutine_threadsafe(self.ft.cancel(sid), self.loop)
        fut.add_done_callback(self._on_jingle_future)
        return fut


# ══════════════════════════════════════════════════════════════════════════════
# Giriş Ekranı
# ══════════════════════════════════════════════════════════════════════════════

class LoginWindow:
    def __init__(self, on_login):
        self.on_login = on_login
        # Kayıtlı temayı yükle
        _saved_theme = _load_config().get("theme", "koyu")
        _apply_color_theme(_saved_theme)

        self.root = tk.Tk()
        self.root.title("XMPP Giriş")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        self.root.geometry("520x620")
        _apply_theme()
        self._build()
        self.root.mainloop()

    def _build(self):
        # Dış gölge + kart
        shadow = tk.Frame(self.root, bg=SHADOW, padx=4, pady=4)
        shadow.place(relx=0.5, rely=0.5, anchor="center")
        card = tk.Frame(shadow, bg=BG_CARD, padx=48, pady=44)
        card.pack()

        # Logo: çift halkalı neon daire + harf
        logo_f = tk.Frame(card, bg=BG_CARD)
        logo_f.pack(pady=(0, 12))
        logo_c = tk.Canvas(logo_f, width=80, height=80,
                           bg=BG_CARD, highlightthickness=0)
        logo_c.pack()
        # Dış glow halkası
        logo_c.create_oval(4, 4, 76, 76, fill="", outline=GLOW, width=6)
        # İç dolgu
        logo_c.create_oval(10, 10, 70, 70, fill=ACCENT2, outline=ACCENT, width=2)
        logo_c.create_text(40, 38, text="X", fill=FG_ME,
                           font=(FONT, 26, "bold"))

        tk.Label(card, text="XMPP Connect",
                 font=(FONT, 18, "bold"),
                 fg=FG, bg=BG_CARD).pack(pady=(6, 2))
        tk.Label(card, text="Hesabınıza giriş yapın",
                 font=(FONT, 9), fg=FG_DIM,
                 bg=BG_CARD).pack(pady=(0, 24))

        def _field(parent, icon, label, var, show="", placeholder="",
                   width=None, side=None):
            frm = tk.Frame(parent, bg=BG_CARD)
            if side:
                frm.pack(side=side, fill="x", expand=width is None, pady=6)
            else:
                frm.pack(fill="x", pady=6)
            lbl_f = tk.Frame(frm, bg=BG_CARD)
            lbl_f.pack(anchor="w")
            tk.Label(lbl_f, text=icon, font=(FONT, 8),
                     fg=FG_DIM, bg=BG_CARD).pack(side="left")
            tk.Label(lbl_f, text=f" {label.upper()}", fg=FG_DIM, bg=BG_CARD,
                     font=(FONT, 7, "bold")).pack(side="left")
            # Rounded input sarmalayıcı
            inp_border = tk.Frame(frm, bg=BORDER, padx=1, pady=1)
            inp_border.pack(fill="x", pady=(4, 0))
            inp_inner = tk.Frame(inp_border, bg=BG_HOVER)
            inp_inner.pack(fill="x")
            if placeholder and not var.get():
                e = PlaceholderEntry(inp_inner, placeholder=placeholder,
                                     textvariable=var,
                                     font=(FONT, 10), style="Modern.TEntry")
                if show:
                    e.configure(show=show)
            else:
                e = ttk.Entry(inp_inner, textvariable=var, show=show,
                              font=(FONT, 10), style="Modern.TEntry")
            if width:
                e.configure(width=width)
            e.pack(fill="x", ipady=8, padx=2, pady=2)
            return e

        # Kayıtlı bilgilerle doldur ("Şifremi hatırla" açıkken ya da otomatik
        # giriş başarısız olduysa düzeltilsin)
        cfg = _load_config()
        saved_jid, saved_pw, saved_port, saved_srv = (
            _saved_login(cfg) or ("", "", 5222, ""))
        self.jid_var  = tk.StringVar(value=saved_jid)
        self.pw_var   = tk.StringVar(value=saved_pw)
        self.srv_var  = tk.StringVar(value=saved_srv)
        self.port_var = tk.StringVar(value=str(saved_port))

        jid_entry = _field(card, "📧", "JID", self.jid_var,
                           placeholder="kullanici@sunucu.tld")
        self._jid_entry = jid_entry
        pw_entry  = _field(card, "🔑", "Şifre", self.pw_var, show="•",
                           placeholder="")

        # Seçenekler satırı
        chk_row = tk.Frame(card, bg=BG_CARD)
        chk_row.pack(fill="x", pady=(8, 0))

        chk_kw = dict(bg=BG_CARD, fg=FG_DIM, selectcolor=BG_HOVER,
                       activebackground=BG_CARD, activeforeground=FG,
                       font=(FONT, 8))

        show_pw = tk.BooleanVar(value=False)
        def _toggle_pw():
            pw_entry.config(show="" if show_pw.get() else "•")
        tk.Checkbutton(chk_row, text="Göster", variable=show_pw,
                       command=_toggle_pw, **chk_kw).pack(side="left")

        # Gelişmiş toggle
        adv_var = tk.BooleanVar(value=False)
        self._adv_frame = tk.Frame(card, bg=BG_CARD)
        def _toggle_adv():
            # Açıkken kart sıkılaşır ve pencere içeriğe göre uzar (en çok
            # 690 px); kapanınca eski boyut. Aksi halde alanlar taşıyordu.
            if adv_var.get():
                self._adv_frame.pack(fill="x", before=self._btn_frame)
                card.config(pady=24)
            else:
                self._adv_frame.pack_forget()
                card.config(pady=44)
            self.root.update_idletasks()
            height = min(max(620, shadow.winfo_reqheight()), 690)
            self.root.geometry(f"520x{height}")
        tk.Checkbutton(chk_row, text="Gelişmiş", variable=adv_var,
                       command=_toggle_adv, **chk_kw).pack(side="right")

        # Şifremi hatırla (varsayılan açık: eski sürüm kutuyu boş açıp
        # "remember": False yazıyordu, o kayıt bir tercih değil) ve otomatik
        # giriş (yalnız hatırlanan bilgilerle; eski kayıtlarda açık). Aynı
        # satırda: ayrı satır kartı 620 px pencereden taşırıyordu.
        self.remember_var = tk.BooleanVar(value=True)
        self.auto_login_var = tk.BooleanVar(
            value=_auto_login_enabled(cfg) if cfg.get("remember") else True)
        auto_cb = tk.Checkbutton(chk_row, text="Otomatik giriş",
                                 variable=self.auto_login_var, **chk_kw)

        def _sync_auto():
            auto_cb.config(state="normal" if self.remember_var.get()
                           else "disabled")
        tk.Checkbutton(chk_row, text="Şifremi hatırla",
                       variable=self.remember_var, command=_sync_auto,
                       **chk_kw).pack(side="left", padx=(10, 0))
        auto_cb.pack(side="left", padx=(10, 0))
        _sync_auto()

        # Sunucu ve port yan yana (alt alta kart pencereden taşıyordu)
        _field(self._adv_frame, "🖧", "Sunucu (boş = SRV)", self.srv_var,
               side="left")
        tk.Frame(self._adv_frame, bg=BG_CARD, width=8).pack(side="left")
        _field(self._adv_frame, "🔌", "Port", self.port_var, width=6,
               side="left")

        # Bağlan butonu — Canvas rounded
        self._btn_frame = tk.Frame(card, bg=BG_CARD)
        self._btn_frame.pack(fill="x", pady=(20, 0))
        self._login_btn_c = tk.Canvas(self._btn_frame, height=44,
                                       bg=BG_CARD, highlightthickness=0)
        self._login_btn_c.pack(fill="x")
        self._login_btn_c.bind("<Configure>", self._draw_login_btn)
        self._login_btn_c.bind("<Button-1>", lambda _: self._connect())
        self._login_btn_c.bind("<Enter>",
            lambda _: self._draw_login_btn(None, hover=True))
        self._login_btn_c.bind("<Leave>",
            lambda _: self._draw_login_btn(None, hover=False))

        # Alt bilgi
        info_f = tk.Frame(card, bg=BG_CARD)
        info_f.pack(fill="x", pady=(16, 0))
        tk.Label(info_f, text="SRV otomatik  •  OMEMO & PGP destekli",
                 fg=FG_DIM, bg=BG_CARD,
                 font=(FONT, 7)).pack()

        self.root.bind("<Return>", lambda _: self._connect())
        jid_entry.focus_set()

    def _draw_login_btn(self, event=None, hover=False):
        c = self._login_btn_c
        c.delete("all")
        w = c.winfo_width() or 300
        h = 44
        color = ACCENT if hover else ACCENT2
        _rounded_rect(c, 0, 0, w, h, 10, fill=color, outline="")
        c.create_text(w // 2, h // 2, text="Bağlan",
                      fill=FG_ME, font=(FONT, 11, "bold"))
        c.configure(cursor="hand2")

    def _connect(self):
        jid  = self.jid_var.get().strip()
        if getattr(getattr(self, "_jid_entry", None), "_showing_ph", False):
            jid = ""   # kutu boş: görünen yer tutucu metni JID değildir
        pw   = self.pw_var.get()
        srv  = self.srv_var.get().strip()
        try:
            port = int(self.port_var.get() or 5222)
        except ValueError:
            port = 5222
        if not jid or not pw:
            messagebox.showwarning("Eksik Bilgi", "JID ve şifre gerekli.")
            return
        if "@" not in jid:
            messagebox.showwarning("Geçersiz JID",
                                   "JID formatı: kullanıcı@sunucu.tld")
            return

        # Şifremi hatırla — giriş bilgilerini kaydet / sil; otomatik giriş seçimi
        cfg = _load_config()
        _store_login(cfg, self.remember_var.get(), jid, pw, port, srv,
                     auto_login=self.auto_login_var.get())
        _save_config(cfg)

        self.root.destroy()
        self.on_login(jid, pw, port, srv)


# ══════════════════════════════════════════════════════════════════════════════
# Ana Pencere
# ══════════════════════════════════════════════════════════════════════════════

PRESENCE_COLOR = {
    "available": ONLINE, "": ONLINE, "online": ONLINE,
    "away": AWAY, "xa": RED,
    "dnd": RED, "unavailable": FG_DIM,
}

STATUS_OPTIONS = [
    ("Online",  "online"),
    ("Away",    "away"),
    ("Meşgul",  "dnd"),
    ("Uzakta",  "xa"),
]

# Bilinen halka açık MUC konferans sunucuları
_KNOWN_MUC_SERVERS = [
    ("conference.jabber.org",      "Jabber.org"),
    ("conference.movim.eu",        "Movim"),
    ("muc.404.city",               "404.city"),
    ("conference.dismail.de",      "Dismail.de"),
    ("muc.systemli.org",           "Systemli.org"),
    ("conference.xmpp.jp",         "XMPP.jp"),
    ("conference.siacs.eu",        "Conversations"),
    ("rooms.jabberfr.org",         "JabberFR"),
]


class MainWindow:
    def __init__(self, bot: XMPPBot, jid: str, gui_q: queue.Queue):
        self.bot   = bot
        self.jid   = jid
        self.gui_q = gui_q
        # İlk _poll "connected"ı işleyebilir (hızlı sunucu): öznitelik hazır olmalı
        self._conn_timeout_id = None

        # Durum
        # chats: jid → [(sender, body, is_me, time_str, tag)]
        self.chats: dict[str, list]    = {}
        self.active: str | None        = None
        self.presence: dict[str, str]  = {}
        self.rooms: list[str]          = []
        self._room_jids: list[str]     = []  # room_list ile birebir eşlenen JID'ler
        self._contacts: dict[str, str] = {}
        self._contact_jids: list[str]  = []
        self.my_nick: dict[str, str]   = {}
        self._typing: set[str]         = set()
        self.room_members: dict[str, dict] = {}  # {room: {nick: {role, affil, show}}}
        self._room_subjects: dict[str, str] = {}  # room → konu
        self._member_index_map: dict[int, str] = {}  # listbox idx → nick
        self._bubble_widgets: list[tk.Widget] = []
        self._photo_refs: list = []  # PIL PhotoImage GC koruması
        self._temp_files: list[str] = []  # kapanışta silinecek geçici dosyalar
        self._avatars: dict[str, bytes] = {}  # bare_jid → foto bytes
        self._msg_ids: dict[str, list] = {}  # jid → [msg_id, ...]  (düzenleme/silme için)
        self._mam_oldest: dict[str, str] = {}  # jid → en eski MAM stanza id'si
        self._mam_has_more: dict[str, bool] = {}  # jid → daha eski kayıt var mı
        self._mam_gen: dict[str, int] = {}  # jid → MAM geçerlilik generation'ı (bayat sonuç guard'ı)
        # [2F] Geçmiş pencere durumu: UI viewport'u domain self.chats'ten bağımsız
        self._history_start: dict[str, int] = {}      # jid → pencere başlangıç indeksi
        self._history_view_mode: dict[str, str] = {}  # jid → "latest" | "history"
        self._history_pending: dict[str, int] = {}    # jid → görüntülenmeyen yeni mesaj sayısı
        self._history_mam_intent: dict[str, str] = {} # jid → "initial" | "older" (tek kullanımlık)
        self._nav_bar = None                          # sabit gezinme çubuğu (tek örnek)
        # [2G] Sınırlı sistem-balon yüzeyi
        self._sys_bubbles: list = []                  # yaşayan sys balonları (FIFO)
        self._subject_bubbles: dict[str, object] = {} # oda → güncel konu balonu
        self._chat_tabs: dict[str, dict] = {}  # ayrı sohbet pencereleri
        self._chat_enc_modes: dict[str, str] = {}  # jid → "none"/"omemo"/"pgp"
        self._reactions: dict[tuple[str, str], dict[str, list]] = {}  # [2M] (jid, mid) → {emoji: [nick,...]}
        self._my_reactions: dict[tuple[str, str], set] = {}  # [2M] (jid, mid) → {emoji,...} (kendi tepkilerim)
        self._reply_map: dict[tuple[str, str], dict] = {}  # [2M] (jid, örnek-kimlik) → {"id","sender","body"}; kimlik: güncel girişte uid, eski girişte mid
        self._pinned_msgs: dict[str, list] = {}  # jid → [(body, sender), ...]
        self._disappearing_ttl: dict[str, int] = {}  # jid → seconds (0=off)
        # [2I][B1][2J.b][2K] TTL sunum vadeleri: (jid, uid) → expires_at
        # (monotonic). Composite anahtar zorunlu: mesaj kimliği
        # gönderici-kontrollüdür ve sohbetler arası benzersiz DEĞİLDİR; vade
        # sohbet başına izole tutulur. uid [2J.b]: girişin dahili örnek
        # kimliği (eski girişlerde mid). Yalnız sunum üstverisi; tek etkili
        # vade — re-render asla sıfırlamaz. [2K] Süresi dolmuş vade SİLİNMEZ;
        # mezar taşı olarak kalır (diriliş yok) ve yalnız clear yollarında
        # temizlenir.
        self._ttl_deadlines: dict[tuple[str, str], float] = {}
        # [2J.b] Mantıksal mesaj örneği sayacı: her yeni history girişine
        # oturum-içi benzersiz UID. Yalnız bellek-içi defterler için; wire'a
        # ve SQLite'a gitmez, re-render asla yenilemez.
        self._msg_inst_seq: int = 0
        # [2O] Ters-korelasyon registry: `_mam_aliases[jid][raw_id] =
        # (canonical_mid, body, is_me)` — MAM kabulünde raw_id ≠ logical_mid
        # ise yazılır; LIVE replay bastırmada YALNIZ gövde/yön + kanonik
        # satır mevcudiyetiyle birlikte kullanılır. Yalnız bellek: DB'ye
        # girmez, self.chats biçimine girmez; archive_id ASLA burada değildir.
        self._mam_aliases: dict[str, dict[str, tuple]] = {}
        self._last_date_label: str = ""  # tarih ayırıcı takibi
        self._recording: bool = False
        # Sohbet sabitleme
        _init_cfg = _load_config()
        self._load_saved_prefs(_init_cfg)
        self._send_read_receipts: bool = _init_cfg.get("send_read_receipts", True)
        self._send_typing_notif: bool = _init_cfg.get("send_typing", True)
        self._relogin = False
        # Okunmamış mesaj sayacı
        self._unread_counts: dict[str, int] = {}  # jid → sayı
        self._pinned_chats: list[str] = _init_cfg.get("pinned_chats", [])
        # Otomatik uzakta
        self._idle_after_min: int = _init_cfg.get("idle_after_min", 5)
        self._last_activity_ts: float = time.time()
        self._is_idle: bool = False
        self._idle_check_id = None
        # Kompakt mod
        self._compact_mode: bool = _init_cfg.get("compact_mode", False)
        # Sohbet arka planı
        self._chat_wallpaper: str = _init_cfg.get("chat_wallpaper", "")
        # Bağlantı hata takibi (durum çubuğu + bildirim)
        self._last_conn_error: str = ""
        self._last_conn_toast_ts: float = 0.0
        # Dosya transferi (Jingle FT)
        self._download_dir = (str(_init_cfg.get("download_dir", "") or "").strip()
                              or os.path.expanduser("~/Downloads"))
        self._ft_auto_accept = bool(_init_cfg.get("ft_auto_accept", False))
        try:
            self._ft_block_size = int(_init_cfg.get("ft_block_size", 4096))
        except (TypeError, ValueError):
            self._ft_block_size = 4096
        try:
            self._ft_warn_mb = max(1, int(_init_cfg.get("ft_warn_mb", 50)))
        except (TypeError, ValueError):
            self._ft_warn_mb = 50
        self._ft_sent_paths: dict[str, str] = {}
        self._ft_pending_out: dict[tuple, str] = {}
        self._ft_progress_wins: dict[str, dict] = {}
        # Bağlantı ping
        self._last_ping_ms: int = 0
        # Kapanış durumu (gecikmeli after zincirleri için)
        self._closing = False
        self._poll_id = None
        self._api_lock = threading.Lock()
        # Sistem tepsisi
        self._tray_icon = None

        # Kayıtlı temayı yükle
        _saved_theme = _load_config().get("theme", "koyu")
        _apply_color_theme(_saved_theme)
        self.root = tk.Tk()
        self.root.title(f"XMPP — {jid}")
        geom = _parse_geometry(_init_cfg.get("win_geometry", ""),
                               self.root.winfo_screenwidth(),
                               self.root.winfo_screenheight())
        self.root.geometry(geom or "1080x720")
        if _init_cfg.get("win_maximized"):
            try:
                self.root.state("zoomed")
            except Exception:
                pass
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_request)
        self._install_bgerror_filter()
        _apply_theme()
        self._build()
        # Varsayılan şifreleme ayarını yükle
        _cfg = _load_config()
        _def_enc = _cfg.get("default_encryption", "none")
        if _def_enc in ("omemo", "pgp"):
            self._encryption_mode.set(_def_enc)
            self._update_enc_btn(silent=True)
        self._restore_font_prefs(_cfg)
        # DnD desteği
        if _HAS_DND:
            try:
                self.root.drop_target_register('DND_Files')
                self.root.dnd_bind('<<Drop>>', self._on_dnd_drop)
            except Exception:
                pass
        # Klavye kısayolları
        self._bind_shortcuts()
        # Otomatik uzakta zamanlayıcı
        self._start_idle_checker()
        self.root.bind_all("<Key>", self._reset_activity, "+")
        self.root.bind_all("<Motion>", self._reset_activity, "+")
        # Sistem tepsisi
        self._setup_tray_icon()
        # Bağlantı ping zamanlayıcı
        self._ping_loop_id = self._after(30000, self._ping_loop)
        # AI hatırlatıcıları (config'te kalıcı; zamanı geçenler hemen çalar)
        self._ai_arm_reminders()
        self._ai_refresh_flags()
        # Otomatik tema geçişi
        self._auto_theme_check()
        self._poll()
        # Pencere kurulurken bağlantı tamamlanmış olabilir; o halde zaman
        # aşımı kurulmaz (aksi halde "connected" olayı AttributeError ile
        # kayboluyor ve kişi listesi hiç dolmuyordu).
        if not getattr(self.bot, "_connected_ok", False):
            self._conn_timeout_id = self._after(20000, self._conn_timeout)
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            _log.info("Klavyeden kesildi — kapatılıyor")
        finally:
            # Beklenmedik çıkışta da zincirleri iptal et (bgerror olmasın)
            if not getattr(self, "_closing", False):
                self._quit()

    # ── Arayüz inşa ───────────────────────────────────────────────────────────
    def _build(self):
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_chat_panel()
        self._build_members_panel()

    # ── Sol kenar çubuğu ──────────────────────────────────────────────────────
    def _build_sidebar(self):
        sb_wrap = tk.Frame(self.root, bg=BORDER)
        sb_wrap.grid(row=0, column=0, sticky="nsew")

        sb = tk.Frame(sb_wrap, bg=BG_PANEL, width=290)
        sb.pack(side="left", fill="both", expand=True)
        self._sidebar_frame = sb
        tk.Frame(sb_wrap, bg=BORDER, width=1).pack(side="right", fill="y")

        sb.grid_propagate(False)
        sb.columnconfigure(0, weight=1)
        sb.rowconfigure(5, weight=2)
        sb.rowconfigure(8, weight=1)

        # ── Profil (glow arka plan) ──
        hdr_bg = tk.Frame(sb, bg=BG_PANEL)
        hdr_bg.grid(row=0, column=0, sticky="ew")
        # Profil alanı alt çizgisi
        hdr_glow = tk.Canvas(hdr_bg, height=1, bg=BG_PANEL, highlightthickness=0)
        hdr_glow.pack(side="bottom", fill="x")
        hdr_glow.bind("<Configure>",
            lambda e: (hdr_glow.delete("all"),
                       hdr_glow.create_rectangle(
                           e.width * 0.15, 0, e.width * 0.85, 1,
                           fill=ACCENT2, outline="")))

        hdr = tk.Frame(hdr_bg, bg=BG_PANEL, padx=16, pady=16)
        hdr.pack(fill="x")

        initial = self.jid[0].upper() if self.jid else "?"
        own_avatar = _load_avatar_cache(self.jid)
        av = _avatar(hdr, 44, initial, ACCENT2, BG_PANEL,
                     photo_data=own_avatar, _photo_refs=self._photo_refs)
        av.pack(side="left")
        self._sidebar_avatar = av
        av.configure(cursor="hand2")
        av.bind("<Button-1>", lambda _: self._change_avatar_dialog())
        # Online durumu noktası (parlak glow)
        av.create_oval(31, 31, 41, 41, fill=ONLINE, outline=BG_PANEL, width=2)

        info_f = tk.Frame(hdr, bg=BG_PANEL)
        info_f.pack(side="left", padx=(14, 0), fill="x", expand=True)
        tk.Label(info_f, text=self.jid.split("@")[0],
                 font=(FONT, 12, "bold"),
                 fg=FG, bg=BG_PANEL).pack(anchor="w")

        # Durum: tıklanabilir label + popup menü (combobox yerine)
        self.status_var = tk.StringVar(value="Online")
        self._status_label = tk.Label(info_f, text="● Online",
                                       font=(FONT, 8), fg=ONLINE,
                                       bg=BG_PANEL, cursor="hand2")
        self._status_label.pack(anchor="w")
        self._status_label.bind("<Button-1>", self._show_status_menu)

        # ── Yeni Sohbet butonu (Canvas rounded) ──
        new_chat_f = tk.Frame(sb, bg=BG_PANEL, padx=14)
        new_chat_f.grid(row=1, column=0, sticky="ew", pady=(4, 6))
        self._new_chat_c = tk.Canvas(new_chat_f, height=36,
                                      bg=BG_PANEL, highlightthickness=0)
        self._new_chat_c.pack(fill="x")
        self._new_chat_c.bind("<Configure>", self._draw_new_chat_btn)
        self._new_chat_c.bind("<Button-1>", lambda _: self._add_contact_dialog())
        self._new_chat_c.bind("<Enter>",
            lambda _: self._draw_new_chat_btn(None, hover=True))
        self._new_chat_c.bind("<Leave>",
            lambda _: self._draw_new_chat_btn(None, hover=False))

        # ── Arama çubuğu ──
        search_f = tk.Frame(sb, bg=BG_PANEL, padx=14)
        search_f.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        search_border = tk.Frame(search_f, bg=BORDER, padx=1, pady=1)
        search_border.pack(fill="x")
        search_inner = tk.Frame(search_border, bg=BG_HOVER)
        search_inner.pack(fill="x")
        tk.Label(search_inner, text="🔍", font=(FONT, 9),
                 fg=FG_DIM, bg=BG_HOVER).pack(side="left", padx=(8, 0))
        self._sidebar_search_var = tk.StringVar()
        self._sidebar_search = PlaceholderEntry(
            search_inner, placeholder=_t("sidebar_search_placeholder"),
            textvariable=self._sidebar_search_var,
            font=(FONT, 9), style="Modern.TEntry")
        self._sidebar_search.pack(fill="x", ipady=5, padx=(4, 4), pady=2)
        # Trace'i widget hazır olduktan SONRA bağla: PlaceholderEntry
        # kurulumu değişkeni set eder ve erken tetiklenirse _filter_sidebar
        # self._sidebar_search'e erişemeden çöker.
        self._sidebar_search_var.trace_add("write", lambda *_: self._filter_sidebar())

        filters = tk.Frame(search_f, bg=BG_PANEL)
        filters.pack(fill="x", pady=(6, 0))
        self._sidebar_filter_var = tk.StringVar(value="all")
        for mode, label in (("all", "filter_all"), ("unread", "filter_unread"),
                            ("pinned", "filter_pinned")):
            ttk.Radiobutton(filters, text=_t(label), value=mode,
                            variable=self._sidebar_filter_var,
                            style="SidebarFilter.TRadiobutton").pack(
                                side="left", fill="x", expand=True, padx=1)
        self._sidebar_filter_var.trace_add("write", lambda *_: self._filter_sidebar())

        # ── Kişiler ──
        ch = tk.Frame(sb, bg=BG_PANEL, padx=16)
        ch.grid(row=3, column=0, sticky="ew", pady=(10, 4))
        tk.Label(ch, text=_t("contacts"), font=(FONT, 7, "bold"),
                 fg=FG_DIM, bg=BG_PANEL).pack(side="left")
        add_c = tk.Label(ch, text="+", font=(FONT, 12, "bold"),
                         fg=FG_DIM, bg=BG_PANEL, cursor="hand2")
        add_c.pack(side="right")
        add_c.bind("<Button-1>", lambda _: self._add_contact_dialog())
        add_c.bind("<Enter>", lambda _: add_c.config(fg=ACCENT))
        add_c.bind("<Leave>", lambda _: add_c.config(fg=FG_DIM))
        _add_tooltip(add_c, _t("add_contact"))

        # Kişi grupları ikonu (araç çubuğundan buraya taşındı)
        grp_c = tk.Label(ch, text="🏷", font=(FONT, 9),
                         fg=FG_DIM, bg=BG_PANEL, cursor="hand2", padx=4)
        grp_c.pack(side="right")
        grp_c.bind("<Button-1>", lambda _: self._contact_groups_dialog())
        grp_c.bind("<Enter>", lambda _: grp_c.config(fg=ACCENT))
        grp_c.bind("<Leave>", lambda _: grp_c.config(fg=FG_DIM))
        _add_tooltip(grp_c, _t("groups"))

        lbox_kw = dict(
            bg=BG_PANEL, fg=FG,
            selectbackground=SEL_BG, selectforeground=SEL_FG,
            activestyle="none", relief="flat", borderwidth=0,
            font=(FONT, 10), highlightthickness=0,
        )
        # ── Asistan (AI; XMPP kişisi değildir — roster/stanza yolu yok) ──
        self._assistant_entry = _ui_sidebar.build_assistant_entry(
            sb, self._ai_assistant_open,
            subtitle="Komut ver ya da soru sor · Ctrl+Shift+K")
        self._assistant_entry.grid(row=4, column=0, sticky="ew", padx=10,
                                   pady=(0, 4))

        self.contact_list = tk.Listbox(sb, selectmode="single", **lbox_kw)
        self.contact_list.grid(row=5, column=0, sticky="nsew", padx=10)
        self.contact_list.bind("<<ListboxSelect>>", self._on_contact_select)
        self.contact_list.bind("<Button-3>",         self._contact_context_menu)
        self.contact_list.bind("<Enter>",            self._contact_hover_start)
        self.contact_list.bind("<Leave>",            self._contact_hover_end)
        self.contact_list.bind("<Motion>",           self._contact_hover_motion)

        # ── Odalar ──
        rh = tk.Frame(sb, bg=BG_PANEL, padx=16)
        rh.grid(row=7, column=0, sticky="ew", pady=(12, 4))
        tk.Label(rh, text=_t("rooms"), font=(FONT, 7, "bold"),
                 fg=FG_DIM, bg=BG_PANEL).pack(side="left")

        room_btns = tk.Frame(rh, bg=BG_PANEL)
        room_btns.pack(side="right")
        for icon, tip, cmd in [
            ("🧭", _t("discover_rooms"), self._search_rooms_dialog),
            ("📑", _t("bookmarks"),      self._bookmarks_dialog),
            ("✚",  _t("create_room"),    self._create_room_dialog),
            ("+",  _t("join_room"),      self._join_room_dialog),
        ]:
            b = tk.Label(room_btns, text=icon, font=(FONT, 9),
                         fg=FG_DIM, bg=BG_PANEL, cursor="hand2",
                         padx=3)
            b.pack(side="left")
            b.bind("<Button-1>", lambda _, c=cmd: c())
            b.bind("<Enter>", lambda e: e.widget.config(fg=ACCENT))
            b.bind("<Leave>", lambda e: e.widget.config(fg=FG_DIM))
            _add_tooltip(b, tip)

        self.room_list = tk.Listbox(sb, selectmode="single", height=6, **lbox_kw)
        self.room_list.grid(row=8, column=0, sticky="nsew", padx=10, pady=(0, 6))
        self.room_list.bind("<<ListboxSelect>>", self._on_room_select)
        self.room_list.bind("<Button-3>",         self._room_context_menu)

        # ── Gajim tarzı durum çubuğu (alt) ──
        status_f = tk.Frame(sb, bg=BG_PANEL, padx=14, pady=7)
        status_f.grid(row=9, column=0, sticky="sew")

        # Üst ayırıcı — ince gradient çizgi
        sep_c = tk.Canvas(status_f, height=1, bg=BG_PANEL, highlightthickness=0)
        sep_c.pack(fill="x", pady=(0, 5))
        sep_c.bind("<Configure>",
            lambda e: (sep_c.delete("all"),
                       sep_c.create_rectangle(
                           e.width * 0.05, 0, e.width * 0.95, 1,
                           fill=BORDER, outline="")))

        # Ping / bağlantı durumu
        self._ping_label = tk.Label(status_f, text="📶 —", font=(FONT, 8),
                                     fg=FG_DIM, bg=BG_PANEL)
        self._ping_label.pack(side="left")

        # ☰ ana menü (Gajim tarzı)
        self._menu_btn = tk.Label(status_f, text="☰", font=(FONT, 13),
                                   fg=FG_DIM, bg=BG_PANEL, cursor="hand2",
                                   padx=6)
        self._menu_btn.pack(side="right")
        self._menu_btn.bind("<Button-1>", self._sidebar_menu)
        self._menu_btn.bind("<Enter>",
                            lambda _: self._menu_btn.config(fg=ACCENT))
        self._menu_btn.bind("<Leave>",
                            lambda _: self._menu_btn.config(fg=FG_DIM))
        _add_tooltip(self._menu_btn, _t("main_menu"))

    def _draw_new_chat_btn(self, event=None, hover=False):
        c = self._new_chat_c
        c.delete("all")
        w = c.winfo_width() or 220
        color = BG_HOVER if hover else BORDER
        _rounded_rect(c, 0, 0, w, 36, 8, fill=color, outline="")
        c.create_text(w // 2, 18, text="＋  Yeni Sohbet",
                      fill=ACCENT if hover else FG_DIM,
                      font=(FONT, 9, "bold"))
        c.configure(cursor="hand2")

    def _show_status_menu(self, event=None):
        """Durum menüsü (ui/profile)."""
        _ui_profile.show_status_menu(
            self.root, self._set_status, event.x_root, event.y_root)

    def _set_status(self, label, show, color):
        self.status_var.set(label)
        self._status_label.config(text=f"● {label}", fg=color)
        # Durum mesajı korunur (metinsiz presence onu siliyordu)
        self.bot.set_presence(show, status=getattr(self, "_status_text", ""))
        was_away = getattr(self, "_my_show", "online") in self._AWAY_SHOWS
        self._my_show = show
        if was_away and show not in self._AWAY_SHOWS:
            self._ai_away_returned()

    def _retry_connection(self, _=None):
        """Bağlantıyı hemen yeniden dene (kenar çubuğu menüsü)."""
        if getattr(self.bot, "_connected_ok", False):
            self._show_toast("✓ Bağlantı", "Zaten bağlısınız")
            return
        self._last_conn_error = ""
        try:
            self.bot.loop.call_soon_threadsafe(self.bot.cancel_connection_attempt)
        except Exception:
            pass
        try:
            self.bot.loop.call_soon_threadsafe(self.bot.connect)
        except Exception as e:
            messagebox.showerror("Bağlantı",
                                 f"Deneme başlatılamadı: {e}",
                                 parent=self.root)
            return
        self._append("⟳ Yeniden bağlanılıyor…", "sys")
        try:
            self._status_label.config(text=_t("connecting"), fg=AWAY)
        except Exception:
            pass

    def _sidebar_menu(self, event=None):
        """Gajim tarzı ☰ ana menü — dağıtılan işlevlerin bölümlü özeti."""
        actions = {
            "search_users":   self._search_users_dialog,
            "groups":         self._contact_groups_dialog,
            "discover_rooms": self._search_rooms_dialog,
            "bookmarks":      self._bookmarks_dialog,
            "gif":            self._show_gif_panel,
            "msg_search":     self._search_messages_dialog,
            "log":            self._log_viewer_dialog,
            "rest_api":       self._rest_api_dialog,
            "reconnect":      self._retry_connection,
            "theme":          self._show_theme_picker,
            "settings":       self._settings_dialog,
        }
        menu = tk.Menu(self.root, tearoff=0, bg=BG_CARD, fg=FG,
                       activebackground=SEL_BG, activeforeground=SEL_FG,
                       borderwidth=1, relief="flat", font=(FONT, 9),
                       disabledforeground=FG_DIM)
        for item in _sidebar_menu_spec(has_active_chat=bool(self.active)):
            if item[0] == "section":
                menu.add_command(label=f"   {item[1]}", state="disabled")
            elif item[0] == "item":
                menu.add_command(label=f"   {item[1]}",
                                 command=actions.get(item[2]))
            else:
                menu.add_separator()
        if event is not None:
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

    # ── Sohbet paneli ─────────────────────────────────────────────────────────
    def _build_chat_panel(self):
        """Sohbet paneli iskeleti (ui/chat/shell.ChatShell) + compat alias'lar."""
        th = _chat_theme()
        cb = {
            "on_header_menu": self._chat_header_menu,
            "on_add_contact": self._add_contact_dialog,
            "on_join_room": self._join_room_dialog,
            "on_discover_rooms": self._search_rooms_dialog,
            "on_cancel_reply": self._cancel_reply,
            "on_show_pinned": self._show_pinned,
            "on_send": self._send_message,
            "on_paste": self._on_paste,
            "on_typing": self._on_typing_key,
            "on_emoji": self._show_emoji_picker,
            "on_gif": self._show_gif_panel,
            "on_file": self._send_file,
            "on_voice": self._toggle_voice,
            "on_encryption": self._show_encryption_menu,
            "on_canvas_enter": self._activate_scroll,
            "on_canvas_leave": self._deactivate_scroll,
            "on_ai": self._ai_composer_menu,
        }
        self._chat_shell = _ChatShell(self.root, _t, th, cb,
                                      entry_cls=PlaceholderEntry,
                                      add_tooltip=_add_tooltip)
        # Compatibility boundary: aynı gerçek widget nesneleri (duplicate yok)
        for _n in _ChatShell.LEGACY_REFS:
            setattr(self, _n, getattr(self._chat_shell, _n))
        self._typing_dots = 0
        self._typing_anim_id = None
        self._typing_send_id = None
        self._composer = _ComposerView(self.msg_var, self._msg_entry,
                                       self._reply_bar, self._reply_lbl)
        self._ai_complete_setup()

    # ── Yazıyor animasyonu ──────────────────────────────────────────────────
    def _refresh_typing_indicator(self):
        """Aktif sohbete göre typing presentation'ını tazele.

        `_typing` set'i yalnızca okunur; timer/lifecycle MainWindow'da kalır.
        """
        if getattr(self, "typing_label", None) is None:
            return
        if self.active and self.active in getattr(self, "_typing", ()):
            self._start_typing_anim()
        else:
            self._stop_typing_anim()

    def _start_typing_anim(self):
        if self._typing_anim_id:
            return
        self._typing_dots = 0
        self._animate_typing()

    def _animate_typing(self):
        if getattr(self, "_closing", False):
            return
        self._typing_dots = (self._typing_dots % 3) + 1
        _typing_ui.show_typing(self.typing_label, _t, self._typing_dots)
        if not getattr(self, "_closing", False):
            self._typing_anim_id = self._after(500, self._animate_typing)

    def _stop_typing_anim(self):
        if self._typing_anim_id:
            self.root.after_cancel(self._typing_anim_id)
            self._typing_anim_id = None
        _typing_ui.hide_typing(self.typing_label)

    # ── Katılımcı paneli ──────────────────────────────────────────────────────
    def _build_members_panel(self):
        mp_wrap = tk.Frame(self.root, bg=BORDER)
        self._members_panel = mp_wrap
        mp = tk.Frame(mp_wrap, bg=BG_PANEL, width=170)
        tk.Frame(mp_wrap, bg=BORDER, width=1).pack(side="left", fill="y")
        mp.pack(side="right", fill="both", expand=True)
        mp.columnconfigure(0, weight=1)
        mp.rowconfigure(1, weight=1)

        self._members_label = tk.Label(mp, text=_t("participants"),
                 font=(FONT, 7, "bold"),
                 fg=FG_DIM, bg=BG_PANEL)
        self._members_label.grid(
            row=0, column=0, sticky="w", padx=14, pady=(12, 6))

        self.members_list = tk.Listbox(
            mp, bg=BG_PANEL, fg=FG,
            selectbackground=SEL_BG, selectforeground=SEL_FG,
            activestyle="none", relief="flat", borderwidth=0,
            font=(FONT, 9), highlightthickness=0,
        )
        self.members_list.grid(row=1, column=0, sticky="nsew",
                               padx=10, pady=(0, 10))
        self.members_list.bind("<Button-3>", self._member_context_menu)

    # ── Canvas scroll yönetimi ────────────────────────────────────────────────
    def _activate_scroll(self, _=None):
        _history_ui.activate_scroll(
            self.root, self._on_scroll,
            lambda d: self.chat_canvas.yview_scroll(d, "units"))

    def _deactivate_scroll(self, _=None):
        _history_ui.deactivate_scroll(self.root)

    def _on_scroll(self, event):
        _history_ui.scroll_wheel(self.chat_canvas, event)

    # ── Balon oluşturma ───────────────────────────────────────────────────────
    _last_sender = None  # art arda aynı gönderici takibi
    # [2F] Geçmiş pencere sabitleri
    _HISTORY_WINDOW_SIZE = 200    # tam render pencere boyu
    _HISTORY_LIVE_HARD_CAP = 250  # canlı latest modu aktif birim tavanı
    # [2G] Sistem/ortam balonu yüzey tavanı
    _MAX_SYS_BUBBLES = 50         # aktif pencerede yaşayan sys balonu sınırı
    # [2H] Detaylı sekme canlı satır tavanı (ilk açılış K=200 ile uyumlu)
    _DETACHED_TAB_MAX_ROWS = 200  # sekme başına yaşayan canlı satır sınırı
    # [2O] Ters-alias registry sınırları: JID başına 256 alias, toplam 64
    # JID kovası — deterministik FIFO tahliye (zamanlayıcı/ttl yok).
    _MAM_ALIAS_CAP_PER_JID = 256
    _MAM_ALIAS_MAX_JIDS = 64

    def _append(self, body: str, tag: str = "them",
                sender: str = "", is_me: bool | None = None,
                time_str: str | None = None, oob: str = "",
                encrypted: bool = False, mid: str = "",
                reply_to: dict | None = None, local_path: str = ""):
        self._prune_photo_refs()
        if time_str is None:
            time_str = datetime.now().strftime("%H:%M")
        if is_me is None:
            is_me = (tag == "me")

        # Tarih ayırıcı
        if tag != "sys":
            self._maybe_add_date_separator(time_str)

        # Sistem mesajı — divider stili (saf sunum); [2G] sınırlı tek yol
        if tag == "sys":
            return self._create_sys_bubble(body)

        # Ses URL'lerini topla
        audio_urls: list[str] = []
        for m in _AUDIO_URL_RE.finditer(body):
            url = m.group(1)
            if url not in audio_urls:
                audio_urls.append(url)
        if oob and _AUDIO_URL_RE.match(oob) and oob not in audio_urls:
            audio_urls.insert(0, oob)

        # Resim URL'lerini topla
        img_urls: list[str] = []
        if oob and oob not in audio_urls:
            img_urls.append(oob)
        for m in _IMG_URL_RE.finditer(body):
            url = m.group(1)
            if url not in img_urls and url not in audio_urls:
                img_urls.append(url)
        display_body = body
        if audio_urls:
            for url in audio_urls:
                display_body = display_body.replace(url, "").strip()
        if img_urls:
            for url in img_urls:
                display_body = display_body.replace(url, "").strip()
        # Şifreli dosyalar (video, belge — aesgcm://): uzun anahtar metni
        # gösterilmez, yerine indirip açan bir kart çıkar
        aes_files = _aesgcm_file_urls(body, set(img_urls) | set(audio_urls))
        for url in aes_files:
            display_body = display_body.replace(url, "").strip()

        # Art arda aynı gönderici kontrolü
        sender_key = ("me" if is_me else sender)
        same_sender = (sender_key == self.__class__._last_sender)
        self.__class__._last_sender = sender_key

        compact = getattr(self, '_compact_mode', False)
        sender_photo = self._avatars.get(self.active) if self.active else None
        view = _render.render_base_message(
            self.msg_frame, _chat_theme(), is_me=is_me, sender=sender,
            same_sender=same_sender, compact=compact, reply_to=reply_to,
            display_body=display_body, formatter=self._format_markdown,
            avatar_factory=_avatar, avatar_photo=sender_photo,
            photo_refs=self._photo_refs, on_jump=self._jump_to_message)
        row, bubble = view.row, view.bubble
        bubble_bg = view.colors["bubble_bg"]
        if view.body_kind == "label":
            row._body_label = view.body_widget  # güncelleme/düzeltme referansı
        elif view.body_kind == "frame":
            row._body_frame = view.body_widget

        # Resimler — mesaj başına zengin görsel sınırı (2E): ilk
        # _MAX_INLINE_IMAGES benzersiz URL zengin akış; fazlası URL başına
        # widget DEĞİL — tek taşan denetimiyle erişilebilir kalır.
        # Kota placeholder/_request_image/dispatcher'dan ÖNCE uygulanır.
        if HAS_PIL and img_urls:
            for url in img_urls[:_MAX_INLINE_IMAGES]:
                img_holder = _media_ui.image_placeholder(
                    bubble, _chat_theme(), bubble_bg)
                self._request_image(url, img_holder, bubble_bg)
            if len(img_urls) > _MAX_INLINE_IMAGES:
                self._add_media_overflow_control(
                    bubble, "image", img_urls[_MAX_INLINE_IMAGES:], bubble_bg)
        elif img_urls:
            for url in img_urls[:_MAX_INLINE_IMAGES]:
                _media_ui.image_link(
                    bubble, _chat_theme(), url, bubble_bg,
                    lambda u=url: _safe_open_url(u))
            if len(img_urls) > _MAX_INLINE_IMAGES:
                self._add_media_overflow_control(
                    bubble, "image", img_urls[_MAX_INLINE_IMAGES:], bubble_bg)

        # Ses dosyaları — ilk _MAX_INLINE_AUDIO benzersiz URL zengin akış;
        # fazlası URL başına widget DEĞİL — tek taşan denetimi (2E takip:
        # fallback_link bubble'ın çocuklarını temizlediği için burada
        # asla bubble ile çağrılmaz).
        for url in audio_urls[:_MAX_INLINE_AUDIO]:
            audio_holder = _audio_ui.audio_placeholder(
                bubble, _chat_theme(), bubble_bg)
            self._request_audio(url, audio_holder, bubble_bg)
        if len(audio_urls) > _MAX_INLINE_AUDIO:
            self._add_media_overflow_control(
                bubble, "audio", audio_urls[_MAX_INLINE_AUDIO:], bubble_bg)

        # URL önizleme — resim olmayan URL'ler için
        all_media = set(img_urls) | set(audio_urls)
        non_img_urls = [u for u in _URL_RE.findall(body)
                        if u not in all_media]
        if non_img_urls:
            for url in non_img_urls[:2]:  # max 2 önizleme
                prev_f = tk.Frame(bubble, bg=BORDER, padx=1, pady=1)
                prev_f.pack(anchor="w", fill="x", pady=(4, 2))
                prev_inner = tk.Frame(prev_f, bg=BG_CARD, padx=8, pady=6)
                prev_inner.pack(fill="x")
                lnk = tk.Label(prev_inner, text=url[:60] + ("…" if len(url) > 60 else ""),
                               fg=ACCENT, bg=BG_CARD, font=(FONT, 7),
                               cursor="hand2", anchor="w")
                lnk.pack(anchor="w")
                lnk.bind("<Button-1>",
                         lambda _, u=url: _safe_open_url(u))
                # Arka planda önizleme çek (cache/in-flight'lı; slot yoksa
                # ya da tekrar eden URL ise sessizce atlanır)
                self._request_url_preview(url, prev_inner)

        # Zaman damgası + şifreleme + gönderildi işareti — sağ alt
        meta_frame = _render.render_meta_row(bubble, _chat_theme(), time_str,
                                             is_me, encrypted, bubble_bg)

        # Mesaj ID'si kaydet (düzenleme/silme/tepki için)
        row._msg_index = len(self._bubble_widgets)
        row._is_me = is_me
        row._body = body
        row._tag = tag
        row._mid = mid
        row._sender = sender
        row._reply_to = reply_to
        row._retracted = False
        row._edited = False
        row._bubble = bubble
        row._oob = oob                # AI: ses/görsel kaynağı
        row._local_path = local_path
        row._encrypted = encrypted    # AI: bulut gizlilik kapısı
        row._meta_frame = meta_frame  # AI: ses dökümü bunun önüne girer
        self._ai_inline_transcript(row)

        # Sağ tık menüsü + çift tık ile yanıtla (tüm alt widget'lar)
        self._bind_message_menu(row)
        def _dbl_reply(_e, r=row):
            if getattr(r, "_mid", "") and not getattr(r, "_retracted", False):
                self._set_reply(r._mid, getattr(r, "_body", ""),
                                getattr(r, "_sender", ""))
        row.bind("<Double-Button-1>", _dbl_reply)
        for child in row.winfo_children():
            child.bind("<Double-Button-1>", _dbl_reply)

        if local_path:
            self._attach_file_card(bubble, bubble_bg, local_path)
        for url in aes_files:
            _media_ui.file_card(
                bubble, _chat_theme(), _aesgcm.file_name(url),
                "🔒 Şifreli dosya (OMEMO)", "⬇ İndir ve aç", "📂 Klasörde göster",
                lambda u=url: self._open_aesgcm_file(u),
                lambda u=url: self._open_aesgcm_file(u, reveal=True))

        self._bubble_widgets.append(row)
        self._bind_scroll_widget(row)
        # [2M] Önizleme sahipliği kaydı append'ten kaldırıldı: tek sahiplik
        # kaynağı _store'un (target, örnek-UID) yazımıdır — append örnek
        # kimliğini bilemez, eski mid-only kaydı çapraz bulaşma üretirdi.
        if mid:
            # [2M] Tepki sunumu (jid, mid) kapsamlı; render aktif sohbet
            # bağlamındadır — her yeni satır mevcut durumu taşır (Policy C).
            self._render_reactions(
                row,
                self._reactions.get((getattr(self, "active", ""), mid), {}))
        self._scroll_bottom()
        return row  # [2I] render yolu kalan-TTL zamanlaması için satırı alır

    def _bind_message_menu(self, widget, row=None):
        """Mesaja ve tüm alt widget'larına sağ tık + hover eylemlerini bağla."""
        row = row if row is not None else widget
        widget.bind("<Button-3>",
                    lambda e, r=row: self._message_context_menu(e, r))
        widget.bind("<Enter>",
                    lambda e, r=row: self._schedule_show_actions(r), "+")
        widget.bind("<Leave>",
                    lambda e: self._schedule_hide_actions(), "+")
        for child in widget.winfo_children():
            self._bind_message_menu(child, row)

    # ── Mesaj eylem çubuğu (hover butonları) ─────────────────────────────────
    def _is_descendant(self, widget, ancestor) -> bool:
        """widget, ancestor'ün alt öğesi mi? (hover takibi için)"""
        w = widget
        try:
            while w is not None:
                if w is ancestor:
                    return True
                w = w.master
        except Exception:
            pass
        return False

    def _cancel_show_actions(self):
        sid = getattr(self, "_actions_show_id", None)
        if sid:
            try:
                self.root.after_cancel(sid)
            except Exception:
                pass
            self._actions_show_id = None

    def _cancel_hide_actions(self):
        hid = getattr(self, "_actions_hide_id", None)
        if hid:
            try:
                self.root.after_cancel(hid)
            except Exception:
                pass
            self._actions_hide_id = None

    def _hide_action_bar_now(self):
        bar = getattr(self, "_actions_bar", None)
        if bar is not None:
            try:
                if bar.winfo_exists():
                    bar.place_forget()
            except Exception:
                pass
        self._actions_row = None

    def _reset_action_bar(self):
        self._cancel_show_actions()
        self._cancel_hide_actions()
        self._hide_action_bar_now()
        self._actions_bar = None

    def _schedule_show_actions(self, row):
        """Fare mesajın üzerine gelince eylem çubuğunu (kısa gecikmeyle) aç."""
        self._cancel_show_actions()
        self._cancel_hide_actions()
        self._actions_show_id = self.root.after(
            120, lambda: self._show_actions(row))

    def _schedule_hide_actions(self, delay: int = 260):
        self._cancel_hide_actions()
        self._actions_hide_id = self.root.after(
            delay, self._hide_actions_if_not_hovered)

    def _hide_actions_if_not_hovered(self):
        row = getattr(self, "_actions_row", None)
        bar = getattr(self, "_actions_bar", None)
        if row is None or bar is None:
            return
        try:
            under = self.root.winfo_containing(*self.root.winfo_pointerxy())
        except Exception:
            under = None
        if under is not None and (self._is_descendant(under, row)
                                  or self._is_descendant(under, bar)):
            self._schedule_hide_actions(160)
            return
        self._hide_action_bar_now()

    def _ensure_action_bar(self):
        bar = getattr(self, "_actions_bar", None)
        try:
            if bar is not None and bar.winfo_exists():
                return bar
        except Exception:
            pass
        bar = _actions_ui.create_action_bar(
            self.msg_frame, _chat_theme(),
            on_enter=self._cancel_hide_actions,
            on_leave=lambda: self._schedule_hide_actions(),
            on_wheel=self._on_scroll,
            on_scroll_units=lambda d: self.chat_canvas.yview_scroll(d, "units"))
        self._actions_bar = bar
        return bar

    def _populate_action_bar(self, bar, row):
        """Satıra uygun butonları (sırayla) kur — sunum ui/chat/actions."""
        body = getattr(row, "_body", "")
        is_me = getattr(row, "_is_me", False)
        mid = getattr(row, "_mid", "")
        sender = getattr(row, "_sender", "")
        retracted = getattr(row, "_retracted", False)
        reply_ref = getattr(row, "_reply_to", None)
        can_send = bool(self.active and self.bot)
        mtype = "groupchat" if self.active in self.rooms else "chat"

        specs = []
        if reply_ref and not retracted:
            specs.append(("⤴", "Alıntılanan mesaja git",
                          lambda: self._jump_to_message(
                              (reply_ref or {}).get("id", "")), False))
        if mid and can_send and not retracted:
            specs.append(("↩", "Yanıtla",
                          lambda: self._set_reply(mid, body, sender), False))
            specs.append(("😊", "Tepki ekle",
                          lambda: self._quick_reaction_popup(bar, mid), False))
        if mid and self._reactions.get(self._reaction_key(mid)):
            specs.append(("👥", "Tepkileri gör",
                          lambda: self._reaction_details_dialog(mid), False))
        if not retracted and self._ai_message_items(row):
            specs.append(("✨", "AI: çevir / yazıya dök / açıkla",
                          lambda: self._ai_message_menu(row, bar), False))
        if body and not retracted:
            specs.append(("📋", "Kopyala",
                          lambda: (self.root.clipboard_clear(),
                                   self.root.clipboard_append(body)), False))
        if body and can_send and not retracted:
            specs.append(("➦", "İlet",
                          lambda: self._forward_dialog(body, sender), False))
            specs.append(("📌", "Sabitle",
                          lambda: self._pin_message(body, sender), False))
        if is_me and mid and can_send and not retracted:
            specs.append(("✏", "Düzenle",
                          lambda: self._edit_message_dialog(mid, body, mtype),
                          False))
            specs.append(("🗑", "Sil",
                          lambda: self._retract_message(mid, mtype), True))
        _actions_ui.populate_action_bar(
            bar, _chat_theme(), specs, add_tooltip=_add_tooltip,
            on_after=self._hide_action_bar_now)

    def _show_actions(self, row):
        if row is None or getattr(row, "_retracted", False):
            return
        bar = self._ensure_action_bar()
        self._populate_action_bar(bar, row)
        if not _actions_ui.position_action_bar(row, bar):
            return
        self._actions_row = row

    def _quick_reaction_popup(self, anchor, mid):
        """😊 butonu: hızlı tepki menüsü + tam seçici (ui/chat/actions)."""
        _actions_ui.show_quick_reaction_menu(
            self.root, anchor, theme=_chat_theme(),
            mine=self._my_reactions.get(self._reaction_key(mid), set()),
            on_react=lambda e: self._toggle_reaction(mid, e),
            on_more=lambda: self._show_emoji_picker(mid))

    def _open_aesgcm_file(self, url, reveal=False):
        """Şifreli dosyayı (aesgcm://) arka planda indir, çöz, kaydet, aç."""
        threading.Thread(target=self._aesgcm_file_worker, args=(url, reveal),
                         daemon=True).start()

    def _aesgcm_file_worker(self, url, reveal=False):
        """Worker: indir + çöz → indirme klasörüne (çakışmasız ad) kaydet →
        dosyayı ya da klasörü aç. Bozuk anahtar/veride hiçbir şey yazılmaz."""
        name = _aesgcm.file_name(url)
        folder = (getattr(self, "_download_dir", "")
                  or os.path.expanduser("~/Downloads"))
        try:
            data = _fetch_url_bytes(url, _NET_AESGCM_FILE_MAX, timeout=60)
            os.makedirs(folder, exist_ok=True)
            path = jingle_ft.unique_download_path(folder, name)
            with open(path, "xb") as f:
                f.write(data)
        except Exception:
            _log.warning("Şifreli dosya açılamadı: %s", name, exc_info=True)
            self._safe_after(0, self._show_toast,
                             "⚠ Şifreli dosya açılamadı", name)
            return
        self._safe_after(0, self._show_toast, "📥 Şifreli dosya",
                         f"{os.path.basename(path)} kaydedildi")
        self._safe_after(0, _safe_open_url, folder if reveal else path)

    def _attach_file_card(self, parent, bg_color, path):
        """Sohbet balonuna yerel dosya kartı ekle (Aç / Klasörü Aç)."""
        try:
            size_txt = jingle_ft.format_size(os.path.getsize(path))
        except OSError:
            size_txt = ""
        _media_ui.file_card(
            parent, _chat_theme(), os.path.basename(path), size_txt,
            _t("ft_open"), _t("ft_open_folder"),
            lambda: _safe_open_url(path),
            lambda: _safe_open_url(os.path.dirname(path) or "."))

    def _image_fetch_worker(self, url):
        """Worker thread: resmi indir, thumbnail üret, abonelere dağıt."""
        MAX_W, MAX_H = 320, 280
        key = ("image", url)
        img = None
        try:
            raw = _fetch_url_bytes(url, _NET_IMG_MAX, timeout=15)
            img = Image.open(io.BytesIO(raw))
            # EXIF yönlendirme düzelt
            try:
                from PIL import ImageOps
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass
            # Oranı koru, küçült
            img.thumbnail((MAX_W, MAX_H), Image.LANCZOS)
            img.load()  # cache'e girecek: BytesIO/ağ bağımlılığı bitmeli
        except Exception:
            img = None
        subs = self._media_inflight_pop(key)
        if img is None:
            # başarısız sonuç cache'e yazılmaz; hata GUI'de dağıtılır
            self._safe_after(0, self._media_image_error, url, subs)
            return
        self._media_cache_put(key, img)
        # Ana thread'de güncelle — PhotoImage GUI thread'inde üretilir
        self._safe_after(0, self._place_image_for_subs, url, img, subs)

    def _place_image_for_subs(self, url, img, subs):
        """GUI thread: aynı fetch'in tüm geçerli abonelerine yerleştir.

        Holder destroy olmuşsa benign no-op; diğer aboneler etkilenmez.
        """
        for holder, bg_color in subs:
            self._place_image(holder, img, bg_color, url)

    def _media_image_error(self, url, subs):
        """GUI thread: başarısız image fetch'in error yolları."""
        for holder, bg_color in subs:
            try:
                if holder.winfo_exists():
                    _media_ui.image_error(holder, _chat_theme())
            except Exception:
                pass

    def _place_image(self, holder, img, bg_color, url):
        """Placeholder'ı gerçek resimle değiştir (GUI thread).

        Holder (sohbet değişimi) destroy olmuşsa benign no-op.
        """
        if not holder.winfo_exists():
            return
        photo = ImageTk.PhotoImage(img)
        self._photo_refs.append(photo)  # GC koruması
        # Tıklayınca büyük göster
        _media_ui.place_image(
            holder, photo, bg_color,
            lambda _: self._show_image_fullscreen(photo, url))
        self._scroll_bottom()

    def _show_image_fullscreen(self, _photo, url):
        """Resmi büyük pencerede göster — orijinale yakın boyutta indir."""
        top, lbl = _media_ui.fullscreen_window(
            self.root, _chat_theme(),
            (lambda: self._open_aesgcm_file(url)) if _aesgcm.parse(url)
            else (lambda: _safe_open_url(url)))

        # Arka planda büyük halini indir
        def _load_full():
            try:
                raw = _fetch_url_bytes(url, _NET_IMG_FULL_MAX, timeout=20)
                img = Image.open(io.BytesIO(raw))
                try:
                    from PIL import ImageOps
                    img = ImageOps.exif_transpose(img)
                except Exception:
                    pass
                # Ekrana sığdır ama çok küçültme
                img.thumbnail((780, 560), Image.LANCZOS)
                self._safe_after(0, _show, img)
            except Exception:
                def _show_error():
                    if lbl.winfo_exists():
                        _media_ui.image_error(lbl, _chat_theme())
                self._safe_after(0, _show_error)

        def _show(img):
            if not lbl.winfo_exists():
                return
            photo = ImageTk.PhotoImage(img)
            self._photo_refs.append(photo)
            _media_ui.place_photo(lbl, photo)

        threading.Thread(target=_load_full, daemon=True).start()

    def _audio_fetch_worker(self, url):
        """Worker thread: ses dosyasını indir, gerekiyorsa WAV'a çevir.

        Tek in-flight kaydı tüketilir; dağıtım GUI resolver'a bırakılır
        (Tk'ya dokunmaz). Tempfile sahipliği her dalda ya tescilli ya
        silinmiş olarak biter. Kapanış sınırlarında: tescil reddedilirse
        worker yeni artefaktı kendisi siler ve kullanmayı bırakır; tescil
        kabul edildiyse sahiplik kapanış temizliğinindedir.
        """
        wav_path = None
        tmp_path = None
        tmp_registered = False
        try:
            if getattr(self, "_closing", False):
                raise _WorkerShutdown
            raw = _fetch_url_bytes(url, _NET_AUDIO_MAX, timeout=30)
            # Geçici dosyaya kaydet
            suffix = ".wav"
            for ext in (".ogg", ".opus", ".mp3", ".m4a", ".flac", ".aac",
                        ".webm"):
                if ext in url.lower():
                    suffix = ext
                    break
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            tmp.write(raw)
            tmp.close()
            tmp_path = wav_path = tmp.name
            if not self._remember_temp(wav_path):
                # sahiplik reddi: kapanış temizliği zaten geçti — yeni
                # artefaktı kendin sil, ffmpeg'e/UI'a hiç gitme
                try:
                    os.unlink(tmp.name)
                except OSError:
                    pass
                wav_path = None
                tmp_path = None
                raise _WorkerShutdown
            tmp_registered = True
            if getattr(self, "_closing", False):
                # tescil kapanış temizliğinin sahipliğinde: ffmpeg'e girme
                raise _WorkerShutdown

            # Eğer WAV değilse, ffmpeg ile dönüştürmeyi dene
            if suffix != ".wav":
                wav_converted = tmp.name + ".wav"
                converted_ok = False
                try:
                    import subprocess
                    result = subprocess.run(
                        ["ffmpeg", "-y", "-i", tmp.name, "-ar", "44100",
                         "-ac", "1", "-f", "wav", wav_converted],
                        capture_output=True, timeout=15)
                    converted_ok = (result.returncode == 0
                                    and os.path.exists(wav_converted))
                except Exception:
                    converted_ok = False
                if converted_ok:
                    wav_path = wav_converted
                    if not self._remember_temp(wav_path):
                        # temizlik ffmpeg sırasında geçti: çıktı artefaktını
                        # sil; original temizlikte silinmişti — hiçbirini
                        # kullanma, yerleşim planlama
                        try:
                            os.unlink(wav_converted)
                        except OSError:
                            pass
                        wav_path = None
                        raise _WorkerShutdown
                    try:
                        # Orijinal non-WAV dosyayı kullanan erişilebilir yol
                        # yok (yerleşim/oynatma yalnız nihai wav_path ile
                        # çalışır): hemen sil, kaydı gerçekle eşle.
                        os.unlink(tmp.name)
                        self._forget_temp(tmp.name)
                    except OSError:
                        pass  # silinemedi: tescilli kalır, kapanışta denenir
                else:
                    # kısmi/bozuk dönüştürme artefaktı: tüketicisi yok
                    try:
                        if os.path.exists(wav_converted):
                            os.unlink(wav_converted)
                    except OSError:
                        pass
        except Exception:
            wav_path = None
            # tescil atlanmışsa yarı kalmamış tempfile'ı bırakma
            if tmp_path and not tmp_registered:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        subs = self._audio_inflight_pop(url)
        if wav_path is not None:
            self._safe_after(0, self._resolve_audio_ready, url, wav_path, subs)
        elif not getattr(self, "_closing", False):
            # kapanışta sessiz çıkış: bayat UI mutasyonu planlanmaz
            self._safe_after(0, self._resolve_audio_failed, url, subs)

    def _place_audio(self, holder, wav_path, bg_color, url):
        """Placeholder'ı ses oynatıcı ile değiştir (destroyed → no-op)."""
        if not holder.winfo_exists():
            return
        _audio_ui.start_player(holder, _chat_theme(), bg_color)
        self._show_voice_waveform(holder, wav_path, bg_color)
        self._scroll_bottom()

    def _place_audio_fallback(self, holder, url, bg_color):
        """Ses yüklenemedi — link göster (destroyed → no-op)."""
        if not holder.winfo_exists():
            return
        _audio_ui.fallback_link(holder, _chat_theme(), bg_color, url,
                                lambda: _safe_open_url(url))

    def _bind_scroll_widget(self, w):
        """Tüm alt widget'larda scroll çalışsın (ui/chat/history)."""
        _history_ui.bind_scroll_widget(
            w, self._on_scroll,
            lambda d: self.chat_canvas.yview_scroll(d, "units"))

    def _scroll_bottom(self):
        _history_ui.scroll_bottom(self.chat_canvas)

    def _clear_chat(self):
        """Görünümü temizle (domain history'ye dokunmaz)."""
        self.__class__._last_sender = None
        self._reset_action_bar()
        _history_ui.clear_view(self.msg_frame, self._bubble_widgets,
                               self._photo_refs)
        # [2G] Sistem balonu kayıtları da temizlenir; yok edilen widget'a
        # işaret eden bayat referans kalmasın.
        getattr(self, "_sys_bubbles", []).clear()
        getattr(self, "_subject_bubbles", {}).clear()

    # ── [2G] Sınırlı sistem/ortam balonu yüzeyi ──────────────────────────────
    def _create_sys_bubble(self, body, sys_kind=None):
        """[2G] tag=='sys' sunumunun TEK sınırlı yolu.

        Her yeni sistem balonu FIFO kayda alınır; cap aşımında en eski
        balon söndürülür. Yalnız sunumdur: self.chats/domain history'ye
        dokunmaz, mesaj pencere durumunu değiştirmez.
        """
        sf = _render.render_system_message(self.msg_frame, _chat_theme(),
                                           body)
        if sys_kind:
            sf._sys_kind = sys_kind
        self._bubble_widgets.append(sf)
        self._register_sys_bubble(sf)
        self._bind_scroll_widget(sf)
        self._scroll_bottom()
        self.__class__._last_sender = None
        return sf

    def _register_sys_bubble(self, sf):
        """[2G] Sys balonunu kayda al; cap aşımında en eskisini söndür."""
        if not hasattr(self, "_sys_bubbles"):
            self._sys_bubbles = []
        self._sys_bubbles.append(sf)
        while len(self._sys_bubbles) > self._MAX_SYS_BUBBLES:
            self._evict_oldest_sys_bubble()

    def _evict_oldest_sys_bubble(self):
        """[2G] En eski sys balonunu söndür; referansları tutarlı bırak.

        Yalnızca sys balonları tahliye edilir: normal mesaj satırları, tarih
        ayırıcılar ve tepki çerçeveleri asla dokunulmaz.
        """
        old = self._sys_bubbles.pop(0)
        kind = getattr(old, "_sys_kind", None)
        subjects = getattr(self, "_subject_bubbles", None)
        if kind and kind[0] == "subject" and subjects is not None:
            # Referans yalnız söndürülen balon o odanın GÜNCEL balonuysa düşer
            if subjects.get(kind[1]) is old:
                subjects.pop(kind[1], None)
        try:
            old.destroy()
        except Exception:
            pass
        try:
            self._bubble_widgets.remove(old)
        except ValueError:
            pass

    def _remove_sys_widget(self, old):
        """[2G] Sys balonunu listelerden güvenle sök ve söndür (idempotent)."""
        try:
            self._sys_bubbles.remove(old)
        except (ValueError, AttributeError):
            pass
        try:
            self._bubble_widgets.remove(old)
        except (ValueError, AttributeError):
            pass
        try:
            old.destroy()
        except Exception:
            pass

    def _show_room_subject(self, target: str, text: str):
        """[2G] Oda konusu: oda başına TEK güncel subject balonu (coalesce).

        Tekrarlayan subject stanza'ları balon biriktirmez: eski balon
        güvenle sökülür (evict/clear/replacement sonrası bayat referans
        yok), en güncel metin sınırlı sys yolundan yeni balonda görünür.
        """
        if not hasattr(self, "_subject_bubbles"):
            self._subject_bubbles = {}
        old = self._subject_bubbles.pop(target, None)
        if old is not None:
            self._remove_sys_widget(old)
        sf = self._create_sys_bubble(text, sys_kind=("subject", target))
        self._subject_bubbles[target] = sf

    def _clear_active_history(self) -> bool:
        """Aktif sohbetin geçmişini hem bellekten hem SQLite'tan sil."""
        if not self.active or self.active not in self.chats:
            return False
        # [2I] TTL sunum vadeleri unutulsun (chats hâlâ okunabilir olmalı)
        self._forget_ttl_deadlines(self.active)
        # [2M-B1] Tepki/önizleme sunum üstverisi de bu JID'e ait olduğu
        # kadarıyla unutulsun — bayat çipler/önizlemeler, silinen geçmişin
        # yerine gelen YENİ aynı-mid mesaja yapışamaz.
        self._forget_message_presentation_state(self.active)
        # [2O] Ters-alias kovası da bu JID'e aittir
        self._mam_alias_forget_jid(self.active)
        self.chats.pop(self.active, None)
        # [2F] Domain geçmişi gitti; bayat pencere indeksi kalmasın (M)
        self._reset_history_ui_state(self.active)
        _db_clear_chat(self.active)
        # Uçuştaki MAM isteklerini geçersiz kıl (bayat sonuç geri doldurmasın)
        self._mam_gen = getattr(self, "_mam_gen", {})
        self._mam_gen[self.active] = self._mam_gen.get(self.active, 0) + 1
        self._load_chat(self.active)
        return True

    def _clear_all_history(self) -> bool:
        """Tüm sohbet geçmişini hem bellekten hem SQLite'tan sil."""
        # [2I] Tüm TTL sunum vadeleri temizlenir (yalnız sunum üstverisi)
        getattr(self, "_ttl_deadlines", {}).clear()
        # [2M-B1] Tüm tepki/önizleme sunum üstverisi temizlenir — clear-all
        # "eski mesaj sunum önbelleği kalmasın" demektir (uid yeniden
        # kullanılamasa bile önbellek yaşam döngüsü geçmişe bağlıdır).
        getattr(self, "_reactions", {}).clear()
        getattr(self, "_my_reactions", {}).clear()
        getattr(self, "_reply_map", {}).clear()
        # [2O] Ters-alias registry tamamen boşalır
        self._mam_alias_clear_all()
        self.chats.clear()
        # [2F] Tüm pencere durumunu da temizle (M)
        self._ensure_history_state()
        self._history_start.clear()
        self._history_view_mode.clear()
        self._history_pending.clear()
        self._history_mam_intent.clear()
        # [2F-Blocker] MAM gezinme üstverisi tüm JID'lerde temizlenir
        getattr(self, "_mam_has_more", {}).clear()
        getattr(self, "_mam_oldest", {}).clear()
        _db_clear_all()
        # Tüm uçuştaki MAM isteklerini geçersiz kıl
        self._mam_gen = getattr(self, "_mam_gen", {})
        self._mam_gen = {k: v + 1 for k, v in self._mam_gen.items()}
        if self.active:
            self._load_chat(self.active)
        return True

    def _remember_temp(self, path: str):
        """Kapanışta silinmek üzere geçici dosyayı kaydet.

        Returns: True → tescil alındı; temizlik (kapanışta) sahipliğini
        üstlendi. False → kapanış temizliği zaten yapıldı, tescil reddedildi:
        çağıran artefaktı kendisi silmeli ve kullanmayı bırakmalıdır.
        """
        with self._temp_lock_get():
            if getattr(self, "_closing", False) and \
                    getattr(self, "_temp_cleanup_done", False):
                return False
            if path and path not in self._temp_files:
                self._temp_files.append(path)
            return True

    def _forget_temp(self, path: str):
        """Tempfile sahipliği kaydından düş (dosya zaten silindi/taşındıysa)."""
        with self._temp_lock_get():
            try:
                self._temp_files.remove(path)
            except (ValueError, AttributeError):
                pass

    def _temp_lock_get(self):
        """Tempfile kaydı için küçük instance kilidi (race-safe sahiplik)."""
        lock = getattr(self, "_temp_lock", None)
        if lock is None:
            lock = self._temp_lock = threading.Lock()
        return lock

    def _play_notification_sound(self):
        """Basit bip sesi çal (paplay/aplay ile) — kayıt sahipliği 2D.

        WAV oluşturulduktan hemen sonra tescil edilir; tescil reddedilirse
        (kapanış temizliği geçti) dosya silinir ve oynatıcı başlatılmaz.
        Gecikmeli temizlik dosyayı sildikten sonra kaydı `_forget_temp`
        ile uzlaştırır; quit temizliği önce gerçekleşirse çağrı no-op'tur.
        """
        tmp_path = None
        registered = False
        try:
            # Kısa WAV oluştur (440 Hz, 150ms)
            import struct
            import subprocess as _notify_sp
            sr = 22050
            dur = 0.15
            n = int(sr * dur)
            buf = b""
            for i in range(n):
                v = int(16000 * (0.5 * (1 - i / n)) *
                        __import__("math").sin(2 * 3.14159 * 440 * i / sr))
                buf += struct.pack("<h", v)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                wf.writeframes(buf)
            if not self._remember_temp(tmp_path):
                # kapanış temizliği zaten geçti: dosyayı sil, çalma
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                return
            registered = True
            for player in ["paplay", "aplay", "pw-play"]:
                try:
                    process = _notify_sp.Popen([player, tmp_path],
                                               stdout=_notify_sp.DEVNULL,
                                               stderr=_notify_sp.DEVNULL)
                    # Çalma bitince dosyayı sil (gecikmeli, bloklamadan);
                    # silince kayıt sahipliğini gerçeğe göre uzlaştır.
                    def _delayed_remove(path=tmp_path, process=process):
                        try:
                            try:
                                process.wait(timeout=10)
                            except _notify_sp.TimeoutExpired:
                                process.kill()
                                process.wait()
                        finally:
                            removed = False
                            try:
                                os.remove(path)
                                removed = True
                            except OSError:
                                removed = not os.path.exists(path)
                            if removed:
                                self._forget_temp(path)
                    threading.Thread(target=_delayed_remove,
                                     daemon=True).start()
                    return
                except FileNotFoundError:
                    continue
            # hiçbir oynatıcı yok: dosya tescilli kalır → kapanış temizliği siler
        except Exception:
            if tmp_path is not None and not registered:
                _cleanup_temp_files([tmp_path])
            _log.warning("Bildirim sesi hazırlanamadı", exc_info=True)

    def _cleanup_temp_registry(self):
        """Tempfile kaydını kilitle çek ve dosyaları sil.

        Bu çağrıdan sonra gelen `_remember_temp` tescilleri reddedilir;
        böylece temizlik anlık görüntüsü ile geç bir worker'ın tescili
        arasında sahipsiz artefakt bırakan pencere oluşmaz.
        """
        with self._temp_lock_get():
            self._temp_cleanup_done = True
            snapshot = list(getattr(self, "_temp_files", []))
            if hasattr(self, "_temp_files"):
                self._temp_files.clear()
        _cleanup_temp_files(snapshot)

    def _prune_photo_refs(self):
        """Global PhotoImage referans listesini sınırla. Her görsel kendi
        widget'ında da referans tuttuğu için eski kayıtlar güvenle düşer."""
        if len(self._photo_refs) > 400:
            del self._photo_refs[:-400]

    def _remember_mid(self, jid, mid, limit=500):
        """Stanza kimliğini sohbet başına sınırlı listede sakla."""
        if not mid:
            return
        ids = self._msg_ids.setdefault(jid, [])
        ids.append(mid)
        if len(ids) > limit:
            del ids[:-limit]

    # ── URL önizleme ─────────────────────────────────────────────────────────
    def _preview_fetch_worker(self, url):
        """Worker thread: URL önizleme bilgisini çek (16 KB cap korunur)."""
        key = ("preview", url)
        try:
            info = _fetch_url_preview(url)
        except Exception:
            info = None
        if not info or (not info.get("title") and not info.get("desc")):
            self._media_inflight_pop(key)
            return  # mevcut sessiz davranış: önizleme gösterilmez
        self._media_cache_put(key, info)
        subs = self._media_inflight_pop(key)
        self._safe_after(0, self._show_preview_for_subs, info, subs)

    def _show_preview_for_subs(self, info, containers):
        """GUI thread: önizleme etiketlerini abone konteynerlere yaz."""
        for container in containers:
            try:
                _media_ui.url_preview_labels(
                    container, _chat_theme(), info.get("title"),
                    info.get("desc"))
                self._scroll_bottom()
            except Exception:
                pass

    # ── Yanıt çözümleme / mesaj içi gezinme ──────────────────────────────────
    def _remember_reply(self, jid, key, reply_to, cap: int = 800):
        """Yanıt alıntısını (jid, örnek-kimlik) ile sakla; sınırı koru.

        [2M] key: güncel girişlerde örnek UID, eski girişlerde mid. Önbellek
        "hangi SAKLANMIŞ GİRİŞ bu önizlemeye sahip" sorusunu yanıtlar;
        peer'in hangi duplicate-mid örneği kastettiğini değil.
        """
        if not (jid and key and reply_to):
            return
        self._reply_map[(jid, key)] = dict(reply_to)
        while len(self._reply_map) > cap:
            self._reply_map.pop(next(iter(self._reply_map)))

    # ── Bounded media worker dispatch (Security Hotfix 2A) ────────────────────
    def _dispatch_media_worker(self, target, args=(), on_saturated=None):
        """Remote-media worker'ı eşzamanlılık tavanıyla başlat.

        Returns: worker başlatıldıysa True. Slot kalmadıysa worker
        BAŞLATMAZ, çağıran thread'i (GUI) bloklamaz ve varsa
        on_saturated() degrade adımını çalıştırır. Semaphore lazy-init
        yalnızca GUI thread'inden çağrım varsayımına dayanır; worker
        bitişleri slotu worker thread'inde bırakır (serbesttir).
        """
        if getattr(self, "_closing", False):
            return False
        sem = getattr(self, "_media_slots", None)
        if sem is None:
            sem = self._media_slots = threading.BoundedSemaphore(
                _MEDIA_WORKER_CAP)
        if not sem.acquire(blocking=False):
            if on_saturated is not None:
                try:
                    on_saturated()
                except Exception:
                    _log.warning("Media saturate degrade adımı başarısız",
                                 exc_info=True)
            return False

        def _run():
            try:
                target(*args)
            except Exception:
                _log.error("Media worker beklenmedik hata", exc_info=True)
            finally:
                sem.release()

        try:
            threading.Thread(target=_run, daemon=True).start()
        except Exception:
            sem.release()  # start edilemedi: slot sızmasın
            if on_saturated is not None:
                try:
                    on_saturated()
                except Exception:
                    _log.warning("Media worker start degrade adımı başarısız",
                                 exc_info=True)
            return False
        return True

    def _saturate_image_holder(self, holder, url):
        """Slot yoksa resim placeholder'ını tıklanabilir bağlantıya çevir."""
        try:
            holder.config(text=f"🔗 {url[:60]}", fg=ACCENT, cursor="hand2")
            holder.bind("<Button-1>", lambda _e, u=url: _safe_open_url(u))
        except Exception:
            pass

    def _saturate_audio_holder(self, holder, url, bg_color):
        """Slot yoksa ses placeholder'ını mevcut bağlantı görünümüne düşür."""
        try:
            _audio_ui.fallback_link(holder, _chat_theme(), bg_color, url,
                                    lambda: _safe_open_url(url))
        except Exception:
            pass

    # ── Taşan medya denetimi + sayfalı görüntüleyici (2E takip) ──────────────
    def _add_media_overflow_control(self, bubble, kind, urls, bg_color):
        """Taşan medya URL'leri için TEK tıklanabilir denetim üret.

        URL listesi closure'da tutulur; URL başına widget üretilmez ve
        bubble'ın mevcut çocuklarına (gövde/zengin medya) dokunulmaz.
        Tık → sayfalı görüntüleyici.
        """
        texts = {"image": "🔗 {n} görsel bağlantısı daha",
                 "audio": "🎤 {n} ses bağlantısı daha"}
        ctl = tk.Label(bubble, text=texts[kind].format(n=len(urls)),
                       fg=ACCENT, bg=bg_color, cursor="hand2",
                       font=(FONT, 8), anchor="w")
        ctl.pack(anchor="w", pady=(2, 0))
        ctl._overflow_urls = list(urls)
        ctl._overflow_kind = kind
        ctl.bind("<Button-1>",
                 lambda _e: self._open_media_overflow_viewer(
                     kind, list(urls)))

    def _open_media_overflow_viewer(self, kind, urls):
        """Taşan medya bağlantılarını sayfalı görüntüleyicide aç (≤30/sayfa).

        Yalnız mevcut URL listesini gösterir; ağ/media isteği yapmaz, cache'e
        dokunmaz. Widget sayısı N'den bağımsız sabittir.
        """
        if getattr(self, "_closing", False):
            return
        titles = {"image": "Görsel bağlantıları", "audio": "Ses bağlantıları"}
        page_size = 30
        pages = max(1, (len(urls) + page_size - 1) // page_size)
        state = {"p": 0}
        top = tk.Toplevel(self.root)
        top.title(f"{titles[kind]} — {len(urls)} bağlantı")
        top.configure(bg=BG)
        top.geometry("600x430")
        top.transient(self.root)
        frame = tk.Frame(top, bg=BG)
        frame.pack(fill="both", expand=True)
        lb = tk.Listbox(frame, bg=BG_CARD, fg=FG, selectbackground=SEL_BG,
                        selectforeground=SEL_FG, activestyle="none",
                        font=(FONT, 9), highlightthickness=0, borderwidth=0)
        lb.pack(fill="both", expand=True, padx=12, pady=(12, 4))

        def show(p):
            p = max(0, min(pages - 1, p))
            state["p"] = p
            lb.delete(0, "end")
            for u in urls[p * page_size:(p + 1) * page_size]:
                lb.insert("end", u)
            info.config(text=f"Sayfa {p + 1}/{pages}")

        def open_selected(_e=None):
            sel = lb.curselection()
            if sel:
                _safe_open_url(urls[state["p"] * page_size + sel[0]])

        lb.bind("<Double-Button-1>", open_selected)
        nav = tk.Frame(top, bg=BG)
        nav.pack(fill="x", padx=12, pady=(0, 12))
        tk.Button(nav, text="◀ Önceki", font=(FONT, 9), bg=BG_CARD, fg=FG,
                  relief="flat", command=lambda: show(state["p"] - 1)
                  ).pack(side="left")
        info = tk.Label(nav, text="", bg=BG, fg=FG_DIM, font=(FONT, 9))
        info.pack(side="left", padx=10)
        tk.Button(nav, text="Sonraki ▶", font=(FONT, 9), bg=BG_CARD, fg=FG,
                  relief="flat", command=lambda: show(state["p"] + 1)
                  ).pack(side="left")
        tk.Button(nav, text="🔗 Tarayıcıda Aç", font=(FONT, 9), bg=BG_CARD,
                  fg=ACCENT, relief="flat", command=open_selected
                  ).pack(side="right")
        show(0)

    # ── Media cache / single-flight (Security Hotfix 2B) ──────────────────────
    def _media_lock_get(self):
        lock = getattr(self, "_media_lock", None)
        if lock is None:
            lock = self._media_lock = threading.Lock()
        return lock

    def _media_cache_get(self):
        cache = getattr(self, "_media_cache", None)
        if cache is None:
            cache = self._media_cache = OrderedDict()
        return cache

    def _media_inflight_get(self):
        infl = getattr(self, "_media_inflight", None)
        if infl is None:
            infl = self._media_inflight = {}
        return infl

    def _media_cache_put(self, key, value):
        """Sınırı aşan en eski girdiyi düşüren deterministic LRU yazımı."""
        with self._media_lock_get():
            cache = self._media_cache_get()
            cache[key] = value
            cache.move_to_end(key)
            while len(cache) > _MEDIA_CACHE_MAX:
                cache.popitem(last=False)

    def _media_inflight_pop(self, key):
        """In-flight kaydını kilitle alınmış biçimde düşür; aboneleri döndür."""
        with self._media_lock_get():
            rec = self._media_inflight_get().pop(key, None)
        return rec["subs"] if rec else []

    def _request_image(self, url, holder, bg_color):
        """Resim isteği: cache hit → yerleşim, in-flight → abone, miss → fetch.

        GUI thread'inden çağrılır. Döndürür: fetch başlatıldı/hizmet
        verildi ise True; kapanış veya slot yokluğu nedeniyle düşürüldü ise
        False (degrade adımı çağrılmıştır).
        """
        if getattr(self, "_closing", False):
            return False
        key = ("image", url)
        with self._media_lock_get():
            cache = self._media_cache_get()
            if key in cache:
                cache.move_to_end(key)
                img = cache[key]
            else:
                img = None
                infl = self._media_inflight_get()
                rec = infl.get(key)
                if rec is not None:
                    rec["subs"].append((holder, bg_color))  # single-flight
                    return True
                infl[key] = {"subs": [(holder, bg_color)]}
        if img is not None:
            self._place_image(holder, img, bg_color, url)  # cache hit
            return True
        started = self._dispatch_media_worker(
            self._image_fetch_worker, (url,),
            on_saturated=lambda: self._image_saturated(key, holder, url))
        if not started:
            with self._media_lock_get():
                self._media_inflight_get().pop(key, None)
        return started

    def _image_saturated(self, key, holder, url):
        """2A slotu yok: in-flight kaydını düşür, link görünümüne geç."""
        self._media_inflight_pop(key)
        self._saturate_image_holder(holder, url)

    def _request_url_preview(self, url, container):
        """URL önizleme isteği: cache/in-flight/single-flight tavanlı."""
        if getattr(self, "_closing", False):
            return False
        key = ("preview", url)
        with self._media_lock_get():
            cache = self._media_cache_get()
            if key in cache:
                cache.move_to_end(key)
                info = cache[key]
            else:
                info = None
                infl = self._media_inflight_get()
                rec = infl.get(key)
                if rec is not None:
                    rec["subs"].append(container)  # single-flight
                    return True
                infl[key] = {"subs": [container]}
        if info is not None:
            self._show_preview_for_subs(info, [container])  # cache hit
            return True
        started = self._dispatch_media_worker(
            self._preview_fetch_worker, (url,),
            on_saturated=lambda: self._media_inflight_pop(key))
        if not started:
            with self._media_lock_get():
                self._media_inflight_get().pop(key, None)
        return started

    # ── Audio single-flight (Security Hotfix 2C) ─────────────────────────────
    def _audio_inflight_get(self):
        infl = getattr(self, "_audio_inflight", None)
        if infl is None:
            infl = self._audio_inflight = {}
        return infl

    def _audio_inflight_pop(self, url):
        """In-flight ses kaydını kilitle alınmış biçimde düşür; aboneleri döndür."""
        with self._media_lock_get():
            rec = self._audio_inflight_get().pop(url, None)
        return rec["subs"] if rec else []

    def _request_audio(self, url, holder, bg_color):
        """Ses isteği: in-flight → abone (weakref), miss → tek worker.

        Tamamlanan ses cache'i YOKTUR (AMP-2 bilinçli olarak açık): her
        çözümlenen istek sonrası kayıt düşer, aynı URL yeniden isterse
        yeniden fetch edilir. GUI thread'inden çağrılır.
        """
        if getattr(self, "_closing", False):
            return False
        infl = self._audio_inflight_get()
        rec = infl.get(url)
        if rec is not None:
            rec["subs"].append((weakref.ref(holder), bg_color))
            return True  # ekstra worker/semaphore slotu yok
        infl[url] = {"subs": [(weakref.ref(holder), bg_color)]}
        started = self._dispatch_media_worker(
            self._audio_fetch_worker, (url,),
            on_saturated=lambda: self._audio_saturated(url, holder,
                                                       bg_color))
        if not started:
            self._audio_inflight_pop(url)  # çifte güvence (saturation pop'lar)
        return started

    def _audio_saturated(self, url, holder, bg_color):
        """2A slotu yok: in-flight düşür, mevcut bağlantı görünümüne geç."""
        self._audio_inflight_pop(url)
        self._saturate_audio_holder(holder, url, bg_color)

    def _resolve_audio_ready(self, url, wav_path, subs):
        """GUI thread: oynatılabilir yolu hayatta kalan abonelere dağıt."""
        for wr, bg_color in subs:
            holder = wr()
            try:
                if holder is None or not holder.winfo_exists():
                    continue  # GC/destroy: diğer aboneleri etkilemez
                self._place_audio(holder, wav_path, bg_color, url)
            except Exception:
                continue

    def _resolve_audio_failed(self, url, subs):
        """GUI thread: başarısız fetch — hayatta kalanlara mevcut fallback."""
        for wr, bg_color in subs:
            holder = wr()
            try:
                if holder is None or not holder.winfo_exists():
                    continue
                self._place_audio_fallback(holder, url, bg_color)
            except Exception:
                continue

    def _resolve_reply(self, reply, frm):
        """Gelen yanıt bilgisini yerel geçmişle zenginleştir."""
        if not reply:
            return None
        rid = str(reply.get("id", "") or "")
        info = {
            "id": rid,
            "sender": reply.get("sender", "") or "",
            "body": _reply_preview(reply.get("body", "")),
        }
        if rid:
            for entry in reversed(self.chats.get(frm, [])):
                if len(entry) > 7 and entry[7] == rid:
                    is_me = bool(entry[2])
                    info["sender"] = "Ben" if is_me else (entry[0] or info["sender"])
                    info["body"] = _reply_preview(entry[1])
                    break
            else:
                # [2M] cache fallback JID-kapsamlıdır: (frm, rid) — başka
                # bir sohbetin önizlemesine asla düşülmez.
                cached = self._reply_map.get((frm, rid))
                if cached:
                    info["sender"] = cached.get("sender", info["sender"]) or info["sender"]
                    info["body"] = _reply_preview(cached.get("body", "")) or info["body"]
        my_names = {"Ben", self.jid.split("@")[0]}
        if frm in self.rooms:
            my_names.add(self.my_nick.get(frm, ""))
        if info["sender"] in my_names:
            info["sender"] = "Ben"
        return info

    def _last_message_row(self, mine: bool):
        """Bu sohbetteki son (benim/gelen) mesaj satırı (ui/chat/identity)."""
        return _identity.find_last_message_row(self._bubble_widgets, mine)

    def _jump_to_message(self, mid):
        """Alıntılanan mesaja kaydır ve kısa süre vurgula."""
        if not mid:
            return
        row = _identity.find_row_by_mid(self._bubble_widgets, mid)
        if row is not None:
            self._scroll_to_row(row)
            self._flash_row(row)
            return
        self._append("↪ Alıntılanan mesaj uygulamada bulunamadı", "sys")

    def _scroll_to_row(self, row):
        """Row'u görünür alana kaydır (ui/chat/identity)."""
        _identity.scroll_to_row(self.chat_canvas, self.msg_frame, row)

    def _flash_row(self, row, pulses: int = 3):
        """Vurgu: metin etiketinin arka planını kısa süre değiştir."""
        lbl = getattr(row, "_body_label", None)
        if lbl is None:
            return
        try:
            normal = lbl.cget("bg")
        except Exception:
            return
        seq = [SEL_BG, normal] * pulses
        def _step(i=0):
            try:
                if not lbl.winfo_exists():
                    return
                if i >= len(seq):
                    lbl.config(bg=normal)
                    return
                lbl.config(bg=seq[i])
                self.root.after(110, _step, i + 1)
            except Exception:
                pass
        _step()

    # ── Mesaj sağ tık menüsü ──────────────────────────────────────────────────
    def _message_context_menu(self, event, row):
        """Mesaj sağ tık menüsü — capability MainWindow, sunum actions.py."""
        body = getattr(row, "_body", "")
        is_me = getattr(row, "_is_me", False)
        mid = getattr(row, "_mid", "")
        sender = getattr(row, "_sender", "")
        retracted = getattr(row, "_retracted", False)
        reply_ref = getattr(row, "_reply_to", None)
        can_send = bool(self.active and self.bot)
        mtype = "groupchat" if self.active in self.rooms else "chat"
        caps = {
            "copy": not retracted,
            "jump": bool(reply_ref) and not retracted,
            "edit": bool(is_me and mid and can_send and not retracted),
            "delete": bool(is_me and mid and can_send and not retracted),
            "reply": bool(mid and can_send and not retracted),
            "forward": bool(body and can_send and not retracted),
            "pin": bool(body and self.active and not retracted),
            "react": bool(mid and can_send and not retracted),
        }
        callbacks = {
            "on_copy": lambda: (self.root.clipboard_clear(),
                                self.root.clipboard_append(body)),
            "on_jump": lambda: self._jump_to_message(
                (reply_ref or {}).get("id", "")),
            "on_edit": lambda: self._edit_message_dialog(mid, body, mtype),
            "on_delete": lambda: self._retract_message(mid, mtype),
            "on_reply": lambda: self._set_reply(mid, body, sender),
            "on_forward": lambda: self._forward_dialog(body, sender),
            "on_pin": lambda: self._pin_message(body, sender),
            "on_react": lambda e: self._toggle_reaction(mid, e),
            "on_more_emoji": lambda: self._show_emoji_picker(mid),
            "on_reactions_details": lambda: self._reaction_details_dialog(mid),
        }
        ai_items = set() if retracted else self._ai_message_items(row)
        for key, _label in _actions_ui.AI_MESSAGE_ITEMS:
            caps[key] = key in ai_items
        callbacks.update(self._ai_message_callbacks(row))
        _actions_ui.show_context_menu(
            self.root, event.x_root, event.y_root, theme=_chat_theme(),
            t=_t, caps=caps,
            mine=self._my_reactions.get(self._reaction_key(mid), set()) if mid else set(),
            has_reactions=bool(mid and self._reactions.get(self._reaction_key(mid))),
            callbacks=callbacks)

    def _apply_local_correction(self, frm, orig_id, new_body):
        """msg_correction/_edit yerel mutasyonu: protokol/network yok."""
        if self.active == frm:
            row = _identity.find_row_by_mid(self._bubble_widgets, orig_id)
            if row is not None:
                _identity.apply_correction_to_row(
                    row, new_body, formatter=self._format_markdown,
                    theme=_chat_theme())
        hist = self.chats.get(frm, [])
        for i, entry in enumerate(hist):
            if len(entry) > 7 and entry[7] == orig_id:
                hist[i] = (*entry[:1], new_body, *entry[2:])
                break
        # [2J.a] Kalıcı mutasyon (jid, mid) kapsamlı — mid çakışması başka
        # sohbetin satırını değiştiremez.
        _db_update_msg_body(frm, orig_id, new_body)

    def _apply_local_retraction(self, frm, retracted_id):
        """msg_retract/_del yerel mutasyonu: protokol/network yok."""
        if self.active == frm:
            row = _identity.find_row_by_mid(self._bubble_widgets,
                                            retracted_id)
            if row is not None:
                _identity.apply_retraction_to_row(
                    row, "🚫 Bu mesaj silindi",
                    formatter=self._format_markdown, theme=_chat_theme(),
                    clear_reactions=lambda r: self._render_reactions(r, {}))
        hist = self.chats.get(frm, [])
        for i, entry in enumerate(hist):
            if len(entry) > 7 and entry[7] == retracted_id:
                hist[i] = (*entry[:1], "🚫 Bu mesaj silindi", *entry[2:])
                break
        reactions_map = getattr(self, "_reactions", None)
        if reactions_map is not None:
            reactions_map.pop((frm, retracted_id), None)
        mine_map = getattr(self, "_my_reactions", None)
        if mine_map is not None:
            mine_map.pop((frm, retracted_id), None)
        _db_clear_reactions_mid(frm, retracted_id)
        # [2J.a] Kalıcı mutasyon (jid, mid) kapsamlı — bkz. _apply_local_correction
        _db_update_msg_body(frm, retracted_id, "🚫 Bu mesaj silindi")
        # [2M] Policy C: tepki durumu (frm, mid) kapsamında silindi; o JID'in
        # aktif satırlarının TAMAMI temiz sunuma yakınsar
        self._refresh_reaction_rows(frm, retracted_id)
        # [2O] Geri çekilen kimliğe işaret eden ters-aliaslar unutulur
        self._mam_alias_forget_identity(frm, retracted_id)

    def _edit_message_dialog(self, mid, old_body, mtype):
        """Mesaj düzenleme diyaloğu (ui/dialogs)."""
        new_body = _ui_chat_actions.ask_edit_message(
            self.root, _t("edit_msg"), _t("new_text"), old_body)
        if new_body and new_body != old_body:
            self.bot.send_correction(self.active, new_body, mid, mtype)
            # Fire-and-forget gönderim; yerel durum iyimser güncellenir
            # (gelen echo aynı mutasyonu idempotent uygular).
            self._apply_local_correction(self.active, mid, new_body)

    def _retract_message(self, mid, mtype):
        """Mesajı geri çek."""
        if messagebox.askyesno(_t("delete_msg"),
                               _t("delete_confirm"),
                               parent=self.root):
            self.bot.retract_message(self.active, mid, mtype)
            # Fire-and-forget gönderim; yerel durum iyimser güncellenir.
            self._apply_local_retraction(self.active, mid)

    # ── Yanıtla / İlet / Sabitle ─────────────────────────────────────────────
    def _set_reply(self, mid, body, sender):
        """Yanıt modunu aç — reply bar'ı göster."""
        if not mid:
            self._append("↩ Bu mesaj yanıtlanamıyor (kimlik yok)", "sys")
            return
        if self.active in self.rooms and sender and sender != "Ben":
            reply_jid = f"{self.active}/{sender}"
        else:
            reply_jid = self.active or ""
        self._composer.set_reply({"mid": mid, "body": body, "sender": sender,
                                  "to": reply_jid})

    def _cancel_reply(self):
        self._composer.cancel_reply()

    def _forward_dialog(self, body, sender):
        """İletme hedefi seçme penceresi (ui/dialogs)."""
        def _do(to, mtype):
            self.bot.forward_message(to, sender, body, mtype)
        _ui_chat_actions.show_forward(
            self.root, self._contacts, self.rooms, body, sender, _do)

    def _pin_message(self, body, sender):
        """Mesajı yerel olarak sabitle."""
        if not self.active:
            return
        pins = self._pinned_msgs.setdefault(self.active, [])
        entry = (body, sender)
        if entry not in pins:
            pins.append(entry)
        self._update_pin_bar()

    def _update_pin_bar(self):
        """Pin bar'ı güncelle."""
        if not self.active:
            return
        pins = self._pinned_msgs.get(self.active, [])
        if pins:
            last = pins[-1]
            preview = last[0][:60] + ("…" if len(last[0]) > 60 else "")
            self._pin_lbl.config(text=f"📌 {last[1]}: {preview}")
            self._pin_bar.pack(side="top", fill="x",
                before=self._pin_bar.master.winfo_children()[-1])
        else:
            self._pin_bar.pack_forget()

    def _show_pinned(self):
        """Sabitlenmiş mesajları listele."""
        pins = self._pinned_msgs.get(self.active, [])
        if not pins:
            return
        pop = tk.Toplevel(self.root)
        pop.title("Sabitlenmiş Mesajlar")
        pop.configure(bg=BG_CARD)
        pop.geometry("380x300")
        pop.transient(self.root)

        for body, sender in pins:
            f = tk.Frame(pop, bg=BG_HOVER, padx=12, pady=8)
            f.pack(fill="x", padx=12, pady=4)
            tk.Label(f, text=sender, fg=ACCENT, bg=BG_HOVER,
                     font=(FONT, 8, "bold")).pack(anchor="w")
            tk.Label(f, text=body[:200], fg=FG, bg=BG_HOVER,
                     font=(FONT, 9), wraplength=340,
                     justify="left").pack(anchor="w")
            # Kaldır butonu
            def remove(b=body, s=sender, fr=f):
                self._pinned_msgs[self.active].remove((b, s))
                fr.destroy()
                self._update_pin_bar()
            tk.Label(f, text="✕", fg=FG_DIM, bg=BG_HOVER,
                     font=(FONT, 8), cursor="hand2").pack(
                         side="right", anchor="n")
            f.winfo_children()[-1].bind("<Button-1>", lambda _, r=remove: r())

    # ── Sürükle-bırak dosya ──────────────────────────────────────────────────
    def _on_dnd_drop(self, event):
        """tkinterdnd2 ile sürüklenen dosyayı gönder."""
        if not self.active or not self.bot:
            return
        files = self.root.tk.splitlist(event.data)
        mtype = "groupchat" if self.active in self.rooms else "chat"
        for f in files:
            if os.path.isfile(f):
                self.bot.send_file(self.active, f, mtype)

    # ── Sohbet başlık menüsü ──────────────────────────────────────────────────
    def _chat_header_menu(self, event=None):
        """⋮ menüsü: yapı `_chat_header_menu_spec`'te (saf veri); burada
        yalnız anahtarlar komutlara eşlenir."""
        if not self.active:
            return
        actions = {
            "profile": lambda: self._profile_card(self.active),
            "search": self._search_messages_dialog,
            "pinned": self._show_pinned,
            "disappearing": self._disappearing_dialog,
            "load_older": self._load_older_mam,
            "schedule": self._schedule_message_dialog,
            "export": self._export_chat,
            "clear_history": self._clear_history_dialog,
            "room_admin": self._room_admin_dialog,
            "location": self._location_dialog,
            "poll": self._poll_dialog,
            "story": self._story_dialog,
            "broadcast": self._broadcast_dialog,
            "omemo_fp": lambda: self._omemo_fingerprint_dialog(self.active),
            "omemo_qr": self._omemo_qr_dialog,
            "blocking": self._blocking_dialog,
            "tab": lambda: self._open_chat_tab(),
            "split": self._split_view_dialog,
            "wallpaper": self._wallpaper_dialog,
            "compact": self._toggle_compact_mode,
            "status_msg": self._status_dialog,
            "backup": self._backup_dialog,
            "shortcuts": self._shortcuts_dialog,
        }

        def new_menu(parent):
            return tk.Menu(parent, tearoff=0, bg=BG_CARD, fg=FG,
                           activebackground=SEL_BG, activeforeground=SEL_FG,
                           font=(FONT, 9))

        def fill(menu, spec):
            for item in spec:
                if item[0] == "sep":
                    menu.add_separator()
                elif item[0] == "ai":
                    menu.add_cascade(label=f"✨ {_t('ai_assistant')}",
                                     menu=self._ai_build_chat_menu(menu))
                elif item[0] == "menu":
                    sub = new_menu(menu)
                    fill(sub, item[2])
                    menu.add_cascade(label=item[1], menu=sub)
                else:
                    menu.add_command(label=item[1], command=actions[item[2]])

        menu = new_menu(self.root)
        fill(menu, _chat_header_menu_spec(
            is_room=self.active in self.rooms, compact=self._compact_mode))
        if event:
            menu.tk_popup(event.x_root, event.y_root)

    # ── AI asistanı (çekirdek xmppcore/ai, pencereler ui/dialogs/ai) ─────────
    # Model/ağ çağrıları daemon worker thread'lerinde koşar; sonuç ve hatalar
    # `_safe_after` ile GUI thread'ine taşınır. Gizlilik kapısı (şifreli
    # sohbet → bulut) her istekten önce GUI thread'inde uygulanır.
    _AI_WORKER_CAP = 2

    def _ai_settings(self) -> dict:
        return _ai.load_settings(_load_config())

    def _ai_is_sensitive(self, jid, entries=(), row=None) -> bool:
        """Şifreli sohbet/mesaj mı? (bulut gizlilik kapısının girdisi)"""
        modes = getattr(self, "_chat_enc_modes", None) or {}
        if jid and modes.get(jid, "none") not in ("", "none"):
            return True
        if row is not None and getattr(row, "_encrypted", False):
            return True
        return any(len(e) > 6 and e[6] for e in entries)

    def _ai_gate(self, settings, sensitive):
        """Dönüş: allow_cloud (bool) ya da iptal için None (GUI thread)."""
        try:
            _ai.ensure_allowed(settings, sensitive=sensitive)
            return False
        except _ai.AIPrivacyError as e:
            ok = messagebox.askyesno(
                "Şifreli Sohbet",
                f"{e}\n\nYalnız bu istek için içerik Claude'a (bulut) "
                "gönderilsin mi?\nHayır derseniz hiçbir şey gönderilmez.",
                parent=self.root)
            return True if ok else None
        except _ai.AIError as e:
            if messagebox.askyesno("AI Asistanı",
                                   f"{e}\n\nAI Ayarları açılsın mı?",
                                   parent=self.root):
                self._ai_settings_dialog()
            return None

    def _ai_submit(self, job, on_done, on_error):
        """job() worker thread'inde; sonuç/hata GUI thread'ine taşınır."""
        sem = getattr(self, "_ai_sem", None)
        if sem is None:
            sem = self._ai_sem = threading.BoundedSemaphore(
                self._AI_WORKER_CAP)

        def _run():
            with sem:
                if getattr(self, "_closing", False):
                    return
                try:
                    result = job()
                except _ai.AICancelled:
                    return          # pencere kapandı: gösterilecek bir şey yok
                except _ai.AIError as e:
                    self._safe_after(0, on_error, e)
                    return
                except Exception as e:
                    _log.error("AI işi başarısız", exc_info=True)
                    self._safe_after(0, on_error,
                                     _ai.AIError(f"Beklenmeyen hata: {e}"))
                    return
            self._safe_after(0, on_done, result)

        threading.Thread(target=_run, daemon=True, name="ai-worker").start()

    def _ai_chat_entries(self, jid):
        entries = list(self.chats.get(jid, []))
        if not entries:
            entries = _db_load_msgs(jid, self._HISTORY_WINDOW_SIZE)
        return entries

    def _ai_chat_label(self, jid) -> str:
        """Kişi adı (rosterdan) ya da JID'in yerel kısmı."""
        name = (getattr(self, "_contacts", None) or {}).get(jid)
        return name or (jid.split("@")[0] if "@" in jid else jid)

    def _ai_open_chat(self, jid):
        """AI penceresindeki bağlantıdan sohbete geç (oda → üye paneli)."""
        if jid in self.rooms:
            self._show_members(jid)
        else:
            self._hide_members()
        self._load_chat(jid)

    def _ai_gate_mixed(self, settings, n_sensitive, n_total):
        """Bir kısmı şifreli içerik (çok sohbetli istek) için gizlilik kapısı.

        Dönüş: ("all", allow_cloud) | ("plain", False) — şifreli içerik
        çıkarılır | None — iptal, hiçbir şey gönderilmez (GUI thread).
        """
        if n_sensitive <= 0 or n_sensitive >= n_total:
            allow = self._ai_gate(settings, n_sensitive > 0)
            return None if allow is None else ("all", allow)
        try:
            _ai.ensure_allowed(settings, sensitive=True)
            return ("all", False)
        except _ai.AIPrivacyError as e:
            ans = messagebox.askyesnocancel(
                "Şifreli Sohbet",
                f"{e}\n\n{n_total} kaynağın {n_sensitive} tanesi şifreli.\n\n"
                "Evet: şifreli içerik de yalnız bu istek için Claude'a "
                "(bulut) gönderilsin.\nHayır: şifreli içerik çıkarılsın, "
                "yalnız kalanı gönderilsin.\nİptal: hiçbir şey "
                "gönderilmesin.", parent=self.root)
            if ans is None:
                return None
            return ("all", True) if ans else ("plain", False)
        except _ai.AIError:
            self._ai_gate(settings, False)      # AI kapalı → ayar önerisi
            return None

    # — Akışlı, takip sorulu AI pencereleri —
    def _ai_open_window(self, title, subtitle, conv, *, on_ask=None,
                        actions=(), ask_hint="Takip sorusu sorun…",
                        ask_ready=False):
        """Sonuç penceresi + iptal olayı. Kapanış süren akışı keser."""
        cancel = threading.Event()
        win = None

        def _ask(question):
            if on_ask is not None:
                on_ask(question)
            else:
                self._ai_followup(win, conv, question, cancel)
        win = _ui_ai.ResultWindow(self.root, title, subtitle, actions,
                                  on_ask=_ask, on_close=cancel.set,
                                  ask_hint=ask_hint, ask_ready=ask_ready)
        return win, cancel

    def _ai_turn(self, win, conv, settings, user_text, allow, cancel, *,
                 images=None, sensitive=None, history_text=None,
                 history_answer=None, as_answer=False, on_done=None):
        """Bir sohbet turunu akışla çalıştır (GUI thread'inde başlatılır).

        Parçalar toplu halde `win.append_text`'e, kesin metin `set_text`
        (ilk tur) ya da `set_answer`'a gider. Tur yalnız başarıyla bitince
        sohbete eklenir. `images`: worker'da görsel yükleyici (takip
        soruları da görseli görür). `history_text` / `history_answer`:
        geçmişe yazılacak kullanıcı metni / yanıt dönüştürücüsü (RAG).
        """
        first = not conv.started and not as_answer
        sens = conv.sensitive if sensitive is None else bool(sensitive)
        history, user = conv.request(user_text,
                                     _ai.conversation_budget(settings))
        sink = _ai.StreamSink(
            lambda chunk: self._safe_after(0, win.append_text, chunk), cancel)

        def job():
            sink.check()
            imgs = images() if images is not None else (conv.images or None)
            text = _ai.chat(settings, conv.system, user, images=imgs,
                            effort=conv.effort, sensitive=sens,
                            allow_cloud=allow, history=history,
                            on_delta=sink, cache=conv.cache)
            sink.finish()
            return text

        def done(text):
            conv.commit(user_text if history_text is None else history_text,
                        history_answer(text) if history_answer else text,
                        sensitive=sens)
            if first:
                win.set_text(text)
            else:
                win.set_answer(text)
            if on_done is not None:
                on_done(text)

        self._ai_submit(job, done, lambda e: win.set_error(str(e)))

    def _ai_followup(self, win, conv, question, cancel, *, images=None):
        """Takip sorusu: aynı içerik üzerinde yeni tur (gizlilik kapısıyla)."""
        settings = self._ai_settings()
        allow = self._ai_gate(settings, conv.sensitive)
        if allow is None:
            return                      # soru kutuda kalır, hiçbir şey gitmez
        win.begin_question(question)
        self._ai_turn(win, conv, settings, question, allow, cancel,
                      images=images)

    def _ai_new_menu(self, parent):
        return tk.Menu(parent, tearoff=0, bg=BG_CARD, fg=FG,
                       activebackground=SEL_BG, activeforeground=SEL_FG,
                       font=(FONT, 9))

    def _ai_fill_chat_items(self, menu, jid):
        """Sohbet AI eylemleri: bağlama özel öğe üstte, gerisi iki alt
        menüde (bu sohbet / tüm sohbetler), ardından asistan ve ayarlar."""
        unread = (getattr(self, "_ai_unread_at_open", None) or {}).get(jid, 0)
        if unread:
            menu.add_command(
                label=f"📝 Okunmamışları özetle ({unread})",
                command=lambda: self._ai_summarize(jid, unread_only=True))
        this = self._ai_new_menu(menu)
        this.add_command(label="📝 Sohbeti özetle",
                         command=lambda: self._ai_summarize(jid))
        this.add_command(label="📅 Görev ve etkinlikleri çıkar",
                         command=lambda: self._ai_extract_actions(jid))
        menu.add_cascade(label="💬 Bu sohbet", menu=this)
        every = self._ai_new_menu(menu)
        every.add_command(label="📥 Neler kaçırdım?",
                          accelerator="Ctrl+Shift+M", command=self._ai_digest)
        every.add_command(label="❓ Yanıt bekleyen sorular",
                          accelerator="Ctrl+Shift+Q",
                          command=self._ai_pending_questions)
        every.add_command(label="📝 Yanıt taslakları",
                          accelerator="Ctrl+Shift+R",
                          command=self._ai_drafts_window)
        every.add_command(label="💬 Geçmişe sor…", accelerator="Ctrl+Shift+H",
                          command=self._ai_ask_history)
        every.add_command(label="🧠 Anlamsal arama…",
                          command=self._ai_semantic_search_dialog)
        menu.add_cascade(label="🗂 Tüm sohbetler", menu=every)
        menu.add_command(label="✨ Asistan…", accelerator="Ctrl+Shift+K",
                         command=self._ai_assistant_open)
        menu.add_separator()
        menu.add_command(label="⚙ AI Ayarları…",
                         command=self._ai_settings_dialog)

    def _ai_build_chat_menu(self, parent):
        """⋮ başlık menüsündeki ✨ alt menüsü."""
        sub = self._ai_new_menu(parent)
        sub.add_command(label="💡 Yanıt öner",
                        command=self._ai_suggest_replies)
        sub.add_separator()
        self._ai_fill_chat_items(sub, self.active)
        return sub

    def _ai_composer_menu(self, event=None):
        """Giriş kutusundaki ✨ butonu: yazma araçları üstte, sohbet
        eylemleri alt menülerde."""
        if not self.active:
            return
        menu = self._ai_new_menu(self.root)
        menu.add_command(label="💡 Yanıt öner",
                         command=self._ai_suggest_replies)
        dictating = (getattr(self, "_recording", False)
                     and getattr(self, "_rec_mode", "voice") == "dictate")
        menu.add_command(label=("⏹ Dikteyi bitir" if dictating
                                else "🎙 Sesle yaz (dikte)"),
                         accelerator="Ctrl+Shift+S", command=self._ai_dictate)
        if self._ai_speaking():
            menu.add_command(label="⏹ Sesli okumayı durdur",
                             command=self._ai_speak_stop)
        rewrite = self._ai_new_menu(menu)
        for mode, (label, _instr) in _ai.REWRITE_MODES.items():
            rewrite.add_command(label=label,
                                command=lambda m=mode: self._ai_rewrite(m))
        menu.add_cascade(label="✍ Taslağı düzenle", menu=rewrite)
        undo = getattr(self, "_ai_undo", None)
        if undo and undo[0] == self.active:
            menu.add_command(label="↶ AI değişikliğini geri al",
                             command=self._ai_undo_rewrite)
        menu.add_separator()
        self._ai_fill_chat_items(menu, self.active)
        if event is not None:
            x, y = event.x_root, event.y_root
        else:
            x, y = self.root.winfo_pointerxy()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    # — Mesaj başına eylemler (çeviri / ses→metin / görsel) —
    def _ai_audio_source(self, row):
        """("url", adres) | ("file", yol) | None"""
        oob = getattr(row, "_oob", "") or ""
        if oob and _AUDIO_URL_RE.match(oob):
            return ("url", oob)
        m = _AUDIO_URL_RE.search(getattr(row, "_body", "") or "")
        if m:
            return ("url", m.group(1))
        path = getattr(row, "_local_path", "") or ""
        if path and re.search(r"\.(wav|ogg|opus|mp3|m4a|flac|aac|webm)$",
                              path, re.IGNORECASE) and os.path.isfile(path):
            return ("file", path)
        return None

    def _ai_image_source(self, row):
        """("url", adres) | ("file", yol) | None"""
        def _raster(url):  # SVG modele verilemez
            return not url.lower().split("?")[0].endswith(".svg")
        oob = getattr(row, "_oob", "") or ""
        if (oob and not _AUDIO_URL_RE.match(oob) and _IMG_URL_RE.match(oob)
                and _raster(oob)):
            return ("url", oob)
        for m in _IMG_URL_RE.finditer(getattr(row, "_body", "") or ""):
            if _raster(m.group(1)):
                return ("url", m.group(1))
        path = getattr(row, "_local_path", "") or ""
        if path and re.search(r"\.(png|jpe?g|gif|webp|bmp)$", path,
                              re.IGNORECASE) and os.path.isfile(path):
            return ("file", path)
        return None

    def _ai_message_items(self, row) -> set:
        """Satır için anlamlı AI eylem anahtarları (actions.AI_MESSAGE_ITEMS)."""
        if row is None or getattr(row, "_retracted", False):
            return set()
        items = set()
        if _ai.message_text(getattr(row, "_body", "") or ""):
            items.update(("ai_translate", "ai_speak"))
        if self._ai_audio_source(row):
            items.add("ai_transcribe")
            if self._ai_row_speech_text(row):
                items.add("ai_speak")       # yazıya dökülmüş ses okunabilir
        if self._ai_image_source(row):
            items.update(("ai_describe", "ai_ask_image"))
        return items

    def _ai_message_callbacks(self, row) -> dict:
        return {
            "on_ai_translate": lambda: self._ai_translate_row(row),
            "on_ai_transcribe": lambda: self._ai_transcribe_row(row),
            "on_ai_describe": lambda: self._ai_describe_row(row),
            "on_ai_ask_image": lambda: self._ai_describe_row(row, ask=True),
            "on_ai_speak": lambda: self._ai_speak_row(row),
        }

    def _ai_message_menu(self, row, anchor):
        """Hover ✨ butonu menüsü (ui/chat/actions)."""
        _actions_ui.show_ai_message_menu(
            self.root, anchor, theme=_chat_theme(),
            items=self._ai_message_items(row),
            callbacks=self._ai_message_callbacks(row))

    def _ai_translate_row(self, row):
        text = _ai.message_text(getattr(row, "_body", "") or "")
        if not text:
            return
        settings = self._ai_settings()
        sensitive = self._ai_is_sensitive(self.active, row=row)
        allow = self._ai_gate(settings, sensitive)
        if allow is None:
            return
        lang = settings["target_language"]
        system, user = _ai.translate_request(text, lang)
        conv = _ai.Conversation(_ai.with_followups(system, lang),
                                effort="low", sensitive=sensitive)
        win, cancel = self._ai_open_window(
            "🌐 Çeviri", _ai.provider_label(settings), conv,
            ask_hint="Örn: Bu ifade ne anlama geliyor?")
        self._ai_turn(win, conv, settings, user, allow, cancel)

    @staticmethod
    def _ai_cache_key(kind, model, source) -> str:
        import hashlib
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        return f"{kind}:{model}:{digest}"

    def _ai_transcribe_row(self, row):
        src = self._ai_audio_source(row)
        if not src:
            return
        settings = self._ai_settings()
        # Ses→metin her zaman yereldir; yalnız AI tamamen kapalıysa durur.
        if settings["provider"] == _ai.PROVIDER_OFF:
            self._ai_gate(settings, False)
            return
        model = settings["whisper_model"]
        win = _ui_ai.ResultWindow(self.root, "🎙 Ses kaydının metni",
                                  f"🖥 Yerel (faster-whisper) · {model}")
        win.set_busy("Yazıya dökülüyor… (ilk kullanımda model indirilir)")

        def done(text):
            win.set_text(text)
            self._ai_stt_done(src[1], text)     # balonda da göster

        self._ai_submit(self._ai_stt_job(src, model, self.active or ""),
                        done, lambda e: win.set_error(str(e)))

    def _ai_stt_job(self, src, model, jid):
        """Worker'da koşacak döküm işi: önbellek → (indir) → whisper."""
        kind, ref = src
        key = self._ai_cache_key("stt", model, ref)

        def job():
            cached = _db_ai_cache_get(key)
            if cached:
                return cached
            if kind == "file":
                text = _ai.transcribe_file(ref, model)
            else:
                raw = _ai.fetch_url(ref, _NET_AUDIO_MAX)
                ext = os.path.splitext(urllib.parse.urlparse(ref).path)[1]
                tmp = tempfile.NamedTemporaryFile(suffix=ext or ".audio",
                                                  delete=False)
                try:
                    tmp.write(raw)
                    tmp.close()
                    if not self._remember_temp(tmp.name):
                        raise _ai.AIError("Uygulama kapanıyor.")
                    text = _ai.transcribe_file(tmp.name, model)
                finally:
                    try:
                        os.unlink(tmp.name)
                    except OSError:
                        pass
                    self._forget_temp(tmp.name)
            _db_ai_cache_set(key, jid, text)
            return text
        return job

    # — Ses→metin: balon içi döküm ve otomatik kuyruk —
    # Otomatik mod (AI Ayarları → "Gelen sesli mesajları otomatik yazıya
    # dök") gelen sesleri TEK bir worker'da, en yeni önce yazıya döker;
    # genel AI semaforunu (_AI_WORKER_CAP) meşgul etmez. Sonuç ai_cache'e
    # yazılır, bellekte ref → metin tutulur ve görünen balona eklenir.
    _AI_STT_QUEUE_CAP = 50
    _AI_STT_MEMO_CAP = 500

    def _ai_refresh_flags(self):
        """Sık okunan AI ayarlarını önbelleğe al (açılış ve kayıt sonrası)."""
        s = self._ai_settings()
        self._ai_auto_stt = (s["auto_transcribe"]
                             and s["provider"] != _ai.PROVIDER_OFF)
        self._ai_stt_model = s["whisper_model"]
        # Satır içi öneri her tuş duraksamasında taslağı modele verir:
        # yalnız yerel (Ollama) sağlayıcıyla çalışır, buluta gitmez.
        self._ai_inline_on = (s["inline_complete"]
                              and s["provider"] == _ai.PROVIDER_OLLAMA)
        self._ai_away_on = (s["away_drafts"]
                            and s["provider"] != _ai.PROVIDER_OFF)
        if not self._ai_inline_on:
            self._ai_complete_hide()

    def _ai_inline_transcript(self, row):
        """_append kancası: bilinen dökümü balona koy; otomatik modda gelen
        sesli mesajı kuyruğa ekle (GUI thread)."""
        src = self._ai_audio_source(row)
        if not src:
            return
        row._stt_ref = src[1]
        text = (getattr(self, "_ai_stt_texts", None) or {}).get(src[1])
        if text:
            self._ai_show_transcript(row, text)
        elif (getattr(self, "_ai_auto_stt", False)
              and not getattr(row, "_is_me", False)):
            self._ai_stt_enqueue(src)

    def _ai_show_transcript(self, row, text):
        """Dökümü satırın balonuna yaz; varsa güncelle (GUI thread)."""
        try:
            if not row.winfo_exists():
                return
        except Exception:
            return
        lbl = getattr(row, "_stt_label", None)
        if lbl is not None:
            _audio_ui.set_transcript(lbl, text)
            return
        bubble = getattr(row, "_bubble", None)
        if bubble is None:
            return
        lbl = _audio_ui.transcript_note(
            bubble, _chat_theme(), bubble.cget("bg"), text,
            is_me=getattr(row, "_is_me", False),
            before=getattr(row, "_meta_frame", None))
        row._stt_label = lbl
        self._bind_message_menu(lbl, row)
        self._bind_scroll_widget(lbl)

    def _ai_stt_done(self, ref, text):
        """Döküm hazır (GUI thread): belleğe al, görünen satırlara yaz."""
        memo = getattr(self, "_ai_stt_texts", None)
        if memo is None:
            memo = self._ai_stt_texts = OrderedDict()
        memo[ref] = text
        memo.move_to_end(ref)
        while len(memo) > self._AI_STT_MEMO_CAP:
            memo.popitem(last=False)
        for row in list(getattr(self, "_bubble_widgets", ())):
            if getattr(row, "_stt_ref", None) == ref:
                self._ai_show_transcript(row, text)

    def _ai_stt_state(self):
        st = getattr(self, "_ai_stt", None)
        if st is None:
            st = self._ai_stt = {"lock": threading.Lock(), "queue": deque(),
                                 "seen": set(), "running": False}
        return st

    def _ai_stt_enqueue(self, src):
        """Kaynağı otomatik döküm kuyruğuna ekle (oturumda tek sefer)."""
        if getattr(self, "_closing", False):
            return
        st = self._ai_stt_state()
        item = (src, getattr(self, "_ai_stt_model", None)
                or _ai.DEFAULTS["whisper_model"], self.active or "")
        with st["lock"]:
            if src[1] in st["seen"]:
                return
            st["seen"].add(src[1])
            st["queue"].append(item)
            while len(st["queue"]) > self._AI_STT_QUEUE_CAP:
                dropped = st["queue"].popleft()     # en eski düşer
                st["seen"].discard(dropped[0][1])
            if st["running"]:
                return
            st["running"] = True
        threading.Thread(target=self._ai_stt_worker, daemon=True,
                         name="ai-stt").start()

    def _ai_stt_worker(self):
        """Otomatik döküm worker'ı: Tk'ya dokunmaz, sonuç _safe_after ile."""
        st = self._ai_stt_state()
        while True:
            with st["lock"]:
                if not st["queue"] or getattr(self, "_closing", False):
                    st["running"] = False
                    return
                src, model, jid = st["queue"].pop()     # en yeni önce
            try:
                text = self._ai_stt_job(src, model, jid)()
            except _ai.AISetupError as e:
                with st["lock"]:
                    st["queue"].clear()
                    st["running"] = False
                self._safe_after(0, self._ai_stt_disable, str(e))
                return
            except Exception:
                # Bu kaynak oturumda yeniden denenmez ("seen" içinde kalır).
                _log.warning("Otomatik ses→metin başarısız", exc_info=True)
                continue
            self._safe_after(0, self._ai_stt_done, src[1], text)

    def _ai_stt_disable(self, message):
        """Yerel bileşen eksik: otomatik modu bu oturum için kapat."""
        self._ai_auto_stt = False
        _log.warning("Otomatik ses→metin durduruldu: %s", message)
        self._show_toast("🎙 Otomatik ses→metin durdu",
                         "faster-whisper/model yok — AI Ayarları → Test Et")

    def _ai_load_image(self, src) -> bytes:
        kind, ref = src
        if kind == "url":
            return _ai.fetch_url(ref, _NET_IMG_FULL_MAX)
        if os.path.getsize(ref) > _NET_IMG_FULL_MAX:
            raise _ai.AIError("Görsel çok büyük.")
        with open(ref, "rb") as f:
            return f.read()

    def _ai_describe_row(self, row, ask=False):
        src = self._ai_image_source(row)
        if not src:
            return
        question = None
        if ask:
            question = simpledialog.askstring(
                "Görsele Soru Sor", "Görsel hakkında ne sormak istiyorsunuz?",
                parent=self.root)
            if not question or not question.strip():
                return
            question = question.strip()
        settings = self._ai_settings()
        sensitive = self._ai_is_sensitive(self.active, row=row)
        allow = self._ai_gate(settings, sensitive)
        if allow is None:
            return
        provider_model = (settings["claude_model"]
                          if settings["provider"] == _ai.PROVIDER_CLAUDE
                          else settings["ollama_vision_model"])
        key = None if question else self._ai_cache_key(
            "img", provider_model, src[1])
        jid = self.active or ""
        title = f"❓ {question}" if question else "🖼 Görsel açıklaması"
        lang = settings["target_language"]
        system, user = _ai.image_request(lang, question)
        conv = _ai.Conversation(_ai.with_followups(system, lang),
                                effort="medium", sensitive=sensitive)
        prepared = []

        def load_images():
            # Worker'da bir kez indirilip hazırlanır; takip soruları da
            # görseli görür (önbellekten gelen açıklamada da).
            if not prepared:
                prepared.append(_ai.prepare_image(self._ai_load_image(src)))
            return list(prepared)

        win, cancel = self._ai_open_window(
            title[:80], _ai.provider_label(settings, vision=True), conv,
            on_ask=lambda q: self._ai_followup(win, conv, q, cancel,
                                               images=load_images),
            ask_hint="Örn: Arka planda ne yazıyor?")
        sink = _ai.StreamSink(
            lambda chunk: self._safe_after(0, win.append_text, chunk), cancel)

        def job():
            if key:
                cached = _db_ai_cache_get(key)
                if cached:
                    return cached
            text = _ai.chat(settings, conv.system, user,
                            images=load_images(), effort=conv.effort,
                            sensitive=sensitive, allow_cloud=allow,
                            on_delta=sink, cache=conv.cache)
            sink.finish()
            if key:
                _db_ai_cache_set(key, jid, text)
            return text

        def done(text):
            conv.commit(user, text, sensitive=sensitive)
            win.set_text(text)

        self._ai_submit(job, done, lambda e: win.set_error(str(e)))

    # — Sohbet özeti ve yanıt önerisi —
    def _ai_summarize(self, jid=None, unread_only=False):
        jid = jid or self.active
        if not jid:
            return
        settings = self._ai_settings()
        entries = self._ai_chat_entries(jid)
        unread = 0
        if unread_only:
            unread = (getattr(self, "_ai_unread_at_open", None)
                      or {}).get(jid, 0)
            # Okunmamışlar + öncesinden kısa bağlam
            entries = entries[-(unread + 15):] if unread else entries
        sensitive = self._ai_is_sensitive(jid, entries)
        allow = self._ai_gate(settings, sensitive)
        if allow is None:
            return
        transcript, count = _ai.build_transcript(
            entries, max_chars=_ai.transcript_budget(settings))
        if not count:
            messagebox.showinfo("Özet", "Özetlenecek mesaj yok.",
                                parent=self.root)
            return
        short = jid.split("@")[0]
        title = (f"📝 {short} — okunmamış {unread} mesajın özeti" if unread
                 else f"📝 {short} — sohbet özeti")
        lang = settings["target_language"]
        system, user = _ai.summary_request(transcript, lang, unread)
        conv = _ai.Conversation(_ai.with_followups(system, lang),
                                effort="medium", sensitive=sensitive)
        win, cancel = self._ai_open_window(
            title, f"{_ai.provider_label(settings)} · son {count} mesaj", conv,
            ask_hint="Örn: Benden ne isteniyor? Saat kaçta buluşuyoruz?")
        self._ai_turn(win, conv, settings, user, allow, cancel)

    # — "Neler kaçırdım?" (tüm okunmamış sohbetler) —
    def _ai_digest(self):
        counts = {j: n for j, n in
                  (getattr(self, "_unread_counts", None) or {}).items()
                  if n > 0}
        if not counts:
            messagebox.showinfo("Neler kaçırdım?",
                                "Okunmamış mesaj yok — her şey okunmuş. 🎉",
                                parent=self.root)
            return
        settings = self._ai_settings()
        chats = []          # (jid, etiket, girişler, okunmamış, şifreli mi)
        for jid, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            part = self._ai_chat_entries(jid)[-(n + _ai.DIGEST_CONTEXT):]
            chats.append((jid, self._ai_chat_label(jid), part, n,
                          self._ai_is_sensitive(jid, part)))
        gate = self._ai_gate_mixed(settings, sum(1 for c in chats if c[4]),
                                   len(chats))
        if gate is None:
            return
        mode, allow = gate
        if mode == "plain":
            chats = [c for c in chats if not c[4]]
        digest, included, omitted = _ai.build_digest(
            [(label, part, n) for _j, label, part, n, _s in chats],
            _ai.transcript_budget(settings))
        if not included:
            messagebox.showinfo("Neler kaçırdım?",
                                "Okunmamışlar arasında özetlenecek metin "
                                "mesajı yok.", parent=self.root)
            return
        shown = [chats[i] for i in included]
        lang = settings["target_language"]
        system, user = _ai.digest_request(
            digest, lang, [chats[i][1] for i in omitted])
        conv = _ai.Conversation(_ai.with_followups(system, lang),
                                effort="medium",
                                sensitive=any(c[4] for c in shown))
        total = sum(c[3] for c in shown)
        win, cancel = self._ai_open_window(
            "📥 Neler kaçırdım?",
            f"{_ai.provider_label(settings)} · {len(shown)} sohbet, "
            f"{total} okunmamış mesaj", conv,
            ask_hint="Örn: Bana kim soru sordu?")
        win.set_sources([(f"💬 {c[1]} ({c[3]})", c[0]) for c in shown],
                        self._ai_open_chat, title="Sohbete git")
        self._ai_turn(win, conv, settings, user, allow, cancel)

    # — Asistan (ajan): doğal dil komutu → onaylı istemci eylemi —
    # Model yalnız kullanıcının yazdığı adı döndürür; hedef YEREL çözülür
    # (kişi listesi modele gitmez). Gönderme/katılma/durum/hatırlatıcı her
    # zaman kartla onaylanır; gönderim normal giriş kutusu yolundan geçer
    # (hassas veri uyarısı, şifreleme modu, kayıt — hepsi aynen).
    _AGENT_EXAMPLES = (
        "Ali'ye yarın 10'da toplantı olduğunu yaz",
        "Yarın 09:00'da faturayı ödemeyi hatırlat",
        "Neler kaçırdım?",
        "Ayşe ile sohbeti özetle",
        "Durumumu meşgul yap",
    )
    _AGENT_LOG_CAP = 200

    def _ai_assistant_open(self, _event=None):
        win = getattr(self, "_ai_assistant_win", None)
        if win is not None and win.alive():
            win.focus()
            return "break"
        settings = self._ai_settings()
        win = _ui_ai.AssistantWindow(
            self.root, self._ai_assistant_subtitle(settings),
            self._ai_agent_submit, on_clear=self._ai_assistant_clear,
            on_speak=self._ai_speak_text, examples=self._AGENT_EXAMPLES)
        self._ai_assistant_win = win
        for role, text in getattr(self, "_ai_agent_log", ()):
            (win.add_user if role == "user" else win.add_reply)(text)
        return "break"

    @staticmethod
    def _ai_assistant_subtitle(settings) -> str:
        return (f"{_ai.provider_label(settings)} · kişi listeniz modele "
                "gönderilmez; gönderme ve değişiklikler onayınızla yapılır")

    def _ai_assistant_clear(self):
        self._ai_agent_log = []
        self._ai_agent_conv = None
        win = getattr(self, "_ai_assistant_win", None)
        if win is not None:
            win.clear()

    def _ai_agent_log_add(self, role, text):
        log = getattr(self, "_ai_agent_log", None)
        if log is None:
            log = self._ai_agent_log = []
        log.append((role, text))
        del log[:-self._AGENT_LOG_CAP]

    def _ai_agent_submit(self, text):
        win = self._ai_assistant_win
        win.add_user(text)
        self._ai_agent_log_add("user", text)
        settings = self._ai_settings()
        try:
            _ai.ensure_allowed(settings, sensitive=False)
        except _ai.AIError as e:
            win.add_note(f"⚠ {e}", error=True)
            return
        win.set_subtitle(self._ai_assistant_subtitle(settings))
        conv = getattr(self, "_ai_agent_conv", None)
        if conv is None:
            conv = self._ai_agent_conv = _ai.Conversation(
                "", effort="low", pin_first=False, cache=False)
        conv.system = _agent.system_prompt(datetime.now(),
                                           settings["target_language"])
        history, user = conv.request(_agent.user_prompt(text),
                                     _ai.conversation_budget(settings))
        win.set_busy("Düşünüyor…")

        def job():
            return _agent.parse_plan(_ai.chat(
                settings, conv.system, user, history=history, effort="low",
                schema=_agent.PLAN_SCHEMA))

        def done(plan):
            win.set_busy(None)
            if conv is not getattr(self, "_ai_agent_conv", None):
                return                  # bu arada "Temizle" denildi
            conv.commit(user, json.dumps(plan, ensure_ascii=False))
            cur = getattr(self, "_ai_assistant_win", None)
            if cur is not None and cur.alive():
                self._ai_agent_handle(cur, plan)
            elif plan["reply"]:         # pencere kapalı: eylem YOK, yalnız
                self._ai_agent_log_add("assistant", plan["reply"])  # kayıt

        def fail(e):
            win.set_busy(None)
            win.add_note(f"⚠ {e}", error=True)

        self._ai_submit(job, done, fail)

    def _ai_agent_reply(self, win, text):
        win.add_reply(text)
        self._ai_agent_log_add("assistant", text)

    def _ai_agent_targets(self):
        """Çözümleme adayları: [(jid, etiket)] — kişiler + odalar."""
        out = dict((getattr(self, "_contacts", None) or {}).items())
        rooms = set(getattr(self, "rooms", None) or ()) | set(
            _load_config().get("rooms") or {})
        for room in rooms:
            out.setdefault(room, room.split("@")[0])
        return [(jid, name or jid) for jid, name in out.items()]

    def _ai_agent_handle(self, win, plan):
        problem = _agent.check_plan(plan, datetime.now())
        if plan["action"] == "answer" or problem:
            self._ai_agent_reply(win, (plan["reply"] if plan["action"] ==
                                       "answer" else problem) or problem
                                 or "…")
            return
        if plan["reply"]:
            self._ai_agent_reply(win, plan["reply"])
        action = plan["action"]
        if action == "join_room":
            # Bilinen (katılınan/kayıtlı) odalardan biri tek eşleşirse o;
            # yoksa yazılan ad/adres kendi oda sunucumuza göre normalize.
            rooms = set(getattr(self, "rooms", None) or ()) | set(
                _load_config().get("rooms") or {})
            hits = _agent.resolve_target(
                plan["target"], [(r, r.split("@")[0]) for r in rooms])
            self._ai_agent_run(win, plan, hits[0][0] if len(hits) == 1
                               else plan["target"])
            return
        if action not in _agent.TARGET_ACTIONS and not (
                action == "remind" and plan["target"]):
            self._ai_agent_run(win, plan, "")
            return
        hits = _agent.resolve_target(plan["target"], self._ai_agent_targets())
        if action == "remind" and len(hits) != 1:
            self._ai_agent_run(win, plan, "")   # kişi isteğe bağlı
            return
        if not hits:
            win.add_note(f"“{plan['target']}” adında bir kişi ya da oda "
                         "bulunamadı.", error=True)
            return
        if len(hits) > 1:
            win.add_choices(
                f"“{plan['target']}” birden çok kişiyle eşleşti",
                [(f"{label} ({jid})", jid) for jid, label in hits],
                lambda jid: self._ai_agent_run(win, plan, jid))
            return
        self._ai_agent_run(win, plan, hits[0][0])

    def _ai_agent_run(self, win, plan, jid):
        """Onaylı eylemde kart açar, diğerlerini hemen yürütür."""
        if plan["action"] not in _agent.CONFIRM_ACTIONS:
            msg, ok = self._ai_agent_execute(plan, jid)
            win.add_note(msg, error=not ok)
            return (msg, ok)
        label = self._ai_chat_label(jid) if jid else ""
        if plan["action"] == "join_room":
            try:
                jid = _normalize_room_jid(jid, self._muc_service())
            except ValueError as e:
                win.add_note(f"⚠ {e}", error=True)
                return (f"⚠ {e}", False)
            label = ""
        elif plan["action"] == "set_status":
            label = self._ai_status_option(plan["status"])[0]
        title, detail = _agent.describe(plan, label, jid)
        win.add_card(title, detail, [
            ("✓ Onayla", lambda: self._ai_agent_execute(plan, jid)),
            ("✗ İptal", lambda: ("İptal edildi.", False))])
        return ("✓ Seçildi", True)

    def _ai_agent_execute(self, plan, jid):
        """Eylemi mevcut yollarla yürüt → (mesaj, başarılı mı)."""
        action = plan["action"]
        label = self._ai_chat_label(jid) if jid else ""
        if action == "open_chat":
            self._ai_open_chat(jid)
            return (f"✓ {label} sohbeti açıldı.", True)
        if action == "draft_message":
            self._ai_offer_text(jid, plan["text"])
            return ("✓ Taslak giriş kutusuna kondu — kontrol edip siz "
                    "gönderin.", True)
        if action == "send_message":
            return self._ai_agent_send(jid, plan["text"])
        if action == "remind":
            ok, msg = self._ai_add_reminders([_agent.reminder_item(plan)],
                                             jid)
            return (msg, ok)
        if action == "join_room":
            if not self.bot:
                return ("⚠ Sunucuya bağlı değilsiniz.", False)
            nick = self.jid.split("@")[0]
            room = self._join_room_normalized(jid, nick)
            if not room:
                return ("⚠ Oda adresi geçersiz.", False)
            return (f"✓ {room} odasına katılma isteği gönderildi.", True)
        if action == "set_status":
            if not self.bot:
                return ("⚠ Sunucuya bağlı değilsiniz.", False)
            label, color = self._ai_status_option(plan["status"])
            self._set_status(label, plan["status"], color)
            return (f"✓ Durum: {label}", True)
        openers = {
            "summarize_chat": lambda: self._ai_summarize(jid),
            "extract_tasks": lambda: self._ai_extract_actions(jid),
            "missed": self._ai_digest,
            "pending_questions": self._ai_pending_questions,
            "ask_history": lambda: self._ai_ask_history(plan["text"]),
        }
        if action in openers:
            openers[action]()
            return ("✓ İlgili pencere açıldı.", True)
        return ("⚠ Bu eylem desteklenmiyor.", False)

    @staticmethod
    def _ai_status_option(show):
        """STATUS_OPTIONS etiketi + durum menüsündeki renk."""
        label = next((lbl for lbl, s in STATUS_OPTIONS if s == show), show)
        color = {"online": ONLINE, "away": AWAY}.get(show, RED)
        return label, color

    def _ai_agent_send(self, jid, text):
        """Normal gönderim yolu: sohbeti aç, metni koy, _send_message.

        Kullanıcının o anki sohbeti ve yarım taslağı her durumda geri
        yüklenir; hassas veri uyarısında vazgeçilirse hiçbir şey gitmez.
        """
        if not self.bot:
            return ("⚠ Sunucuya bağlı değilsiniz.", False)
        if text.startswith("/") and not text.startswith("//"):
            return ("⚠ “/” ile başlayan metin komut sayılır; gönderilmedi.",
                    False)
        prev_active = self.active
        prev_text = self._ai_composer_text()
        self._ai_offer_text(jid, text)
        self._send_message()
        sent = not self._ai_composer_text().strip()
        if prev_active and prev_active != jid:
            self._ai_open_chat(prev_active)
        if prev_text:
            self._ai_set_composer_text(prev_text)
        elif not sent:
            self._composer.clear_text()     # gönderilmeyen ajan metni kalmaz
        label = self._ai_chat_label(jid)
        if sent:
            return (f"✓ {label} kişisine gönderildi.", True)
        return ("Gönderilmedi (uyarıda vazgeçildi).", False)

    # — Yanıt taslakları: uzaktayken hazırlananlar + harici (MCP/REST) —
    # Hiçbir taslak kendiliğinden gönderilmez: "Kullan" metni giriş
    # kutusuna koyar. Uzaktayken gelen her 1:1 mesaj sohbet başına
    # gecikmeli (art arda mesajlar tek istek) bir taslak üretimi tetikler.
    # Şifreli sohbet + bulut + izin yok → "onay bekliyor"; arka planda
    # asla soru sorulmaz, içerik izinsiz buluta gitmez.
    _AWAY_SHOWS = ("away", "xa")
    _AWAY_DRAFT_DELAY_MS = 15000
    _DRAFTS_MAX = 10
    _DRAFT_EXTERNAL_MAX = 5

    def _ai_is_away(self) -> bool:
        return (bool(getattr(self, "_is_idle", False))
                or getattr(self, "_my_show", "online") in self._AWAY_SHOWS)

    def _ai_drafts_get(self):
        drafts = getattr(self, "_ai_drafts", None)
        if drafts is None:
            drafts = self._ai_drafts = OrderedDict()
        return drafts

    def _ai_draft_entry(self, jid):
        drafts = self._ai_drafts_get()
        entry = drafts.get(jid)
        if entry is None:
            if len(drafts) >= self._DRAFTS_MAX:
                return None
            entry = drafts[jid] = {"jid": jid, "options": [], "external": [],
                                   "external_source": "", "away": False,
                                   "count": 0, "last": "", "state": "idle",
                                   "error": "", "gen": 0}
        return entry

    def _ai_away_note_message(self, jid):
        """Gelen 1:1 mesaj (GUI thread): uzaktaysak taslak üretimini planla."""
        if (not getattr(self, "_ai_away_on", False) or not self._ai_is_away()
                or jid in (getattr(self, "rooms", None) or ())):
            return
        entry = self._ai_draft_entry(jid)
        if entry is None:
            return
        entry["away"] = True
        entry["count"] += 1
        entry["state"] = "pending"
        timers = getattr(self, "_ai_draft_timers", None)
        if timers is None:
            timers = self._ai_draft_timers = {}
        self._after_cancel(timers.pop(jid, None))
        timers[jid] = self._after(self._AWAY_DRAFT_DELAY_MS,
                                  self._ai_draft_generate, jid)
        self._ai_drafts_refresh()

    def _ai_draft_generate(self, jid, allow=False):
        (getattr(self, "_ai_draft_timers", None) or {}).pop(jid, None)
        entry = self._ai_drafts_get().get(jid)
        if entry is None:
            return
        settings = self._ai_settings()
        entries = self._ai_chat_entries(jid)[-40:]
        sensitive = self._ai_is_sensitive(jid, entries)
        last = next((e for e in reversed(entries)
                     if not e[2] and len(e) > 4 and e[4] != "sys"), None)
        if last is not None:
            entry["last"] = _questions.snippet(last[1], 160)
        try:
            _ai.ensure_allowed(settings, sensitive=sensitive,
                               allow_cloud=allow)
        except _ai.AIPrivacyError:
            entry["state"] = "blocked"
            self._ai_drafts_refresh()
            return
        except _ai.AIError as e:
            entry.update(state="error", error=str(e))
            self._ai_drafts_refresh()
            return
        transcript, count = _ai.build_transcript(
            entries, max_chars=min(8000, _ai.transcript_budget(settings)))
        if not count:
            entry.update(state="error", error="Sohbette metin mesajı yok.")
            self._ai_drafts_refresh()
            return
        system, user = _ai.suggest_request(transcript)
        entry["gen"] += 1
        gen = entry["gen"]
        entry["state"] = "pending"
        self._ai_drafts_refresh()

        def current():
            return (self._ai_drafts_get().get(jid) is entry
                    and entry["gen"] == gen)

        def done(options):
            if not current():
                return
            if options:
                entry.update(options=options, state="ready", error="")
            else:
                entry.update(state="error", error="Model öneri üretemedi.")
            self._ai_drafts_refresh()

        def fail(e):
            if current():
                entry.update(state="error", error=str(e))
                self._ai_drafts_refresh()

        self._ai_submit(lambda: _ai.parse_suggestions(_ai.chat(
            settings, system, user, effort="low", sensitive=sensitive,
            allow_cloud=allow)), done, fail)

    def _ai_draft_consent(self, item):
        """Şifreli sohbet: kullanıcı onayıyla (yalnız bu istek) üret."""
        settings = self._ai_settings()
        allow = self._ai_gate(settings, True)
        if allow is not None:
            self._ai_draft_generate(item["jid"], allow=allow)

    def _ai_add_draft(self, jid, texts, source):
        """Harici taslak (MCP/REST): kutuya ekle, kullanıcıya haber ver."""
        texts = [t.strip() for t in texts if isinstance(t, str) and t.strip()]
        if not texts or "@" not in (jid or ""):
            return
        entry = self._ai_draft_entry(jid)
        if entry is None:
            self._show_toast("📝 Taslak alınamadı",
                             "Taslak kutusu dolu — önce birkaçını kaldırın")
            return
        entry["external"] = (entry["external"] + texts)[
            -self._DRAFT_EXTERNAL_MAX:]
        entry["external_source"] = source
        self._ai_drafts_refresh()
        self._show_toast("📝 Yeni yanıt taslağı",
                         f"{source}: {self._ai_chat_label(jid)}"
                         " — Ctrl+Shift+R")

    def _ai_drafts_forget(self, jid):
        drafts = getattr(self, "_ai_drafts", None)
        if drafts and drafts.pop(jid, None) is not None:
            self._after_cancel(
                (getattr(self, "_ai_draft_timers", None) or {}).pop(jid, None))
            self._ai_drafts_refresh()

    def _ai_away_returned(self):
        """Uzaktan dönüş: hazır/hazırlanan taslak varsa bir kez haber ver."""
        drafts = getattr(self, "_ai_drafts", None) or {}
        n = sum(1 for e in drafts.values() if e["away"])
        if n and not getattr(self, "_closing", False):
            self._show_toast("📝 Uzaktayken gelenler",
                             f"{n} sohbet için yanıt taslağı — Ctrl+Shift+R")

    def _ai_drafts_view(self):
        out = []
        for e in self._ai_drafts_get().values():
            sources = [e["external_source"] if e["external"] else "",
                       "🌙 Uzaktayken" if e["away"] else ""]
            out.append({
                "jid": e["jid"], "label": self._ai_chat_label(e["jid"]),
                "source": " · ".join(s for s in sources if s),
                "count": e["count"], "last": e["last"],
                "options": list(e["external"]) + list(e["options"]),
                "state": e["state"] if e["away"] else "ready",
                "error": e["error"], "regen": e["away"]})
        return out

    def _ai_drafts_window(self):
        win = getattr(self, "_ai_drafts_win", None)
        if win is None or not win.alive():
            win = self._ai_drafts_win = _ui_ai.DraftsWindow(
                self.root,
                on_use=lambda e, t: self._ai_offer_text(e["jid"], t),
                on_regen=lambda e: self._ai_draft_generate(e["jid"]),
                on_consent=self._ai_draft_consent,
                on_dismiss=lambda e: self._ai_drafts_forget(e["jid"]))
        win.set_entries(self._ai_drafts_view())

    def _ai_drafts_refresh(self):
        win = getattr(self, "_ai_drafts_win", None)
        if win is not None and win.alive():
            win.set_entries(self._ai_drafts_view())

    # — Satır içi öneri (yazarken; yalnız yerel model) —
    # Sözcük bitip (boşluk) yazım _AI_COMPLETE_DELAY_MS duraksayınca kısa
    # bir devam istenir; geç gelen/eski yanıtlar sıra numarası ve taslak
    # eşitliğiyle atılır. Tab kabul eder, Esc ya da yazmaya devam gizler.
    _AI_COMPLETE_DELAY_MS = 650
    _AI_COMPLETE_IGNORED_KEYS = frozenset((
        "Tab", "ISO_Left_Tab", "Escape", "Return", "KP_Enter", "Shift_L",
        "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Super_L",
        "Super_R", "Caps_Lock"))

    def _ai_complete_setup(self):
        """Öneri çubuğunu giriş satırına kur (panel yeniden kurulursa yeni
        giriş widget'ına yeniden bağlanır)."""
        entry = getattr(self, "_msg_entry", None)
        parent = getattr(getattr(self, "_inp_border", None), "master", None)
        if entry is None or parent is None:
            return
        if getattr(self, "_suggest_entry", None) is entry:
            return
        self._suggest_entry = entry
        self._suggest_bar = _SuggestionBar(
            parent, _chat_theme(), on_accept=self._ai_complete_accept)
        entry.bind("<KeyRelease>", self._ai_complete_on_key, add="+")
        entry.bind("<Tab>", self._ai_complete_tab)
        entry.bind("<Escape>", self._ai_complete_escape)

    def _ai_complete_hide(self):
        bar = getattr(self, "_suggest_bar", None)
        if bar is not None:
            bar.hide()

    def _ai_complete_cancel(self):
        self._after_cancel(getattr(self, "_ai_complete_after", None))
        self._ai_complete_after = None

    def _ai_complete_on_key(self, event=None):
        if getattr(event, "keysym", "") in ("Tab", "ISO_Left_Tab"):
            return                      # kabul/odak; öneri zaten işlendi
        self._ai_complete_hide()
        self._ai_complete_cancel()
        if (getattr(event, "keysym", "") in self._AI_COMPLETE_IGNORED_KEYS
                or not getattr(self, "_ai_inline_on", False)
                or not self.active):
            return
        draft = self._ai_composer_text()
        if (len(draft.strip()) < 3 or not draft.endswith(" ")
                or draft.startswith("/")):
            return
        try:                            # yalnız imleç sondayken
            if self._msg_entry.index("insert") != len(draft):
                return
        except Exception:
            pass
        self._ai_complete_after = self._after(self._AI_COMPLETE_DELAY_MS,
                                              self._ai_complete_request)

    def _ai_complete_request(self):
        self._ai_complete_after = None
        jid = self.active
        draft = self._ai_composer_text()
        if (not jid or not draft.endswith(" ")
                or getattr(self, "_ai_complete_busy", False)):
            return
        settings = self._ai_settings()
        if settings["provider"] != _ai.PROVIDER_OLLAMA:
            return                      # bulut sağlayıcıya taslak gitmez
        self._ai_complete_seq = getattr(self, "_ai_complete_seq", 0) + 1
        seq = self._ai_complete_seq
        entries = self._ai_chat_entries(jid)[-12:]
        transcript, _n = _ai.build_transcript(entries, max_chars=2500)
        system, user = _ai.completion_request(transcript, draft.rstrip())
        self._ai_complete_busy = True

        def job():
            return _ai.clean_completion(draft, _ai.chat(
                settings, system, user, effort="low",
                max_tokens=_ai.COMPLETION_MAX_TOKENS))

        def done(text):
            self._ai_complete_busy = False
            if (text and seq == self._ai_complete_seq and self.active == jid
                    and self._ai_composer_text() == draft):
                self._suggest_bar.show(draft, text)

        def fail(e):
            self._ai_complete_busy = False
            _log.debug("Satır içi öneri alınamadı: %s", e)

        self._ai_submit(job, done, fail)

    def _ai_complete_accept(self):
        bar = getattr(self, "_suggest_bar", None)
        if bar is None or not bar.visible:
            return
        text = bar.text
        bar.hide()
        self._ai_set_composer_text(self._ai_composer_text() + text)

    def _ai_complete_tab(self, _event=None):
        bar = getattr(self, "_suggest_bar", None)
        if bar is None or not bar.visible:
            return None                 # öneri yok: normal Tab davranışı
        self._ai_complete_accept()
        return "break"

    def _ai_complete_escape(self, _event=None):
        bar = getattr(self, "_suggest_bar", None)
        if bar is None or not bar.visible:
            return None
        bar.hide()
        return "break"

    # — Sesli okuma (yerel TTS; xmppcore/tts) —
    # Tek seferde tek okuma: yenisi eskisini durdurur (nesil sayacı).
    # Süreç worker thread'inde beklenir; Tk'ya dokunulmaz.
    _TTS_TIMEOUT = 300

    def _ai_row_speech_text(self, row) -> str:
        text = _ai.message_text(getattr(row, "_body", "") or "")
        if text:
            return text
        ref = getattr(row, "_stt_ref", None)
        spoken = (getattr(self, "_ai_stt_texts", None) or {}).get(ref, "")
        return "" if spoken == _ai.NO_SPEECH else spoken

    def _ai_speak_row(self, row):
        text = self._ai_row_speech_text(row)
        if text:
            self._ai_speak_text(text)

    def _ai_tts_lock(self):
        lock = getattr(self, "_tts_lock", None)
        if lock is None:
            lock = self._tts_lock = threading.Lock()
        return lock

    def _ai_speaking(self) -> bool:
        proc = getattr(self, "_tts_proc", None)
        return proc is not None and proc.poll() is None

    def _ai_speak_text(self, text):
        settings = self._ai_settings()
        self._ai_speak_stop()
        fd, wav = tempfile.mkstemp(prefix="xmpp-tts-", suffix=".wav")
        os.close(fd)
        try:
            steps = _tts.plan_speech(text, settings, wav)
        except _ai.AIError as e:
            os.unlink(wav)
            messagebox.showinfo("🔊 Sesli okuma", str(e), parent=self.root)
            return
        if not self._remember_temp(wav):
            os.unlink(wav)
            return
        with self._ai_tts_lock():
            self._tts_gen = getattr(self, "_tts_gen", 0) + 1
            gen = self._tts_gen
        threading.Thread(target=self._ai_speak_worker, args=(steps, wav, gen),
                         daemon=True, name="ai-tts").start()

    def _ai_speak_worker(self, steps, wav, gen):
        """Adımları sırayla çalıştır (worker); hata _safe_after ile."""
        lock = self._ai_tts_lock()
        try:
            for argv, stdin in steps:
                with lock:
                    if gen != self._tts_gen or getattr(self, "_closing",
                                                       False):
                        return
                    proc = _sp.Popen(
                        argv, stdin=_sp.PIPE if stdin is not None
                        else _sp.DEVNULL, stdout=_sp.DEVNULL,
                        stderr=_sp.DEVNULL)
                    self._tts_proc = proc
                try:
                    proc.communicate(
                        stdin.encode("utf-8") if stdin is not None else None,
                        timeout=self._TTS_TIMEOUT)
                except _sp.TimeoutExpired:
                    proc.kill()
                    proc.communicate()
                    return
                if proc.returncode != 0:
                    if gen == self._tts_gen:    # durdurulmadıysa gerçek hata
                        self._safe_after(0, self._ai_speak_failed,
                                         os.path.basename(argv[0]))
                    return
        except OSError as e:
            self._safe_after(0, self._ai_speak_failed, str(e))
        finally:
            with lock:
                if getattr(self, "_tts_proc", None) is not None and \
                        gen == self._tts_gen:
                    self._tts_proc = None
            try:
                os.unlink(wav)
            except OSError:
                pass
            self._forget_temp(wav)

    def _ai_speak_failed(self, what):
        self._show_toast("🔊 Sesli okuma başarısız", f"{what} çalışmadı")

    def _ai_speak_stop(self):
        with self._ai_tts_lock():
            self._tts_gen = getattr(self, "_tts_gen", 0) + 1
            proc = getattr(self, "_tts_proc", None)
            self._tts_proc = None
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass

    # — MCP sunucusu (xmpp_mcp.py; erişim AI Ayarları'ndan açılır) —
    @staticmethod
    def _mcp_command() -> str:
        import shlex
        import sys
        base = os.path.dirname(os.path.abspath(__file__))
        venv_py = os.path.join(base, ".venv-xmpp", "bin", "python")
        python = venv_py if os.path.exists(venv_py) else sys.executable
        return (f"claude mcp add xmpp -- {shlex.quote(python)} "
                f"{shlex.quote(os.path.join(base, 'xmpp_mcp.py'))}")

    # — Şifresiz gönderimde hassas veri uyarısı (yerel; model yok) —
    def _leak_guard_ok(self, target, body, enc_mode, parent=None) -> bool:
        """Gönderilsin mi? Şifresiz taslakta hassas bilgi varsa sorar.

        Tarama tamamen yereldir (xmppcore/sensitive); şifreli sohbet ve
        AI Ayarları'nda kapatılmış uyarı hiç taramaz (GUI thread).
        """
        if enc_mode not in ("", "none"):
            return True
        findings = _sensitive.scan(body)
        if not findings or not self._ai_settings()["leak_guard"]:
            return True
        return messagebox.askyesno(
            "⚠ Hassas bilgi",
            _sensitive.warning_text(findings, room=target in self.rooms),
            icon="warning", default="no", parent=parent or self.root)

    # — Yanıt bekleyen sorular (yerel sezgi; model yok) —
    _QUESTION_NUDGE_SECS = 3600

    def _questions_scan(self, on_done, on_error=None):
        """Yanıt bekleyen soruları worker'da bul; odalar hariç."""
        cfg = _load_config()
        dismissed = cfg.get(_questions.DISMISS_KEY) or []
        rooms = set(getattr(self, "rooms", ()) or ()) | set(
            cfg.get("rooms") or {})

        def job():
            return _questions.find_pending(
                _db_unanswered(), dismissed=dismissed, skip_jids=rooms)

        self._ai_submit(job, on_done, on_error or (
            lambda e: _log.warning("Soru taraması başarısız: %s", e)))

    def _ai_pending_questions(self):
        win = _ui_ai.PendingQuestionsWindow(
            self.root, on_open=lambda e: self._ai_open_chat(e["jid"]),
            on_remind=self._questions_remind,
            on_dismiss=self._questions_dismiss)

        def done(entries):
            now = datetime.now()
            win.set_entries([
                dict(e, label=self._ai_chat_label(e["jid"]),
                     age=_questions.format_age(e["since"], now))
                for e in entries])

        self._questions_scan(done, lambda e: win.set_error(str(e)))

    def _questions_remind(self, entry):
        item = _questions.reminder_item(entry, entry["label"],
                                        datetime.now().date())
        return self._ai_add_reminders([item], entry["jid"])

    def _questions_dismiss(self, entry):
        cfg = _load_config()
        cfg[_questions.DISMISS_KEY] = _questions.dismiss(
            cfg.get(_questions.DISMISS_KEY), entry["key"])
        _save_config(cfg)

    def _questions_nudge(self):
        """Bağlanınca oturumda bir kez: uzun bekleyen soru varsa bildir."""
        if getattr(self, "_questions_nudged", False):
            return
        self._questions_nudged = True

        def done(entries):
            waiting = _questions.waiting_longer_than(
                entries, datetime.now(), self._QUESTION_NUDGE_SECS)
            if waiting and not getattr(self, "_closing", False):
                self._show_toast("❓ Yanıt bekleyen sorular",
                                 f"{len(waiting)} sohbette soru yanıt "
                                 "bekliyor — Ctrl+Shift+Q")

        self._questions_scan(done)

    # — Görev / etkinlik çıkarma, .ics ve hatırlatıcılar —
    _AI_REMINDER_POLL_MS = 30000

    def _ai_extract_actions(self, jid=None):
        jid = jid or self.active
        if not jid:
            return
        settings = self._ai_settings()
        entries = self._ai_chat_entries(jid)
        sensitive = self._ai_is_sensitive(jid, entries)
        allow = self._ai_gate(settings, sensitive)
        if allow is None:
            return
        transcript, count = _ai.build_transcript(
            entries, max_chars=_ai.transcript_budget(settings))
        if not count:
            messagebox.showinfo("Görevler ve Etkinlikler",
                                "Bu sohbette henüz mesaj yok.",
                                parent=self.root)
            return
        label = self._ai_chat_label(jid)
        system, user = _ai.actions_request(transcript, datetime.now(),
                                           settings["target_language"])
        win = _ui_ai.ActionsWindow(
            self.root, f"📅 {label} — görevler ve etkinlikler",
            f"{_ai.provider_label(settings)} · son {count} mesaj",
            on_export=lambda items: self._ai_export_ics(items, label),
            on_remind=lambda items: self._ai_add_reminders(items, jid))
        win.set_busy("Sohbet inceleniyor…")
        self._ai_submit(
            lambda: _ai.parse_actions(_ai.chat(
                settings, system, user, effort="medium", sensitive=sensitive,
                allow_cloud=allow, schema=_ai.ACTIONS_SCHEMA)),
            win.set_items, lambda e: win.set_error(str(e)))

    def _ai_export_ics(self, items, label):
        """Seçili öğeleri .ics dosyasına yaz → (başarılı, mesaj) | None."""
        valid, errors = _ai.validate_actions(items)
        if errors:
            return (False, f"⚠ {errors[0]}")
        if not valid:
            return (False, "Kaydedilecek öğe yok.")
        from tkinter import filedialog
        safe = re.sub(r"[^\w.-]+", "_", label).strip("_") or "sohbet"
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Takvim dosyasını kaydet",
            defaultextension=".ics", initialfile=f"{safe}-gorevler.ics",
            filetypes=[("iCalendar", "*.ics"), ("Tüm dosyalar", "*")])
        if not path:
            return None
        try:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(_ai.build_ics(valid))
        except OSError as e:
            return (False, f"⚠ Dosya yazılamadı: {e}")
        return (True, f"✓ {len(valid)} öğe kaydedildi: "
                      f"{os.path.basename(path)} — takvim uygulamanızla "
                      "açabilirsiniz.")

    def _ai_add_reminders(self, items, jid):
        """Tarih+saati ileride olan öğelere uygulama içi hatırlatıcı."""
        valid, errors = _ai.validate_actions(items)
        if errors:
            return (False, f"⚠ {errors[0]}")
        now = datetime.now()
        new = [r for r in (_ai.reminder_from_action(i, jid, now)
                           for i in valid) if r]
        if not new:
            return (False, "Hatırlatıcı için seçili öğelerde ileri bir "
                           "tarih ve saat olmalı.")
        cfg = _load_config()
        stored = cfg.get(_ai.REMINDER_KEY)
        cfg[_ai.REMINDER_KEY] = (stored if isinstance(stored, list)
                                 else []) + new
        _save_config(cfg)
        self._ai_arm_reminders()
        msg = f"⏰ {len(new)} hatırlatıcı kuruldu."
        skipped = len(valid) - len(new)
        if skipped:
            msg += (f" {skipped} öğede ileri tarih/saat olmadığı için "
                    "kurulmadı.")
        return (True, msg)

    def _ai_arm_reminders(self):
        """Bekleyen hatırlatıcı varsa denetim zincirini başlat (tekil)."""
        if (getattr(self, "_ai_reminder_after", None) is None
                and not getattr(self, "_closing", False)):
            self._ai_reminder_after = self._after(1000,
                                                  self._ai_check_reminders)

    def _ai_check_reminders(self):
        self._ai_reminder_after = None
        if getattr(self, "_closing", False):
            return
        cfg = _load_config()
        stored = cfg.get(_ai.REMINDER_KEY)
        if not stored:
            return
        records = stored if isinstance(stored, list) else []
        now = datetime.now()
        due, pending = _ai.split_due_reminders(records, now)
        if len(pending) != len(records) or records is not stored:
            # Çalan (ve bozuk) kayıtlar önce kalıcı listeden düşer: bildirim
            # penceresi açıkken ya da çökme sonrası ikinci kez çalmazlar.
            cfg[_ai.REMINDER_KEY] = pending
            _save_config(cfg)
        if pending:
            self._ai_reminder_after = self._after(
                self._AI_REMINDER_POLL_MS, self._ai_check_reminders)
        if due:
            self._ai_fire_reminders(due, now)

    def _ai_fire_reminders(self, due, now):
        lines = []
        for r in sorted(due, key=lambda r: r["when"]):
            when = _ai.reminder_time(r)
            text = r["title"] + (f" — {r['location']}"
                                 if r.get("location") else "")
            _desktop_notify("⏰ Hatırlatıcı", text)
            line = f"• {when:%d.%m %H:%M}  {text}"
            if r.get("jid"):
                line += f"  ({self._ai_chat_label(r['jid'])})"
            if (now - when).total_seconds() > 300:
                line += "  — zamanı geçti"
            lines.append(line)
        messagebox.showinfo("⏰ Hatırlatıcı", "\n".join(lines),
                            parent=self.root)

    def _ai_composer_text(self) -> str:
        entry = getattr(self, "_msg_entry", None)
        if entry is not None and hasattr(entry, "get_value"):
            return entry.get_value()
        return self.msg_var.get()

    def _ai_set_composer_text(self, text):
        entry = getattr(self, "_msg_entry", None)
        if entry is not None and getattr(entry, "_showing_ph", False):
            entry._showing_ph = False      # placeholder değil, gerçek metin
            try:
                entry.configure(foreground=FG)
            except Exception:
                pass
        self.msg_var.set(text)
        if entry is not None:
            try:
                entry.focus_set()
                entry.icursor("end")
            except Exception:
                pass

    def _ai_composer_busy(self, busy):
        btn = getattr(getattr(self, "_chat_shell", None), "_ai_btn", None)
        if btn is not None:
            try:
                btn.config(text="⏳" if busy else "✨")
            except Exception:
                pass

    def _ai_suggest_replies(self):
        jid = self.active
        if not jid:
            return
        settings = self._ai_settings()
        entries = self._ai_chat_entries(jid)[-60:]
        sensitive = self._ai_is_sensitive(jid, entries)
        allow = self._ai_gate(settings, sensitive)
        if allow is None:
            return
        transcript, count = _ai.build_transcript(
            entries, max_chars=min(8000, _ai.transcript_budget(settings)))
        if not count:
            messagebox.showinfo("Yanıt Öner", "Bu sohbette henüz mesaj yok.",
                                parent=self.root)
            return
        win = _ui_ai.ResultWindow(self.root, "💡 Yanıt önerileri",
                                  _ai.provider_label(settings))
        system, user = _ai.suggest_request(transcript)

        def _done(text):
            items = _ai.parse_suggestions(text)
            if not items:
                win.set_text(text)
                return
            win.set_choices(items, lambda s: self._ai_offer_text(jid, s))

        self._ai_submit(
            lambda: _ai.chat(settings, system, user, effort="low",
                             sensitive=sensitive, allow_cloud=allow),
            _done, lambda e: win.set_error(str(e)))

    def _ai_offer_text(self, jid, text):
        """Seçilen öneriyi giriş kutusuna koy (gönderim kullanıcıya kalır)."""
        if self.active != jid:
            self._load_chat(jid)
        self._ai_set_composer_text(text)

    def _ai_rewrite(self, mode):
        jid = self.active
        text = self._ai_composer_text().strip()
        if not jid:
            return
        if not text:
            messagebox.showinfo("AI Asistanı",
                                "Önce giriş kutusuna bir mesaj yazın.",
                                parent=self.root)
            return
        settings = self._ai_settings()
        sensitive = self._ai_is_sensitive(jid)
        allow = self._ai_gate(settings, sensitive)
        if allow is None:
            return
        system, user = _ai.rewrite_request(text, mode)
        self._ai_composer_busy(True)

        def _done(result):
            self._ai_composer_busy(False)
            if (self.active == jid
                    and self._ai_composer_text().strip() == text):
                self._ai_undo = (jid, text)
                self._ai_set_composer_text(result)
                return
            # Bu arada sohbet/metin değişti: üzerine yazma, ayrı göster.
            win = _ui_ai.ResultWindow(self.root, _ai.REWRITE_MODES[mode][0],
                                      _ai.provider_label(settings))
            win.set_text(result)

        def _fail(e):
            self._ai_composer_busy(False)
            messagebox.showerror("AI Asistanı", str(e), parent=self.root)

        self._ai_submit(
            lambda: _ai.chat(settings, system, user, effort="low",
                             sensitive=sensitive, allow_cloud=allow),
            _done, _fail)

    def _ai_undo_rewrite(self):
        undo = getattr(self, "_ai_undo", None)
        if undo and undo[0] == self.active:
            self._ai_set_composer_text(undo[1])
            self._ai_undo = None

    # — Sesle yaz (dikte): kayıt → yerel faster-whisper → giriş kutusu —
    def _ai_dictate(self):
        if not self.active:
            return
        if getattr(self, "_recording", False):
            # İkinci basış dikteyi bitirir; ses mesajı kaydına dokunulmaz.
            if getattr(self, "_rec_mode", "voice") == "dictate":
                self._stop_recording(send=True)
            return
        settings = self._ai_settings()
        # Ses→metin her zaman yereldir; yalnız AI tamamen kapalıysa durur.
        if settings["provider"] == _ai.PROVIDER_OFF:
            self._ai_gate(settings, False)
            return
        if not _HAS_PYAUDIO:
            messagebox.showwarning(
                "Sesle Yaz", "Mikrofon için PyAudio gerekli:\n"
                "  .venv-xmpp/bin/python -m pip install pyaudio",
                parent=self.root)
            return
        import importlib.util
        if importlib.util.find_spec("faster_whisper") is None:
            messagebox.showwarning(
                "Sesle Yaz", "Ses→metin için faster-whisper gerekli (yerel "
                "çalışır):\n  .venv-xmpp/bin/python -m pip install "
                "faster-whisper", parent=self.root)
            return
        self._start_recording(mode="dictate")

    def _ai_transcribe_dictation(self, raw_audio, target):
        """Dikte kaydını worker'da işle + yazıya dök; metni taslağa ekle."""
        model = self._ai_settings()["whisper_model"]
        self._ai_composer_busy(True)

        def job():
            path = None
            try:
                processed = self._process_audio(raw_audio)
                with tempfile.NamedTemporaryFile(suffix=".wav",
                                                 delete=False) as tmp:
                    path = tmp.name
                with wave.open(path, "wb") as wf:
                    wf.setnchannels(self._VOICE_CHANNELS)
                    wf.setsampwidth(2)  # 16-bit
                    wf.setframerate(self._VOICE_RATE)
                    wf.writeframes(processed)
                if not self._remember_temp(path):
                    raise _ai.AICancelled("Uygulama kapanıyor.")
                return _ai.transcribe_file(path, model)
            finally:
                if path is not None:
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
                    self._forget_temp(path)

        def done(text):
            self._ai_composer_busy(False)
            text = (text or "").strip()
            if not text or text == _ai.NO_SPEECH:
                messagebox.showinfo("Sesle Yaz", "Konuşma algılanmadı.",
                                    parent=self.root)
                return
            if self.active == target:
                self._ai_set_composer_text(
                    _ai.append_dictation(self._ai_composer_text(), text))
                return
            # Bu arada sohbet değişti: başka taslağa yazma, ayrı göster.
            win = _ui_ai.ResultWindow(
                self.root, "🎙 Dikte", f"🖥 Yerel (faster-whisper) · {model}",
                actions=[("✍ Taslağa koy",
                          lambda t: self._ai_offer_text(target, t))])
            win.set_text(text, status="✓ Sohbet değiştiği için burada "
                                      "gösteriliyor")

        def fail(e):
            self._ai_composer_busy(False)
            messagebox.showerror("Sesle Yaz", str(e), parent=self.root)

        self._ai_submit(job, done, fail)

    # — Anlamsal arama (yerel gömme) —
    def _ai_semantic_search_dialog(self):
        settings = self._ai_settings()
        if settings["provider"] == _ai.PROVIDER_OFF:
            self._ai_gate(settings, False)
            return
        model = settings["embed_model"]
        win = _ui_ai.SemanticSearchWindow(
            self.root,
            f"🖥 Yerel gömme · {model} — mesajlar bilgisayardan çıkmaz",
            on_search=lambda q: self._ai_semantic_search(win, settings, q),
            on_open=self._ai_open_search_hit)
        self._ai_index_messages(win, settings)

    def _ai_index_messages(self, win, settings):
        """Gömmesi olmayan mesajları arka planda (artımlı) indeksle."""
        if getattr(self, "_ai_indexing", False):
            win.set_status("⏳ İndeksleme zaten sürüyor…")
            return
        self._ai_indexing = True

        def job():
            return self._ai_index_pending(
                settings, lambda done, total: self._safe_after(
                    0, win.set_status,
                    f"⏳ Mesajlar indeksleniyor: {done}/{total} (arama "
                    "şimdiden çalışır)"))

        def _done(n):
            self._ai_indexing = False
            win.set_status(f"✓ {n} yeni mesaj indekslendi." if n
                           else "✓ İndeks güncel.")

        def _fail(e):
            self._ai_indexing = False
            win.set_status(f"⚠ {e}", error=True)

        win.set_status("⏳ İndeks kontrol ediliyor…")
        self._ai_submit(job, _done, _fail)

    def _ai_index_pending(self, settings, progress=None, cancel=None):
        """Gömmesi olmayan mesajları indeksle (worker). Dönüş: işlenen sayı.

        `progress(işlenen, toplam)` her partide çağrılır; `cancel`
        kurulursa sonraki partiden önce `AICancelled` fırlar.
        """
        model = settings["embed_model"]
        skip = (_ai.RETRACTED_BODY, _ai.VOICE_PLACEHOLDER)
        total = _db_ai_pending_count(model, skip)
        done = 0
        seen = set()
        while not getattr(self, "_closing", False):
            if cancel is not None and cancel.is_set():
                raise _ai.AICancelled("İptal edildi.")
            batch = _db_ai_pending(model, 32, skip)
            if not batch:
                break
            ids = {r[0] for r in batch}
            if ids <= seen:
                raise _ai.AIError("Gömmeler veritabanına yazılamadı.")
            seen |= ids
            items, texts, targets = [], [], []
            for msg_id, jid, sender, body in batch:
                if _ai.message_text(body):
                    texts.append(_ai.embed_document_text(
                        model, sender or "", body))
                    targets.append((msg_id, jid))
                else:
                    # Yalnız medya/çok kısa: işaretle, aramada elenir.
                    items.append((msg_id, jid, model, b""))
            for (msg_id, jid), vec in zip(
                    targets, _ai.ollama_embed(settings, texts)):
                items.append((msg_id, jid, model, _ai.pack_vec(vec)))
            _db_ai_store_embeddings(items)
            done += len(batch)
            if progress is not None:
                progress(done, max(total, done))
        return done

    def _ai_iter_embeddings(self, model, cancel=None):
        """Gömmeleri parça parça oku (worker): (msg_id, jid, sender, body,
        ts, mid, vec) — DB kilidi uzun tutulmaz."""
        after = 0
        while True:
            if cancel is not None and cancel.is_set():
                raise _ai.AICancelled("İptal edildi.")
            chunk = _db_ai_embedding_chunk(model, after, 500)
            if not chunk:
                return
            yield from chunk
            after = chunk[-1][0]

    def _ai_semantic_search(self, win, settings, query):
        model = settings["embed_model"]
        win.set_status("⏳ Aranıyor…")

        def job():
            qvec = _ai.ollama_embed(
                settings, [_ai.embed_query_text(model, query)])[0]
            rows = (((jid, sender, body, ts, mid), vec)
                    for _id, jid, sender, body, ts, mid, vec
                    in self._ai_iter_embeddings(model))
            return _ai.top_k(_ai.pack_vec(qvec), rows, k=30, min_score=0.2)

        def _done(hits):
            results = []
            for score, (jid, sender, body, ts, mid) in hits:
                short = jid.split("@")[0]
                preview = _ai.strip_media_urls(body).replace("\n", " ")
                results.append((f"{score:4.0%}  [{short}] {sender or '?'} "
                                f"({ts}): {preview[:90]}", (jid, mid)))
            win.set_results(results)
            win.set_status(f"{len(results)} sonuç — açmak için çift tıklayın"
                           if results else "Eşleşen mesaj bulunamadı.")

        self._ai_submit(job, _done,
                        lambda e: win.set_status(f"⚠ {e}", error=True))

    def _ai_open_search_hit(self, payload):
        jid, mid = payload
        self._ai_open_chat(jid)
        if mid:
            self._safe_after(200, self._ai_reveal_message, mid)

    def _ai_reveal_message(self, mid):
        """Mesaj görünür penceredeyse kaydır ve vurgula (yoksa sessiz)."""
        row = _identity.find_row_by_mid(self._bubble_widgets, mid)
        if row is not None:
            self._scroll_to_row(row)
            self._flash_row(row)

    # — Geçmişe sor (RAG): yerel gömme ile bul, modelle kaynaklı yanıtla —
    def _ai_ask_history(self, question=None):
        settings = self._ai_settings()
        if settings["provider"] == _ai.PROVIDER_OFF:
            self._ai_gate(settings, False)
            return
        lang = settings["target_language"]
        conv = _ai.Conversation(
            _ai.rag_system(lang, datetime.now().strftime("%Y-%m-%d")),
            effort="low", pin_first=False, cache=False)
        state = {"previous": ""}
        win, cancel = self._ai_open_window(
            "💬 Geçmişe sor",
            f"{_ai.provider_label(settings)} · arama yerel "
            f"({settings['embed_model']})", conv,
            on_ask=lambda q: self._ai_rag_turn(win, conv, q, cancel, state),
            ask_hint="Örn: Ali'nin verdiği adres neydi?", ask_ready=True)
        win.set_status("Sorunuzu aşağıya yazın: ilgili mesajlar bu "
                       "bilgisayarda bulunur, yanıt kaynaklarıyla gelir.")
        win.focus_ask()
        if question:                    # asistandan gelen soru hemen sorulur
            self._ai_rag_turn(win, conv, question, cancel, state)

    def _ai_rag_turn(self, win, conv, question, cancel, state):
        """1. aşama (worker): indeksi güncelle, sorguyu göm, eşleşmeleri ve
        komşularını oku. 2. aşama `_ai_rag_answer` (GUI thread)."""
        settings = self._ai_settings()
        if settings["provider"] == _ai.PROVIDER_OFF:
            self._ai_gate(settings, False)
            return
        model = settings["embed_model"]
        query = _ai.rag_query_text(question, state.get("previous", ""))
        index_now = not getattr(self, "_ai_indexing", False)
        if index_now:
            self._ai_indexing = True
        win.begin_question(question)
        win.set_sources([], None)          # önceki turun kaynakları eskidi
        win.set_busy("İlgili mesajlar aranıyor…")

        def progress(done, total):
            self._safe_after(0, win.set_busy,
                             f"Mesajlar indeksleniyor: {done}/{total}…")

        def job():
            try:
                if index_now:
                    self._ai_index_pending(settings, progress, cancel)
            except _ai.AICancelled:
                raise
            except _ai.AIError:
                # Yazılamayan parti vb.: mevcut indeksle aramaya devam.
                _log.warning("Geçmişe sor: indeksleme tamamlanamadı",
                             exc_info=True)
            finally:
                if index_now:
                    self._ai_indexing = False
            qvec = _ai.ollama_embed(
                settings, [_ai.embed_query_text(model, query)])[0]
            rows = ((msg_id, vec) for msg_id, _j, _s, _b, _t, _m, vec
                    in self._ai_iter_embeddings(model, cancel))
            hits = _ai.top_k(_ai.pack_vec(qvec), rows, k=_ai.RAG_TOP_K,
                             min_score=_ai.RAG_MIN_SCORE)
            ids = [msg_id for _score, msg_id in hits]
            context = (_db_ai_context(ids, _ai.RAG_BEFORE, _ai.RAG_AFTER)
                       if ids else [])
            return ids, context

        self._ai_submit(
            job,
            lambda res: self._ai_rag_answer(win, conv, question, res[0],
                                            res[1], cancel, state, settings),
            lambda e: win.set_error(str(e)))

    def _ai_rag_answer(self, win, conv, question, ids, rows, cancel, state,
                       settings):
        if not win.alive():
            return
        modes = getattr(self, "_chat_enc_modes", None) or {}

        def secret(row):
            return bool(row[7]) or modes.get(row[1], "none") not in ("",
                                                                      "none")
        if not rows:
            win.set_answer("Bu soruyla ilgili bir mesaj bulunamadı. Farklı "
                           "kelimelerle sormayı deneyin.",
                           status="Eşleşme yok")
            return
        if conv.sensitive:
            # Önceki yanıtlar şifreli içerikten türedi: süzülemez, sorulur.
            allow = self._ai_gate(settings, True)
            mode = "all"
            if allow is None:
                win.set_error("Gönderilmedi.")
                return
        else:
            gate = self._ai_gate_mixed(settings, sum(map(secret, rows)),
                                       len(rows))
            if gate is None:
                win.set_error("İptal edildi — hiçbir şey gönderilmedi.")
                return
            mode, allow = gate
        if mode == "plain":
            rows = [r for r in rows if not secret(r)]
        labels = {jid: self._ai_chat_label(jid) for jid in {r[1] for r in rows}}
        context, sources = _ai.build_rag_context(
            rows, {msg_id: i for i, msg_id in enumerate(ids)}, labels,
            max_chars=_ai.transcript_budget(settings))
        if not sources:
            win.set_answer("Eşleşen mesajlar gönderilebilecek metin "
                           "içermiyor (yalnız medya ya da şifreli içerik).",
                           status="Eşleşme yok")
            return
        # Yalnız gerçekten gönderilen satırlar (bütçe kesmiş olabilir).
        sensitive = any(s["encrypted"] or modes.get(s["jid"], "none")
                        not in ("", "none") for s in sources)

        def show_sources(answer):
            cited = [n for n in _ai.cited_numbers(answer)
                     if 1 <= n <= len(sources)]
            picked = ([sources[n - 1] for n in cited] if cited
                      else [s for s in sources if s["hit"]])
            win.set_sources(
                [(f"[{s['n']}] {s['label']} · {s['who']} ({s['ts']}): "
                  f"{s['text'][:70]}", (s["jid"], s["mid"])) for s in picked],
                self._ai_open_search_hit,
                title="Kaynaklar" if cited else "İlgili mesajlar")
            state["previous"] = question

        win.set_busy("Yanıt hazırlanıyor…")
        self._ai_turn(win, conv, settings, _ai.rag_user(context, question),
                      allow, cancel, sensitive=conv.sensitive or sensitive,
                      history_text=question,
                      history_answer=_ai.strip_citations, as_answer=True,
                      on_done=show_sources)

    # — Ayarlar —
    def _ai_settings_dialog(self):
        settings = self._ai_settings()

        def _save(values, key):
            cfg = _load_config()
            _ai.merge_settings(cfg, values, key)
            _save_config(cfg)
            self._ai_refresh_flags()

        def _test(values, key, report):
            stored = dict(_load_config().get("ai") or {})
            stored.update(values)
            if key is not None:
                stored["claude_api_key"] = _encode_pw(key) if key else ""
            s = _ai.load_settings({"ai": stored})

            def job():
                if s["provider"] == _ai.PROVIDER_OFF:
                    return "AI kapalı — test edilecek sağlayıcı yok."
                lines = []
                try:
                    have = _ai.ollama_models(s)
                    names = set(have) | {n.split(":")[0] for n in have
                                         if n.endswith(":latest")}
                    wanted = [s["embed_model"]]
                    if s["provider"] == _ai.PROVIDER_OLLAMA:
                        wanted[:0] = [s["ollama_model"],
                                      s["ollama_vision_model"]]
                    missing = [m for m in dict.fromkeys(wanted)
                               if m not in names]
                    lines.append(
                        "✓ Ollama çalışıyor; modeller hazır." if not missing
                        else "✗ Ollama çalışıyor ama eksik model var: "
                        + ", ".join(f"ollama pull {m}" for m in missing))
                except _ai.AIError as e:
                    lines.append(f"✗ {e}")
                if s["provider"] == _ai.PROVIDER_CLAUDE:
                    try:
                        _ai.claude_chat(s, "Reply with the single word OK.",
                                        "ping", effort="low")
                        lines.append(f"✓ Claude erişilebilir "
                                     f"({s['claude_model']}).")
                    except _ai.AIError as e:
                        lines.append(f"✗ Claude: {e}")
                try:
                    import faster_whisper  # noqa: F401
                    lines.append("✓ faster-whisper kurulu (ses→metin).")
                except ImportError:
                    lines.append("✗ Ses→metin için: .venv-xmpp/bin/python "
                                 "-m pip install faster-whisper")
                lines.append(_tts.describe_engines(s))
                if s["mcp_enabled"]:
                    lines.append(
                        "✓ MCP erişimi açık; REST API çalışıyor (taslak "
                        "bırakılabilir)." if getattr(self, "_api_server", None)
                        else "ℹ MCP erişimi açık; taslak bırakmak için "
                             "REST API'yi de açın.")
                return "\n".join(lines)

            self._ai_submit(job, lambda msg: report(msg, "✗" not in msg),
                            lambda e: report(str(e), False))

        _ui_ai.show_settings(self.root, settings,
                             bool(settings["claude_api_key"]),
                             _ai.WHISPER_MODELS, _save, _test,
                             tts_engines=_ai.TTS_ENGINES,
                             keep_alive_choices=_ai.KEEP_ALIVE_CHOICES,
                             mcp_command=self._mcp_command())

    # ── Clipboard yapıştır (Ctrl+V resim) ─────────────────────────────────────
    def _on_paste(self, event=None):
        """Ctrl+V — panodan resim yapıştır."""
        if not self.active or not self.bot:
            return
        if not HAS_PIL:
            return
        try:
            from PIL import ImageGrab
            img = ImageGrab.grabclipboard()
            if img is None:
                return  # Normal metin yapıştırma
            # Geçici dosyaya kaydet ve gönder
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            img.save(tmp, format="PNG")
            tmp.close()
            self._remember_temp(tmp.name)
            self.bot.send_file(self.active, tmp.name,
                "groupchat" if self.active in self.rooms else "chat")
            return "break"  # Metin yapıştırmayı engelle
        except Exception:
            return  # Normal yapıştır devam etsin

    # ── Tarih ayırıcı ──────────────────────────────────────────────────────────
    def _maybe_add_date_separator(self, time_str=None):
        """Gerekirse tarih ayırıcı ekle (mesajın gerçek tarihine göre)."""
        msg_date = _parse_msg_date(time_str) or datetime.now().date()
        day_key = msg_date.strftime("%Y-%m-%d")
        if day_key == self._last_date_label:
            return
        self._last_date_label = day_key
        label = _date_separator_label(
            day_key, datetime.now().strftime("%Y-%m-%d"), msg_date)
        sf = _render.render_date_separator(self.msg_frame, _chat_theme(),
                                           label)
        self._bubble_widgets.append(sf)
        self._bind_scroll_widget(sf)

    # ── Engelleme diyaloğu ─────────────────────────────────────────────────────
    def _blocking_dialog(self):
        """Engelli kişiler listesi ve yönetimi."""
        pop = tk.Toplevel(self.root)
        pop.title("Engelli Kişiler")
        pop.configure(bg=BG_CARD)
        pop.geometry("360x400")
        pop.transient(self.root)

        tk.Label(pop, text="Engelli Kişiler", fg=FG, bg=BG_CARD,
                 font=(FONT, 12, "bold")).pack(padx=16, pady=(16, 8), anchor="w")

        lb = tk.Listbox(pop, bg=BG_PANEL, fg=FG, selectbackground=SEL_BG,
                         font=(FONT, 9), relief="flat", highlightthickness=0)
        lb.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        blocked_jids = []

        def _populate(jids):
            if not pop.winfo_exists():
                return
            lb.delete(0, "end")
            blocked_jids.clear()
            for j in (jids or []):
                blocked_jids.append(str(j))
                lb.insert("end", f"  🚫 {j}")

        if self.bot:
            self.bot.get_blocked_list(_populate)

        btn_f = tk.Frame(pop, bg=BG_CARD)
        btn_f.pack(fill="x", padx=16, pady=(0, 16))

        def _unblock():
            sel = lb.curselection()
            if not sel:
                return
            jid = blocked_jids[sel[0]]
            self.bot.unblock_contact(jid)
            lb.delete(sel[0])
            blocked_jids.pop(sel[0])

        def _block_new():
            jid = simpledialog.askstring("Engelle", "JID:", parent=pop)
            jid = jid and self._jid_or_warn(jid, "Engelle", parent=pop)
            if jid:
                self.bot.block_contact(jid)
                blocked_jids.append(jid)
                lb.insert("end", f"  🚫 {jid}")

        ttk.Button(btn_f, text="Engeli Kaldır", command=_unblock).pack(
            side="left", padx=(0, 8))
        ttk.Button(btn_f, text="Yeni Engelle", command=_block_new).pack(
            side="left")

    # ── Durum mesajı diyaloğu ─────────────────────────────────────────────────
    def _status_dialog(self):
        """Durum mesajı penceresi (ui/dialogs)."""
        def _apply(text, show):
            if self.bot:
                self._publish_status(text, show)
        _ui_presence.show_status(self.root, _apply)

    def _publish_status(self, text, show="chat"):
        """Durum mesajını yayınla ve kaydet: yeniden bağlanınca (ve açılışta)
        aynısı geri yayınlanır."""
        self._status_text, self._status_show = text, show
        cfg = _load_config()
        cfg["status_text"], cfg["presence_show"] = text, show
        _save_config(cfg)
        self.bot.set_status_message(text, show)

    # ── Profil kartı diyaloğu ─────────────────────────────────────────────────
    def _profile_card(self, jid=None):
        """Bir kullanıcının profil kartını göster."""
        if jid is None:
            jid = self.active
        if not jid or not self.bot:
            return
        pop = tk.Toplevel(self.root)
        pop.title(f"Profil — {jid}")
        pop.configure(bg=BG_CARD)
        pop.geometry("340x320")
        pop.transient(self.root)

        # Avatar
        photo_data = self._avatars.get(jid)
        av = _avatar(pop, 72, jid[0], ACCENT2, BG_CARD,
                     photo_data=photo_data, _photo_refs=self._photo_refs)
        av.pack(pady=(24, 12))

        tk.Label(pop, text=jid, fg=FG, bg=BG_CARD,
                 font=(FONT, 12, "bold")).pack()

        info_f = tk.Frame(pop, bg=BG_CARD)
        info_f.pack(fill="x", padx=24, pady=(16, 0))
        tk.Label(info_f, text="vCard bilgileri yükleniyor…",
                 fg=FG_DIM, bg=BG_CARD, font=(FONT, 8)).pack(anchor="w")

        def _show_vcard(vcard):
            if not pop.winfo_exists():
                return
            for w in info_f.winfo_children():
                w.destroy()
            if vcard is None:
                tk.Label(info_f, text="vCard bulunamadı",
                         fg=FG_DIM, bg=BG_CARD, font=(FONT, 8)).pack(anchor="w")
                return
            # Anahtarlar XMPPBot._get_vcard'ın ürettiği info sözlüğüyle eşleşir
            fields = [("Ad", "fn"), ("Takma Ad", "nickname"), ("E-posta", "email"),
                      ("Web", "url"), ("Doğum", "bday")]
            shown = 0
            for label, key in fields:
                val = str(vcard.get(key) or "")
                if val:
                    shown += 1
                    row = tk.Frame(info_f, bg=BG_CARD)
                    row.pack(fill="x", pady=2)
                    tk.Label(row, text=f"{label}:", fg=FG_DIM, bg=BG_CARD,
                             font=(FONT, 8, "bold"), width=10,
                             anchor="e").pack(side="left")
                    tk.Label(row, text=val, fg=FG, bg=BG_CARD,
                             font=(FONT, 9)).pack(side="left", padx=(8, 0))
            if not shown:
                tk.Label(info_f, text="vCard boş",
                         fg=FG_DIM, bg=BG_CARD, font=(FONT, 8)).pack(anchor="w")

        self.bot.get_vcard(jid, _show_vcard)

        btn_f = tk.Frame(pop, bg=BG_CARD)
        btn_f.pack(pady=(16, 16))
        ttk.Button(btn_f, text="Mesaj Gönder",
                   command=lambda: (self._load_chat(jid), pop.destroy())).pack(
                       side="left", padx=4)
        ttk.Button(btn_f, text="Engelle",
                   command=lambda: (self.bot.block_contact(jid),
                                    pop.destroy())).pack(side="left", padx=4)

    # ── Konum paylaşımı diyaloğu ─────────────────────────────────────────────
    def _location_dialog(self):
        """Konum paylaşım penceresi (ui/dialogs)."""
        def _publish(lat, lon, desc):
            if self.bot:
                self.bot.publish_location(lat, lon, desc)

        def _stop():
            if self.bot:
                self.bot.stop_location()

        _ui_presence.show_location(self.root, _publish, _stop)

    # ── OMEMO parmak izi doğrulama ─────────────────────────────────────────────
    def _omemo_fingerprint_dialog(self, jid=None):
        """Belirli bir kişinin OMEMO parmak izlerini göster."""
        if jid is None:
            jid = self.active
        if not jid or not self.bot:
            return
        pop = tk.Toplevel(self.root)
        pop.title(f"OMEMO Parmak İzleri — {jid}")
        pop.configure(bg=BG_CARD)
        pop.geometry("440x350")
        pop.transient(self.root)

        tk.Label(pop, text="OMEMO Parmak İzleri", fg=FG, bg=BG_CARD,
                 font=(FONT, 12, "bold")).pack(padx=16, pady=(16, 4), anchor="w")
        tk.Label(pop, text=jid, fg=FG_DIM, bg=BG_CARD,
                 font=(FONT, 9)).pack(padx=16, anchor="w")

        info_f = tk.Frame(pop, bg=BG_CARD)
        info_f.pack(fill="both", expand=True, padx=16, pady=12)
        tk.Label(info_f, text="Yükleniyor…",
                 fg=FG_DIM, bg=BG_CARD, font=(FONT, 8)).pack(anchor="w")

        def _show(data):
            if not pop.winfo_exists():
                return
            for w in info_f.winfo_children():
                w.destroy()
            if data is None or "error" in (data or {}):
                err = (data or {}).get("error", "Bilgi alınamadı")
                tk.Label(info_f, text=f"Hata: {err}",
                         fg=RED, bg=BG_CARD, font=(FONT, 9)).pack(anchor="w")
                return
            devices = data.get("devices", [])
            if not devices:
                tk.Label(info_f, text="Cihaz bulunamadı",
                         fg=FG_DIM, bg=BG_CARD, font=(FONT, 9)).pack(anchor="w")
                return
            for dev in devices:
                df = tk.Frame(info_f, bg=BG_HOVER, padx=12, pady=8)
                df.pack(fill="x", pady=3)
                active = "aktif" if dev.get("active") else "pasif"
                ac = ACCENT_G if dev.get("active") else FG_DIM
                tk.Label(df, text=f"Cihaz: {dev.get('device_id', '?')}  ({active})",
                         fg=ac, bg=BG_HOVER, font=(FONT, 8, "bold")).pack(anchor="w")
                fp = dev.get("fingerprint", "?")
                fp_var = tk.StringVar(value=fp)
                fp_e = ttk.Entry(df, textvariable=fp_var, font=(FONT, 7),
                                 state="readonly", style="Modern.TEntry")
                fp_e.pack(fill="x", pady=(4, 0))

        self.bot.get_omemo_fingerprints(jid, _show)

    # ── Kaybolan mesajlar ──────────────────────────────────────────────────────
    def _disappearing_dialog(self):
        """Mevcut sohbet için kaybolan mesaj TTL ayarla (ui/dialogs)."""
        if not self.active:
            return
        _ui_chat_options.show_disappearing(
            self.root,
            self._chat_ttl(self.active),
            self._set_disappearing_ttl)

    def _set_disappearing_ttl(self, ttl):
        """TTL'i uygula (aktif sohbet; dialog açıkken değişmiş olabilir)."""
        self._disappearing_ttl[self.active] = ttl

    def _chat_ttl(self, jid):
        """Kaybolan mesaj süresi: sohbete özel seçim, yoksa Ayarlar'daki varsayılan."""
        ttl = self._disappearing_ttl.get(jid)
        return getattr(self, "_default_disappear", 0) if ttl is None else ttl

    def _schedule_disappear(self, row, ttl):
        """TTL sonra mesaj balonunu sil."""
        if ttl <= 0:
            return
        def _remove():
            try:
                row.destroy()
                if row in self._bubble_widgets:
                    self._bubble_widgets.remove(row)
            except Exception:
                pass
        self.root.after(ttl * 1000, _remove)

    def _next_msg_uid(self):
        """[2J.b] Yeni mantıksal mesaj örneği için dahili benzersiz UID.

        Yalnız bellek-içi defterler (TTL sunum vadeleri) için; wire
        kimliklerine ve SQLite'a gitmez. Giriş yaşıyorsa UID de yaşar:
        re-render/rebase yeniden üretmez. Tembel kurulum bare çiftleri
        kırılmaz.
        """
        self._msg_inst_seq = getattr(self, "_msg_inst_seq", 0) + 1
        return self._msg_inst_seq

    def _entry_instance_uid(self, entry, fallback_mid=""):
        """[2J.b] History girişinin örnek kimliği: index 9'daki UID.

        UID'siz (eski/ithal) girişler mid'e düşer — 2I-B1 kapsamı korunur;
        bu girişler güvenle render edilir, TTL defteri mid kadar izole olur
        (aynı-sohbet duplicate-mid belgelenmiş rezidüeldir).
        """
        if entry is not None:
            if len(entry) > 9 and entry[9]:
                return entry[9]
            if len(entry) > 7:
                return entry[7] or fallback_mid
        return fallback_mid

    def _record_ttl_deadline(self, jid, uid, ttl):
        """[2I][B1][2J.b][2K] Mesaj için TEK etkili vade kaydet (sıfırlama yok).

        Vade teslim/gönderim anında alınır; defer (history modu) dahil her
        yolda kaydedilir. Re-render bu vadeyi asla yenilemez. Anahtar
        (jid, uid): uid girişin dahili örnek kimliğidir — aynı sohbetin
        duplicate-mid örnekleri bağımsız vade taşır. [2K] Süresi dolmuş vade
        mezar taşıdır: render yolları onu asla kaldırmaz, clear yolları
        kaldırır; setdefault eski (dolmuş) vadeyi korur — yeniden kayıt
        diriliş üretemez.
        """
        if not hasattr(self, "_ttl_deadlines"):
            self._ttl_deadlines = {}
        self._ttl_deadlines.setdefault((jid, uid), time.monotonic() + ttl)

    def _ttl_remaining(self, jid, uid, fallback_ttl):
        """[2I][B1][2J.b] Kayıtlı vadeden kalan süre; kayıt yoksa fallback."""
        deadlines = getattr(self, "_ttl_deadlines", None)
        key = (jid, uid) if uid else None
        if deadlines is not None and key is not None and key in deadlines:
            return max(0.0, deadlines[key] - time.monotonic())
        return fallback_ttl

    def _forget_ttl_deadlines(self, jid: str):
        """[2I][B1] JID geçmişi silinirken TTL sunum vadelerini de unut.

        Anahtarlar (jid, mid) olduğundan JID filtresi anahtarın kendisinden
        okunur; chats'e bağımlılık yoktur. Yalnız sunum üstverisidir;
        domain/DB'ye ve MAM generation mantığına dokunmaz.
        """
        deadlines = getattr(self, "_ttl_deadlines", None)
        if not deadlines:
            return
        for key in [k for k in deadlines if k[0] == jid]:
            deadlines.pop(key, None)

    def _forget_message_presentation_state(self, jid):
        """[2M-B1] JID'in mesaj-sunum üstverisini unut (tepki + önizleme).

        Alan/DB geçmişi silindiğinde onu tanımlayan sunum durumu da
        yaşamaz: _reactions/_my_reactions/_reply_map içinde İLK öğesi jid
        olan TÜM anahtarlar kaldırılır — ikinci öğenin tipinden (int uid
        ya da str mid) bağımsızdır. Diğer JID'ler korunur. Yalnız sunum:
        DB'ye dokunmaz; TTL defteri kendi yoluyla (_forget_ttl_deadlines)
        temizlenir. Filtre liste-kopya üzerinden yapılır (canlı anahtar
        görünümü üzerinde mutasyon yok).
        """
        for store in (getattr(self, "_reactions", None),
                      getattr(self, "_my_reactions", None),
                      getattr(self, "_reply_map", None)):
            if not store:
                continue
            for key in [k for k in store if k[0] == jid]:
                store.pop(key, None)

    # ── Sohbet dışa aktarma ─────────────────────────────────────────────────
    def _export_chat(self):
        """Mevcut sohbeti dosyaya aktar."""
        if not self.active:
            return
        from tkinter import filedialog
        history = self.chats.get(self.active, [])
        if not history:
            messagebox.showinfo("Dışa Aktar", "Sohbet geçmişi boş.", parent=self.root)
            return

        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Sohbet Dışa Aktar",
            defaultextension=".txt",
            filetypes=[("Metin", "*.txt"), ("JSON", "*.json"), ("Tümü", "*.*")],
            initialfile=f"chat_{self.active.replace('@', '_').replace('.', '_')}")
        if not path:
            return

        try:
            if path.endswith(".json"):
                import json
                data = []
                # _store tuple sırası: (sender, body, is_me, ts, tag, oob, encrypted)
                for entry in history:
                    data.append({
                        "sender": entry[0] if len(entry) > 0 else "",
                        "body": entry[1] if len(entry) > 1 else "",
                        "time": entry[3] if len(entry) > 3 else "",
                        "tag": entry[4] if len(entry) > 4 else "",
                    })
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(f"Sohbet: {self.active}\n")
                    f.write(f"Dışa aktarma: {datetime.now().isoformat()}\n")
                    f.write("=" * 60 + "\n\n")
                    for entry in history:
                        sender = entry[0] if len(entry) > 0 else ""
                        body = entry[1] if len(entry) > 1 else ""
                        ts = entry[3] if len(entry) > 3 else ""
                        f.write(f"[{ts}] {sender}: {body}\n")

            messagebox.showinfo("Dışa Aktar",
                f"Sohbet başarıyla dışa aktarıldı:\n{path}",
                parent=self.root)
        except Exception as e:
            messagebox.showerror("Hata", f"Dışa aktarma hatası: {e}",
                                 parent=self.root)

    # ── Ses mesajı ─────────────────────────────────────────────────────────────
    _VOICE_RATE = 44100
    _VOICE_CHANNELS = 1
    _VOICE_CHUNK = 1024
    _VOICE_MAX_SEC = 120  # maksimum kayıt süresi

    def _toggle_voice(self):
        """Ses kaydını başlat veya durdur (gönder)."""
        if (getattr(self, "_recording", False)
                and getattr(self, "_rec_mode", "voice") == "dictate"):
            # ⏹ dikteyi bitirir (yerel yazıya dökme; bağlantı gerekmez).
            self._stop_recording(send=True)
            return
        if not self.active or not self.bot:
            return
        if not _HAS_PYAUDIO:
            messagebox.showwarning("Ses Mesajı",
                "PyAudio yüklü değil.\npip install pyaudio",
                parent=self.root)
            return

        if self._recording:
            self._stop_recording(send=True)
        else:
            self._start_recording()

    def _start_recording(self, mode="voice"):
        """Kayıt başlat, overlay göster.

        mode="voice": bitince ses mesajı gönderilir; "dictate": bitince
        yerelde yazıya dökülüp giriş kutusuna eklenir (✨ Sesle yaz).
        """
        self._recording = True
        self._rec_mode = mode
        self._voice_frames = []
        self._voice_lock = threading.Lock()
        self._rec_start_time = time.time()
        self._rec_cancelled = False

        # — Kayıt overlay paneli —
        self._rec_overlay = tk.Frame(self.root, bg=BG_CARD)
        self._rec_overlay.place(relx=0.5, rely=1.0, anchor="s",
                                relwidth=0.6, height=56)

        inner = tk.Frame(self._rec_overlay, bg=BG_CARD)
        inner.pack(fill="both", expand=True, padx=10, pady=6)

        # Kırmızı titreyen kayıt noktası
        self._rec_dot = tk.Label(inner, text="🔴", font=(FONT, 10),
                                  fg=RED, bg=BG_CARD)
        self._rec_dot.pack(side="left")
        self._rec_dot_visible = True

        # Süre etiketi
        self._rec_timer_lbl = tk.Label(inner, text="0:00", font=(FONT, 11, "bold"),
                                        fg=FG, bg=BG_CARD)
        self._rec_timer_lbl.pack(side="left", padx=(6, 0))

        # Canlı ses seviyesi göstergesi (mini canvas)
        self._rec_level_canvas = tk.Canvas(inner, width=120, height=28,
                                            bg=BG_CARD, highlightthickness=0)
        self._rec_level_canvas.pack(side="left", padx=(12, 0))

        # İptal butonu
        cancel_btn = tk.Label(inner, text="✕ İptal", font=(FONT, 9),
                               fg=RED, bg=BG_CARD, cursor="hand2")
        cancel_btn.pack(side="right", padx=(10, 0))
        cancel_btn.bind("<Button-1>", lambda _: self._stop_recording(send=False))

        # Gönder (dikte modunda: yazıya dök) butonu
        send_btn = tk.Label(inner, text=("✍ Yazıya dök" if mode == "dictate"
                                         else "▶ Gönder"),
                            font=(FONT, 9, "bold"),
                            fg=ACCENT_G, bg=BG_CARD, cursor="hand2")
        send_btn.pack(side="right", padx=(10, 0))
        send_btn.bind("<Button-1>", lambda _: self._stop_recording(send=True))

        # Mikrofon butonunu güncelle
        self._mic_btn.config(text="⏹", fg=RED)

        # Kayıt thread'i
        def _record():
            pa = stream = None
            try:
                pa = pyaudio.PyAudio()
                stream = pa.open(format=pyaudio.paInt16,
                                 channels=self._VOICE_CHANNELS,
                                 rate=self._VOICE_RATE, input=True,
                                 frames_per_buffer=self._VOICE_CHUNK)
                while self._recording:
                    data = stream.read(self._VOICE_CHUNK,
                                       exception_on_overflow=False)
                    with self._voice_lock:
                        self._voice_frames.append(data)
                    # Ses seviyesini UI'a bildir
                    try:
                        samples = struct.unpack(f"<{len(data)//2}h", data)
                        peak = max(abs(s) for s in samples) if samples else 0
                        level = min(1.0, peak / 20000)
                        self._safe_after(0, self._update_rec_level, level)
                    except Exception:
                        pass
            except Exception as e:
                self._recording = False
                self._safe_after(0, lambda err=str(e): messagebox.showerror(
                    "Hata", f"Ses kaydı hatası: {err}", parent=self.root))
            finally:
                # Okuma/aygıt hatasında da PortAudio serbest bırakılmalı
                for close in ((stream.stop_stream if stream else None),
                              (stream.close if stream else None),
                              (pa.terminate if pa else None)):
                    if close is None:
                        continue
                    try:
                        close()
                    except Exception:
                        pass

        threading.Thread(target=_record, daemon=True).start()
        self._update_rec_timer()

    def _update_rec_timer(self):
        """Kayıt süresini ve titreyen noktayı güncelle."""
        if getattr(self, "_closing", False) or not self._recording:
            return
        elapsed = time.time() - self._rec_start_time
        mins = int(elapsed) // 60
        secs = int(elapsed) % 60
        try:
            self._rec_timer_lbl.config(text=f"{mins}:{secs:02d}")
            # Titreyen nokta
            self._rec_dot_visible = not self._rec_dot_visible
            self._rec_dot.config(fg=RED if self._rec_dot_visible else BG_CARD)
        except Exception:
            return
        # Maksimum süreyi aş → otomatik gönder
        if elapsed >= self._VOICE_MAX_SEC:
            self._stop_recording(send=True)
            return
        if not getattr(self, "_closing", False):
            self._after(500, self._update_rec_timer)

    def _update_rec_level(self, level: float):
        """Canlı ses seviyesi çubuklarını güncelle."""
        try:
            c = self._rec_level_canvas
            c.delete("all")
            bar_count = 20
            bar_w = 4
            gap = 2
            for i in range(bar_count):
                # Her çubuğa rastgele-ish yükseklik (sese bağlı)
                import random
                h = max(2, int(level * 24 * (0.4 + 0.6 * random.random())))
                x = i * (bar_w + gap)
                y = 14 - h // 2
                color = ACCENT_G if level > 0.5 else (ACCENT if level > 0.2 else FG_DIM)
                c.create_rectangle(x, y, x + bar_w, y + h, fill=color, outline="")
        except Exception:
            pass

    def _join_voice_frames(self) -> bytes:
        """Ses karelerinin kilitli anlık görüntüsünü birleştir.

        Kayıt thread'i her parçayı kilit altında ekler; GUI'nin join'i
        ile yarışan son parça kaybolmaz (P1-6a).
        """
        with self._voice_lock:
            return b"".join(self._voice_frames)

    def _stop_recording(self, send: bool = True):
        """Kaydı durdur. send=True → dosyayı gönder, False → iptal."""
        if not self._recording:
            return
        self._recording = False
        self._rec_cancelled = not send
        mode = getattr(self, "_rec_mode", "voice")
        self._rec_mode = "voice"

        # Overlay'ı kaldır
        try:
            self._rec_overlay.place_forget()
            self._rec_overlay.destroy()
        except Exception:
            pass

        # Buton sıfırla
        self._mic_btn.config(text="🎤", fg=FG_DIM)

        raw_audio = self._join_voice_frames()
        if not send or not raw_audio:
            return

        # Minimum süre kontrolü (0.5 sn)
        duration = time.time() - self._rec_start_time
        if duration < 0.5:
            return

        # İşleme + WAV yazımı worker'da — GUI donmaz (P1-5)
        target = self.active  # işlem sırasında sohbet değişse de hedef sabit
        if mode == "dictate":
            self._ai_transcribe_dictation(raw_audio, target)
            return
        threading.Thread(target=self._finalize_recording,
                         args=(raw_audio, target), daemon=True).start()

    def _finalize_recording(self, raw_audio, target):
        """Kaydı işle ve WAV yaz (worker thread); GUI'ye _safe_after ile dön.

        Sahiplik üreticide (2D): WAV yazılır yazılmaz tescillenir. Tescil
        reddedilirse (kapanış temizliği geçti) dosya silinir, gönderim ve
        UI planlanmaz. Callback'te artık tescil yoktur.
        """
        tmp_path = None
        try:
            processed = self._process_audio(raw_audio)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(self._VOICE_CHANNELS)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(self._VOICE_RATE)
                wf.writeframes(processed)
            if not self._remember_temp(tmp_path):
                # kapanış temizliği zaten geçti: dosyayı sil, gönderme
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                return
            self._safe_after(0, self._on_recording_ready, tmp_path, target)
        except Exception as e:
            # yarı kalmış tempfile sahipsiz kalmasın
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                    self._forget_temp(tmp_path)
                except OSError:
                    pass
            if not getattr(self, "_closing", False):
                self._safe_after(0, lambda err=str(e): messagebox.showerror(
                    "Hata", f"Ses mesajı gönderilemedi: {err}",
                    parent=self.root))

    def _on_recording_ready(self, wav_path, target):
        """WAV hazır — GUI thread'inde kaydet ve gönder.

        Tescil artık üreticide (`_finalize_recording`) yapıldığından burada
        kayıt yapılmaz; yalnız gönderim + gösterim.
        """
        mtype = "groupchat" if target in self.rooms else "chat"
        self.bot.send_file(target, wav_path, mtype)
        self._show_sent_voice(wav_path, target)

    @staticmethod
    def _process_audio(raw: bytes) -> bytes:
        """Ses verisini işle: noise gate + normalize + baş/son sessizlik kes."""
        n_samples = len(raw) // 2
        if n_samples == 0:
            return raw
        samples = list(struct.unpack(f"<{n_samples}h", raw))

        # — Noise gate: düşük genlik → sıfır —
        noise_threshold = 300  # ~-36dB
        for i in range(len(samples)):
            if abs(samples[i]) < noise_threshold:
                samples[i] = 0

        # — Baş ve son sessizliği kes —
        silence_threshold = 400
        start = 0
        end = len(samples) - 1
        while start < end and abs(samples[start]) < silence_threshold:
            start += 1
        while end > start and abs(samples[end]) < silence_threshold:
            end -= 1
        # Biraz marj bırak (50ms ~ 2205 sample @44100)
        margin = 2205
        start = max(0, start - margin)
        end = min(len(samples) - 1, end + margin)
        samples = samples[start:end + 1]

        if not samples:
            return raw

        # — Normalize: peak'i %90'a getir —
        peak = max(abs(s) for s in samples)
        if peak > 0:
            target = int(32767 * 0.90)
            factor = target / peak
            if factor > 1.0:  # sadece yükselt, kırpmak yok
                factor = min(factor, 8.0)  # maksimum 8x gain
                samples = [max(-32767, min(32767, int(s * factor)))
                           for s in samples]

        return struct.pack(f"<{len(samples)}h", *samples)

    def _show_sent_voice(self, wav_path, target=None):
        """Gönderilen ses mesajını dalga formu ile göster."""
        target = target or self.active
        ts = datetime.now().strftime("%H:%M")
        self._store(target, "🎤 Ses mesajı", tag="me", sender="Ben", is_me=True)
        if target != self.active:
            return  # işlem sırasında başka sohbete geçildi; kayıt yeterli
        row, bubble = _audio_ui.sent_voice_bubble(self.msg_frame,
                                                  _chat_theme())
        self._show_voice_waveform(bubble, wav_path, BG_ME)
        _audio_ui.finish_voice_bubble(bubble, _chat_theme(), ts)
        row._is_me = True
        row._body = "🎤 Ses mesajı"
        self._bubble_widgets.append(row)
        self._scroll_bottom()

    def _reaction_key(self, mid):
        """[2M] Tepki sunum anahtarı: (aktif-jid, mid).

        Tepki wire kimliği mid-scoped olduğundan içsel UID peer niyeti
        TEMSİL ETMEZ; kapsamlandırma JID ile yapılır.
        """
        return (getattr(self, "active", ""), mid)

    def _refresh_reaction_rows(self, jid, mid):
        """[2M] Policy C: (jid, mid) tepki durumu o JID'in aktif render'ında
        mid'li TÜM satırlara uygulanır.

        Canlı güncelleme ile reload her zaman aynı sunumu gösterir; aynı
        sohbetteki duplicate-mid wire belirsizliği tutarlı biçimde
        sergilenir (ilk-satır-only tutarsızlığı kapanır, hiçbir olay
        sessizce düşmez). Yalnız aktif pencere: pasif sohbetin satırları
        zaten görünmez, alakasız sohbet taranmaz.
        """
        if not mid or getattr(self, "active", "") != jid:
            return
        # Guard'lı okuma: bare test çiftleri bu haritaları taşımaz (2K kalıbı)
        reactions = getattr(self, "_reactions", {}).get((jid, mid), {})
        for row in list(getattr(self, "_bubble_widgets", [])):
            if getattr(row, "_mid", "") == mid:
                self._render_reactions(row, reactions)

    def _render_reactions(self, row, reactions: dict):
        """Tepki çipleri (ui/chat/reactions) + mevcut autoscroll davranışı."""
        mid = getattr(row, "_mid", "")
        mine = (self._my_reactions.get(self._reaction_key(mid), set())
                if mid else set())
        rf = _reactions_ui.render_reactions(
            row, reactions, mine, theme=_chat_theme(),
            on_toggle=lambda em: self._toggle_reaction(mid, em),
            on_details=lambda em: self._reaction_details_dialog(mid, em),
            on_reply=lambda: self._set_reply(
                getattr(row, "_mid", ""), getattr(row, "_body", ""),
                getattr(row, "_sender", "")),
            on_add=lambda: self._show_emoji_picker(mid),
            tooltip_fn=_reaction_tooltip, add_tooltip=_add_tooltip)
        if rf is not None:
            self._scroll_bottom()

    def _toggle_reaction(self, mid, emoji):
        """Kendi tepkimi aç/kapat; tam kümeyi gönder (XEP-0444)."""
        if not (mid and self.active and self.bot):
            return
        key = self._reaction_key(mid)
        new_set = _toggle_reaction_set(self._my_reactions.get(key), emoji)
        if new_set:
            self._my_reactions[key] = new_set
        else:
            self._my_reactions.pop(key, None)
        mtype = "groupchat" if self.active in self.rooms else "chat"
        self.bot.send_reaction(self.active, mid, sorted(new_set), mtype)
        # Yerel iyimser güncelleme — [2M] (jid, mid) kapsamlı
        store = self._reactions.setdefault(key, {})
        me = "Ben"
        for em in list(store.keys()):
            senders = store[em]
            if me in senders:
                senders.remove(me)
            if not senders:
                del store[em]
        for em in new_set:
            store.setdefault(em, []).append(me)
        if not store:
            self._reactions.pop(key, None)
        self._persist_my_reactions(mid)
        # [2M] Policy C: o JID'in aktif satırlarının TAMAMI aynı sunuma
        # yakınsar (eski davranış yalnız ilk eşleşen satırı güncelliyordu).
        self._refresh_reaction_rows(self.active, mid)

    def _persist_my_reactions(self, mid):
        """Kendi tepkilerimi SQLite'a yaz (yeniden başlatınca da geçerli)."""
        target = self.active
        if not target:
            return
        _db_clear_my_reactions(target, mid)
        for em in sorted(self._my_reactions.get(self._reaction_key(mid),
                                                set())):
            _db_save_reaction(target, mid, em, "Ben", True)

    def _reaction_details_dialog(self, mid, emoji: str | None = None):
        """Tepki verenleri listeleyen pencere (ui/dialogs/simple)."""
        _ui_simple.show_reaction_details(
            self.root, self._reactions.get(self._reaction_key(mid), {}), emoji)

    # ── Mesaj saklama ─────────────────────────────────────────────────────────
    def _store(self, target, body, tag="them", sender="", is_me=None,
               oob="", encrypted=False, mid="", local_path="", reply_to=None):
        ts = datetime.now().strftime("%H:%M")
        if is_me is None:
            is_me = (tag == "me")
        # Tuple sırası: (sender, body, is_me, ts, tag, oob, encrypted, mid,
        # local_path, inst_uid) — [2J.b] inst_uid: dahili örnek kimliği,
        # yalnız bellek-içi (TTL defteri); wire'a ve SQLite'a gitmez.
        self.chats.setdefault(target, []).append(
            (sender, body, is_me, ts, tag, oob, encrypted, mid, local_path,
             self._next_msg_uid()))
        # [2M] Önizleme sahipliği: (target, örnek-UID) — store az önce
        # uid'li girişi ekledi; bu kayıt tek sahiplik kaynağıdır.
        hist = self.chats.get(target) or []
        self._remember_reply(
            target, hist[-1][9] if hist else "", reply_to)
        # SQLite'a da kaydet
        rep = reply_to or {}
        _db_store_msg(target, sender, body, is_me, ts, tag, oob, encrypted, mid,
                      local_path, rep.get("id", ""), rep.get("sender", ""),
                      rep.get("body", ""))
        if is_me:
            self._ai_drafts_forget(target)      # yanıtlandı: taslak düşer

    # ── Oda hafızası ─────────────────────────────────────────────────────────
    def _save_room(self, room):
        """Katılınan odayı config'e kaydet."""
        cfg = _load_config()
        rooms = cfg.setdefault("rooms", {})
        nick = self.my_nick.get(room, self.jid.split("@")[0])
        rooms[room] = {"nick": nick}
        _save_config(cfg)

    def _remove_room(self, room):
        """Ayrılınan odayı config'den sil."""
        cfg = _load_config()
        rooms = cfg.get("rooms", {})
        if room in rooms:
            del rooms[room]
            _save_config(cfg)

    def _load_pgp_keymap(self):
        """Kayıtlı PGP JID→KeyID eşleştirmelerini XEP-0027'ye yükle."""
        try:
            cfg = _load_config()
            pgp_map = cfg.get("pgp_keymap", {})
            if pgp_map:
                xep = _get_xep(self.bot, "xep_0027")
                for jid_str, keyid in pgp_map.items():
                    xep.set_keyid(jid=jid_str, keyid=keyid)
        except Exception:
            pass

    def _fetch_avatars(self):
        """Kendi ve kişilerin avatarlarını arka planda yükle."""
        if not HAS_PIL:
            return
        # Önce cache'den yükle
        for bare in [self.jid] + list(self._contacts.keys()):
            cached = _load_avatar_cache(bare)
            if cached:
                self._avatars[bare] = cached
        # Sidebar kendi avatarını hemen güncelle
        self._update_sidebar_avatar()
        # Ağdan yükle
        all_jids = list(self._contacts.keys())
        all_jids.insert(0, self.jid)
        self.bot.fetch_all_avatars(all_jids, self._on_avatar_received)

    def _on_avatar_received(self, bare_jid, data):
        """Avatar verisi geldiğinde çağrılır (XMPP thread'inden)."""
        if data:
            # Veriyi GUI thread'inde sözlüğe yaz + arayüzü güncelle
            self._safe_after(0, self._on_avatar_update, bare_jid, data)

    def _on_avatar_update(self, bare_jid, data=None):
        """Avatar yüklendikten sonra GUI'yi güncelle."""
        if data is not None:
            self._avatars[bare_jid] = data
        # Kendi avatarımız güncellendiyse sidebar'ı güncelle
        if bare_jid == self.jid:
            self._update_sidebar_avatar()
        # Aktif sohbetin avatarıysa header'ı güncelle
        if self.active and bare_jid == self.active:
            self._load_chat(self.active)

    def _save_contact_groups(self, groups):
        """Kişi gruplarını config'e yaz."""
        cfg = _load_config()
        cfg["contact_groups"] = groups
        _save_config(cfg)

    def _restore_avatar(self, jid, old_data):
        """Avatar yayını başarısız olunca eski hale döndür."""
        if old_data is None:
            self._avatars.pop(jid, None)
            try:
                path = _avatar_cache_path(jid)
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                _log.warning("Avatar önbelleği silinemedi: %s", jid,
                             exc_info=True)
        else:
            self._avatars[jid] = old_data
            _save_avatar_cache(jid, old_data)
        self._update_sidebar_avatar()

    def _update_sidebar_avatar(self):
        """Sidebar'daki kendi profil avatarını güncelle (ui/sidebar)."""
        if not hasattr(self, "_sidebar_avatar"):
            return
        _ui_sidebar.update_sidebar_avatar(
            self._sidebar_avatar, self.jid, self._avatars.get(self.jid),
            self._photo_refs)

    def _rejoin_saved_rooms(self):
        """Kayıtlı odalara otomatik katıl (auto_rejoin ayarına bağlı)."""
        cfg = _load_config()
        if not cfg.get("auto_rejoin", True):
            return
        rooms = cfg.get("rooms", {})
        for room, info in rooms.items():
            nick = info.get("nick", self.jid.split("@")[0])
            self.my_nick[room] = nick
            self.bot.join_room(room, nick)

    def _load_chat(self, target):
        self.active = target
        self._ai_complete_hide()
        # Typing indicator'ı yeni aktif sohbete göre tazele
        self._refresh_typing_indicator()
        # AI özeti için açılış anındaki okunmamış sayısını hatırla
        seen = getattr(self, "_ai_unread_at_open", None)
        if seen is None:
            seen = self._ai_unread_at_open = {}
        seen[target] = self._unread_counts.get(target, 0)
        # Okunmamış sayacı sıfırla
        if self._unread_counts.get(target, 0) > 0:
            self._unread_counts[target] = 0
            self._refresh_contacts()
            total = sum(self._unread_counts.values())
            badge = f" [{total}]" if total > 0 else ""
            self.root.title(f"XMPP — {self.jid}{badge}")
        # Kısa isim göster
        short = target.split("@")[0] if "@" in target else target
        self.chat_title.config(text=short)
        # Oda konusunu göster
        subj = self._room_subjects.get(target, "")
        if subj and target in self.rooms:
            short_subj = (subj[:60] + "…") if len(subj) > 60 else subj
            self._chat_subject.config(text=f"📌 {short_subj}")
            self._chat_subject.pack(anchor="w")
        else:
            self._chat_subject.config(text="")
            self._chat_subject.pack_forget()
        # Başlık avatarını güncelle
        self._hdr_avatar.delete("all")
        avatar_data = self._avatars.get(target)
        if avatar_data and HAS_PIL:
            try:
                img = Image.open(io.BytesIO(avatar_data))
                img = img.resize((34, 34), Image.LANCZOS)
                from PIL import ImageDraw
                mask = Image.new("L", (34, 34), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, 34, 34), fill=255)
                img.putalpha(mask)
                photo = ImageTk.PhotoImage(img)
                self._hdr_avatar.create_oval(1, 1, 37, 37, fill="",
                                              outline=BORDER, width=2)
                self._hdr_avatar.create_image(19, 19, image=photo)
                self._hdr_avatar._photo = photo
                self._photo_refs.append(photo)
            except Exception:
                avatar_data = None
        if not avatar_data or not HAS_PIL:
            self._hdr_avatar.create_oval(1, 1, 37, 37, fill="",
                                          outline=BORDER, width=2)
            self._hdr_avatar.create_oval(4, 4, 34, 34, fill=ACCENT2, outline="")
            self._hdr_avatar.create_text(19, 19, text=short[0].upper(),
                                          fill=FG_ME, font=(FONT, 12, "bold"))
        self._chat_shell.show_chat()
        # [2F] Pencere durumu: her JID kendi görünüm modunu saklar (L)
        self._ensure_history_state()
        # Tarih ayırıcı durumu yeni sohbet render'ından ÖNCE sıfırlanmalı
        self._last_date_label = ""
        history = self.chats.get(target, [])
        if history:
            if self._history_view_mode.get(target, "latest") == "history":
                # Kayıtlı mantıksal viewport korunur; pending sayacı durur (L)
                self._render_bounded(
                    target, self._history_start.get(target, 0),
                    scroll_top=True)
            else:
                # latest: en yeni K'ya snap; yeni mesaj sayacı sıfırlanır (D/L)
                self._history_view_mode[target] = "latest"
                self._history_pending[target] = 0
                self._render_bounded(
                    target,
                    max(0, len(history) - self._HISTORY_WINDOW_SIZE))
        else:
            self._history_view_mode[target] = "latest"
            self._history_start[target] = 0
            self._history_pending[target] = 0
            self._clear_chat()
            # Geçmiş yoksa MAM'dan çek (oda dahil: oda arşivi odadadır).
            # Initial-MAM tespiti yalnız niyet iledir; niyet
            # _load_mam_history içinde o isteğin token'ına
            # bağlanır — _history_start varlığı belirleyici DEĞİLDİR (D).
            if self.bot:
                self._load_mam_history()
        self._update_history_nav(target)
        # Bu sohbetin şifreleme modunu geri yükle
        saved_enc = self._chat_encryption(target)
        self._encryption_mode.set(saved_enc)
        self._update_enc_btn(silent=True)
        # Yanıt modunu sıfırla
        self._cancel_reply()
        # Pin bar güncelle
        self._update_pin_bar()
        # Arka plan uygula
        if self._chat_wallpaper:
            self._apply_wallpaper()

    def _render_history_entry(self, entry):
        """Tek history tuple'ını mevcut _append semantiğiyle çiz.

        [B1] TTL vade anahtarı (self.active, mid): _render_bounded'ın tüm
        çağıranları ya aktif hedeflidir ya da active == jid guard'lıdır;
        render her zaman aktif sohbet bağlamındadır.
        """
        sender, body, is_me, ts, tag = entry[:5]
        oob = entry[5] if len(entry) > 5 else ""
        enc = entry[6] if len(entry) > 6 else False
        mid = entry[7] if len(entry) > 7 else ""
        local_path = entry[8] if len(entry) > 8 else ""
        # [2M] Yanıt önizleme sahipliği: (jid, örnek-kimlik) — güncel
        # girişlerde uid, eski girişlerde mid. Global mid-only fallback YOK:
        # aynı-mid çapraz-sohbet ve aynı-sohbet duplicate-mid önizleme
        # bulaşması kapanır.
        inst_uid = self._entry_instance_uid(entry)
        reply_to = (self._reply_map.get((self.active, inst_uid or mid))
                    if mid else None)
        # [2I][B1][2J.b][2K] TTL vadesi: geçerli mesaj yalnız KALAN süre
        # kadar yaşar (re-render TTL sıfırlamaz); süresi DOLMUŞ örnek gizli
        # kalır. Anahtar (self.active, örnek-uid): render her zaman aktif
        # sohbet bağlamındadır; vade çizilen girişin örnek kimliğiyle izole
        # edilir (eski girişlerde uid = mid). active yalnız vade metadata'sı
        # mevcutken okunur (bare test çiftleri bu öznitelik taşımaz).
        deadlines = getattr(self, "_ttl_deadlines", None)
        deadline = None
        if deadlines:
            # [2L-B1] Kimlik örnek-UID'dir; mid ŞART DEĞİLDİR (mid="" olan
            # güncel girişler — örn. sekmenin kendi gönderimi — TTL'lidir).
            # Eski girişler mid fallback'ine düşer (_entry_instance_uid);
            # kimlik çözülemeyen (uid="") girişler TTL'siz normal çizilir.
            key = (self.active, inst_uid)
            deadline = deadlines.get(key) if key[1] else None
            if deadline is not None and deadline - time.monotonic() <= 0:
                # [2K] Mezar taşı: dolmuş vade POP EDİLMEZ. Kalmaya devam
                # eden süresi-dolmuş vade, alan girişi var oldukça kalıcı
                # görsel süre-dolmasıdır; pop etmek sonraki render'larda
                # dirilişe yol açardı. Vade yalnız clear yollarında
                # (_forget_ttl_deadlines / clear-all) kalkar.
                # [2O] Süre-dolma temizliği: bu kimliğe işaret eden
                # ters-aliaslar unutulur (bayat alias yeni mesajı susturmaz).
                self._mam_alias_forget_identity(self.active, mid)
                return
        row = self._append(body, tag, sender=sender, is_me=is_me,
                           time_str=ts, oob=oob, encrypted=enc,
                           local_path=local_path, mid=mid, reply_to=reply_to)
        if deadline is not None and row is not None:
            self._schedule_disappear(row, deadline - time.monotonic())

    # ── [2F] Geçmiş penceresi: state + sınırlı render + gezinme ──────────────
    def _ensure_history_state(self):
        """[2F] Pencere durum sözlüklerini tembel tek-seferlik kur (B)."""
        if not hasattr(self, "_history_start"):
            self._history_start = {}
        if not hasattr(self, "_history_view_mode"):
            self._history_view_mode = {}
        if not hasattr(self, "_history_pending"):
            self._history_pending = {}
        if not hasattr(self, "_history_mam_intent"):
            self._history_mam_intent = {}

    def _reset_history_ui_state(self, jid: str):
        """[2F] Domain geçmişi silinen JID'in pencere durumunu sıfırla (M).

        [2F-Blocker] Bayat MAM gezinme üstverisi de temizlenir: aksi hâlde
        clear sonrası _mam_has_more/_mam_oldest yanıltıcı Daha eski durumu
        gösterir. _mam_gen burada DOKUNULMAZ — uçuştaki sonuçları
        düşüren generation bump'ı clear yollarının kendi işidir.
        """
        self._ensure_history_state()
        self._history_start.pop(jid, None)
        self._history_view_mode.pop(jid, None)
        self._history_pending.pop(jid, None)
        self._history_mam_intent.pop(jid, None)
        getattr(self, "_mam_has_more", {}).pop(jid, None)
        getattr(self, "_mam_oldest", {}).pop(jid, None)

    def _history_window_slice(self, target: str, start: int | None = None):
        """[2F] (pencere, start, end): K ile sınırlı dilim, güvenli clamp (C).

        Her tam geçmiş render'ı BU yardımcıdan geçer; K'sız hist[start:]
        kullanımı yoktur (INV I1). Domain listesi kopyalanır, yazılmaz (I8).
        """
        hist = self.chats.get(target, [])
        if start is None:
            start = self._history_start.get(target, 0)
        start = max(0, min(int(start), len(hist)))
        end = min(len(hist), start + self._HISTORY_WINDOW_SIZE)
        return hist[start:end], start, end

    def _render_bounded(self, target: str, start: int,
                        scroll_top: bool = False) -> int:
        """[2F] Tek tam-render yolu: clear + K-sınırlı dilim (INV I1).

        Returns: render edilen mesaj sayısı (<= _HISTORY_WINDOW_SIZE).
        """
        self._ensure_history_state()
        window, s, _end = self._history_window_slice(target, start)
        self._history_start[target] = s
        self._clear_chat()
        # Tarih ayırıcı durumu pencere render'ından önce sıfırlanmalı (V-4)
        self._last_date_label = ""
        _history_ui.render_history(window, self._render_history_entry)
        self._update_history_nav(target)
        if scroll_top:
            self._history_scroll_top()
        return len(window)

    def _rebase_latest_window(self, target: str):
        """[2F] HARD_CAP aşımı: transyan taşma olmadan en yeni K'ya rebase (E).

        251'inci widget önce oluşturulmaz; clear + sınırlı render ile aktif
        birim sayısı her an <= _HISTORY_LIVE_HARD_CAP kalır (INV I2).
        """
        self._ensure_history_state()
        hist = self.chats.get(target, [])
        self._history_view_mode[target] = "latest"
        self._history_pending[target] = 0
        self._render_bounded(
            target, max(0, len(hist) - self._HISTORY_WINDOW_SIZE))

    def _live_view_action(self, target: str) -> str:
        """[2F] Store sonrası canlı teslim kararı (E/F): append|rebase|defer.

        - latest + active_count <= HARD_CAP → append (sonuç asla CAP+1 olmaz)
        - latest + taşma                    → rebase
        - history                           → defer: 0 render, pending++, I3
        """
        self._ensure_history_state()
        if self._history_view_mode.get(target, "latest") == "history":
            self._history_pending[target] = \
                self._history_pending.get(target, 0) + 1
            self._update_history_nav(target)
            return "defer"
        hist = getattr(self, "chats", {}).get(target, [])
        active_count = len(hist) - self._history_start.get(target, 0)
        if active_count <= self._HISTORY_LIVE_HARD_CAP:
            return "append"
        return "rebase"

    def _deliver_live(self, target: str, append_fn) -> str:
        """[2F] Store sonrası tek canlı teslim noktası (E/F).

        append_fn yalnız "append" aksiyonunda çağrılır; rebase'de yeni mesaj
        zaten render edilen pencerenin içindedir (çift widget oluşmaz).
        """
        action = self._live_view_action(target)
        if action == "append":
            append_fn()
        elif action == "rebase":
            self._rebase_latest_window(target)
        return action

    def _note_inactive_live(self, target: str):
        """[2F] Pasif sohbete gelen mesaj: history modunda pending artır (F).

        latest kaydı için pending gerekmez; yeniden açılışta en yeni K'ya
        snap yapılır. UI render YOK; gösterge yeniden açılışta görünür.
        """
        if getattr(self, "_history_view_mode", {}).get(target) == "history":
            self._ensure_history_state()
            self._history_pending[target] = \
                self._history_pending.get(target, 0) + 1

    def _history_scroll_top(self):
        """[2F] Deterministik üst kaydırma (I: history modu top policy).

        Shell her msg_frame Configure'unda ~10 ms sonra en alta döner;
        üst kaydırma 60 ms sonra teyit edilerek üstünlük sağlanır.
        """
        canvas = getattr(self, "chat_canvas", None)
        after = getattr(getattr(self, "root", None), "after", None)
        if canvas is None or after is None:
            return
        canvas.update_idletasks()
        canvas.yview_moveto(0.0)
        after(60, lambda: canvas.yview_moveto(0.0))

    def _ensure_history_nav(self):
        """[2F] Sabit gezinme çubuğu (tek örnek; mesaj başına widget YOK, O)."""
        if getattr(self, "_nav_bar", None) is not None:
            return
        shell = getattr(self, "_chat_shell", None)
        area = getattr(shell, "_chat_area", None)
        if area is None:
            return
        self._nav_bar = _history_ui.build_history_nav(
            area, _chat_theme(),
            on_older=self._on_history_older,
            on_latest=self._on_history_latest)

    def _update_history_nav(self, target: str):
        """[2F] Gezinme çubuğu senkronu: durum → sunum (widget sayısı sabit)."""
        self._ensure_history_nav()
        bar = getattr(self, "_nav_bar", None)
        if bar is None:
            return
        mode = self._history_view_mode.get(target, "latest")
        _history_ui.update_history_nav(
            bar,
            show_older=(self._history_start.get(target, 0) > 0
                        or self._mam_has_more.get(target, False)),
            show_latest=(mode == "history"),
            pending=(self._history_pending.get(target, 0)
                     if mode == "history" else 0))

    def _on_history_older(self):
        """[2F] ⬆ Daha eski: yerel pencere kaydırma ya da explicit older MAM (I)."""
        target = self.active
        if not target:
            return
        self._ensure_history_state()
        start = self._history_start.get(target, 0)
        if start > 0:
            self._history_view_mode[target] = "history"
            self._render_bounded(
                target, max(0, start - self._HISTORY_WINDOW_SIZE),
                scroll_top=True)
        elif self._mam_has_more.get(target, False):
            # Niyet _load_older_mam içinde "older" olarak kurulur; sonuç
            # _adjust_history_window_for_mam'da değerlendirilir.
            self._load_older_mam()

    def _on_history_latest(self):
        """[2F] ↓ En yeni / Yeni mesajlar: sınırlı K re-render + en alta (K)."""
        target = self.active
        if not target:
            return
        self._ensure_history_state()
        self._history_view_mode[target] = "latest"
        self._history_pending[target] = 0
        self._render_bounded(
            target,
            max(0, len(self.chats.get(target, [])) - self._HISTORY_WINDOW_SIZE))
        self._scroll_bottom()

    def _adjust_history_window_for_mam(self, jid: str, added: int,
                                       intent: str | None):
        """[2F] MAM prepend sonrası pencere uyumu (G/H/J).

        - initial: pencere en yeni K'ya çekilir; aktifse sınırlı render (H).
        - older + aktif: start = max(0, M - K), sınırlı render, üst kaydırma (J).
        - pasif prepend / older + pasif: saved viewport korunur (start += M),
          otomatik render YOK (INV I4/I5).
        - Pencere durumu hiç yoksa (2F öncesi çiftler): eski davranış —
          aktifse yeniden çiz.
        """
        self._ensure_history_state()
        if intent == "initial":
            self._history_view_mode[jid] = "latest"
            self._history_pending[jid] = 0
            self._history_start[jid] = max(
                0, len(self.chats.get(jid, [])) - self._HISTORY_WINDOW_SIZE)
            if self.active == jid:
                self._render_bounded(jid, self._history_start[jid])
                self._scroll_bottom()
            return
        if intent == "older" and self.active == jid:
            self._history_view_mode[jid] = "history"
            self._render_bounded(
                jid, max(0, added - self._HISTORY_WINDOW_SIZE),
                scroll_top=True)
            return
        if jid in self._history_view_mode:
            # Pasif prepend / older-inactive: her eski mantıksal mesaj M kadar
            # sağa kaydı; kayıtlı viewport indeksleri de aynı kadar kayar (G).
            if jid in self._history_start:
                self._history_start[jid] += added
            return
        if self.active == jid:
            self._load_chat(jid)

    # ── Kişi listesi ─────────────────────────────────────────────────────────
    # ── Kişi hover yardımcıları ──
    def _contact_hover_start(self, event):
        self._hover_timer = None

    def _contact_hover_end(self, event):
        if hasattr(self, '_hover_timer') and self._hover_timer:
            self.root.after_cancel(self._hover_timer)
        if hasattr(self, '_contact_card_pop') and self._contact_card_pop:
            try:
                self._contact_card_pop.destroy()
            except Exception:
                pass
            self._contact_card_pop = None

    def _contact_hover_motion(self, event):
        if hasattr(self, '_hover_timer') and self._hover_timer:
            self.root.after_cancel(self._hover_timer)
        idx = self.contact_list.nearest(event.y)
        if 0 <= idx < len(self._contact_jids):
            jid = self._contact_jids[idx]
            self._hover_timer = self.root.after(
                800, lambda: self._show_contact_card(event, jid))

    def _sidebar_query_view(self):
        search_var = getattr(self, "_sidebar_search_var", None)
        query = search_var.get().strip() if search_var is not None else ""
        search = getattr(self, "_sidebar_search", None)
        if search is not None and getattr(search, "_showing_ph", False):
            query = ""
        view_var = getattr(self, "_sidebar_filter_var", None)
        view = view_var.get() if view_var is not None else "all"
        return query, view

    @staticmethod
    def _sidebar_selected_jid(widget, jids):
        selection = widget.curselection()
        if selection and 0 <= selection[0] < len(jids):
            return jids[selection[0]]
        return None

    @staticmethod
    def _restore_sidebar_selection(widget, jids, selected):
        if selected in jids:
            index = jids.index(selected)
            widget.selection_set(index)
            widget.activate(index)

    def _refresh_contacts(self):
        if getattr(self, "_closing", False):
            return
        query, view = self._sidebar_query_view()
        counts = getattr(self, "_unread_counts", {})
        selected = self._sidebar_selected_jid(
            self.contact_list, getattr(self, "_contact_jids", []))
        self._contact_jids = _ui_sidebar.ordered_contact_jids(
            self._contacts, self.presence, self._pinned_chats, query,
            unread_counts=counts, view=view)
        _ui_sidebar.render_contacts(
            self.contact_list, self._contacts, self.presence,
            self._pinned_chats, counts, self._contact_jids)
        self._restore_sidebar_selection(self.contact_list, self._contact_jids, selected)
        if getattr(self, "room_list", None) is not None:
            self._refresh_rooms()

    def _refresh_rooms(self):
        query, view = self._sidebar_query_view()
        counts = getattr(self, "_unread_counts", {})
        selected = self._sidebar_selected_jid(
            self.room_list, getattr(self, "_room_jids", []))
        self._room_jids = _ui_sidebar.filtered_rooms(
            self.rooms, query, pinned=self._pinned_chats, unread_counts=counts, view=view)
        _ui_sidebar.render_rooms(self.room_list, self._room_jids,
                                 pinned=self._pinned_chats, unread_counts=counts)
        self._restore_sidebar_selection(self.room_list, self._room_jids, selected)

    def _filter_sidebar(self):
        """Arama ve görünüm filtresini kişi/oda güncellemelerinde birlikte koru."""
        # Liste widget'ları henüz kurulmadıysa sessizce çık (init sırası)
        if getattr(self, "contact_list", None) is None \
                or getattr(self, "room_list", None) is None:
            return
        self._refresh_contacts()

    # ── Seçim ─────────────────────────────────────────────────────────────────
    def _on_contact_select(self, _):
        sel = self.contact_list.curselection()
        if sel and sel[0] < len(self._contact_jids):
            self._hide_members()
            self._load_chat(self._contact_jids[sel[0]])

    def _on_room_select(self, _):
        sel = self.room_list.curselection()
        if sel and sel[0] < len(self._room_jids):
            room = self._room_jids[sel[0]]
            self._load_chat(room)
            self._show_members(room)

    def _show_members(self, room):
        self._members_panel.grid(row=0, column=2, sticky="nsew",
                                 padx=(0, 0), pady=0)
        self._members_panel.grid_propagate(False)
        self._refresh_members(room)

    def _hide_members(self):
        self._members_panel.grid_remove()

    def _refresh_members(self, room):
        """KATILIMCILAR listesini çiz (ui/sidebar)."""
        self._member_index_map = _ui_sidebar.render_members(
            self.members_list, self._members_label,
            self.room_members.get(room, {}))

    # ── Üye bağlam menüsü ────────────────────────────────────────────────────
    def _member_context_menu(self, event):
        if not self.active or self.active not in self.rooms:
            return
        idx = self.members_list.nearest(event.y)
        nick = self._member_index_map.get(idx)
        if not nick:
            return
        room = self.active
        my_nick = self.my_nick.get(room, self.jid.split("@")[0])
        if nick == my_nick:
            return  # kendi üzerinde işlem yok

        mbrs = self.room_members.get(room, {})
        my_info = mbrs.get(my_nick, {})
        target_info = mbrs.get(nick, {})
        t_affil = target_info.get("affil", "")
        t_role = target_info.get("role", "")

        _AFFIL_RANK = {"owner": 0, "admin": 1, "member": 2, "none": 3, "": 3}
        can_admin = _AFFIL_RANK.get(my_info.get("affil", ""), 3) <= 1
        can_mod = my_info.get("role", "") == "moderator" or can_admin

        _ui_rooms_menu.show_member_menu(
            self.root, nick, t_affil, t_role, can_mod, can_admin,
            lambda: self._start_private_muc_chat(room, nick),
            lambda: self._kick_member(room, nick),
            lambda role: self.bot.set_user_role(room, nick, role),
            lambda: self._ban_member(room, nick),
            lambda affil: self._set_member_affiliation(room, nick, affil),
            event.x_root, event.y_root)

    def _start_private_muc_chat(self, room, nick):
        """MUC'taki birine özel mesaj başlat."""
        pm_jid = f"{room}/{nick}"
        self._load_chat(pm_jid)

    def _kick_member(self, room, nick):
        reason = simpledialog.askstring(
            "Kick", f"{nick} atılsın mı?\nSebep (opsiyonel):",
            parent=self.root)
        if reason is None:  # İptal
            return
        self.bot.kick_user(room, nick, reason.strip())

    def _ban_member(self, room, nick):
        # Ban için JID gerekli — muc presence'tan almayı dene
        reason = simpledialog.askstring(
            "Ban", f"{nick} yasaklansın mı?\nSebep (opsiyonel):",
            parent=self.root)
        if reason is None:
            return
        # JID'yi bulmaya çalış (xep_0045'in getJidProperty'si)
        try:
            muc = _get_xep(self.bot, "xep_0045")
            jid = muc.get_jid_property(room, nick, "jid")
            if jid:
                self.bot.ban_user(room, str(jid), reason)
                return
        except Exception:
            pass
        # JID bulunamazsa kullanıcıdan iste
        jid_str = simpledialog.askstring(
            "Ban", f"{nick} için JID girin:",
            parent=self.root)
        if jid_str:
            self.bot.ban_user(room, jid_str, reason)

    def _set_member_affiliation(self, room, nick, affiliation):
        try:
            muc = _get_xep(self.bot, "xep_0045")
            jid = muc.get_jid_property(room, nick, "jid")
            if jid:
                self.bot.set_user_affiliation(room, str(jid), affiliation)
                return
        except Exception:
            pass
        jid_str = simpledialog.askstring(
            "Yetki Değiştir", f"{nick} için JID girin:",
            parent=self.root)
        if jid_str:
            self.bot.set_user_affiliation(room, jid_str, affiliation)

    # ── Bağlam menüleri ───────────────────────────────────────────────────────
    def _contact_context_menu(self, event):
        idx = self.contact_list.nearest(event.y)
        if idx < 0 or idx >= len(self._contact_jids):
            return
        self.contact_list.selection_set(idx)
        jid = self._contact_jids[idx]
        _ui_sidebar.show_contact_menu(
            self.root, jid, jid in self._pinned_chats,
            lambda: self._load_chat(jid),
            lambda: self._toggle_pin_chat(jid),
            lambda: self._common_groups_dialog(jid),
            lambda: self._remove_contact(jid),
            event.x_root, event.y_root)

    def _remove_contact(self, jid):
        if messagebox.askyesno("Kişiyi Kaldır",
                               f"{jid} kaldırılsın mı?",
                               parent=self.root):
            self.bot.remove_contact(jid)

    def _room_context_menu(self, event):
        idx = self.room_list.nearest(event.y)
        if idx < 0 or idx >= len(self._room_jids):
            return
        self.room_list.selection_set(idx)
        room = self._room_jids[idx]

        # Kendi yetkimi kontrol et
        mbrs = self.room_members.get(room, {})
        my_nick = self.my_nick.get(room, self.jid.split("@")[0])
        my_info = mbrs.get(my_nick, {})
        my_affil = my_info.get("affil", "")
        _ui_rooms_menu.show_room_menu(
            self.root, room, self._room_subjects.get(room, ""),
            my_affil in ("owner", "admin"), my_affil == "owner",
            lambda: self._change_room_subject(room),
            lambda: self._invite_to_room_dialog(room),
            lambda: self._room_config_dialog(room),
            lambda: self._leave_room(room),
            lambda: self._destroy_room_confirm(room),
            event.x_root, event.y_root,
            room in getattr(self, "_pinned_chats", []),
            lambda: self._toggle_pin_chat(room))

    def _leave_room(self, room):
        nick = self.my_nick.get(room, self.jid.split("@")[0])
        self.bot.leave_room(room, nick)

    def _change_room_subject(self, room):
        current = self._room_subjects.get(room, "")
        new_subj = simpledialog.askstring(
            "Oda Konusu", "Yeni konu:",
            initialvalue=current, parent=self.root)
        if new_subj is not None:
            self.bot.set_room_subject(room, new_subj)

    def _invite_to_room_dialog(self, room):
        target = _ui_rooms.ask_invite(self.root, room)
        if target:
            jid, reason = target
            jid = self._jid_or_warn(jid, "Davet")
            if jid:
                self.bot.invite_to_room(room, jid, reason)

    def _destroy_room_confirm(self, room):
        if messagebox.askyesno(
            "Odayı Sil",
            f"{room} kalıcı olarak silinecek.\nEmin misiniz?",
            parent=self.root):
            reason = simpledialog.askstring(
                "Odayı Sil", "Sebep (opsiyonel):",
                parent=self.root) or ""
            self.bot.destroy_room(room, reason)

    def _room_config_dialog(self, room):
        """Oda yapılandırma formunu aç."""
        self.bot.get_room_config(room, None)

    def _show_room_config_form(self, room, form):
        """Oda ayarları formu (ui/dialogs/rooms)."""
        def _submit(form):
            form['type'] = 'submit'
            self.bot.set_room_config(room, form)
        _ui_rooms.show_room_config(self.root, room, form, _submit)

    # ── Durum ─────────────────────────────────────────────────────────────────
    # ── Şifreleme seçici ─────────────────────────────────────────────────────
    # ── Şifreleme seçici ─────────────────────────────────────────────────────
    def _show_encryption_menu(self, event=None):
        """Kilit butonuna tıklayınca şifreleme modu seçim menüsü."""
        menu = tk.Menu(self.root, tearoff=0,
                       bg=BG_CARD, fg=FG, activebackground=ACCENT2,
                       activeforeground=FG_ME, borderwidth=1,
                       relief="flat", font=(FONT, 9))

        current = self._encryption_mode.get()

        def _set(mode):
            self._encryption_mode.set(mode)
            self._update_enc_btn()

        menu.add_command(
            label=f"{'● ' if current == 'none' else '  '}🔓  Şifreleme Kapalı",
            command=lambda: _set("none"))
        menu.add_separator()

        # OMEMO
        omemo_ok = HAS_OMEMO and self.bot.omemo_ready
        omemo_label = f"{'● ' if current == 'omemo' else '  '}🔒  OMEMO"
        if not HAS_OMEMO:
            omemo_label += "  (kütüphane yüklü değil)"
        elif not self.bot.omemo_ready:
            omemo_label += "  (başlatılıyor…)"
        menu.add_command(label=omemo_label,
                         command=lambda: _set("omemo") if omemo_ok else None,
                         foreground=FG if omemo_ok else FG_DIM)

        # PGP
        pgp_ok = self.bot.pgp_available()
        pgp_label = f"{'● ' if current == 'pgp' else '  '}🔑  OpenPGP"
        if not pgp_ok:
            pgp_label += "  (GPG anahtarı yok)"
        menu.add_command(label=pgp_label,
                         command=lambda: _set("pgp") if pgp_ok else None,
                         foreground=FG if pgp_ok else FG_DIM)

        menu.tk_popup(event.x_root, event.y_root - 80)

    def _update_enc_btn(self, silent=False):
        """Şifreleme butonunun ve başlık badge'inin görünümünü güncelle."""
        mode = self._encryption_mode.get()
        encrypted = mode != "none"
        border_color = ACCENT_G if encrypted else BORDER
        try:
            self._inp_border.config(bg=border_color)
        except Exception:
            pass
        if mode == "omemo":
            self._enc_btn.config(text="🔒", fg=ACCENT_G)
            self._enc_badge.config(text="🔒 OMEMO", fg=ACCENT_G, bg="#1a3a1a")
            if not silent:
                self._append("🔒 OMEMO şifreleme açıldı", "sys")
        elif mode == "pgp":
            self._enc_btn.config(text="🔑", fg=ACCENT_G)
            self._enc_badge.config(text="🔑 PGP", fg=ACCENT_G, bg="#1a3a1a")
            if not silent:
                self._append("🔑 OpenPGP şifreleme açıldı", "sys")
        else:
            self._enc_btn.config(text="🔓", fg=FG_DIM)
            self._enc_badge.config(text="", bg=BG_CARD)
            if not silent:
                self._append("🔓 Şifreleme kapatıldı", "sys")
        # Sohbet başına şifreleme modunu kaydet
        if self.active:
            self._chat_enc_modes[self.active] = mode

    # ── Yazıyor bildirimi (XEP-0085) ────────────────────────────────────────
    def _on_typing_key(self, event=None):
        """Tuş basımında composing, 3s sessizlikte paused gönder."""
        if not self.active or not self.bot or not self._send_typing_notif:
            return
        target = self.active
        mtype = "groupchat" if target in self.rooms else "chat"
        self.bot.send_chatstate(target, "composing", mtype)
        # Önceki paused zamanlayıcısını iptal et
        if self._typing_send_id:
            self.root.after_cancel(self._typing_send_id)
        self._typing_send_id = self.root.after(
            3000, lambda t=target, m=mtype: self._send_paused_state(t, m))

    def _send_paused_state(self, target, mtype):
        """Paused'ı timer'ın kurulduğu sohbete gönder (fire anındaki active değil)."""
        if not target or not self.bot:
            return
        self.bot.send_chatstate(target, "paused", mtype)
        self._typing_send_id = None

    # ── Gönder ────────────────────────────────────────────────────────────────
    def _send_message(self, _=None):
        if not self.active:
            return
        body = self._composer.get_text().strip()
        if not body:
            return
        is_command = body.startswith("/") and not body.startswith("//")
        if not is_command and not self._leak_guard_ok(
                self.active, body, self._encryption_mode.get()):
            return                      # taslak kutuda kalır, gönderilmez
        self._composer.clear_text()
        ts = datetime.now().strftime("%H:%M")
        enc_mode = self._encryption_mode.get()
        is_encrypted = enc_mode != "none"
        mtype = "groupchat" if self.active in self.rooms else "chat"

        # Yanıt modu (consume: capture + temizle)
        reply = self._composer.consume_reply()

        # Bot komutları kontrol
        if body.startswith("/") and not body.startswith("//"):
            self._handle_bot_command(body)
            return

        mid = _new_msg_id()
        self._store(self.active, body, tag="me", sender="Ben", is_me=True,
                    encrypted=is_encrypted, mid=mid, reply_to=reply)
        # [2I][2J.b][2L] TTL vadesi teslim/sekmeye beslemeden ÖNCE kaydedilir:
        # sekme kalan süreyi yetkili haritadan çözer. Defter anahtarı girişin
        # örnek UID'sidir; eski/UID'siz girişlerde mid'e düşer.
        ttl = self._chat_ttl(self.active)
        uid = ""
        # [2L-B1] mid şart DEĞİL: kimlik örnek-UID'dir; eski girişler mid
        # fallback'iyle çözer.
        if ttl > 0:
            hist_last = (self.chats.get(self.active) or [None])[-1]
            uid = self._entry_instance_uid(hist_last, mid)
            if uid:
                self._record_ttl_deadline(self.active, uid, ttl)
        # [2F] Canlı teslim: append / rebase / defer (E/F)
        live_action = self._deliver_live(self.active, lambda: self._append(
            body, "me", sender="Ben", is_me=True, time_str=ts,
            encrypted=is_encrypted, mid=mid, reply_to=reply))
        # Ayrı sohbet penceresi açıksa canlı güncelle — [2L] tam alan girişi
        # (uid'li) ile beslenir; TTL çözümü tab add yolundadır
        _tab = self._chat_tabs.get(self.active)
        if _tab and _tab["win"].winfo_exists():
            try:
                hist = self.chats.get(self.active) or []
                _tab["add"](hist[-1] if hist else ("Ben", body, True, ts, "me"))
            except Exception:
                _log.warning("Sohbet sekmesi güncellenemedi", exc_info=True)

        if reply:
            self.bot.send_reply(self.active, body, reply["mid"],
                                reply["body"], mtype, enc_mode,
                                mid=mid, reply_to_jid=reply.get("to"))
        elif mtype == "groupchat":
            self.bot.send_gc(self.active, body, encryption=enc_mode, mid=mid)
        else:
            self.bot.send_chat(self.active, body, encryption=enc_mode, mid=mid)

        # Gönderimde "active" chatstate gönder
        if self.bot and self._send_typing_notif:
            if self._typing_send_id:
                self.root.after_cancel(self._typing_send_id)
                self._typing_send_id = None
            self.bot.send_chatstate(self.active, "active", mtype)

        # Gönderilen mesaja da disappearing TTL uygula — [2L] kayıt yukarıda
        # (sekmeye beslemeden önce); burada yalnız pencere satırına kalan
        # süre zamanlanır (defer: pencere dokunulmaz)
        if ttl > 0 and live_action != "defer" and self._bubble_widgets:
            self._schedule_disappear(
                self._bubble_widgets[-1],
                self._ttl_remaining(self.active, uid, ttl))

    # ── Emoji Picker ─────────────────────────────────────────────────────────
    def _show_emoji_picker(self, reaction_mid: str | None = None):
        if not self.active:
            return
        pop = tk.Toplevel(self.root)
        pop.title("Tepki seç" if reaction_mid else "Emoji")
        pop.configure(bg=BG_CARD)
        pop.geometry("340x320")
        pop.transient(self.root)
        pop.attributes("-topmost", True)

        nb = ttk.Notebook(pop)
        nb.pack(fill="both", expand=True, padx=4, pady=4)

        for cat_name, emojis in _EMOJI_CATEGORIES.items():
            tab = tk.Frame(nb, bg=BG_CARD)
            nb.add(tab, text=cat_name)
            # Scrollable emoji grid
            canvas = tk.Canvas(tab, bg=BG_CARD, highlightthickness=0)
            canvas.pack(fill="both", expand=True)
            frame = tk.Frame(canvas, bg=BG_CARD)
            canvas.create_window((0, 0), window=frame, anchor="nw")
            frame.bind("<Configure>",
                lambda e, c=canvas: c.configure(scrollregion=c.bbox("all")))
            canvas.bind("<Button-4>", lambda _, c=canvas: c.yview_scroll(-3, "units"))
            canvas.bind("<Button-5>", lambda _, c=canvas: c.yview_scroll(3, "units"))

            col = 0
            row_n = 0
            for ch in emojis:
                btn = tk.Label(frame, text=ch, font=(FONT, 14),
                               bg=BG_CARD, cursor="hand2", padx=2, pady=2)
                btn.grid(row=row_n, column=col, padx=1, pady=1)
                if reaction_mid:
                    btn.bind("<Button-1>",
                        lambda _, emoji=ch, p=pop, m=reaction_mid: (
                            self._toggle_reaction(m, emoji), p.destroy()))
                else:
                    btn.bind("<Button-1>",
                        lambda _, emoji=ch, p=pop: self._insert_emoji(emoji, p))
                btn.bind("<Enter>", lambda e: e.widget.config(bg=BG_HOVER))
                btn.bind("<Leave>", lambda e: e.widget.config(bg=BG_CARD))
                col += 1
                if col >= 10:
                    col = 0
                    row_n += 1

    def _insert_emoji(self, emoji, popup):
        self._composer.insert_text(emoji)
        popup.destroy()

    # ── Dosya Gönderme ───────────────────────────────────────────────────────
    def _send_file(self):
        """📎 — HTTP yükleme veya P2P gönderim seçimi."""
        if not self.active:
            return
        menu = tk.Menu(self.root, tearoff=0, bg=BG_CARD, fg=FG,
                       activebackground=SEL_BG, activeforeground=SEL_FG,
                       font=(FONT, 9))
        menu.add_command(label=_t("ft_http"), command=self._send_file_http)
        if self.active not in self.rooms:
            menu.add_command(label=_t("ft_p2p"), command=self._send_file_p2p)
        try:
            menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())
        finally:
            menu.grab_release()

    def _ask_send_path(self):
        from tkinter import filedialog
        return filedialog.askopenfilename(title="Dosya Seç", parent=self.root)

    def _upload_file_path(self, path, target=None):
        target = target or self.active
        if self.active == target:
            self._append(f"📎 Yükleniyor: {os.path.basename(path)}…", "sys")
        self.bot.upload_file(path, target)

    def _send_file_http(self):
        path = self._ask_send_path()
        if path:
            self._upload_file_path(path)

    def _send_file_p2p(self):
        path = self._ask_send_path()
        if not path:
            return
        name = os.path.basename(path)
        try:
            size = os.path.getsize(path)
        except OSError as e:
            messagebox.showerror("Hata", str(e), parent=self.root)
            return
        if size > self._ft_warn_mb * 1024 * 1024:
            if not messagebox.askyesno(
                    _t("ft_title"),
                    _t("ft_large_warn").format(mb=self._ft_warn_mb),
                    parent=self.root):
                return
        if self.presence.get(self.active, "offline") in ("offline", "unavailable"):
            if not messagebox.askyesno(_t("ft_title"), _t("ft_online_check"),
                                       parent=self.root):
                return
        self._ft_pending_out[(self.active, name)] = path
        self._append(f"⚡ P2P: {name}", "sys")
        self.bot.jingle_send(self.active, path, self._ft_block_size)

    # ── Gelen dosya teklifi (Jingle FT) ──────────────────────────────────────
    def _ft_offer_dialog(self, data):
        sid = data.get("sid", "")
        name = data.get("name", "dosya")
        size = int(data.get("size", 0))
        peer = data.get("peer", "")
        if self._ft_auto_accept:
            os.makedirs(self._download_dir, exist_ok=True)
            target = jingle_ft.unique_download_path(self._download_dir, name)
            self._append(f"📥 {name} — {_t('ft_auto_saved')}", "sys")
            self.bot.jingle_accept(sid, target)
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(_t("ft_offer_title"))
        dlg.configure(bg=BG_CARD)
        dlg.geometry("400x320")
        dlg.transient(self.root)
        _safe_grab_set(dlg)
        dlg.attributes("-topmost", True)

        tk.Label(dlg, text="📥", font=(FONT, 24), bg=BG_CARD).pack(pady=(16, 4))
        tk.Label(dlg, text=name, font=(FONT, 11, "bold"), fg=FG,
                 bg=BG_CARD, wraplength=340).pack()
        tk.Label(dlg, text=f"{peer.split('/')[0]}  ·  {jingle_ft.format_size(size)}",
                 font=(FONT, 8), fg=FG_DIM, bg=BG_CARD).pack(pady=(4, 0))
        hash_short = data.get("hash_short", "")
        if hash_short:
            tk.Label(dlg, text=f"sha-256: {hash_short}…", font=(FONT, 7),
                     fg=FG_DIM, bg=BG_CARD).pack(pady=(2, 0))
        tk.Label(dlg, text=_t("ft_not_e2e"), font=(FONT, 7), fg=RED,
                 bg=BG_CARD).pack(pady=(8, 0))

        state = {"decided": False}
        btns = tk.Frame(dlg, bg=BG_CARD)
        btns.pack(side="bottom", fill="x", padx=16, pady=16)

        def _mark_done():
            if state["decided"]:
                return False
            state["decided"] = True
            dlg.after_cancel(state["timer"])
            return True

        def _accept():
            from tkinter import filedialog
            path = filedialog.asksaveasfilename(
                parent=dlg, title=_t("ft_accept_save"),
                initialdir=self._download_dir, initialfile=name)
            if not path or not _mark_done():
                return
            dlg.destroy()
            self.bot.jingle_accept(sid, path)

        def _decline():
            if not _mark_done():
                return
            dlg.destroy()
            self.bot.jingle_decline(sid)

        def _timeout():
            if not state["decided"]:
                state["decided"] = True
                dlg.destroy()
                self.bot.jingle_decline(sid)
                self._append(f"⏱ {name} — {_t('ft_timeout')}", "sys")

        state["timer"] = _after_alive(dlg, 60000, _timeout)
        dlg.protocol("WM_DELETE_WINDOW", _decline)
        ttk.Button(btns, text=f"  {_t('ft_accept_save')}  ",
                   command=_accept).pack(side="left", expand=True, fill="x",
                                         padx=(0, 6))
        ttk.Button(btns, text=f"  {_t('ft_decline')}  ", style="Danger.TButton",
                   command=_decline).pack(side="left", expand=True, fill="x")

    def _ft_error(self, data):
        sid = data.get("sid", "")
        msg = str(data.get("error", "")) or "bilinmeyen hata"
        self._append(f"❌ Dosya transferi: {msg}", "sys")
        win = self._ft_progress_wins.pop(sid, None)
        if win is not None:
            try:
                win["win"].destroy()
            except Exception:
                pass
        peer = str(data.get("peer", "")).split("/")[0]
        state = data.get("state", "")
        self._ft_pending_out.pop((data.get("peer", ""), data.get("name", "")), None)
        path = self._ft_sent_paths.pop(sid, "")
        if state in ("cancelled", "declined"):
            return
        target = peer or self.active
        if path and os.path.isfile(path) and target:
            if messagebox.askyesno(_t("ft_title"), _t("ft_http_fallback"),
                                   parent=self.root):
                self._upload_file_path(path, target)

    def _ft_update_progress(self, data):
        sid = data.get("sid", "")
        total = int(data.get("total", 0)) or 1
        done = int(data.get("done", 0))
        win = self._ft_progress_wins.get(sid)
        if win is None:
            win = self._make_ft_progress_window(sid, data)
        if win.get("closed"):
            return
        now = time.time()
        if now - win["ui_ts"] < 0.1 and done < total:
            return
        win["ui_ts"] = now
        dt = now - win["ts"]
        if dt > 0:
            win["speed"] = (done - win["last_done"]) / dt
        win["ts"], win["last_done"] = now, done
        win["bar"]["value"] = max(0.0, min(done / total, 1.0)) * 100
        eta = ((total - done) / win["speed"]) if win["speed"] > 0 else -1
        win["info"].config(text=(
            f"{jingle_ft.format_size(done)} / {jingle_ft.format_size(total)}  ·  "
            f"{jingle_ft.format_speed(win['speed'])}  ·  "
            f"{jingle_ft.format_eta(eta) if eta >= 0 else '—'}"))

    def _make_ft_progress_window(self, sid, data):
        win = tk.Toplevel(self.root)
        win.title(_t("ft_progress_title"))
        win.configure(bg=BG_CARD)
        win.geometry("400x180")
        win.transient(self.root)
        win.attributes("-topmost", True)
        direction = _t("ft_sent") if data.get("direction") == "out" else _t("ft_received")
        tk.Label(win, text=f"{direction}: {data.get('name', '')}",
                 font=(FONT, 10, "bold"), fg=FG, bg=BG_CARD,
                 wraplength=360).pack(padx=16, pady=(16, 8))
        bar = ttk.Progressbar(win, maximum=100, style="TProgressbar")
        bar.pack(fill="x", padx=16)
        info = tk.Label(win, text="", font=(FONT, 8), fg=FG_DIM, bg=BG_CARD)
        info.pack(pady=(6, 0))
        state = {"win": win, "bar": bar, "info": info, "ts": time.time(),
                 "ui_ts": 0.0, "last_done": 0, "speed": 0.0, "closed": False}

        def _cancel():
            self.bot.jingle_cancel(sid)
            state["closed"] = True
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _cancel)
        ttk.Button(win, text=_t("ft_cancel"), style="Small.TButton",
                   command=_cancel).pack(pady=(10, 12))
        self._ft_progress_wins[sid] = state
        return state

    def _ft_finished(self, data):
        sid = data.get("sid", "")
        win = self._ft_progress_wins.pop(sid, None)
        if win is not None:
            try:
                win["win"].destroy()
            except Exception:
                pass
        self._ft_sent_paths.pop(sid, None)
        direction = data.get("direction", "in")
        name = data.get("name", "dosya")
        path = data.get("path", "")
        peer = data.get("peer", "")
        if direction == "out":
            target = peer.split("/")[0] or self.active
            tag, sender = "me", "Ben"
        else:
            target = peer.split("/")[0]
            tag, sender = "them", target
        body = f"📎 {name}"
        if target:
            self._store(target, body, tag=tag, sender=sender,
                        is_me=(tag == "me"), local_path=path)
            if self.active == target:
                # [2F] Canlı teslim: append / rebase / defer
                self._deliver_live(
                    target,
                    lambda t=tag, s=sender, p=path: self._append(
                        body, t, sender=s, is_me=(t == "me"),
                        local_path=p))
        if direction == "in":
            self._append(f"📥 {_t('ft_received')}: {name}", "sys")
            _desktop_notify(_t("ft_received"), name)
            if self._sound_enabled:
                self._play_notification_sound()

    # ── Mesaj Arama ──────────────────────────────────────────────────────────
    def _search_messages_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Mesaj Arama")
        dlg.configure(bg=BG_CARD)
        dlg.geometry("460x400")
        dlg.transient(self.root)

        # Arama çubuğu
        top = tk.Frame(dlg, bg=BG_CARD, padx=16, pady=12)
        top.pack(fill="x")
        tk.Label(top, text="🔍  Mesajlarda Ara", font=(FONT, 11, "bold"),
                 fg=FG, bg=BG_CARD).pack(anchor="w")

        search_var = tk.StringVar()
        sb = tk.Frame(top, bg=BORDER, padx=1, pady=1)
        sb.pack(fill="x", pady=(8, 0))
        se = PlaceholderEntry(sb, placeholder="Aranacak metin...",
                              textvariable=search_var,
                              font=(FONT, 10), style="Modern.TEntry")
        se.pack(fill="x", ipady=7, padx=2, pady=2)

        # Sonuçlar
        results_frame = tk.Frame(dlg, bg=BG_CARD)
        results_frame.pack(fill="both", expand=True, padx=16, pady=(4, 16))

        result_list = tk.Listbox(results_frame, bg=BG_PANEL, fg=FG,
                                  selectbackground=SEL_BG, selectforeground=SEL_FG,
                                  font=(FONT, 9), relief="flat",
                                  highlightthickness=0, activestyle="none")
        result_list.pack(fill="both", expand=True)

        _result_data = []

        def _do_search(_=None):
            query = search_var.get().strip().lower()
            if not query or len(query) < 2:
                return
            result_list.delete(0, "end")
            _result_data.clear()
            for jid, msgs in self.chats.items():
                short = jid.split("@")[0]
                for msg in msgs:
                    sender, body = msg[0], msg[1]
                    if query in body.lower():
                        ts = msg[3] if len(msg) > 3 else ""
                        line = f"[{short}] {sender} ({ts}): {body[:80]}"
                        result_list.insert("end", line)
                        _result_data.append(jid)

        def _goto_result(_=None):
            sel = result_list.curselection()
            if sel and sel[0] < len(_result_data):
                jid = _result_data[sel[0]]
                dlg.destroy()
                self._load_chat(jid)

        se.bind("<Return>", _do_search)
        result_list.bind("<Double-1>", _goto_result)
        _after_alive(dlg, 50, se.focus_force)

    # ── Tema Seçici ──────────────────────────────────────────────────────────
    def _show_theme_picker(self):
        menu = tk.Menu(self.root, tearoff=0,
                       bg=BG_CARD, fg=FG, activebackground=ACCENT2,
                       activeforeground=FG_ME, borderwidth=1,
                       relief="flat", font=(FONT, 9))
        cfg = _load_config()
        current = cfg.get("theme", "koyu")
        _icons = {"koyu": "🌙 ", "acik": "☀ ", "gece-mavisi": "🌊 ",
                  "amoled": "⬛ ", "dracula": "🧛 ", "nord": "❄ ",
                  "gruvbox": "🟠 ", "solarized": "🌞 ", "monokai": "🎨 ",
                  "midnight": "🌌 "}
        for key in _theme_choices():
            prefix = "● " if key == current else "  "
            label = f"{_icons.get(key, '')}{key}"
            menu.add_command(label=f"{prefix}{label}",
                command=lambda k=key: self._apply_and_save_theme(k))
        try:
            x = self.root.winfo_rootx() + 200
            y = self.root.winfo_rooty() + 50
            menu.tk_popup(x, y)
        except Exception:
            pass

    def _apply_and_save_theme(self, theme_name):
        cfg = _load_config()
        cfg["theme"] = theme_name
        _save_config(cfg)
        _apply_color_theme(theme_name)
        self._refresh_theme()
        messagebox.showinfo("Tema",
                            "Tema uygulandı. Bazı öğeler yeniden başlatmada yenilenir.",
                            parent=self.root)

    # ── MAM Geçmiş Yükleme ──────────────────────────────────────────────────
    def _load_mam_history(self):
        if self.active:
            if not self.chats.get(self.active):
                self._ensure_history_state()
                # [2F-Blocker] Aynı JID'de bekleyen UI isteği varken yeni
                # istek gönderilmez (E: küçük deterministik çözüm).
                if self._history_mam_intent.get(self.active):
                    return
                self._mam_gen = getattr(self, "_mam_gen", {})
                gen = self._mam_gen.setdefault(self.active, 0)
                # Niyet, İSTEĞİN kendi token'ına bağlanır (A kuralı):
                # sonuç yalnız bu token'la eşleşince tüketilir.
                self._history_mam_intent[self.active] = {"token": gen,
                                                         "intent": "initial"}
                # [Phase B3] Fetch senkron raise ederse niyeti geri al.
                try:
                    self.bot.fetch_mam(self.active, 50, token=gen)
                except Exception:
                    self._history_mam_intent.pop(self.active, None)
                    _log.warning("MAM history isteği başlatılamadı "
                                 "(jid=%s)", self.active, exc_info=True)

    def _mam_alias_register(self, jid, raw_id, canonical_mid, body, is_me):
        """[2O] raw_id → (canonical_mid, body, yön) ters-korelasyon kaydı.

        Yalnız geçerli kanıt için: jid/raw_id/canonical_mid dolu ve
        raw_id ≠ canonical_mid (aynı kimlik için alias gereksizdir). Kova
        ve genel sınırlar deterministik FIFO ile tahliye edilir; tahliye
        fail-open'dır (alias kaybı kopyaya izin verebilir, mesaj silmez).
        """
        if not (jid and raw_id and canonical_mid) or raw_id == canonical_mid:
            return
        buckets = getattr(self, "_mam_aliases", None)
        if buckets is None:
            buckets = {}
            self._mam_aliases = buckets
        if jid not in buckets and len(buckets) >= self._MAM_ALIAS_MAX_JIDS:
            buckets.pop(next(iter(buckets)))       # en eski kova (FIFO)
        bucket = buckets.setdefault(jid, {})
        while len(bucket) >= self._MAM_ALIAS_CAP_PER_JID:
            bucket.pop(next(iter(bucket)))         # en eski alias (FIFO)
        bucket[raw_id] = (canonical_mid, body, bool(is_me))

    def _mam_alias_forget_jid(self, jid):
        """[2O] JID'in tüm alias kovasını düşür (clear yolları)."""
        buckets = getattr(self, "_mam_aliases", None)
        if buckets is not None:
            buckets.pop(jid, None)

    def _mam_alias_forget_identity(self, jid, mid):
        """[2O] mid silindiğinde: alias anahtarı ya da canonical_mid == mid
        olan kayıtlar unutulur — bayat alias yeni mesajı susturamaz."""
        bucket = getattr(self, "_mam_aliases", {}).get(jid)
        if not bucket or not mid:
            return
        for k in [k for k, v in bucket.items() if k == mid or v[0] == mid]:
            bucket.pop(k, None)

    def _mam_alias_clear_all(self):
        """[2O] Registry'yi tamamen boşalt (clear-all/disconnect/quit)."""
        buckets = getattr(self, "_mam_aliases", None)
        if buckets is not None:
            buckets.clear()

    def _mam_alias_lookup(self, jid, alias):
        """[2O] (canonical_mid, body, is_me) döndür; yoksa None."""
        return getattr(self, "_mam_aliases", {}).get(jid, {}).get(alias)

    def _is_live_duplicate(self, jid, mid, body, direction):
        """[2O] LIVE teslim replay kontrolü (kind == "msg" yetkili sınırı).

        (A) Exact match: chats[jid]'de aynı (mid, body, yön) satırı VARSA
        bastır. (B) Ters-alias: registry kaydı + gövde/yön eşleşmesi +
        kanonik satırın hâlâ aynı içerikle mevcut olması. Şüpheli/bayat
        kanıt FAIL-OPEN'dır (mesaj materialize edilir); mid'siz asla.
        """
        if not mid:
            return False
        # Guard'lı okuma: bare test çiftleri `chats` taşımaz (2K/2M kalıbı)
        hist = getattr(self, "chats", {}).get(jid, [])
        for e in reversed(hist):
            if len(e) > 7 and e[7] == mid:
                # (A) bilinen depolanan kimlik: birebir içerik gerekir
                return e[1] == body and bool(e[2]) == bool(direction)
        hit = self._mam_alias_lookup(jid, mid)
        if hit is None:
            return False
        canonical_mid, alias_body, alias_me = hit
        for e in reversed(hist):
            if len(e) > 7 and e[7] == canonical_mid:
                # (B) kanonik satır yaşıyor ve içerik birebir uyuyorsa bastır
                return (alias_body == body and alias_me == bool(direction)
                        and e[1] == body and bool(e[2]) == bool(direction))
        return False                           # kanonik kayboldu → fail-open

    def _load_older_mam(self):
        """Arşivden bir sayfa daha eski mesaj iste (1:1 ve oda)."""
        if not self.active:
            return
        target = self.active
        before = self._mam_oldest.get(target) or None
        self._ensure_history_state()
        # [2F-Blocker] Outstanding Older isteği varken ikinci istek yok (E);
        # niyet isteğin token'ına bağlanır (B kuralı).
        if self._history_mam_intent.get(target):
            return
        self._mam_gen = getattr(self, "_mam_gen", {})
        gen = self._mam_gen.setdefault(target, 0)
        self._history_mam_intent[target] = {"token": gen, "intent": "older"}
        # [Phase B3] Fetch senkron raise ederse niyeti geri al: stale intent
        # o JID için sonraki tüm Load Older isteklerini kilitler.
        try:
            self.bot.fetch_mam(target, 50, before=before, token=gen)
        except Exception:
            self._history_mam_intent.pop(target, None)
            _log.warning("MAM older isteği başlatılamadı (jid=%s)",
                         target, exc_info=True)

    def _mam_consume_intent(self, jid: str, result_token):
        """[2F-Blocker] Niyet sahipliği: token eşleşirse tüket, niyeti döndür.

        Sonuç, niyetin ait olduğu isteğin token'ı taşıyorsa niyet tüketilir
        (C kuralı); aksi hâlde niyet DOKUNULMADAN None döner — bayat/geç
        sonuç yeni isteğin sahipliğini asla tüketemez (D kuralı).
        """
        owning = self._history_mam_intent.get(jid)
        if isinstance(owning, dict) and owning.get("token") == result_token:
            return self._history_mam_intent.pop(jid).get("intent")
        return None

    @staticmethod
    def _iso_to_hm(ts: str) -> str:
        """ISO zaman damgasını HH:MM'e çevir."""
        if not ts:
            return ""
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt.strftime("%H:%M")
        except Exception:
            return ts[-8:-3] if len(ts) > 8 else ""

    # ── Yer İmleri Diyaloğu ──────────────────────────────────────────────────
    def _bookmarks_dialog(self):
        self.bot.get_bookmarks(None)

    def _show_bookmarks(self, bookmarks):
        """Yer imleri penceresi (ui/dialogs/rooms)."""
        _ui_rooms.show_bookmarks(
            self.root, self.jid, self.active, self.rooms, self.my_nick,
            bookmarks, self._join_bookmark, self._save_bookmarks_requested)

    def _join_bookmark(self, room, nick):
        self.my_nick[room] = nick
        self.bot.join_room(room, nick)

    def _save_bookmarks_requested(self, bookmarks):
        self.bot.save_bookmarks(bookmarks)

    # ── Kullanıcı Arama Diyaloğu ────────────────────────────────────────────
    def _search_users_dialog(self):
        """Kullanıcı arama penceresi (ui/dialogs/contact)."""
        self._search_dlg_ref, self._search_list_ref, self._search_jids_ref = \
            _ui_contact.show_search_users(
                self.root,
                self.jid.split("@")[1] if "@" in self.jid else "",
                self._request_user_search, self._start_chat_from_search)

    def _request_user_search(self, server, query):
        self.bot.search_users(server, query)

    def _start_chat_from_search(self, jid):
        if jid not in self._contacts:
            self._contacts[jid] = jid
            self._refresh_contacts()
        self._hide_members()
        self._load_chat(jid)

    # ── Dialog: Kişi ekle / Sohbet başlat ────────────────────────────────────
    def _add_contact_dialog(self):
        """Yeni Sohbet / kişi ekle penceresi (ui/dialogs/contact)."""
        _ui_contact.show_add_contact(
            self.root, self._contacts, self.presence,
            self.jid.split("@")[1] if "@" in self.jid else "",
            self._open_chat_from_add, self._subscribe_contact,
            self._request_user_search, self._set_search_refs)

    def _set_search_refs(self, dlg, s_list, jids):
        """Arama sekmesi referanslarını kaydet (_handle kontratı)."""
        self._search_list_ref = s_list
        self._search_jids_ref = jids

    def _open_chat_from_add(self, jid):
        """Sohbeti aç; kişi değilse listeye ekle (davranış birebir)."""
        if jid not in self._contacts:
            self._contacts[jid] = jid
            self._refresh_contacts()
        self._hide_members()
        self._load_chat(jid)

    def _subscribe_contact(self, jid):
        """Kişi olarak ekle: sohbeti aç + abonelik isteği (bot owner)."""
        self._open_chat_from_add(jid)
        if self.bot:
            self.bot.add_contact(jid)

    # ── Dialog: Oda keşfet (sekmeli) ─────────────────────────────────────────
    def _search_rooms_dialog(self):
        """Oda Keşfet penceresi (ui/dialogs/rooms)."""
        domain = self.jid.split("@")[1] if "@" in self.jid else ""
        _ui_rooms.show_room_search(
            self.root, self.jid.split("@")[0], domain, _KNOWN_MUC_SERVERS,
            self._search_rooms_requested, self._join_searched_room,
            self._add_room_bookmark, self._discover_rooms_requested,
            own_conf=self._muc_service())

    # search.jabber.network: GET /rooms sorguyu yok sayar (alfabetik liste);
    # arama POST /search ile yapılır. Anahtar kelimeler en az 3 harf, çoklu
    # kelime VE mantığıyla eşleşir.
    _ROOM_SEARCH_URL = "https://search.jabber.network/api/1.0/search"
    _ROOM_SEARCH_MIN_KEYWORD = 3

    def _search_rooms_requested(self, query, on_done, on_error):
        """HTTP arama worker'ı (thread); sonuç _safe_after ile GUI'ye."""
        keywords = [w for w in query.split()
                    if len(w) >= self._ROOM_SEARCH_MIN_KEYWORD]
        too_short = (f"En az {self._ROOM_SEARCH_MIN_KEYWORD} harfli "
                     "bir kelime girin")
        if not keywords:
            on_error(too_short)
            return

        def _fetch():
            body = json.dumps({"keywords": keywords, "sinname": True,
                               "sindescr": True, "sinaddr": True}).encode()
            try:
                req = urllib.request.Request(
                    self._ROOM_SEARCH_URL, data=body, method="POST",
                    headers={"Accept": "application/json",
                             "Content-Type": "application/json",
                             "User-Agent": "deneme-xmpp/1.0"})
                with urllib.request.urlopen(req, timeout=12) as r:
                    data = json.loads(_read_bounded(r, _NET_JSON_MAX))
                items = _parse_room_search(data)
                self._safe_after(0, on_done, items)
            except urllib.error.HTTPError as ex:
                msg = too_short if ex.code == 400 else f"HTTP {ex.code}"
                self._safe_after(0, on_error, msg)
            except Exception as ex:
                self._safe_after(0, on_error, str(ex))
        threading.Thread(target=_fetch, daemon=True).start()

    def _muc_service(self) -> str:
        """Kendi oda sunucumuz: XEP-0030 ile keşfedilen, yoksa eski tahmin."""
        found = getattr(getattr(self, "bot", None), "muc_service", "")
        if found:
            return found
        jid = getattr(self, "jid", "") or ""
        return "conference." + (jid.split("@")[1] if "@" in jid else "")

    def _join_room_normalized(self, room, nick):
        """Tüm katılım yollarının tek girişi: adres normalize edilir.

        Ham adres (büyük harf, boşluk, xmpp: bağlantısı) slixmpp'nin
        normalize olaylarıyla eşleşmez; my_nick/rooms anahtarları da gelen
        mesajlarla aynı (normalize) adresi kullanmalıdır.
        """
        try:
            room = _normalize_room_jid(room, self._muc_service())
        except ValueError as e:
            messagebox.showerror("Odaya Katıl", str(e), parent=self.root)
            return None
        self.my_nick[room] = nick
        self.bot.join_room(room, nick)
        return room

    def _join_searched_room(self, room, nick):
        self._join_room_normalized(room, nick)

    def _add_room_bookmark(self, room, name, nick, set_saved):
        def _cb(bookmarks):
            lst = list(bookmarks or [])
            _bookmark_add(lst, room, name=name, nick=nick)
            self.bot.save_bookmarks(lst)
            set_saved()
        self.bot.get_bookmarks(_cb)

    # ── Dialog: Odaya katıl ───────────────────────────────────────────────────
    def _join_room_dialog(self):
        """Odaya Katıl penceresi (ui/dialogs/rooms)."""
        _ui_rooms.show_join_room(
            self.root, self._muc_service(),
            self.jid.split("@")[0],
            self._discover_rooms_requested, self._join_room_requested)

    def _discover_rooms_requested(self, server):
        self.bot.discover_rooms(server)

    def _join_room_requested(self, room, nick):
        self._join_room_normalized(room, nick)

    # ── Oda oluştur ─────────────────────────────────────────────────────────
    def _create_room_dialog(self):
        """Oda Oluştur penceresi (ui/dialogs/rooms)."""
        _ui_rooms.show_create_room(
            self.root, self._muc_service(),
            self.jid.split("@")[0], self._create_room_requested)

    def _create_room_requested(self, room_jid, nick, kind="normal", name=""):
        """Katıl + yapılandır: bot sunucunun 201 (oda yeni) yanıtını bekler.

        `name` oda başlığıdır (adres "sifreli-oda", başlık "Şifreli Oda")."""
        try:
            room_jid = _normalize_room_jid(room_jid, self._muc_service())
        except ValueError as e:
            messagebox.showerror("Oda Oluştur", str(e), parent=self.root)
            return
        self.my_nick[room_jid] = nick
        self.bot.create_room(room_jid, nick, kind, name)

    def _room_taken(self, data):
        """Oluşturulmak istenen adreste başka bir oda var: başka ad seçilsin."""
        room = data["room"]
        if room not in getattr(self, "rooms", ()):
            self.my_nick.pop(room, None)
        messagebox.showwarning(
            "Oda Oluştur",
            f"{room} adresinde zaten bir oda var.\n\n"
            "Lütfen başka bir ad seçin. Oda sizinse odalar bölümündeki "
            "+ (Odaya Katıl) düğmesiyle girebilirsiniz.", parent=self.root)

    def _jid_or_warn(self, raw, title, parent=None):
        """Yazılan kişi JID'ini normalize et; geçersizse nedenini göster → None."""
        try:
            return _normalize_user_jid(raw)
        except ValueError as e:
            messagebox.showerror(title, str(e), parent=parent or self.root)
            return None

    def _room_created(self, data):
        """Yeni oda yapılandırıldı: şifreliyse OMEMO'yu aç ve kalıcı işaretle."""
        room, kind = data["room"], data["kind"]
        if not _muc_room_kind_ok(kind, data.get("missing", ())):
            self._append(
                "⚠ Sunucu şifreli oda ayarlarını (yalnız üyeler / gerçek JID'ler) "
                "desteklemiyor; OMEMO bu odada çalışmaz. Oda normal ayarlarla "
                "açıldı.", "sys")
            return
        if kind != "encrypted":
            self._append("🌐 Oda hazır: adresi bilen herkes katılabilir.", "sys")
            return
        self._encrypted_rooms.add(room)
        cfg = _load_config()
        cfg["encrypted_rooms"] = sorted(
            set(cfg.get("encrypted_rooms", [])) | {room})
        _save_config(cfg)
        self._chat_enc_modes[room] = "omemo"
        if self.active == room:
            self._encryption_mode.set("omemo")
            self._update_enc_btn(silent=True)
        self._append(
            "🔒 Şifreli oda hazır: mesajlar OMEMO ile şifrelenir; yalnız davet "
            "ettikleriniz katılabilir (odaya sağ tık → 📨 Davet Gönder).", "sys")

    def _chat_encryption(self, target):
        """Sohbet açılınca şifreleme: açık seçim > şifreli oda > varsayılan.

        Ayarlar'daki varsayılan yalnız 1:1 sohbetlere uygulanır; anonim
        odada OMEMO düz metne düşeceğinden odalar yalnız şifreli kurulduysa
        OMEMO ile açılır."""
        mode = self._chat_enc_modes.get(target)
        if mode is not None:
            return mode
        if target in self.rooms:
            encrypted = getattr(self, "_encrypted_rooms", ())
            return "omemo" if target in encrypted else "none"
        return getattr(self, "_default_encryption", "none")

    # ── Oda tarayıcı ──────────────────────────────────────────────────────────
    def _show_rooms_browser(self, rooms: list):
        """Keşfedilen odalar penceresi (ui/dialogs/rooms)."""
        _ui_rooms.show_rooms_browser(
            self.root, self.jid.split("@")[0], rooms,
            self._join_discovered_room)

    def _join_discovered_room(self, room, nick):
        self._join_room_normalized(room, nick)

    # ── Dialog: Ayarlar ──────────────────────────────────────────────────────
    def _change_avatar_dialog(self):
        """Profil fotoğrafı değiştirme diyaloğu (ui/profile)."""
        _ui_profile.show_avatar_dialog(
            self.root, self.jid, self._avatars.get(self.jid), self._photo_refs,
            on_publish=self._avatar_publish,
            on_forget=self._avatar_forget_local,
            on_removed=self._avatar_publish_removal)

    def _avatar_publish(self, photo_bytes, on_result):
        """Yeni fotoğrafı kaydet ve yayınla; sonuç `on_result(ok)` ile GUI
        thread'inde bildirilir. Yayın başarısızsa eski fotoğrafa dönülür."""
        old_data = self._avatars.get(self.jid)

        def _done(ok):
            def _ui():
                if not ok:
                    self._restore_avatar(self.jid, old_data)
                on_result(ok)
            self._safe_after(0, _ui)
        self._avatars[self.jid] = photo_bytes
        _save_avatar_cache(self.jid, photo_bytes)
        self._update_sidebar_avatar()
        self.bot.publish_avatar(photo_bytes, "image/png", _done)

    def _avatar_forget_local(self):
        """Fotoğrafı bellekten ve diskteki önbellekten sil."""
        self._avatars.pop(self.jid, None)
        path = _avatar_cache_path(self.jid)
        if os.path.exists(path):
            os.remove(path)

    def _avatar_publish_removal(self):
        """Fotoğrafın kaldırıldığını kenar çubuğuna ve sunucuya yansıt."""
        self._update_sidebar_avatar()
        self.bot.publish_avatar(b"", "image/png")

    def _settings_dialog(self):
        """Ayarlar penceresi (ui/dialogs/settings); kayıt _settings_apply'da."""
        cfg = _load_config()
        _ui_settings.show_settings(
            self.root, cfg, self._settings_state(cfg),
            self._settings_actions(), self._settings_apply)

    def _settings_state(self, cfg):
        """Ayarlar penceresinin gösterdiği çalışma zamanı bilgisi."""
        omemo_ok = HAS_OMEMO and self.bot.omemo_ready
        pgp_ok = self.bot.pgp_available()
        pgp_keys = None
        if pgp_ok:
            try:
                pgp_keys = self.bot.pgp_list_keys()
            except Exception:
                pass
        try:
            import qrcode  # noqa: F401
            has_qrcode = True
        except ImportError:
            has_qrcode = False

        server = self.jid.split("@")[1] if "@" in self.jid else "—"
        about = [
            ("Hesap", self.jid),
            ("Sunucu", server),
            ("OMEMO", f"{'🟢 Aktif' if omemo_ok else '🔴 Pasif'}"),
            ("PGP", f"{'🟢 Aktif' if pgp_ok else '⚫ Pasif'}"),
            ("PyAudio", f"{'🟢 Yüklü' if _HAS_PYAUDIO else '⚫ Yok'}"),
            ("Kişi Sayısı", str(len(self._contacts))),
            ("Aktif Odalar", str(len(self.rooms))),
            ("Ayar Dosyası", _CONFIG_PATH),
        ]
        if HAS_OMEMO:
            about.append(("OMEMO Veri", str(_OMEMO_DIR)))

        libs = []
        for name, check in [("slixmpp", True), ("slixmpp-omemo", HAS_OMEMO),
                            ("Pillow", HAS_PIL), ("PyAudio", _HAS_PYAUDIO)]:
            if check:
                libs.append(f"🟢 {name}")
            else:
                libs.append(f"⚫ {name}")
        try:
            import gnupg  # noqa: F401
            libs.append("🟢 python-gnupg")
        except ImportError:
            libs.append("⚫ python-gnupg")
        if _HAS_DND:
            libs.append("🟢 tkinterdnd2")
        else:
            libs.append("⚫ tkinterdnd2")
        try:
            import pystray  # noqa: F401
            libs.append("🟢 pystray")
        except ImportError:
            libs.append("⚫ pystray")
        libs.append("🟢 qrcode" if has_qrcode else "⚫ qrcode")

        return {
            "jid": self.jid,
            "auto_login": _auto_login_enabled(cfg),
            "avatar_data": self._avatars.get(self.jid),
            "photo_refs": self._photo_refs,
            "compact_mode": self._compact_mode,
            "wallpaper": self._chat_wallpaper,
            "current_lang": _current_lang,
            "tray_active": bool(self._tray_icon),
            "has_omemo": HAS_OMEMO,
            "omemo_ok": omemo_ok,
            "pgp_ok": pgp_ok,
            "pgp_keys": pgp_keys,
            "has_qrcode": has_qrcode,
            "ping_ms": self._last_ping_ms,
            "connected": self.bot.is_connected() if self.bot else False,
            "contacts_count": len(self._contacts),
            "rooms_count": len(self.rooms),
            "about": about,
            "libs": libs,
        }

    def _settings_actions(self):
        """Ayarlar penceresinin yan etkileri (bot, config, alt pencereler)."""
        def _keep_pgp_entries(entries):
            # "Kaydet" eşleştirmeleri buradan okur (_settings_apply)
            self._pgp_entries_ref = entries

        return {
            "set_photo": self._settings_set_photo,
            "remove_photo": self._settings_remove_photo,
            "refresh_sidebar_avatar": lambda: self._update_sidebar_avatar(),
            "switch_account": lambda acc: self._switch_account(acc),
            "encode_pw": _encode_pw,
            "wallpaper": lambda: self._wallpaper_dialog(),
            "test_sound": lambda: threading.Thread(
                target=self._play_notification_sound, daemon=True).start(),
            "blocking": lambda: self._blocking_dialog(),
            "omemo_device_info": lambda cb: self.bot.omemo_device_info(
                lambda info: self._safe_after(0, cb, info)),
            "pgp_entries": _keep_pgp_entries,
            "omemo_qr": lambda: self._omemo_qr_dialog(),
            "proxy": lambda: self._proxy_dialog(),
            "auto_theme": lambda: self._auto_theme_dialog(),
            "pin_lock": lambda: self._pin_lock_dialog(),
            "clear_history": lambda: self._clear_history_dialog(),
            "export_chat": lambda: self._export_chat(),
            "config_json": lambda: json.dumps(_load_config(), indent=2,
                                              ensure_ascii=False),
            "backup": lambda: self._backup_dialog(),
            "shortcuts": lambda: self._shortcuts_dialog(),
        }

    def _settings_set_photo(self, path, parent):
        """Profil fotoğrafını kare 256 px PNG yapıp yayınla; baytları döndür.
        Yayın sonradan başarısız olursa eski fotoğraf geri yüklenir."""
        img = Image.open(path)
        w, h = img.size
        s = min(w, h)
        left, top = (w - s) // 2, (h - s) // 2
        img = img.crop((left, top, left + s, top + s))
        img = img.resize((256, 256), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        photo_bytes = buf.getvalue()
        old_data = self._avatars.get(self.jid)

        def _done(ok):
            def _ui():
                if not ok:
                    self._restore_avatar(self.jid, old_data)
                    messagebox.showerror(
                        "Hata",
                        "Fotoğraf yayınlanamadı; eski fotoğraf korundu.",
                        parent=parent)
            self._safe_after(0, _ui)

        self.bot.publish_avatar(photo_bytes, "image/png", _done)
        self._avatars[self.jid] = photo_bytes
        _save_avatar_cache(self.jid, photo_bytes)
        return photo_bytes

    def _settings_remove_photo(self):
        """Profil fotoğrafını kaldır (yayın + yerel önbellek)."""
        self.bot.publish_avatar(b"", "image/png")
        self._avatars.pop(self.jid, None)
        p = _avatar_cache_path(self.jid)
        if os.path.exists(p):
            os.remove(p)

    def _settings_apply(self, v):
        """Ayarlar "Kaydet ve Kapat": config'e yaz ve canlı uygula.
        `v` ui/dialogs/settings'in topladığı değerlerdir."""
        cfg = _load_config()
        # Genel
        cfg["notifications"] = v["notifications"]
        cfg["sounds"] = v["sounds"]
        cfg["status_text"] = v["status_text"]
        cfg["presence_show"] = v["presence_show"]
        cfg["accounts"] = v["accounts"]
        self._apply_login_prefs(cfg, v["remember_pw"], v["auto_login"])
        # Görünüm
        cfg["theme"] = v["theme"]
        cfg["font_size"] = v["font_size"]
        cfg["font_family"] = v["font_family"]
        cfg["language"] = v["language"]
        # Bildirimler & Gizlilik
        cfg["send_read_receipts"] = v["send_read_receipts"]
        cfg["send_typing"] = v["send_typing"]
        cfg["default_disappear"] = v["default_disappear"]
        # Bağlantı
        cfg["auto_rejoin"] = v["auto_rejoin"]
        cfg["idle_after_min"] = v["idle_after_min"]
        # Görünüm ek
        cfg["compact_mode"] = v["compact_mode"]
        # Şifreleme
        cfg["default_encryption"] = v["default_encryption"]
        pgp_map = {}
        if hasattr(self, "_pgp_entries_ref"):
            for jv, kv in self._pgp_entries_ref:
                j = jv.get().strip()
                k = kv.get().strip()
                if j and k:
                    pgp_map[j] = k
            try:
                xep = _get_xep(self.bot, "xep_0027")
                for jid_str, keyid in pgp_map.items():
                    xep.set_keyid(jid=jid_str, keyid=keyid)
            except Exception:
                pass
        cfg["pgp_keymap"] = pgp_map
        # Dosya Transferi
        cfg["download_dir"] = (v["download_dir"].strip()
                               or os.path.expanduser("~/Downloads"))
        cfg["ft_auto_accept"] = bool(v["ft_auto_accept"])
        try:
            cfg["ft_block_size"] = max(1024, min(int(v["ft_block_size"]), 8192))
        except (TypeError, ValueError):
            cfg["ft_block_size"] = 4096
        try:
            cfg["ft_warn_mb"] = max(1, int(v["ft_warn_mb"]))
        except (TypeError, ValueError):
            cfg["ft_warn_mb"] = 50
        # Canlı güncelle
        self._download_dir = cfg["download_dir"]
        self._ft_auto_accept = cfg["ft_auto_accept"]
        self._ft_block_size = cfg["ft_block_size"]
        self._ft_warn_mb = cfg["ft_warn_mb"]
        _save_config(cfg)

        # Ayarları uygula — varsayılan şifreleme yalnız sonraki sohbet
        # açılışlarına; açık sohbetin seçimi sessizce değişmez
        self._default_encryption = v["default_encryption"]
        self._default_disappear = v["default_disappear"]
        self._sound_enabled = v["sounds"]
        self._notify_enabled = v["notifications"]
        self._send_read_receipts = v["send_read_receipts"]
        self._send_typing_notif = v["send_typing"]
        self._idle_after_min = v["idle_after_min"]
        self._compact_mode = v["compact_mode"]

        # Tema uygula
        _apply_color_theme(v["theme"])
        self._refresh_theme()

        # Font uygula
        self._apply_font_settings(family=v["font_family"], size=v["font_size"])

        # Dil güncelle
        global _current_lang
        _current_lang = v["language"]

        # Durum mesajını uygula
        self._status_text, self._status_show = (v["status_text"],
                                                v["presence_show"])
        if self.bot:
            self.bot.set_status_message(v["status_text"], v["presence_show"])

    # ── Kayıtlı tercihler (açılışta) ─────────────────────────────────────────
    def _load_saved_prefs(self, cfg):
        """Ayarlar'da kaydedilen tercihleri yükle (_build'den önce: dil)."""
        global _current_lang
        self._notify_enabled = bool(cfg.get("notifications", True))
        self._sound_enabled = bool(cfg.get("sounds", True))
        self._default_encryption = cfg.get("default_encryption", "none")
        try:
            self._default_disappear = max(0, int(cfg.get("default_disappear", 0)))
        except (TypeError, ValueError):
            self._default_disappear = 0
        self._encrypted_rooms = set(cfg.get("encrypted_rooms", []))
        self._status_text = cfg.get("status_text", "") or ""
        self._status_show = cfg.get("presence_show", "chat") or "chat"
        if cfg.get("language") in _STRINGS:
            _current_lang = cfg["language"]

    def _restore_font_prefs(self, cfg):
        """Kaydedilmiş yazı tipini uygula; hiç kaydedilmediyse dokunma."""
        if "font_family" in cfg or "font_size" in cfg:
            self._apply_font_settings(family=cfg.get("font_family"),
                                      size=cfg.get("font_size"))

    def _restore_status_prefs(self):
        """Ayarlar'daki durum mesajını bağlanınca (ve her yeniden bağlanışta)
        yayınla; durum çubuğu uzakta/meşgul seçimini yansıtsın."""
        cfg = _load_config()
        text = getattr(self, "_status_text", None)
        if text is None:
            text = cfg.get("status_text", "") or ""
        show = (getattr(self, "_status_show", None)
                or cfg.get("presence_show", "chat") or "chat")
        busy = show in ("away", "dnd", "xa")
        if not text and not busy:
            return
        self.bot.set_status_message(text, show)
        if busy:
            label, color = self._ai_status_option(show)
            self.status_var.set(label)
            self._status_label.config(text=f"● {label}", fg=color)
            self._my_show = show

    # ── Canlı tema / font yenileme ─────────────────────────────────────────────
    def _refresh_theme(self):
        """Mevcut widget'ları, kaydedilen eski→yeni renk eşlemesiyle yenile."""
        remap = dict(_COLOR_REMAP)

        def _map_color(value):
            if not value:
                return None
            return remap.get(str(value))

        def _walk(w):
            try:
                wtype = w.winfo_class()
                if wtype in ("Frame", "Label", "Canvas", "Text",
                             "Listbox", "Entry", "Toplevel"):
                    try:
                        old_bg = str(w.cget("bg"))
                    except Exception:
                        old_bg = ""
                    new_bg = _map_color(old_bg)
                    if new_bg:
                        try:
                            w.config(bg=new_bg)
                        except Exception:
                            pass
                    if wtype in ("Label", "Text", "Listbox", "Entry"):
                        try:
                            old_fg = str(w.cget("fg"))
                        except Exception:
                            old_fg = ""
                        new_fg = _map_color(old_fg)
                        if new_fg:
                            try:
                                w.config(fg=new_fg)
                            except Exception:
                                pass
                    if wtype == "Text":
                        try:
                            old_ins = str(w.cget("insertbackground"))
                            new_ins = _map_color(old_ins)
                            if new_ins:
                                w.config(insertbackground=new_ins)
                        except Exception:
                            pass
            except Exception:
                pass
            for child in w.winfo_children():
                _walk(child)

        # Ana pencere renklerini doğrudan güncelle
        try:
            self.root.config(bg=BG)
            if hasattr(self, '_sidebar_frame'):
                self._sidebar_frame.config(bg=BG_PANEL)
            if hasattr(self, '_chat_frame'):
                self._chat_frame.config(bg=BG_CHAT)
        except Exception:
            pass
        _walk(self.root)

    def _apply_font_settings(self, family: str = None, size: int = None):
        """Font ailesi/boyutunu tüm widget'lara uygula."""
        global FONT
        if family:
            FONT = family
        sz = size or 10

        def _walk(w):
            try:
                wtype = w.winfo_class()
                if wtype == "Label":
                    try:
                        old_font = w.cget("font")
                        # Font tuple ise boyutu güncelle, string ise yeni font ata
                        if isinstance(old_font, tuple):
                            new_f = (FONT, old_font[1] if len(old_font) > 1 else sz)
                        elif isinstance(old_font, str) and old_font:
                            # Tkinter bazen "family size" string döner
                            parts = old_font.split()
                            try:
                                old_sz = int(parts[-1]) if len(parts) > 1 else sz
                            except ValueError:
                                old_sz = sz
                            new_f = (FONT, old_sz)
                        else:
                            new_f = (FONT, sz)
                        w.config(font=new_f)
                    except Exception:
                        pass
                elif wtype == "Text":
                    try:
                        w.config(font=(FONT, sz))
                    except Exception:
                        pass
            except Exception:
                pass
            for child in w.winfo_children():
                _walk(child)

        _walk(self.root)

        # ttk stillerini de güncelle
        try:
            style = ttk.Style()
            style.configure("Modern.TEntry", font=(FONT, sz))
            style.configure("TButton", font=(FONT, sz))
            style.configure("TNotebook.Tab", font=(FONT, sz - 1))
        except Exception:
            pass

    # ── Sohbet sabitleme ─────────────────────────────────────────────────────
    def _toggle_pin_chat(self, jid):
        if jid in self._pinned_chats:
            self._pinned_chats.remove(jid)
        else:
            self._pinned_chats.insert(0, jid)
        cfg = _load_config()
        cfg["pinned_chats"] = self._pinned_chats
        _save_config(cfg)
        self._refresh_contacts()

    # ── Otomatik uzakta ──────────────────────────────────────────────────────
    def _reset_activity(self, event=None):
        self._last_activity_ts = time.time()
        if self._is_idle:
            self._is_idle = False
            if self.bot:
                self.bot.set_presence("online")
                self._status_label.config(text="● Online", fg=ONLINE)
            self._ai_away_returned()

    def _start_idle_checker(self):
        self._idle_check_id = self._after(30000, self._check_idle)

    def _check_idle(self):
        self._idle_check_id = None
        if getattr(self, "_closing", False):
            return
        if self._idle_after_min > 0:
            elapsed = time.time() - self._last_activity_ts
            if elapsed >= self._idle_after_min * 60 and not self._is_idle:
                self._is_idle = True
                if self.bot:
                    self.bot.set_presence("away")
                    self._status_label.config(text="● Uzakta (oto)", fg=AWAY)
        if not getattr(self, "_closing", False):
            self._idle_check_id = self._after(30000, self._check_idle)

    # ── Sistem tepsisi ───────────────────────────────────────────────────────
    def _safe_after(self, ms, func, *args):
        """GUI thread'inden güvenli `after`; başka thread'de kuyruk üzerinden.

        Worker/XMPP/loop/tepsi thread'lerinden Tcl'e dokunmak yerine olay
        `gui_q`'ya bırakılır; `_poll`/`_handle` ana thread'de çalıştırır.
        Gecikme (ms) yalnızca GUI thread'inde doğrudan çağrıda uygulanır.
        """
        if getattr(self, "_closing", False):
            return None
        if threading.current_thread() is threading.main_thread():
            try:
                return self.root.after(ms, func, *args)
            except Exception:
                return None
        try:
            self.gui_q.put(("__ui__", (func, args)))
        except Exception:
            _log.warning("GUI olayı kuyruğa konulamadı", exc_info=True)
        return None

    def _after(self, ms: int, func, *args):
        """İzlenen `after`: kapanışta tüm zincirler iptal edilebilsin.

        Tk, `destroy()` sonrası kuyrukta kalan script'leri çalıştırmaya
        çalışınca "invalid command name" bgerror'u üretir; bu sarmalayıcı
        kimlikleri kaydeder ve kapanışta tek noktadan iptal eder.
        """
        if getattr(self, "_closing", False):
            return None
        ids = getattr(self, "_after_ids", None)
        if ids is None:
            ids = self._after_ids = set()
        holder: dict = {}

        def _run():
            ids.discard(holder.get("id"))
            if not getattr(self, "_closing", False):
                func(*args)

        try:
            holder["id"] = self.root.after(ms, _run)
        except Exception:
            return None
        ids.add(holder["id"])
        return holder["id"]

    def _after_cancel(self, aid):
        """`_after` ile kurulan zinciri iptal et ve kayıttan düş."""
        if not aid:
            return
        try:
            self.root.after_cancel(aid)
        except Exception:
            pass
        ids = getattr(self, "_after_ids", None)
        if ids is not None:
            ids.discard(aid)

    def _install_bgerror_filter(self):
        """Kapanış sırasında kalan Tcl callback gürültüsünü sustur."""
        try:
            self.root.tk.eval(
                "if {[llength [info commands __xmpp_orig_bgerror]] == 0} {"
                " rename bgerror __xmpp_orig_bgerror }"
                "proc bgerror {msg} {"
                "  if {[info exists ::xmpp_closing] && $::xmpp_closing} {"
                "    return"
                "  }"
                "  catch {__xmpp_orig_bgerror $msg}"
                "}")
        except Exception:
            pass

    def _setup_tray_icon(self):
        try:
            import pystray
            from PIL import Image as PilImage
            img = PilImage.new("RGB", (64, 64), ACCENT2)
            from PIL import ImageDraw
            d = ImageDraw.Draw(img)
            d.ellipse((8, 8, 56, 56), fill=ACCENT)
            d.text((22, 18), "X", fill="white")
            menu = pystray.Menu(
                pystray.MenuItem("Göster", lambda: self._safe_after(0, self._tray_show)),
                pystray.MenuItem("Çıkış", lambda: self._safe_after(0, self._quit)),
            )
            self._tray_icon = pystray.Icon("xmpp", img, "XMPP İstemci", menu)
            threading.Thread(target=self._tray_icon.run, daemon=True).start()
        except ImportError:
            self._tray_icon = None
        except Exception:
            self._tray_icon = None

    def _tray_show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _minimize_to_tray(self):
        if self._tray_icon:
            self.root.withdraw()
        else:
            self.root.iconify()

    # ── Bağlantı kalitesi — ping ─────────────────────────────────────────────
    def _ping_loop(self):
        self._ping_loop_id = None
        if getattr(self, "_closing", False):
            return
        if self.bot and self.bot.is_connected():
            t0 = time.time()
            try:
                bloop = getattr(self.bot, "loop", None)
                if bloop is not None:
                    bloop.call_soon_threadsafe(
                        lambda: self.bot.plugin['xep_0199'].send_ping(
                            self.bot.boundjid.domain, timeout=5))
                self._last_ping_ms = int((time.time() - t0) * 1000)
            except Exception:
                self._last_ping_ms = -1
            self._update_ping_label()
        if not getattr(self, "_closing", False):
            self._ping_loop_id = self._after(30000, self._ping_loop)

    def _update_ping_label(self):
        if not hasattr(self, '_ping_label'):
            return
        if self._last_ping_ms < 0:
            self._ping_label.config(text="📶 ✕", fg=RED)
        elif self._last_ping_ms < 100:
            self._ping_label.config(text=f"📶 {self._last_ping_ms}ms", fg=ONLINE)
        elif self._last_ping_ms < 300:
            self._ping_label.config(text=f"📶 {self._last_ping_ms}ms", fg=AWAY)
        else:
            self._ping_label.config(text=f"📶 {self._last_ping_ms}ms", fg=RED)

    # ── Mesaj arama (Ctrl+F) ─────────────────────────────────────────────────
    def _toggle_search_bar(self, event=None):
        if not self.active:
            return
        if hasattr(self, '_search_bar') and self._search_bar.winfo_ismapped():
            self._search_bar.pack_forget()
            return
        if not hasattr(self, '_search_bar'):
            self._search_bar = tk.Frame(self._chat_panel, bg=BG_CARD, padx=12, pady=6)
            self._search_var = tk.StringVar()
            tk.Label(self._search_bar, text="🔍", font=(FONT, 10),
                     fg=FG_DIM, bg=BG_CARD).pack(side="left")
            se = ttk.Entry(self._search_bar, textvariable=self._search_var,
                           font=(FONT, 10), width=30)
            se.pack(side="left", padx=(6, 0), fill="x", expand=True)
            se.bind("<Return>", lambda _: self._search_in_chat())
            se.bind("<Escape>", lambda _: self._search_bar.pack_forget())
            self._search_count_lbl = tk.Label(self._search_bar, text="",
                                               font=(FONT, 8), fg=FG_DIM, bg=BG_CARD)
            self._search_count_lbl.pack(side="left", padx=(8, 0))
            close_btn = tk.Label(self._search_bar, text="✕", font=(FONT, 10),
                                  fg=FG_DIM, bg=BG_CARD, cursor="hand2")
            close_btn.pack(side="right", padx=(6, 0))
            close_btn.bind("<Button-1>", lambda _: self._search_bar.pack_forget())
        self._search_bar.pack(before=self._input_area, fill="x")
        # Odakla
        for child in self._search_bar.winfo_children():
            if isinstance(child, ttk.Entry):
                child.focus_set()
                break

    def _search_in_chat(self):
        query = self._search_var.get().strip().lower()
        if not query or len(query) < 2:
            return
        # Mevcut balonlarda ara, eşleşenleri vurgula
        count = 0
        first_match = None
        for w in self._bubble_widgets:
            body = getattr(w, '_body', '').lower()
            if query in body:
                count += 1
                # Vurgu efekti
                try:
                    for child in w.winfo_children():
                        if isinstance(child, tk.Frame):
                            child.config(highlightbackground=ACCENT, highlightthickness=2)
                            if first_match is None:
                                first_match = w
                except Exception:
                    pass
            else:
                try:
                    for child in w.winfo_children():
                        if isinstance(child, tk.Frame):
                            child.config(highlightthickness=0)
                except Exception:
                    pass
        self._search_count_lbl.config(text=f"{count} sonuç")
        # İlk eşleşmeye kaydır
        if first_match:
            self.chat_canvas.yview_moveto(0)
            self.root.update_idletasks()
            try:
                y = first_match.winfo_y()
                ch = self.chat_canvas.winfo_height()
                total = self.msg_frame.winfo_height()
                if total > ch:
                    self.chat_canvas.yview_moveto(max(0, (y - 50) / total))
            except Exception:
                pass

    # ── Mesaj formatlama (markdown) ──────────────────────────────────────────
    @staticmethod
    def _format_markdown(text: str) -> list:
        """Basit markdown: *kalın*, _italik_, `kod` parçalayıcı.
        Döndürür: [(text, style), ...] style = 'bold'|'italic'|'code'|None"""
        import re
        parts = []
        pattern = re.compile(r'(\*\*(.+?)\*\*|\*(.+?)\*|_(.+?)_|`(.+?)`)')
        last = 0
        for m in pattern.finditer(text):
            if m.start() > last:
                parts.append((text[last:m.start()], None))
            if m.group(2):  # **bold**
                parts.append((m.group(2), "bold"))
            elif m.group(3):  # *bold*
                parts.append((m.group(3), "bold"))
            elif m.group(4):  # _italic_
                parts.append((m.group(4), "italic"))
            elif m.group(5):  # `code`
                parts.append((m.group(5), "code"))
            last = m.end()
        if last < len(text):
            parts.append((text[last:], None))
        return parts if parts else [(text, None)]

    # ── Sticker/GIF paneli ───────────────────────────────────────────────────
    def _show_gif_panel(self):
        if not self.active:
            return
        pop = tk.Toplevel(self.root)
        pop.title("GIF / Sticker")
        pop.configure(bg=BG_CARD)
        pop.geometry("400x360")
        pop.transient(self.root)
        pop.attributes("-topmost", True)

        top_f = tk.Frame(pop, bg=BG_CARD, padx=12, pady=8)
        top_f.pack(fill="x")
        tk.Label(top_f, text="🎭 GIF Ara", font=(FONT, 11, "bold"),
                 fg=FG, bg=BG_CARD).pack(anchor="w")

        search_var = tk.StringVar()
        sf = tk.Frame(top_f, bg=BORDER, padx=1, pady=1)
        sf.pack(fill="x", pady=(6, 0))
        se = ttk.Entry(sf, textvariable=search_var, font=(FONT, 10))
        se.pack(side="left", fill="x", expand=True, ipady=5, padx=2, pady=2)
        ttk.Button(sf, text="🔍", width=3,
                   command=lambda: self._gif_search(
                       search_var.get(), grid_f, status_lbl)).pack(
            side="left", padx=2)
        se.bind("<Return>", lambda _: self._gif_search(
            search_var.get(), grid_f, status_lbl))

        # Sonuç grid
        canvas = tk.Canvas(pop, bg=BG_CARD, highlightthickness=0)
        canvas.pack(fill="both", expand=True, padx=8, pady=4)
        grid_f = tk.Frame(canvas, bg=BG_CARD)
        canvas.create_window((0, 0), window=grid_f, anchor="nw")
        grid_f.bind("<Configure>",
                    lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Button-4>", lambda _, c=canvas: c.yview_scroll(-3, "units"))
        canvas.bind("<Button-5>", lambda _, c=canvas: c.yview_scroll(3, "units"))

        # Dahili sticker seti
        stickers = [
            "👍", "👎", "❤️", "😂", "😢", "😡", "🎉", "🤔",
            "👏", "🙏", "💪", "🔥", "⭐", "🌈", "🎵", "🍕",
            "☕", "🎮", "📱", "💻", "🎸", "🏆", "🌍", "🚀",
            "😎", "🤗", "😱", "🥳", "😴", "🤮", "💀", "👻",
        ]
        col = 0
        row_n = 0
        for s in stickers:
            btn = tk.Label(grid_f, text=s, font=(FONT, 20),
                           bg=BG_CARD, cursor="hand2", padx=4, pady=4)
            btn.grid(row=row_n, column=col, padx=2, pady=2)
            btn.bind("<Button-1>",
                     lambda _, st=s, p=pop: self._send_sticker(st, p))
            btn.bind("<Enter>", lambda e: e.widget.config(bg=BG_HOVER))
            btn.bind("<Leave>", lambda e: e.widget.config(bg=BG_CARD))
            col += 1
            if col >= 8:
                col = 0
                row_n += 1

        # Durum / ipucu satırı
        status_lbl = tk.Label(
            pop,
            text="💡 Üstteki kutuya yazıp Enter'a basın "
                 "(ilk aramada Tenor API anahtarı sorulur)",
            font=(FONT, 7), fg=FG_DIM, bg=BG_CARD, wraplength=380)
        status_lbl.pack(pady=(0, 8))

    def _send_sticker(self, sticker, popup):
        popup.destroy()
        if not self.active or not self.bot:
            return
        self.msg_var.set(sticker)
        self._send_message()

    def _gif_api_key(self, parent=None):
        """Tenor API anahtarı: kayıtlıysa onu döndür, yoksa bir kez sor ve
        şifreli kaydet (iptal → None). Elle yazılmış düz metin de geçerli."""
        stored = _load_config().get("gif_api_key", "") or ""
        if stored:
            return (_decode_pw(stored) if stored.startswith("fernet:")
                    else stored) or None
        key = simpledialog.askstring(
            "GIF Araması",
            "Tenor API anahtarı (Google Cloud Console → Tenor API):",
            parent=parent or self.root)
        key = (key or "").strip()
        if not key:
            return None
        cfg = _load_config()
        cfg["gif_api_key"] = _encode_pw(key)
        _save_config(cfg)
        return key

    def _gif_search(self, query, grid_f, status_lbl):
        """Tenor API üzerinden GIF ara."""
        query = (query or "").strip()
        if not query:
            return
        key = self._gif_api_key(parent=status_lbl)
        if not key:
            status_lbl.config(
                text="⚠ GIF araması için Tenor API anahtarı gerekli",
                fg=AWAY)
            return
        status_lbl.config(text="⏳ Aranıyor…", fg=FG_DIM)

        def _fetch():
            try:
                url = ("https://tenor.googleapis.com/v2/search?q="
                       + urllib.parse.quote(query)
                       + f"&key={urllib.parse.quote(key)}"
                         "&limit=18&media_filter=tinygif,gif")
                req = urllib.request.Request(
                    url, headers={"User-Agent": "xmpp-client/1.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    payload = json.loads(
                        _read_bounded(resp, _NET_JSON_MAX).decode("utf-8"))
                results = _parse_tenor_results(payload)
                self._safe_after(
                    0, self._show_gif_results, results, grid_f, status_lbl)
            except Exception as e:
                self._safe_after(0, lambda err=str(e): status_lbl.config(
                    text=f"Hata: {err}", fg=RED))

        threading.Thread(target=_fetch, daemon=True).start()

    def _show_gif_results(self, results, grid_f, status_lbl):
        for w in grid_f.winfo_children():
            w.destroy()
        if not results:
            status_lbl.config(text="Sonuç bulunamadı", fg=FG_DIM)
            return
        status_lbl.config(
            text=f"{len(results)} GIF — tıklayınca gönderilir", fg=ACCENT_G)
        for i, g in enumerate(results):
            lbl = tk.Label(grid_f, text="🎞", font=(FONT, 14), fg=FG,
                           bg=BG_HOVER, cursor="hand2", padx=8, pady=8,
                           width=8, height=3)
            lbl.grid(row=i // 3, column=i % 3, padx=3, pady=3)
            lbl.bind("<Button-1>", lambda _, u=g["url"]: self._send_gif(u))
            if HAS_PIL and g.get("preview"):
                self._load_gif_thumb(g["preview"], lbl)

    def _load_gif_thumb(self, url, lbl):
        def _fetch():
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = _read_bounded(resp, _NET_GIF_THUMB_MAX)
                img = Image.open(io.BytesIO(data)).convert("RGBA")
                img.thumbnail((96, 96), Image.LANCZOS)
                def _apply():
                    if lbl.winfo_exists():
                        photo = ImageTk.PhotoImage(img)
                        _media_ui.place_photo(lbl, photo)
                        self._photo_refs.append(photo)
                self._safe_after(0, _apply)
            except Exception:
                pass

        threading.Thread(target=_fetch, daemon=True).start()

    def _send_gif(self, url):
        if not self.active or not self.bot:
            return
        self.msg_var.set(url)
        self._send_message()

    # ── Sohbet yedekleme / geri yükleme ──────────────────────────────────────
    def _backup_dialog(self):
        from tkinter import filedialog
        dlg = tk.Toplevel(self.root)
        dlg.title("Yedekleme / Geri Yükleme")
        dlg.configure(bg=BG_CARD)
        dlg.geometry("380x200")
        dlg.transient(self.root)
        _safe_grab_set(dlg)

        tk.Label(dlg, text="💾 Sohbet Yedekleme", font=(FONT, 12, "bold"),
                 fg=FG, bg=BG_CARD).pack(padx=16, pady=(16, 12))

        def _export_all():
            path = filedialog.asksaveasfilename(
                parent=dlg, defaultextension=".json",
                filetypes=[("JSON", "*.json")],
                title="Yedek Kaydet")
            if not path:
                return
            import json as _json
            backup = {
                "jid": self.jid,
                "chats": {k: v for k, v in self.chats.items()},
                "pinned": self._pinned_chats,
                "config": _load_config(),
            }
            with open(path, "w", encoding="utf-8") as f:
                _json.dump(backup, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Yedek", f"Yedeklendi: {path}", parent=dlg)

        def _import_backup():
            path = filedialog.askopenfilename(
                parent=dlg, filetypes=[("JSON", "*.json")],
                title="Yedek Yükle")
            if not path:
                return
            import json as _json
            try:
                with open(path, "r", encoding="utf-8") as f:
                    backup = _json.load(f)
                chats = backup.get("chats", {})
                for k, v in chats.items():
                    self.chats.setdefault(k, []).extend(v)
                pinned = backup.get("pinned", [])
                for p in pinned:
                    if p not in self._pinned_chats:
                        self._pinned_chats.append(p)
                messagebox.showinfo("Yedek", f"Geri yüklendi: {len(chats)} sohbet",
                                     parent=dlg)
                if self.active:
                    self._load_chat(self.active)
            except Exception as e:
                messagebox.showerror("Hata", str(e), parent=dlg)

        btn_f = tk.Frame(dlg, bg=BG_CARD, padx=16)
        btn_f.pack(fill="x", pady=8)
        ttk.Button(btn_f, text="📤 Yedekle (JSON)",
                   command=_export_all).pack(fill="x", ipady=4, pady=4)
        ttk.Button(btn_f, text="📥 Geri Yükle",
                   command=_import_backup).pack(fill="x", ipady=4)

    # ── QR ile OMEMO doğrulama ───────────────────────────────────────────────
    def _omemo_qr_dialog(self):
        if not self.bot:
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("OMEMO QR Doğrulama")
        dlg.configure(bg=BG_CARD)
        dlg.geometry("340x400")
        dlg.transient(self.root)

        tk.Label(dlg, text="🔐 OMEMO Parmak İzi", font=(FONT, 12, "bold"),
                 fg=FG, bg=BG_CARD).pack(padx=16, pady=(16, 8))

        fp_var = tk.StringVar(value="Yükleniyor…")
        tk.Label(dlg, textvariable=fp_var, font=("Courier", 9),
                 fg=ACCENT, bg=BG_CARD, wraplength=300).pack(padx=16, pady=8)

        qr_holder = tk.Frame(dlg, bg=BG_CARD)
        qr_holder.pack(pady=8)
        state = {"fp": ""}

        def _show(info):
            if not dlg.winfo_exists():
                return
            if not info or info.get("error"):
                fp_var.set("(OMEMO hazır değil)")
                return
            fp = info.get("fingerprint", "")
            state["fp"] = fp
            fp_var.set(fp)
            try:
                import qrcode
                qr = qrcode.make(
                    f"xmpp:{self.jid}?omemo-sid={info.get('device_id', '')}"
                    f"&fp={fp.replace(' ', '')}")
                qr = qr.resize((200, 200))
                photo = ImageTk.PhotoImage(qr)
                qr_lbl = tk.Label(qr_holder, image=photo, bg=BG_CARD)
                qr_lbl.image = photo
                qr_lbl.pack()
                self._photo_refs.append(photo)
            except ImportError:
                tk.Label(qr_holder, text="QR için: pip install qrcode",
                         font=(FONT, 8), fg=FG_DIM,
                         bg=BG_CARD).pack(pady=16)

        self.bot.omemo_device_info(
            lambda info: self._safe_after(0, _show, info))

        # Kopyala butonu
        def _copy():
            if not state["fp"]:
                return
            self.root.clipboard_clear()
            self.root.clipboard_append(state["fp"].replace(" ", ""))
            messagebox.showinfo("Kopyalandı", "Parmak izi panoya kopyalandı",
                                 parent=dlg)
        ttk.Button(dlg, text="📋 Kopyala", command=_copy).pack(pady=8)

    # ── Sohbet arka plan özelleştirme ────────────────────────────────────────
    def _wallpaper_dialog(self):
        from tkinter import colorchooser, filedialog
        dlg = tk.Toplevel(self.root)
        dlg.title("Sohbet Arka Planı")
        dlg.configure(bg=BG_CARD)
        dlg.geometry("340x260")
        dlg.transient(self.root)
        _safe_grab_set(dlg)

        tk.Label(dlg, text="🖼 Sohbet Arka Planı", font=(FONT, 12, "bold"),
                 fg=FG, bg=BG_CARD).pack(padx=16, pady=(16, 12))

        def _choose_image():
            path = filedialog.askopenfilename(
                parent=dlg,
                filetypes=[("Resim", "*.png *.jpg *.jpeg *.gif *.bmp")],
                title="Arka Plan Seç")
            if path:
                self._chat_wallpaper = path
                self._apply_wallpaper()
                cfg = _load_config()
                cfg["chat_wallpaper"] = path
                _save_config(cfg)
                dlg.destroy()

        def _choose_color():
            result = colorchooser.askcolor(parent=dlg, title="Arka Plan Rengi")
            if result and result[1]:
                self._chat_wallpaper = result[1]
                self._apply_wallpaper()
                cfg = _load_config()
                cfg["chat_wallpaper"] = result[1]
                _save_config(cfg)
                dlg.destroy()

        def _reset():
            self._chat_wallpaper = ""
            self._apply_wallpaper()
            cfg = _load_config()
            cfg["chat_wallpaper"] = ""
            _save_config(cfg)
            dlg.destroy()

        btn_f = tk.Frame(dlg, bg=BG_CARD, padx=16)
        btn_f.pack(fill="x", pady=8)
        ttk.Button(btn_f, text="🖼 Resim Seç",
                   command=_choose_image).pack(fill="x", ipady=4, pady=4)
        ttk.Button(btn_f, text="🎨 Renk Seç",
                   command=_choose_color).pack(fill="x", ipady=4, pady=4)
        ttk.Button(btn_f, text="↩ Varsayılana Dön",
                   command=_reset).pack(fill="x", ipady=4)

    def _apply_wallpaper(self):
        wp = self._chat_wallpaper
        if not wp:
            self.chat_canvas.config(bg=BG_CHAT)
            self.msg_frame.config(bg=BG_CHAT)
        elif wp.startswith("#"):
            self.chat_canvas.config(bg=wp)
            self.msg_frame.config(bg=wp)
        elif HAS_PIL and os.path.isfile(wp):
            # Resim arka plan — canvas bg olarak koy
            try:
                img = Image.open(wp)
                cw = self.chat_canvas.winfo_width() or 600
                ch = self.chat_canvas.winfo_height() or 400
                img = img.resize((cw, ch), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.chat_canvas._bg_photo = photo
                self._photo_refs.append(photo)
                # Canvas bg image olarak kullan
                self.chat_canvas.config(bg=BG_CHAT)
                self.chat_canvas.create_image(0, 0, image=photo, anchor="nw",
                                              tags="wallpaper")
                self.chat_canvas.tag_lower("wallpaper")
            except Exception:
                pass

    # ── Kompakt/rahat mod ────────────────────────────────────────────────────
    def _toggle_compact_mode(self):
        self._compact_mode = not self._compact_mode
        cfg = _load_config()
        cfg["compact_mode"] = self._compact_mode
        _save_config(cfg)
        # Mevcut sohbeti yeniden yükle
        if self.active:
            self._load_chat(self.active)

    # ── Klavye kısayolları ───────────────────────────────────────────────────
    def _reply_last_incoming(self):
        """Ctrl+R — son gelen mesaja yanıt başlat."""
        row = self._last_message_row(False)
        if row is None:
            self._append("↩ Yanıtlanacak mesaj yok", "sys")
            return
        self._set_reply(row._mid, getattr(row, "_body", ""),
                        getattr(row, "_sender", ""))

    def _edit_last_own(self):
        """Ctrl+Shift+E — son mesajımı düzenle."""
        row = self._last_message_row(True)
        if row is None or not getattr(row, "_mid", ""):
            self._append("✏ Düzenlenecek mesajım yok", "sys")
            return
        mtype = "groupchat" if self.active in self.rooms else "chat"
        self._edit_message_dialog(row._mid, getattr(row, "_body", ""), mtype)

    def _delete_last_own(self):
        """Ctrl+Shift+D — son mesajımı geri çek."""
        row = self._last_message_row(True)
        if row is None or not getattr(row, "_mid", ""):
            self._append("🗑 Silinecek mesajım yok", "sys")
            return
        mtype = "groupchat" if self.active in self.rooms else "chat"
        self._retract_message(row._mid, mtype)

    def _bind_shortcuts(self):
        self.root.bind("<Control-f>", self._toggle_search_bar)
        self.root.bind("<Control-k>", self._quick_switch_dialog)
        # Widget bağlantısı sınıfın Ctrl+K (satırı kes) davranışından önce çalışır.
        for widget in (getattr(self, "_msg_entry", None),
                       getattr(self, "_sidebar_search", None)):
            if widget is not None:
                widget.bind("<Control-k>", self._quick_switch_dialog)
        self.root.bind("<Control-comma>", lambda _: self._settings_dialog())
        self.root.bind("<Control-n>", lambda _: self._add_contact_dialog())
        self.root.bind("<Control-e>", lambda _: self._show_emoji_picker())
        self.root.bind("<Control-r>", lambda _: self._reply_last_incoming())
        self.root.bind("<Control-Shift-E>", lambda _: self._edit_last_own())
        self.root.bind("<Control-Shift-D>", lambda _: self._delete_last_own())
        self.root.bind("<Control-Shift-M>", lambda _: self._ai_digest())
        self.root.bind("<Control-Shift-H>", lambda _: self._ai_ask_history())
        self.root.bind("<Control-Shift-S>", lambda _: self._ai_dictate())
        self.root.bind("<Control-Shift-Q>",
                       lambda _: self._ai_pending_questions())
        self.root.bind("<Control-Shift-K>", self._ai_assistant_open)
        self.root.bind("<Control-Shift-R>", lambda _: self._ai_drafts_window())
        self.root.bind("<Control-b>", lambda _: self._backup_dialog())
        self.root.bind("<Control-question>", lambda _: self._shortcuts_dialog())
        self.root.bind("<Escape>", self._on_escape)

    def _on_escape(self, event=None):
        # Yanıt modundaysa iptal et
        if self._composer.has_reply():
            self._composer.cancel_reply()
            return
        # Arama çubuğu açıksa kapat
        if hasattr(self, '_search_bar') and self._search_bar.winfo_ismapped():
            self._search_bar.pack_forget()
            return

    def _quick_switch_dialog(self, event=None):
        """Ctrl+K: Hızlı kişi/oda arama ve geçiş (ui/sidebar)."""
        if getattr(self, "_closing", False):
            return "break"

        def _targets(query):
            return _ui_sidebar.quick_switch_targets(
                self._contacts, self.rooms, getattr(self, "_pinned_chats", []),
                getattr(self, "_unread_counts", {}), query)

        def _go(jid, is_room):
            if is_room:
                self._show_members(jid)
            else:
                self._hide_members()
            self._load_chat(jid)
            self._filter_sidebar()

        _ui_sidebar.show_quick_switch(self.root, _targets, _go)
        return "break"

    def _shortcuts_dialog(self):
        """Klavye kısayolları listesi (ui/dialogs/simple)."""
        _ui_simple.show_shortcuts(self.root)

    # ── Sesli mesaj dalga formu + oynatma ────────────────────────────────────
    def _show_voice_waveform(self, bubble, wav_path, bubble_bg):
        """Ses mesajı için dalga formu, oynat/durdur, ilerleme çubuğu göster."""
        is_me = (bubble_bg == BG_ME)
        accent_color = ACCENT if not is_me else "#a5b4fc"
        fg_color = FG_ME if is_me else FG

        wf_frame = tk.Frame(bubble, bg=bubble_bg)
        wf_frame.pack(anchor="w", pady=(4, 2))

        # Oynat/Durdur butonu
        play_btn = tk.Label(wf_frame, text="▶", font=(FONT, 14),
                            fg=accent_color, bg=bubble_bg, cursor="hand2")
        play_btn.pack(side="left", padx=(0, 6))

        # Dalga formu + ilerleme canvas
        wf_width = 180
        wf_height = 32
        wf_canvas = tk.Canvas(wf_frame, width=wf_width, height=wf_height,
                               bg=bubble_bg, highlightthickness=0)
        wf_canvas.pack(side="left")

        # Süre/örnek çözümü worker'da yapılır (P1-5); GUI yalnız başlığı bekler
        duration = 0
        bars = []
        dur_txt = "0:00"

        # Süre etiketi
        dur_lbl = tk.Label(wf_frame, text=dur_txt, font=(FONT, 7, "bold"),
                           fg=fg_color, bg=bubble_bg, width=4)
        dur_lbl.pack(side="left", padx=(6, 0))

        # Dalga formu çiz
        def _draw_waveform(progress: float = 0.0):
            """progress: 0.0-1.0 arasında oynatma ilerleme oranı."""
            _audio_ui.draw_waveform(wf_canvas, bars, wf_width, wf_height,
                                    progress, accent_color, _chat_theme(),
                                    is_me)

        _draw_waveform(0.0)

        # Dalga formu verisi arka planda hazırlanır; hazır olunca çizilir
        def _bars_ready(new_duration, new_bars):
            if not wf_canvas.winfo_exists():
                return
            nonlocal duration
            duration = new_duration
            bars.extend(new_bars)
            if duration > 0:
                _audio_ui.set_duration(dur_lbl, duration)
            _draw_waveform(0.0)

        threading.Thread(
            target=lambda: self._safe_after(
                0, _bars_ready, *self._load_waveform_bars(wav_path)),
            daemon=True).start()

        # Oynatma durumu (GUI + oynatma thread'i kilitle korunur)
        state = {"playing": False, "stop_flag": False, "pa_stream": None,
                 "proc": None, "gen": 0}
        state_lock = threading.Lock()

        def _request_stop():
            """Dışarıdan (kapanış/relogin) stop isteği: oturumu geçersiz kıl,
            aktif stream/fallback prosesi kapat. Tk'ya dokunmaz."""
            with state_lock:
                state["gen"] += 1
                state["stop_flag"] = True
                state["playing"] = False
                proc = state["proc"]
                state["proc"] = None
            # PyAudio stream'ine burada DOKUNULMAZ: Pa_StopStream başka
            # thread'in bloklu Pa_WriteStream'iyle eşzamanlı güvenli değil
            # (write takılı kalır, stream/PortAudio sızar). Oynatma thread'i
            # stop_flag'i her parçada görüp stream'i kendisi kapatır.
            try:
                if proc and proc.poll() is None:
                    proc.terminate()
            except Exception:
                pass

        # Kapanış/relogin tüm aktif oynatıcılara erişebilsin (V-5)
        players = getattr(self, "_voice_players", None)
        if players is None:
            try:
                players = weakref.WeakKeyDictionary()
            except Exception:
                players = {}
            self._voice_players = players
        try:
            players[bubble] = _request_stop
        except TypeError:
            pass

        def _stop_requested(my_gen=None):
            # Yeni oturum (gen) başladıysa eski thread de durur: hızlı
            # durdur→oynat'ta iki ses üst üste binmesin.
            with state_lock:
                return state["stop_flag"] or (
                    my_gen is not None and state["gen"] != my_gen)

        def _apply_progress(my_gen, progress, label_text):
            with state_lock:
                if state["gen"] != my_gen:
                    return
            if not wf_canvas.winfo_exists():
                return
            _draw_waveform(progress)
            if label_text and dur_lbl.winfo_exists():
                dur_lbl.config(text=label_text)

        def _toggle_play(_=None):
            with state_lock:
                playing = state["playing"]
                if playing:
                    state["stop_flag"] = True
                    state["playing"] = False
                    my_gen = 0
                else:
                    state["gen"] += 1
                    my_gen = state["gen"]
                    state["playing"] = True
                    state["stop_flag"] = False
            if playing:
                # Durdur: yalnız bayrak; stream'i oynatma thread'i kapatır
                _audio_ui.set_play_icon(play_btn, False)
            else:
                # Oynat
                _audio_ui.set_play_icon(play_btn, True)
                threading.Thread(target=_play_thread, args=(my_gen,),
                                 daemon=True).start()

        def _play_thread(my_gen):
            try:
                if _HAS_PYAUDIO:
                    # Durdurma başka thread'den stop_stream() çağırır ve
                    # stream.write burada hata fırlatır; kaynaklar her yolda
                    # serbest bırakılmalı (aksi halde PortAudio/dosya sızar).
                    wf = pa = stream = None
                    try:
                        wf = wave.open(wav_path, "rb")
                        pa = pyaudio.PyAudio()
                        stream = pa.open(
                            format=pa.get_format_from_width(wf.getsampwidth()),
                            channels=wf.getnchannels(),
                            rate=wf.getframerate(), output=True)
                        with state_lock:
                            state["pa_stream"] = stream
                        total = wf.getnframes()
                        played = 0
                        chunk = 1024
                        data = wf.readframes(chunk)
                        while data and not _stop_requested(my_gen):
                            stream.write(data)
                            played += chunk
                            # İlerleme güncelle
                            prog = min(1.0, played / total) if total > 0 else 0
                            elapsed = prog * duration
                            e_min = int(elapsed) // 60
                            e_sec = int(elapsed) % 60
                            self._safe_after(0, _apply_progress, my_gen, prog,
                                             f"{e_min}:{e_sec:02d}")
                            data = wf.readframes(chunk)
                    finally:
                        with state_lock:
                            if state["pa_stream"] is stream:
                                state["pa_stream"] = None
                        for close in ((stream.stop_stream if stream else None),
                                      (stream.close if stream else None),
                                      (pa.terminate if pa else None),
                                      (wf.close if wf else None)):
                            if close is None:
                                continue
                            try:
                                close()
                            except Exception:
                                pass
                else:
                    # Fallback: sistem oynatıcı (kapanışta terminate edilebilir)
                    import subprocess
                    proc = subprocess.Popen(
                        ["paplay", wav_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
                    with state_lock:
                        cancel_proc = (state["stop_flag"]
                                       or state["gen"] != my_gen)
                        if not cancel_proc:
                            state["proc"] = proc
                    if cancel_proc:
                        try:
                            proc.terminate()
                        except Exception:
                            pass
                    try:
                        proc.wait(timeout=int(duration) + 5)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass
                    with state_lock:
                        if state["proc"] is proc:
                            state["proc"] = None
            except Exception:
                pass
            with state_lock:
                if state["gen"] != my_gen:
                    return  # eski thread yeni oturumun state'ini ezmesin
                state["playing"] = False
                state["stop_flag"] = False
            # Sıfırla (destroyed widget → no-op)
            def _reset_ui():
                if not wf_canvas.winfo_exists():
                    return
                _audio_ui.set_play_icon(play_btn, False)
                _draw_waveform(0.0)
                if dur_lbl.winfo_exists():
                    _audio_ui.set_duration(dur_lbl, duration)
            self._safe_after(0, _reset_ui)

        play_btn.bind("<Button-1>", _toggle_play)

        # Tıklayarak ilerleme atla
        def _seek(event):
            if not bars:
                return
            ratio = event.x / wf_width
            ratio = max(0.0, min(1.0, ratio))
            _draw_waveform(ratio)
            s = int(ratio * duration)
            dur_lbl.config(text=f"{s // 60}:{s % 60:02d}")
        wf_canvas.bind("<Button-1>", _seek)

    def _stop_voice_playback(self):
        """Tüm aktif ses oynatıcılarına stop sinyali gönder (V-5).

        Kapanış/relogin'de çağrılır; handler'lar Tk'ya dokunmaz. Idempotent.
        """
        players = getattr(self, "_voice_players", None)
        if not players:
            return
        for handler in list(players.values()):
            try:
                handler()
            except Exception:
                _log.warning("Ses oynatıcı durdurulamadı", exc_info=True)
        try:
            players.clear()
        except Exception:
            pass

    def _load_waveform_bars(self, wav_path):
        """WAV örneklerini çöz, (süre, 45 barlık veri) döndür (worker).

        GUI thread'ini bloklamamak için `_show_voice_waveform` bunu
        arka plan thread'inde çalıştırır (P1-5).
        """
        duration = 0.0
        bars = []
        try:
            with wave.open(wav_path, "rb") as wf:
                n_frames = wf.getnframes()
                rate = wf.getframerate()
                duration = n_frames / rate if rate > 0 else 0.0
                raw = wf.readframes(n_frames)
            n_samples = len(raw) // 2
            if n_samples > 0:
                samples = struct.unpack(f"<{n_samples}h", raw)
                bar_count = 45
                step = max(1, n_samples // bar_count)
                for i in range(0, n_samples, step):
                    chunk = samples[i:i + step]
                    val = max(abs(s) for s in chunk) if chunk else 0
                    bars.append(val)
                bars = bars[:bar_count]
        except Exception:
            pass
        return duration, bars

    # ── Mesaj zamanlama ──────────────────────────────────────────────────────
    def _schedule_message_dialog(self):
        if not self.active:
            return
        pop = tk.Toplevel(self.root)
        pop.title("Mesaj Zamanla")
        pop.configure(bg=BG_CARD)
        pop.geometry("340x280")
        pop.transient(self.root)
        _safe_grab_set(pop)

        tk.Label(pop, text="⏰ Mesaj Zamanla", font=(FONT, 12, "bold"),
                 fg=FG, bg=BG_CARD).pack(padx=16, pady=(16, 8))

        # Mesaj
        tk.Label(pop, text="Mesaj:", font=(FONT, 9),
                 fg=FG_DIM, bg=BG_CARD).pack(anchor="w", padx=16)
        msg_var = tk.StringVar()
        ttk.Entry(pop, textvariable=msg_var, font=(FONT, 10)).pack(
            fill="x", padx=16, ipady=5, pady=(0, 8))

        # Süre (dakika)
        tk.Label(pop, text="Kaç dakika sonra gönderilsin:", font=(FONT, 9),
                 fg=FG_DIM, bg=BG_CARD).pack(anchor="w", padx=16)
        delay_var = tk.IntVar(value=5)
        delay_f = tk.Frame(pop, bg=BG_CARD)
        delay_f.pack(fill="x", padx=16)
        for val, txt in [(1, "1 dk"), (5, "5 dk"), (15, "15 dk"),
                         (30, "30 dk"), (60, "1 saat")]:
            tk.Radiobutton(delay_f, text=txt, variable=delay_var, value=val,
                          bg=BG_CARD, fg=FG, selectcolor=BG_HOVER,
                          font=(FONT, 8)).pack(side="left", padx=(0, 6))

        # Özel dakika
        custom_f = tk.Frame(pop, bg=BG_CARD)
        custom_f.pack(fill="x", padx=16, pady=(4, 0))
        tk.Label(custom_f, text="Özel (dk):", font=(FONT, 8),
                 fg=FG_DIM, bg=BG_CARD).pack(side="left")
        custom_var = tk.StringVar()
        ttk.Entry(custom_f, textvariable=custom_var, width=6,
                  font=(FONT, 9)).pack(side="left", padx=(4, 0))

        target = self.active

        def _schedule():
            body = msg_var.get().strip()
            if not body:
                return
            try:
                mins = int(custom_var.get()) if custom_var.get().strip() else delay_var.get()
            except ValueError:
                mins = delay_var.get()
            if self._schedule_send(target, body, mins, parent=pop):
                pop.destroy()

        ttk.Button(pop, text="⏰ Zamanla", command=_schedule).pack(
            fill="x", padx=16, ipady=4, pady=12)

    def _schedule_send(self, target, body, mins, parent=None) -> bool:
        """Mesajı `mins` dk sonra gönder. Şifreleme ve hassas veri uyarısı
        ZAMANLAMA anında (hedef sohbet açıkken) belirlenir; gönderim anında
        başka bir sohbet açık olabilir."""
        enc = self._encryption_mode.get()
        if not self._leak_guard_ok(target, body, enc, parent=parent):
            return False
        short = body if len(body) <= 40 else body[:40] + "…"
        self._append(f"⏰ Zamanlanmış mesaj ({mins} dk sonra): {short}", "sys")

        def _send_scheduled():
            if not self.bot:
                return
            mid = _new_msg_id()
            self._store(target, body, tag="me", sender="Ben", is_me=True,
                        mid=mid)
            if self.active == target:
                # [2F] Canlı teslim: append / rebase / defer
                self._deliver_live(target, lambda: self._append(
                    body, "me", sender="Ben", is_me=True, mid=mid))
            if target in self.rooms:
                self.bot.send_gc(target, body, encryption=enc, mid=mid)
            else:
                self.bot.send_chat(target, body, encryption=enc, mid=mid)

        self._after(mins * 60 * 1000, _send_scheduled)
        return True

    # ── Kişi grupları / etiketler ────────────────────────────────────────────
    def _contact_groups_dialog(self):
        """Kişi grupları penceresi (ui/dialogs/contact)."""
        cfg = _load_config()
        groups = cfg.get("contact_groups", {})  # {group_name: [jid, ...]}
        _ui_contact.show_contact_groups(
            self.root, self._contacts, groups, self._save_contact_groups)

    # ── Oda yönetim paneli ───────────────────────────────────────────────────
    def _room_admin_dialog(self):
        """Oda Yönetimi penceresi (ui/dialogs/rooms)."""
        if not self.active or self.active not in self.rooms:
            return
        room = self.active

        def _set_subject(new_subj):
            if not self.bot:
                return False
            self.bot.set_room_subject(room, new_subj)
            self._room_subjects[room] = new_subj
            return True

        def _invite(jid):
            if not self.bot:
                return False
            jid = self._jid_or_warn(jid, "Davet")
            if not jid:
                return False
            self.bot.invite_to_room(room, jid)
            return True

        _ui_rooms.show_room_admin(
            self.root, room, self.room_members.get(room, {}),
            self._room_subjects.get(room, ""), self._contacts,
            _set_subject, _invite)

    # ── Toplu mesaj (broadcast) ──────────────────────────────────────────────
    def _broadcast_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Toplu Mesaj")
        dlg.configure(bg=BG_CARD)
        dlg.geometry("420x400")
        dlg.transient(self.root)
        _safe_grab_set(dlg)

        tk.Label(dlg, text="📢 Toplu Mesaj Gönder", font=(FONT, 12, "bold"),
                 fg=FG, bg=BG_CARD).pack(padx=16, pady=(16, 8))

        tk.Label(dlg, text="Mesaj:", font=(FONT, 9),
                 fg=FG_DIM, bg=BG_CARD).pack(anchor="w", padx=16)
        msg_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=msg_var, font=(FONT, 10)).pack(
            fill="x", padx=16, ipady=5, pady=(0, 8))

        tk.Label(dlg, text="Alıcıları seçin:", font=(FONT, 9),
                 fg=FG_DIM, bg=BG_CARD).pack(anchor="w", padx=16)

        lb = tk.Listbox(dlg, bg=BG_PANEL, fg=FG, selectbackground=SEL_BG,
                         font=(FONT, 9), selectmode="multiple",
                         relief="flat", highlightthickness=0)
        lb.pack(fill="both", expand=True, padx=16, pady=4)
        jids = sorted(self._contacts.keys())
        for j in jids:
            lb.insert("end", f"  {self._contacts[j] or j}")

        count_lbl = tk.Label(dlg, text="0 kişi seçildi", font=(FONT, 8),
                              fg=FG_DIM, bg=BG_CARD)
        count_lbl.pack(padx=16)
        lb.bind("<<ListboxSelect>>",
                lambda _: count_lbl.config(text=f"{len(lb.curselection())} kişi seçildi"))

        def _send():
            body = msg_var.get().strip()
            if not body:
                return
            sel = lb.curselection()
            if not sel:
                return
            enc = self._encryption_mode.get()
            for i in sel:
                # Alıcı başına ayrı kimlik: düzenleme/geri çekme ve sunucu
                # yankısıyla eşleşme bu kimliğe dayanır
                mid = _new_msg_id()
                self.bot.send_chat(jids[i], body, encryption=enc, mid=mid)
                self._store(jids[i], body, tag="me", sender="Ben", is_me=True,
                            mid=mid)
            messagebox.showinfo("Toplu Mesaj",
                                f"{len(sel)} kişiye gönderildi", parent=dlg)
            dlg.destroy()

        ttk.Button(dlg, text="📨 Gönder", command=_send).pack(
            fill="x", padx=16, ipady=4, pady=8)

    # ── Toast bildirim balonu ────────────────────────────────────────────────
    def _show_toast(self, title, message, duration=4000):
        """Sağ alt köşede kaybolabilen bildirim."""
        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(bg=ACCENT2)

        # Konum: sağ alt
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        tw, th = 300, 80
        toast.geometry(f"{tw}x{th}+{sw - tw - 20}+{sh - th - 60}")

        inner = tk.Frame(toast, bg=BG_CARD, padx=12, pady=8)
        inner.pack(fill="both", expand=True, padx=2, pady=2)
        tk.Label(inner, text=title, font=(FONT, 9, "bold"),
                 fg=FG, bg=BG_CARD).pack(anchor="w")
        tk.Label(inner, text=message[:80], font=(FONT, 8),
                 fg=FG_DIM, bg=BG_CARD, wraplength=270).pack(anchor="w")

        # Tıklayınca kapat
        toast.bind("<Button-1>", lambda _: toast.destroy())
        # Otomatik kaybol
        toast.after(duration, lambda: toast.destroy() if toast.winfo_exists() else None)

    # ── Otomatik tema geçişi (saate göre) ────────────────────────────────────
    def _auto_theme_check(self):
        """Saate göre otomatik tema geçişi. Zincir her zaman yeniden kurulur."""
        # Önceki zamanlayıcıyı iptal et — çoklu zincir oluşmasın.
        old_id = getattr(self, "_auto_theme_id", None)
        if old_id is not None:
            try:
                self.root.after_cancel(old_id)
            except Exception:
                pass
            self._auto_theme_id = None

        cfg = _load_config()
        if cfg.get("auto_theme", False):
            hour = datetime.now().hour
            day_theme = cfg.get("day_theme", "acik")
            night_theme = cfg.get("night_theme", "koyu")
            day_start = cfg.get("day_start_hour", 7)
            night_start = cfg.get("night_start_hour", 20)

            target = (day_theme if day_start <= hour < night_start
                      else night_theme)
            current = cfg.get("theme", "koyu")
            if target != current:
                _apply_color_theme(target)
                self._refresh_theme()
                cfg["theme"] = target
                _save_config(cfg)

        # Her 10 dakikada kontrol et (kapalıyken de zincir canlı kalır)
        if not getattr(self, "_closing", False):
            self._auto_theme_id = self._after(600000, self._auto_theme_check)

    def _auto_theme_dialog(self):
        cfg = _load_config()
        dlg = tk.Toplevel(self.root)
        dlg.title("Otomatik Tema Geçişi")
        dlg.configure(bg=BG_CARD)
        dlg.geometry("360x300")
        dlg.transient(self.root)
        _safe_grab_set(dlg)

        tk.Label(dlg, text="🌓 Otomatik Tema Geçişi", font=(FONT, 12, "bold"),
                 fg=FG, bg=BG_CARD).pack(padx=16, pady=(16, 12))

        auto_var = tk.BooleanVar(value=cfg.get("auto_theme", False))
        tk.Checkbutton(dlg, text="Otomatik tema geçişini etkinleştir",
                       variable=auto_var, bg=BG_CARD, fg=FG,
                       selectcolor=BG_HOVER, font=(FONT, 9)).pack(anchor="w", padx=16)

        themes = list(_THEMES.keys())
        tk.Label(dlg, text="Gündüz teması:", font=(FONT, 9),
                 fg=FG_DIM, bg=BG_CARD).pack(anchor="w", padx=16, pady=(12, 0))
        day_var = tk.StringVar(value=cfg.get("day_theme", "acik"))
        ttk.Combobox(dlg, textvariable=day_var, values=themes,
                     state="readonly", font=(FONT, 9)).pack(fill="x", padx=16)

        tk.Label(dlg, text="Gece teması:", font=(FONT, 9),
                 fg=FG_DIM, bg=BG_CARD).pack(anchor="w", padx=16, pady=(8, 0))
        night_var = tk.StringVar(value=cfg.get("night_theme", "koyu"))
        ttk.Combobox(dlg, textvariable=night_var, values=themes,
                     state="readonly", font=(FONT, 9)).pack(fill="x", padx=16)

        tk.Label(dlg, text="Gündüz başlangıç saati:", font=(FONT, 9),
                 fg=FG_DIM, bg=BG_CARD).pack(anchor="w", padx=16, pady=(8, 0))
        day_h = tk.IntVar(value=cfg.get("day_start_hour", 7))
        tk.Scale(dlg, from_=0, to=23, orient="horizontal", variable=day_h,
                 bg=BG_CARD, fg=FG, troughcolor=BG_HOVER,
                 highlightthickness=0, activebackground=ACCENT).pack(
                     fill="x", padx=16)

        tk.Label(dlg, text="Gece başlangıç saati:", font=(FONT, 9),
                 fg=FG_DIM, bg=BG_CARD).pack(anchor="w", padx=16, pady=(4, 0))
        night_h = tk.IntVar(value=cfg.get("night_start_hour", 20))
        tk.Scale(dlg, from_=0, to=23, orient="horizontal", variable=night_h,
                 bg=BG_CARD, fg=FG, troughcolor=BG_HOVER,
                 highlightthickness=0, activebackground=ACCENT).pack(
                     fill="x", padx=16)

        def _save():
            cfg = _load_config()
            cfg["auto_theme"] = auto_var.get()
            cfg["day_theme"] = day_var.get()
            cfg["night_theme"] = night_var.get()
            cfg["day_start_hour"] = day_h.get()
            cfg["night_start_hour"] = night_h.get()
            _save_config(cfg)
            if auto_var.get():
                self._auto_theme_check()
            dlg.destroy()

        ttk.Button(dlg, text="Kaydet", command=_save).pack(
            fill="x", padx=16, ipady=4, pady=12)

    # ── Uygulama kilidi (PIN) ────────────────────────────────────────────────
    def _pin_lock_dialog(self):
        cfg = _load_config()
        dlg = tk.Toplevel(self.root)
        dlg.title("Uygulama Kilidi")
        dlg.configure(bg=BG_CARD)
        dlg.geometry("320x240")
        dlg.transient(self.root)
        _safe_grab_set(dlg)

        tk.Label(dlg, text="🔑 Uygulama Kilidi", font=(FONT, 12, "bold"),
                 fg=FG, bg=BG_CARD).pack(padx=16, pady=(16, 12))

        has_pin = bool(cfg.get("app_pin"))

        if has_pin:
            tk.Label(dlg, text="Mevcut PIN ayarlanmış ✓", font=(FONT, 9),
                     fg=ACCENT_G, bg=BG_CARD).pack(anchor="w", padx=16)

            def _remove_pin():
                old = simpledialog.askstring("PIN Doğrula", "Mevcut PIN:",
                                              parent=dlg, show="*")
                if old and _verify_pin(cfg.get("app_pin", ""), old):
                    cfg.pop("app_pin", None)
                    _save_config(cfg)
                    messagebox.showinfo("PIN", "PIN kaldırıldı", parent=dlg)
                    dlg.destroy()
                else:
                    messagebox.showerror("Hata", "Yanlış PIN", parent=dlg)

            ttk.Button(dlg, text="🗑 PIN'i Kaldır",
                       command=_remove_pin).pack(fill="x", padx=16, ipady=4, pady=8)
        else:
            tk.Label(dlg, text="Yeni PIN belirleyin:", font=(FONT, 9),
                     fg=FG_DIM, bg=BG_CARD).pack(anchor="w", padx=16)
            pin_var = tk.StringVar()
            pe = ttk.Entry(dlg, textvariable=pin_var, show="*",
                           font=(FONT, 14))
            pe.pack(fill="x", padx=16, ipady=5, pady=(0, 4))
            pe.focus_set()

            tk.Label(dlg, text="Tekrar girin:", font=(FONT, 9),
                     fg=FG_DIM, bg=BG_CARD).pack(anchor="w", padx=16)
            pin2_var = tk.StringVar()
            ttk.Entry(dlg, textvariable=pin2_var, show="*",
                      font=(FONT, 14)).pack(fill="x", padx=16, ipady=5)

            def _set_pin():
                p1 = pin_var.get().strip()
                p2 = pin2_var.get().strip()
                if not p1 or len(p1) < 4:
                    messagebox.showwarning("PIN", "PIN en az 4 karakter olmalı",
                                            parent=dlg)
                    return
                if p1 != p2:
                    messagebox.showerror("Hata", "PIN'ler eşleşmiyor", parent=dlg)
                    return
                cfg["app_pin"] = _encode_pw(p1)
                _save_config(cfg)
                messagebox.showinfo("PIN", "PIN ayarlandı ✓", parent=dlg)
                dlg.destroy()

            ttk.Button(dlg, text="🔒 PIN Ayarla",
                       command=_set_pin).pack(fill="x", padx=16, ipady=4, pady=8)

    # ── Mesaj geçmişi silme ──────────────────────────────────────────────────
    def _clear_history_dialog(self):
        """Mesaj geçmişi silme penceresi (ui/dialogs)."""
        _ui_chat_options.show_clear_history(
            self.root,
            sum(len(v) for v in self.chats.values()), len(self.chats),
            bool(self.active),
            self._clear_active_history, self._clear_all_history)

    # ── Anonim bağlantı (proxy/SOCKS) ────────────────────────────────────────
    def _proxy_dialog(self):
        cfg = _load_config()
        dlg = tk.Toplevel(self.root)
        dlg.title("Proxy Ayarları")
        dlg.configure(bg=BG_CARD)
        dlg.geometry("380x360")
        dlg.transient(self.root)
        _safe_grab_set(dlg)

        tk.Label(dlg, text="🔒 Proxy / SOCKS Ayarları", font=(FONT, 12, "bold"),
                 fg=FG, bg=BG_CARD).pack(padx=16, pady=(16, 12))

        proxy_cfg = cfg.get("proxy", {})

        tk.Label(dlg, text="Proxy türü:", font=(FONT, 9),
                 fg=FG_DIM, bg=BG_CARD).pack(anchor="w", padx=16)
        type_var = tk.StringVar(value=proxy_cfg.get("type", "none"))
        type_f = tk.Frame(dlg, bg=BG_CARD)
        type_f.pack(fill="x", padx=16)
        for val, txt in [("none", "Yok"), ("socks5", "SOCKS5"),
                         ("socks4", "SOCKS4"), ("http", "HTTP")]:
            tk.Radiobutton(type_f, text=txt, variable=type_var, value=val,
                          bg=BG_CARD, fg=FG, selectcolor=BG_HOVER,
                          font=(FONT, 8)).pack(side="left", padx=(0, 8))

        tk.Label(dlg, text="Adres:", font=(FONT, 9),
                 fg=FG_DIM, bg=BG_CARD).pack(anchor="w", padx=16, pady=(8, 0))
        host_var = tk.StringVar(value=proxy_cfg.get("host", "127.0.0.1"))
        ttk.Entry(dlg, textvariable=host_var, font=(FONT, 10)).pack(
            fill="x", padx=16, ipady=4)

        tk.Label(dlg, text="Port:", font=(FONT, 9),
                 fg=FG_DIM, bg=BG_CARD).pack(anchor="w", padx=16, pady=(4, 0))
        port_var = tk.StringVar(value=str(proxy_cfg.get("port", 9050)))
        ttk.Entry(dlg, textvariable=port_var, font=(FONT, 10)).pack(
            fill="x", padx=16, ipady=4)

        tk.Label(dlg, text="💡 Tor için: SOCKS5, 127.0.0.1:9050",
                 font=(FONT, 7), fg=FG_DIM, bg=BG_CARD).pack(
                     anchor="w", padx=16, pady=(8, 0))
        tk.Label(dlg, text="Yalnız XMPP bağlantısı proxy'den geçer; dosya "
                           "yükleme/indirme, bağlantı önizlemesi, GIF ve AI "
                           "istekleri geçmez. Kimlik doğrulamalı proxy "
                           "desteklenmez.",
                 font=(FONT, 7), fg=FG_DIM, bg=BG_CARD, wraplength=340,
                 justify="left").pack(anchor="w", padx=16, pady=(4, 0))

        def _save():
            try:
                value = _proxy_from_form(type_var.get(), host_var.get(),
                                         port_var.get())
            except ValueError as e:
                messagebox.showerror("Proxy", str(e), parent=dlg)
                return
            cfg = _load_config()
            cfg["proxy"] = value
            _save_config(cfg)
            messagebox.showinfo("Proxy", "Ayarlar kaydedildi.\n"
                                "Bir sonraki bağlantıda uygulanır "
                                "(ör. uygulamayı yeniden başlatınca).",
                                parent=dlg)
            dlg.destroy()

        ttk.Button(dlg, text="Kaydet", command=_save).pack(
            fill="x", padx=16, ipady=4, pady=12)

    # ── Bot komutları (/komut) ───────────────────────────────────────────────
    def _handle_bot_command(self, body):
        """Giriş alanından gelen /komut'ları işle."""
        parts = body.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        commands = {
            "/help": lambda: self._append(
                "Kullanılabilir komutlar:\n"
                "/help — Bu yardım\n"
                "/clear — Sohbet geçmişini temizle\n"
                "/nick <isim> — Oda takma adını değiştir\n"
                "/topic <konu> — Oda konusunu değiştir\n"
                "/invite <jid> — Odaya davet et\n"
                "/kick <nick> — Odadan at\n"
                "/ban <jid> — Yasakla\n"
                "/join <oda> — Odaya katıl\n"
                "/leave — Odadan ayrıl\n"
                "/status <mesaj> — Durum mesajı değiştir\n"
                "/ping — Sunucu ping\n"
                "/time — Şu anki saat\n"
                "/broadcast — Toplu mesaj\n"
                "/schedule — Mesaj zamanla\n"
                "/reply <metin> — Son gelen mesaja yanıt ver\n"
                "/react <emoji> — Son gelen mesaja tepki ekle\n"
                "/edit <metin> — Son mesajımı düzenle\n"
                "/del — Son mesajımı sil",
                "sys"),
            "/clear": lambda: self._clear_active_history(),
            # [Phase6A-F1] Önceden tuple-lambda bellek-içi temizliği yapıyor
            # ama canonical DB silgisini (_db_clear_chat) atlıyordu; MAM
            # arşivi/restart sonrası "silinen" geçmiş geri geliyordu. Tek
            # yetkili yol canonical _clear_active_history'e delege edilir.
            "/ping": lambda: self._append(
                f"📶 Son ping: {self._last_ping_ms}ms", "sys"),
            "/time": lambda: self._append(
                f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "sys"),
            "/broadcast": lambda: self._broadcast_dialog(),
            "/schedule": lambda: self._schedule_message_dialog(),
        }

        if cmd in commands:
            commands[cmd]()
        elif cmd == "/nick" and arg and self.active in self.rooms:
            self.bot.change_nick(self.active, arg.strip())
            self.my_nick[self.active] = arg.strip()
            self._append(f"Takma ad değiştirildi: {arg.strip()}", "sys")
        elif cmd == "/topic" and self.active in self.rooms:
            self.bot.set_room_subject(self.active, arg.strip())
            self._append(f"Konu değiştirildi: {arg.strip()}", "sys")
        elif cmd == "/invite" and arg and self.active in self.rooms:
            jid = self._jid_or_warn(arg, "Davet")
            if jid:
                self.bot.invite_to_room(self.active, jid)
                self._append(f"Davet gönderildi: {jid}", "sys")
        elif cmd == "/kick" and arg and self.active in self.rooms:
            try:
                self.bot.kick_user(self.active, arg.strip())
                self._append(f"Kullanıcı atıldı: {arg.strip()}", "sys")
            except Exception as e:
                self._append(f"Hata: {e}", "sys")
        elif cmd == "/ban" and arg and self.active in self.rooms:
            jid = self._jid_or_warn(arg, "Yasakla")
            if jid:
                self.bot.ban_user(self.active, jid)
                self._append(f"Kullanıcı yasaklanıyor: {jid}", "sys")
        elif cmd == "/join" and arg:
            room = self._join_room_normalized(arg, self.jid.split("@")[0])
            if room:
                self._append(f"Odaya katılınıyor: {room}", "sys")
        elif cmd == "/leave" and self.active in self.rooms:
            self._append(f"Odadan ayrılınıyor: {self.active}", "sys")
            self._leave_room(self.active)
        elif cmd == "/status" and arg:
            self._publish_status(arg.strip(), "chat")
            self._append(f"Durum güncellendi: {arg.strip()}", "sys")
        elif cmd == "/reply" and arg:
            self._reply_last_incoming()
            if self._composer.has_reply():
                self.msg_var.set(arg)
                self._send_message()
        elif cmd == "/react" and arg:
            row = self._last_message_row(False)
            if row is not None:
                self._toggle_reaction(row._mid, arg.strip()[:8])
            else:
                self._append("😊 Tepki verilecek mesaj yok", "sys")
        elif cmd == "/edit" and arg:
            row = self._last_message_row(True)
            if row is not None and getattr(row, "_mid", ""):
                mtype = "groupchat" if self.active in self.rooms else "chat"
                self.bot.send_correction(self.active, arg, row._mid, mtype)
                # Normal düzenleme yolu: balon + geçmiş + DB birlikte
                self._apply_local_correction(self.active, row._mid, arg)
            else:
                self._append("✏ Düzenlenecek mesajım yok", "sys")
        elif cmd == "/del":
            self._delete_last_own()
        else:
            self._append(f"Bilinmeyen komut: {cmd}\n/help yazarak yardım alabilirsiniz", "sys")

    # ── Çoklu sohbet sekmeleri ───────────────────────────────────────────────
    def _tab_evict_oldest_row(self, rows):
        """[2H] Detaylı sekme canlı satır sınırı: ekleme ÖNCESİ cap altına in.

        Söndürme eklemeden ÖNCE yapılır: satır sayısı hiçbir an sınırı
        aşmaz (peak = _DETACHED_TAB_MAX_ROWS). Yalnız sunumdur — self.chats
        geçmişine dokunulmaz; hem gelen/own-send `add` yolu hem sekmenin
        kendi gönderme yolu bu tek mekanizmayı kullanır.
        """
        while len(rows) >= self._DETACHED_TAB_MAX_ROWS:
            old = rows.pop(0)
            try:
                old.destroy()
            except Exception:
                pass

    def _remove_tab_row(self, rows, row):
        """[2L] Tab-lokal TTL temizliği: satırı FIFO'dan kimliğiyle çıkar,
        widget'ı güvenle söndür.

        Yalnız sunumdur: self.chats, _ttl_deadlines (2K mezar taşları), MAM
        durumuna dokunmaz. Bayat zamanlayıcı zararsızdır — satır 2H cap'ince
        zaten tahliye edilmişse rows.remove sessizce pas geçer; sekme
        kapatılıp yerine yenisi açılmışsa rows listesi sekme-örneği lokal
        olduğundan yeni sekmenin FIFO'suna dokunamaz.
        """
        try:
            rows.remove(row)
        except ValueError:
            pass
        try:
            row.destroy()
        except Exception:
            pass

    def _open_chat_tab(self, target=None):
        """Yeni bir sohbet sekmesi aç (split view benzeri)."""
        if target is None:
            target = self.active
        if not target:
            return

        top = tk.Toplevel(self.root)
        short = target.split("@")[0] if "@" in target else target
        top.title(f"Sohbet — {short}")
        top.configure(bg=BG_CHAT)
        top.geometry("500x500")

        # Mesaj alanı
        canvas = tk.Canvas(top, bg=BG_CHAT, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        msg_f = tk.Frame(canvas, bg=BG_CHAT)
        canvas.create_window((0, 0), window=msg_f, anchor="nw")
        msg_f.bind("<Configure>",
                   lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Button-4>", lambda _: canvas.yview_scroll(-3, "units"))
        canvas.bind("<Button-5>", lambda _: canvas.yview_scroll(3, "units"))

        # Geçmişi göster
        rows: list = []  # [2H] sekmenin yaşayan satır kaydı (FIFO, sekme başına)

        def _add(entry):
            # [2H] Canlı sınır: ekleme ÖNCE cap altına in (peak asla cap+1
            # olmaz); en eski satır söner, en yeni içerik görünür kalır.
            self._tab_evict_oldest_row(rows)
            sender, body, is_me, ts, _tag = entry[:5]
            # [2L] TTL paritesi: tek yetkili haritadan (target, örnek-uid)
            # çöz. Metadata yok → normal; canlı → yalnız KALAN ömür kadar
            # tab-lokal temizlik zamanlanır; dolmuş mezar taşı (2K) → satır
            # ÇİZİLMEZ, taş hiçbir yoldan kaldırılmaz ve TTL asla sekme
            # açılışında yeniden başlamaz. Eski/UID'siz girişler mid
            # fallback'iyle ana TTL çizim davranışını izler.
            uid = self._entry_instance_uid(entry)
            deadlines = getattr(self, "_ttl_deadlines", None)
            # [2L-B1] mid şart DEĞİL: güncel girişler uid ile adreslenir
            # (mid="" olsa da — sekmenin kendi gönderimi); eski girişler
            # mid fallback'iyle çözer; uid="" (çözülemeyen) normal çizilir.
            deadline = (deadlines.get((target, uid))
                        if (deadlines and uid) else None)
            now = time.monotonic()
            if deadline is not None and deadline - now <= 0:
                return
            bubble_bg = BG_ME if is_me else BG_THEM
            bubble_fg = FG_ME if is_me else FG
            row = tk.Frame(msg_f, bg=BG_CHAT)
            row.pack(fill="x", padx=12, pady=2)
            bubble = tk.Frame(row, bg=bubble_bg, padx=10, pady=6)
            if is_me:
                bubble.pack(side="right", anchor="e", padx=(40, 0))
            else:
                bubble.pack(side="left", anchor="w", padx=(0, 40))
            if not is_me and sender:
                tk.Label(bubble, text=sender, fg=ACCENT, bg=bubble_bg,
                         font=(FONT, 7, "bold")).pack(anchor="w")
            tk.Label(bubble, text=body, fg=bubble_fg, bg=bubble_bg,
                     font=(FONT, 9), wraplength=350, justify="left").pack(anchor="w")
            tk.Label(bubble, text=ts, fg=FG_DIM, bg=bubble_bg,
                     font=(FONT, 6)).pack(anchor="e")
            rows.append(row)
            if deadline is not None:
                # [2L] Tab-lokal kaldırma: satır-örneğine bağlı closure; FIFO
                # + widget ağacı birlikte temizlenir, başka hiçbir şeye
                # dokunulmaz (bayat timer için _remove_tab_row zararsızdır).
                self.root.after(
                    max(0.0, deadline - now) * 1000,
                    lambda r=row: self._remove_tab_row(rows, r))
            canvas.yview_moveto(1.0)

        history = self.chats.get(target, [])
        # [2F-Blocker] Ayrı sekme de sınırlıdır: en yeni K mesaj; toplam
        # stored history'nin O(N) render'ı hiçbir üretim yolunda olamaz.
        # Sekmeler pencere durumunu PAYLAŞMAZ; gezinme mimarisi ayrıdır.
        window = history[max(0, len(history) - self._HISTORY_WINDOW_SIZE):]
        for entry in window:
            # [2L] Başlangıç render TTL paritesi: _add yetkili haritadan
            # çözerek dolmuş girişi atlar, canlıyı kalan ömürle yaşatır.
            _add(entry)

        # Canlı güncelleme için kaydı tut; pencere kapanınca düşür
        self._chat_tabs[target] = {
            "win": top, "frame": msg_f, "canvas": canvas, "add": _add,
            "rows": rows,
        }
        top.protocol("WM_DELETE_WINDOW", lambda t=target, w=top: (
            self._chat_tabs.pop(t, None), w.destroy()))

        # Giriş alanı
        inp_f = tk.Frame(top, bg=BG_CARD, padx=8, pady=8)
        inp_f.pack(fill="x", side="bottom")
        inp_f.columnconfigure(0, weight=1)
        msg_v = tk.StringVar()
        entry = ttk.Entry(inp_f, textvariable=msg_v, font=(FONT, 10))
        entry.grid(row=0, column=0, sticky="ew", ipady=6)
        entry.focus_set()

        def _send(_=None):
            body = msg_v.get().strip()
            if not body or not self.bot:
                return
            # Sekmenin hedefi için kayıtlı mod (aktif sohbetin modu değil)
            enc = self._chat_enc_modes.get(target, "none")
            if not self._leak_guard_ok(target, body, enc, parent=top):
                return
            msg_v.set("")
            mtype = "groupchat" if target in self.rooms else "chat"
            self._store(target, body, tag="me", sender="Ben", is_me=True)
            if mtype == "groupchat":
                self.bot.send_gc(target, body, encryption=enc)
            else:
                self.bot.send_chat(target, body, encryption=enc)
            # [2L-B1] TTL paritesi (kimlik = örnek-UID; mid ŞART DEĞİL):
            # store → giriş/uid → mutlak vade kaydı → _add; sekme yetkiliyi
            # eklemeden ÖNCE görür. Inline send mid ÜRETMEZ (wire dokunulmaz);
            # _disappearing_ttl bare çiftlerde olmayabilir (guard'lı okuma).
            hist = self.chats.get(target) or []
            ttl_tab = getattr(self, "_disappearing_ttl", {}).get(target, 0)
            if ttl_tab > 0 and hist:
                uid_tab = self._entry_instance_uid(hist[-1])
                if uid_tab:
                    self._record_ttl_deadline(target, uid_tab, ttl_tab)
            # Balona ekle — [2L] aynı sınırlı TTL-parite yolu: evict + TTL
            # çözümü _add içinde; tam alan girişi (uid'li) ile beslenir.
            if hist:
                _add(hist[-1])

        entry.bind("<Return>", _send)
        send_btn = tk.Label(inp_f, text="➤", font=(FONT, 14),
                            fg=ACCENT, bg=BG_CARD, cursor="hand2")
        send_btn.grid(row=0, column=1, padx=(6, 0))
        send_btn.bind("<Button-1>", _send)

    # ── Bölünmüş ekran ──────────────────────────────────────────────────────
    def _split_view_dialog(self):
        """İki sohbeti yan yana göster."""
        if len(self.chats) < 2:
            messagebox.showinfo("Bölünmüş Ekran",
                                "En az 2 sohbet gerekli", parent=self.root)
            return

        pop = tk.Toplevel(self.root)
        pop.title("Bölünmüş Ekran — İkinci sohbet seçin")
        pop.configure(bg=BG_CARD)
        pop.geometry("300x300")
        pop.transient(self.root)

        lb = tk.Listbox(pop, bg=BG_PANEL, fg=FG, selectbackground=SEL_BG,
                         font=(FONT, 9), relief="flat", highlightthickness=0)
        lb.pack(fill="both", expand=True, padx=12, pady=12)

        targets = sorted(self.chats.keys())
        for t in targets:
            short = t.split("@")[0] if "@" in t else t
            lb.insert("end", f"  {short}")

        def _go(_=None):
            sel = lb.curselection()
            if sel:
                pop.destroy()
                self._open_chat_tab(targets[sel[0]])

        lb.bind("<Double-1>", _go)
        ttk.Button(pop, text="Aç", command=_go).pack(
            fill="x", padx=12, ipady=4, pady=(0, 12))

    # ── Polling / Olay işleme ─────────────────────────────────────────────────
    def _poll(self):
        self._poll_id = None
        if getattr(self, "_closing", False):
            return
        try:
            while True:
                kind, data = self.gui_q.get_nowait()
                try:
                    self._handle(kind, data)
                except Exception:
                    _log.error("Olay işlenemedi (kind=%s)", kind, exc_info=True)
                # _handle içinde _quit çağrıldıysa (auth_failed/relogin) Tk
                # yıkılmıştır; kuyrukta kalan olayları işlemeye devam etme.
                if getattr(self, "_closing", False):
                    return
        except queue.Empty:
            pass
        finally:
            # Tek bir olayın hatası döngüyü asla durdurmamalı.
            if not getattr(self, "_closing", False):
                try:
                    self._poll_id = self.root.after(100, self._poll)
                except Exception:
                    self._poll_id = None

    def _handle(self, kind, data):
        if kind == "connected":
            if self._conn_timeout_id:
                self.root.after_cancel(self._conn_timeout_id)
                self._conn_timeout_id = None
            self._contacts = data
            self._refresh_contacts()
            self._append("✓ Bağlandı", "sys")
            if getattr(self, "_last_conn_error", ""):
                self._last_conn_error = ""
                self._show_toast("✓ Bağlantı Kuruldu", "Sunucuya bağlanıldı")
            try:
                self._status_label.config(text="● Online", fg=ONLINE)
                self._restore_status_prefs()
            except Exception:
                _log.warning("Durum mesajı geri yüklenemedi", exc_info=True)
            # Son açık sohbeti geri yükle (yalnızca kayıtlı kişi ise)
            _last = _load_config().get("last_chat", "")
            if _last and _last in self._contacts:
                try:
                    self._load_chat(_last)
                except Exception:
                    _log.warning("Son sohbet geri yüklenemedi: %s", _last,
                                 exc_info=True)
            # Kayıtlı PGP anahtar eşleştirmelerini yükle
            self._load_pgp_keymap()
            # Kayıtlı odalara otomatik katıl
            self._rejoin_saved_rooms()
            # Avatarları yükle (kendi + kişiler)
            self._fetch_avatars()
            # Uzun süredir yanıt bekleyen soru varsa bir kez hatırlat
            self._questions_nudge()

        elif kind == "msg":
            frm  = data["from"]
            nick = data["nick"]
            body = data["body"]
            oob  = data.get("oob", "")
            enc  = data.get("encrypted", False)
            mid  = data.get("mid", "")
            is_enc = bool(enc)
            reply = self._resolve_reply(data.get("reply"), frm)
            self._remember_mid(frm, mid)
            # Gelen OMEMO mesajı → o sohbet için OMEMO'yu otomatik aç
            if enc == "omemo" and self._chat_enc_modes.get(frm) != "omemo":
                self._chat_enc_modes[frm] = "omemo"
                if self.active == frm:
                    self._encryption_mode.set("omemo")
                    self._update_enc_btn(silent=True)
            # [2O] Materialization dedupe (tek yetkili sınır): MAM kopyası
            # ile birebir eşleşen replay, _store yan etkilerinden ÖNCE
            # bastırılır (exact-match ya da ters-alias kanıtıyla; fail-open).
            if mid and self._is_live_duplicate(frm, mid, body, False):
                return
            self._store(frm, body, tag="them", sender=nick, is_me=False,
                        oob=oob, encrypted=is_enc, mid=mid, reply_to=reply)
            self._ai_away_note_message(frm)
            # [2I][2J.b][2L] TTL vadesi teslim anında kaydedilir — defer
            # (history modu) dahil; dönüşte kalan süre geçerlidir, sıfırlanmaz.
            # [2L] Kayıt sekme beslemesinden ÖNCE yapılır (yalnız aktif
            # sohbet — pasif sohbetin "kayıt yok" mevcut politikası değişmez;
            # _disappearing_ttl da yalnız aktif dalda okunur — bare test
            # çiftleri bu özniteliği taşımaz): sekme kalan süreyi yetkili
            # haritadan çözer. Defter anahtarı girişin örnek UID'sidir
            # (store az önce girişi ekledi); eski/UID'siz girişlerde mid'e düşer.
            ttl = 0
            uid = ""
            if self.active == frm:
                ttl = self._chat_ttl(frm)
                # [2L-B1] mid şart DEĞİL: kimlik örnek-UID'dir (store az önce
                # girişi uid'le ekledi); eski girişler mid fallback'iyle çözer.
                if ttl > 0:
                    hist_last = (self.chats.get(frm) or [None])[-1]
                    uid = self._entry_instance_uid(hist_last, mid)
                    if uid:
                        self._record_ttl_deadline(frm, uid, ttl)
            # Ayrı sohbet penceresi açıksa canlı güncelle — [2L] tam alan
            # girişi (uid'li) ile beslenir; TTL çözümü _add içindedir
            tab = self._chat_tabs.get(frm)
            if tab and tab["win"].winfo_exists():
                try:
                    hist = self.chats.get(frm) or []
                    tab["add"](hist[-1] if hist else
                               (nick or frm, body, False,
                                datetime.now().strftime("%H:%M"), "them"))
                except Exception:
                    _log.warning("Sohbet sekmesi güncellenemedi", exc_info=True)
            if self.active == frm:
                # [2F] Canlı teslim: append / rebase / defer (E/F)
                live_action = self._deliver_live(
                    frm, lambda: self._append(
                        body, "them", sender=nick, is_me=False,
                        oob=oob, encrypted=is_enc, mid=mid,
                        reply_to=reply))
                if live_action != "defer":
                    # Okundu bilgisi gönder
                    if mid and self.bot and self._send_read_receipts:
                        self.bot.send_marker(frm, mid, "displayed")
                    # Kaybolan mesaj zamanlayıcısı (kalan süreyle — [2I])
                    if ttl > 0:
                        last_row = self._bubble_widgets[-1] if self._bubble_widgets else None
                        if last_row:
                            self._schedule_disappear(
                                last_row, self._ttl_remaining(frm, uid, ttl))
            else:
                # [2F] History modunda kayıtlı pasif sohbet: pending sayacı
                self._note_inactive_live(frm)
                # Okunmamış sayacı artır
                self._unread_counts[frm] = self._unread_counts.get(frm, 0) + 1
                self._refresh_contacts()
                total = sum(self._unread_counts.values())
                icon = ("🔒" if enc == "omemo" else
                        "🔑" if enc == "pgp" else "🔔")
                badge = f" [{total}]" if total > 0 else ""
                self.root.title(f"XMPP — {self.jid}{badge}  {icon}  {frm}")
                # Şifreli medya bağlantısı (aesgcm://) çözme anahtarı taşır:
                # bildirim geçmişine düşmesin, yer tutucu gösterilir
                notify_body = (_ai.strip_media_urls(body)
                               if "aesgcm://" in (body or "").lower() else body)
                # Masaüstü bildirimi
                if self._notify_enabled:
                    _desktop_notify(f"Mesaj — {nick or frm}",
                                    notify_body[:100] if notify_body else "Yeni mesaj")
                # Bildirim sesi
                if self._sound_enabled:
                    threading.Thread(target=self._play_notification_sound,
                                     daemon=True).start()
                # Toast bildirim balonu
                self._show_toast(f"💬 {nick or frm}",
                                 notify_body[:80] if notify_body else "Yeni mesaj")

        elif kind == "own_msg":
            # Aynı hesabın başka cihazından (ör. telefondaki Monocles)
            # gönderilmiş mesaj: carbon (1:1) ya da aynı takma adlı oda
            # oturumu. Bizim mesajımız gibi saklanır ve gösterilir.
            to = data["to"]
            body = data["body"]
            mid = data.get("mid", "")
            oob = data.get("oob", "")
            is_enc = bool(data.get("encrypted", False))
            reply = self._resolve_reply(data.get("reply"), to)
            self._remember_mid(to, mid)
            if mid and self._is_live_duplicate(to, mid, body, True):
                return
            self._store(to, body, tag="me", sender="Ben", is_me=True,
                        oob=oob, encrypted=is_enc, mid=mid, reply_to=reply)
            tab = self._chat_tabs.get(to)
            if tab and tab["win"].winfo_exists():
                try:
                    hist = self.chats.get(to) or []
                    tab["add"](hist[-1] if hist else
                               ("Ben", body, True,
                                datetime.now().strftime("%H:%M"), "me"))
                except Exception:
                    _log.warning("Sohbet sekmesi güncellenemedi", exc_info=True)
            if self.active == to:
                self._deliver_live(to, lambda: self._append(
                    body, "me", sender="Ben", is_me=True, oob=oob,
                    encrypted=is_enc, mid=mid, reply_to=reply))
            # Telefondan yanıt verildiyse sohbet masaüstünde okunmamış kalmaz
            if self._unread_counts.pop(to, None):
                self._refresh_contacts()

        elif kind == "read_elsewhere":
            # Sohbet aynı hesabın başka cihazında okundu (XEP-0333 carbon)
            if self._unread_counts.pop(data, None):
                self._refresh_contacts()

        elif kind == "search_results":
            items = data.get("items", [])
            err = data.get("error", "")
            try:
                lb = self._search_list_ref
                jids = self._search_jids_ref
                lb.delete(0, "end")
                jids.clear()
                if err:
                    lb.insert("end", f"  Arama hatası: {err[:60]}")
                    jids.append(None)
                elif not items:
                    lb.insert("end", "  Sonuç bulunamadı")
                    jids.append(None)
                else:
                    for item in items:
                        jid_val = item.get("jid", item.get("email", ""))
                        name = item.get("name", item.get("fn", jid_val))
                        line = f"  {name}  —  {jid_val}" if name != jid_val else f"  {jid_val}"
                        lb.insert("end", line)
                        jids.append(jid_val)
            except Exception:
                pass

        elif kind == "mam_results":
            jid_val = data.get("jid", "")
            # Bayat (temizlik sonrası eski generation) sonuçları yok say
            token = data.get("token")
            if token is not None and token != getattr(self, "_mam_gen", {}).get(jid_val, 0):
                # [2F-Blocker] Bayat sonuç yalnız KENDİ token'ına ait niyeti
                # düşürebilir; yeni isteğin sahipliğine dokunamaz (D kuralı).
                if hasattr(self, "_history_mam_intent"):
                    self._mam_consume_intent(jid_val, token)
                return
            msgs = data.get("messages", [])
            # [2F] Sahiplik: niyet yalnız o isteğin token'ını taşıyan sonuçla
            # tüketilir; farklı sonuç pasif prepend sayılır (C/D kuralı).
            intent = (self._mam_consume_intent(jid_val, token)
                      if hasattr(self, "_history_mam_intent") else None)
            if not msgs:
                self._mam_has_more[jid_val] = False
            else:
                hist = self.chats.get(jid_val, [])
                # [2N] Muhafazakâr imza dedupe: (kimlik-alias, body, yön).
                # Eski mid-only `seen` yerine mevcut geçmişten imzalar
                # kurulur — yalnız non-empty stored_mid katılır.
                seen = {(e[7], e[1], bool(e[2]))
                        for e in hist if len(e) > 7 and e[7]}
                fresh = []
                for m in msgs:
                    logical_mid = m.get("mid", "")
                    raw_id = m.get("raw_id", "")
                    body = m["body"]
                    direction = bool(m["is_me"])
                    aliases = {a for a in (logical_mid, raw_id) if a}
                    # [2N] Alias kimliği TEK BAŞINA duplikasyon kanıtı
                    # değildir: aynı alias + FARKLI gövde ya da FARKLI yön
                    # KORUNUR (sunucu-ekli stanza-id ↔ live raw-id kesişimi
                    # tek başına silme gerekçesi olamaz). Kimliği hiç
                    # olmayan mesajlar asla dedupe edilmez.
                    if aliases and any((a, body, direction) in seen
                                       for a in aliases):
                        continue
                    sender = ("Ben" if m["is_me"]
                              else (m.get("nick")
                                    or m["from"].split("@")[0]))
                    tag = "me" if m["is_me"] else "them"
                    # Yalnız logical_mid depolanır; raw_id/archive_id
                    # geçicidir ve self.chats biçimine girmez.
                    fresh.append((sender, body, m["is_me"],
                                  self._iso_to_hm(m.get("ts", "")), tag,
                                  "", False, logical_mid, "",
                                  self._next_msg_uid()))
                    # [2O] Ters-korelasyon kaydı: yalnız KABUL edilen
                    # (canonical satırı materialize edilen) mesaj için;
                    # raw_id ≠ logical_mid ise R → S alias'ı yazılır.
                    # archive_id burada ASLA kullanılmaz.
                    if raw_id and raw_id != logical_mid:
                        self._mam_alias_register(jid_val, raw_id,
                                                 logical_mid, body,
                                                 m["is_me"])
                    # [2N] Sayfa-içi dedupe: kabul edilen mesajın TÜM
                    # non-empty alias imzaları kayda geçer.
                    for a in aliases:
                        seen.add((a, body, direction))
                if fresh:
                    self.chats[jid_val] = fresh + hist
                # [2N] İmleç taşıma üstverisidir: archive_id varsa imleç O'dur;
                # logical_mid fallback yalnız eski/test uyumluluğu içindir.
                first_cursor = (msgs[0].get("archive_id")
                                or msgs[0].get("mid", ""))
                if first_cursor:
                    self._mam_oldest[jid_val] = first_cursor
                # [Phase B1] İmleç türetilemeyen sayfada continuation False
                # (fail-stop): aksi hâlde aynı sayfa cursor'sız sonsuza dek
                # yeniden istenir (livelock).
                self._mam_has_more[jid_val] = (
                    len(msgs) >= 50 and bool(first_cursor))
                # [2F] Pencere uyumu: initial / older / pasif ayrımı (G/H/J)
                self._adjust_history_window_for_mam(jid_val, len(fresh),
                                                    intent)

        elif kind == "file_uploaded":
            url = data["url"]
            target = data.get("cb", self.active)
            if target:
                body = url
                # Deterministik korelasyon: optimistic row, gönderilen stanza
                # ve sent_mid aynı origin-id'yi taşır (V-2).
                mid = _new_msg_id()
                self._store(target, body, tag="me", sender="Ben", is_me=True,
                            oob=url, mid=mid)
                if self.active == target:
                    # [2F] Canlı teslim: append / rebase / defer
                    self._deliver_live(target, lambda: self._append(
                        body, "me", sender="Ben", is_me=True, oob=url,
                        mid=mid))
                if target in self.rooms:
                    self.bot.send_gc(target, body, mid=mid)
                else:
                    self.bot.send_chat(target, body, mid=mid)

        elif kind == "ft_offer":
            self._ft_offer_dialog(data)

        elif kind == "ft_state":
            if data.get("state") == "waiting_accept" and data.get("direction") == "out":
                key = (data.get("peer", ""), data.get("name", ""))
                path = self._ft_pending_out.pop(key, "")
                if path:
                    self._ft_sent_paths[data.get("sid", "")] = path

        elif kind == "ft_progress":
            self._ft_update_progress(data)

        elif kind == "ft_done":
            self._ft_finished(data)

        elif kind == "ft_error":
            self._ft_error(data)

        elif kind == "bookmarks":
            self._show_bookmarks(data)

        elif kind == "bookmarks_update":
            cb = data.get("cb")
            if cb:
                try:
                    cb(data.get("bookmarks", []))
                except Exception:
                    _log.error("Yer imi callback'i çöktü", exc_info=True)

        elif kind == "blocked_list":
            items = data.get("items", [])
            cb = data.get("cb")
            if cb:
                try:
                    cb(items)
                except Exception:
                    _log.error("Engelli liste callback'i çöktü", exc_info=True)

        elif kind == "marker_displayed":
            frm = data["from"]
            mid = data["mid"]
            # Aktif sohbetteki son mesajımıza "✓✓" işareti ekle
            if self.active == frm:
                for w in reversed(self._bubble_widgets):
                    if getattr(w, "_is_me", False) and getattr(w, "_mid", "") == mid:
                        # Zaman damgası frame'ine okundu işareti ekle
                        for child in w.winfo_children():
                            for sub in child.winfo_children():
                                if isinstance(sub, tk.Frame) and sub.cget("bg") == BG_ME:
                                    for ts_child in sub.winfo_children():
                                        if isinstance(ts_child, tk.Frame):
                                            tk.Label(ts_child, text=" ✓✓",
                                                     font=(FONT, 6), fg=ACCENT_G,
                                                     bg=BG_ME).pack(side="left")
                                            break
                        break

        elif kind == "presence":
            self.presence[data["jid"]] = data["pshow"] or data["ptype"]
            self._refresh_contacts()

        elif kind == "room_joined":
            room = data
            if room not in self.rooms:
                self.rooms.append(room)
                self.room_members[room] = {}
                self._filter_sidebar()
            self._load_chat(room)
            self._show_members(room)
            self._append(f"✓ {room} odasına katıldı", "sys")
            self._save_room(room)

        elif kind == "room_created":
            self._room_created(data)

        elif kind == "room_taken":
            self._room_taken(data)

        elif kind == "room_exists":
            self._append(
                f"ℹ {data['room']} zaten vardı: mevcut odaya katıldınız, "
                "ayarları değiştirilmedi.", "sys")

        elif kind == "room_left":
            room = data
            if room in self.rooms:
                self.rooms.remove(room)
                self.room_members.pop(room, None)
                self._filter_sidebar()
            self._remove_room(room)
            if self.active == room:
                self.active = None
                self.chat_title.config(text="Bir kişi veya oda seçin")
                self._chat_shell.show_empty_state()
                self._hide_members()

        elif kind == "muc_presence":
            room  = data["room"]
            nick  = data["nick"]
            mbrs  = self.room_members.setdefault(room, {})
            if data["online"]:
                mbrs[nick] = {
                    "role":  data.get("role", ""),
                    "affil": data.get("affil", ""),
                    "show":  data.get("show", ""),
                }
            else:
                mbrs.pop(nick, None)
            if self.active == room:
                self._refresh_members(room)

        elif kind == "muc_subject":
            room = data["room"]
            subject = data["subject"]
            self._room_subjects[room] = subject
            if self.active == room:
                if subject:
                    short_subj = (subject[:60] + "…") if len(subject) > 60 else subject
                    self._chat_subject.config(text=f"📌 {short_subj}")
                    self._chat_subject.pack(anchor="w")
                    # [2G] Oda başına tek konu balonu: her stanza yeni balon
                    # EKLEMEZ; güncel konu eskisinin yerine geçer (sınırlı yol).
                    self._show_room_subject(room, f"📌 Konu: {subject}")
                else:
                    self._chat_subject.config(text="")
                    self._chat_subject.pack_forget()

        elif kind == "room_config":
            room = data["room"]
            form = data["form"]
            self._show_room_config_form(room, form)

        elif kind == "typing":
            jid = data["jid"]
            if data["active"]:
                self._typing.add(jid)
            else:
                self._typing.discard(jid)
            self._refresh_typing_indicator()

        elif kind == "muc_invite":
            room   = data["room"]
            reason = data["reason"]
            ans = messagebox.askyesno(
                "MUC Daveti",
                f"{room} odasına davet edildiniz.\n"
                f"Sebep: {reason or '—'}\n\nKabul et?",
                parent=self.root)
            if ans:
                nick = self.jid.split("@")[0]
                self.my_nick[room] = nick
                self.bot.join_room(room, nick)

        elif kind == "subscribe_req":
            jid = data
            ans = messagebox.askyesno(
                "Arkadaşlık İsteği",
                f"{jid} sizi takip etmek istiyor.\nKabul et?",
                parent=self.root)
            self.bot.approve_subscribe(jid, ans)
            if ans:
                self.bot.add_contact(jid)

        elif kind == "contact_removed":
            jid = data
            self._contacts.pop(jid, None)
            self._refresh_contacts()
            if self.active == jid:
                self.active = None
                self.chat_title.config(text="Bir kişi veya oda seçin")
                self._chat_shell.show_empty_state()

        elif kind == "sys_msg":
            self._append(data, "sys")
            # OMEMO hazır olduğunda şifreleme menüsünü güncelle
            if "OMEMO" in str(data) and "hazır" in str(data):
                # Aktif sohbette OMEMO seçiliyse badge'ı yenile
                if self._encryption_mode.get() == "omemo":
                    self._update_enc_btn(silent=True)

        elif kind == "api_draft":
            # REST/MCP taslağı — gönderilmez, taslak kutusuna eklenir
            self._ai_add_draft(data["to"], [data["text"]],
                               source=f"🔌 {data.get('source') or 'REST API'}")

        elif kind == "api_store":
            # REST thread'inden gelen kayıt — GUI thread'inde _store
            self._store(data["target"], data["body"],
                        tag=data.get("tag", "them"),
                        sender=data.get("sender", ""),
                        is_me=data.get("is_me"))

        elif kind == "__ui__":
            # Worker/loop thread'inden gelen Tk işi (P1-3)
            fn, args = data
            fn(*args)

        elif kind == "rooms_discovered":
            self._show_rooms_browser(data)

        elif kind == "rooms_discover_failed":
            # Diyalog kapanmış ve açık sohbet olmayabilir: sys balonu
            # görünmezdi, bu yüzden her zaman görünür bilgi kutusu.
            messagebox.showinfo("Oda Keşfi", data, parent=self.root)

        elif kind == "auth_failed":
            if self._conn_timeout_id:
                self.root.after_cancel(self._conn_timeout_id)
                self._conn_timeout_id = None
            messagebox.showerror("Giriş Hatası", data, parent=self.root)
            self._relogin = True
            self._quit()

        elif kind == "sent_mid":
            to = data["to"]
            mid = data["mid"]
            self._msg_ids.setdefault(to, []).append(mid)
            # Yalnız hedef sohbet aktifse UI yaması uygula (yanlış sohbete sızmasın)
            if to != self.active:
                return
            # Row zaten bu mid ile doğduysa yama gerekmez; başka bir
            # mid'siz satıra da yazılmamalı (deterministik korelasyon).
            if _identity.find_row_by_mid(self._bubble_widgets, mid) is not None:
                return
            # Fail-safe: birden fazla unresolved outgoing varsa hangisine ait
            # olduğu belirsizdir; yanlış satırı mutasyona uğratmak yerine
            # unresolved bırak.
            unresolved = [w for w in self._bubble_widgets
                          if getattr(w, "_is_me", False)
                          and not getattr(w, "_mid", "")]
            if len(unresolved) != 1:
                if len(unresolved) > 1:
                    _log.warning(
                        "sent_mid: %d unresolved outgoing satır — eşleme "
                        "belirsiz, yama atlandı (mid=%s, to=%s)",
                        len(unresolved), mid, to)
                return
            # Son gönderilen balonumuza mid ata (mid zaten atanmış olabilir)
            target = unresolved[0]
            target._mid = mid
            rep = getattr(target, "_reply_to", None)
            if rep:
                # [2M] preview sahipliği: mid'li alan girişinin örnek-uid'i
                # (ters tarama); bulunamazsa (to, mid) legacy fallback
                entry_uid = ""
                for e in reversed(self.chats.get(to, [])):
                    if (len(e) > 9 and e[9] and len(e) > 7 and e[7] == mid):
                        entry_uid = e[9]
                        break
                self._remember_reply(to, entry_uid or mid, rep)
                # [2J.a] (jid, mid) kapsamlı — to, hedef sohbetin kimliğidir
                _db_update_msg_reply(to, mid, rep.get("id", ""),
                                     rep.get("sender", ""),
                                     rep.get("body", ""))
            if self._reactions.get((to, mid)):
                # [2M] Policy C: mid'li TÜM satırlar aynı sunumu alır
                self._refresh_reaction_rows(to, mid)

        elif kind == "vcard":
            cb = data.get("cb")
            if cb:
                try:
                    cb(data.get("info"))
                except Exception:
                    _log.error("vCard callback'i çöktü", exc_info=True)

        elif kind == "omemo_fps":
            cb = data.get("cb")
            if cb:
                if data.get("error"):
                    cb({"error": data["error"]})
                else:
                    cb({"devices": data.get("fps", [])})

        elif kind == "msg_correction":
            self._apply_local_correction(data["from"], data["orig_id"],
                                         data["body"])

        elif kind == "msg_retract":
            self._apply_local_retraction(data["from"], data["retracted_id"])

        elif kind == "msg_reactions":
            frm = data["from"]
            target_id = data["target_id"]
            nick = data["nick"]
            emojis = data["emojis"]
            my_names = {"Ben"}
            my_jid = getattr(self, "jid", "") or ""
            persist = bool(my_jid)
            if my_jid:
                my_names.add(my_jid.split("@")[0])
            if frm in getattr(self, "rooms", ()):
                my_names.add(getattr(self, "my_nick", {}).get(frm, ""))
            # Tepki deposunu güncelle — [2M] (jid, mid) kapsamlı
            rkey = (frm, target_id)
            reactions = self._reactions.setdefault(rkey, {})
            if emojis:
                for em in emojis:
                    senders = reactions.setdefault(em, [])
                    if nick not in senders:
                        senders.append(nick)
                    if persist:
                        _db_save_reaction(frm, target_id, em, nick, True)
            else:
                # Boş küme = geri çekme: nick'i tüm emojilerden çıkar
                for em in list(reactions.keys()):
                    if nick in reactions[em]:
                        reactions[em].remove(nick)
                        if persist:
                            _db_save_reaction(frm, target_id, em, nick, False)
                    if not reactions[em]:
                        del reactions[em]
            if not reactions:
                self._reactions.pop(rkey, None)
            # Kendi tepkilerim (başka cihazdan gelmiş olabilir)
            mine_map = getattr(self, "_my_reactions", None)
            if mine_map is None:
                mine_map = {}
                self._my_reactions = mine_map
            if persist and nick in my_names:
                mine_now = {em for em, senders in reactions.items()
                            if nick in senders}
                if mine_now:
                    mine_map[rkey] = mine_now
                else:
                    mine_map.pop(rkey, None)
            # Depo büyümesini sınırla (en eski girdiler düşer) — [2M] cap
            # artık 500 (jid, mid) kapsamlı anahtar üzerinden sayılır
            while len(self._reactions) > 500:
                self._reactions.pop(next(iter(self._reactions)))
            # Aktif sohbette ilgili balonun altına tepkileri göster —
            # [2M] Policy C: mid'li TÜM aktif satırlar aynı sunumu alır
            if self.active == frm:
                self._refresh_reaction_rows(frm, target_id)

        elif kind == "error":
            messagebox.showerror("Hata", data, parent=self.root)

        elif kind == "disconnected":
            # [2O] Bağlantı kopması: ters-alias registry oturum-yerelidir
            self._mam_alias_clear_all()
            # [Phase B3] Bağlantı kopması uçuştaki MAM isteklerinin
            # sonuçlarını da öldürür: niyetler stale kalıp sonraki
            # yüklemeleri kilitlemesin diye temizlenir.
            self._history_mam_intent.clear()
            self._append("⚠ Bağlantı kesildi", "sys")

        elif kind == "conn_failed":
            detail = str(data.get("error", "")) or "bilinmeyen hata"
            domain = str(data.get("domain", "") or "")
            port = data.get("port", 5222)
            where = data.get("address", "") or (
                f"{domain}:{port}" if domain else "")
            first = detail != getattr(self, "_last_conn_error", "")
            self._last_conn_error = detail
            try:
                self._status_label.config(text="⚠ Bağlanılamadı", fg=RED)
            except Exception:
                pass
            self._append(
                f"⚠ Bağlantı başarısız{(' (' + where + ')') if where else ''}: "
                f"{detail}", "sys")
            now = time.time()
            if first or now - getattr(self, "_last_conn_toast_ts", 0.0) > 30:
                self._last_conn_toast_ts = now
                self._show_toast(
                    f"⚠ {_t('disconnected')}",
                    f"{where + ' — ' if where else ''}{detail}")

    # ── Anket oluşturma ─────────────────────────────────────────────────────
    def _poll_dialog(self):
        if not self.active or not self.bot:
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("📊 Anket Oluştur")
        dlg.configure(bg=BG_CARD)
        dlg.geometry("400x380")
        dlg.transient(self.root)
        _safe_grab_set(dlg)

        tk.Label(dlg, text="📊 Anket Oluştur", font=(FONT, 12, "bold"),
                 fg=FG, bg=BG_CARD).pack(padx=16, pady=(16, 8))

        tk.Label(dlg, text="Soru:", font=(FONT, 9),
                 fg=FG, bg=BG_CARD).pack(anchor="w", padx=16)
        q_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=q_var, font=(FONT, 10)).pack(
            fill="x", padx=16, ipady=5, pady=(0, 8))

        tk.Label(dlg, text="Seçenekler (her satır bir seçenek):", font=(FONT, 9),
                 fg=FG, bg=BG_CARD).pack(anchor="w", padx=16)
        opts_text = tk.Text(dlg, height=6, font=(FONT, 9), bg=BG_INPUT,
                            fg=FG, insertbackground=FG)
        opts_text.pack(fill="x", padx=16, pady=(0, 8))
        opts_text.insert("1.0", "Evet\nHayır\nKararsızım")

        def _send_poll():
            question = q_var.get().strip()
            options = [opt.strip() for opt in opts_text.get("1.0", "end").strip().split("\n") if opt.strip()]
            if not question or len(options) < 2:
                messagebox.showwarning("Anket", "Soru ve en az 2 seçenek gerekli", parent=dlg)
                return
            # Anketi emoji numaralarıyla mesaj olarak gönder
            lines = [f"📊 **{question}**", ""]
            emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
            for i, opt in enumerate(options[:9]):
                lines.append(f"{emojis[i]} {opt}")
            lines.append("\n💡 Oy vermek için ilgili emoji ile tepki ekleyin")
            body = "\n".join(lines)
            mtype = "groupchat" if self.active in self.rooms else "chat"
            mid = _new_msg_id()
            if mtype == "groupchat":
                self.bot.send_gc(self.active, body, mid=mid)
            else:
                self.bot.send_chat(self.active, body, mid=mid)
            self._store(self.active, body, tag="me", sender="Ben", is_me=True,
                        mid=mid)
            self._append(body, "me", sender="Ben", is_me=True, mid=mid)
            dlg.destroy()

        ttk.Button(dlg, text="📊 Anketi Gönder", command=_send_poll).pack(
            padx=16, pady=8, fill="x", ipady=4)

    # ── Hikaye/durum paylaşımı (PEP) ────────────────────────────────────────
    def _story_dialog(self):
        """Hikaye/Durum penceresi (ui/profile)."""
        _ui_profile.show_story_dialog(self.root, self._publish_story)

    def _publish_story(self, text, mood, photo_path):
        """Hikaye yayınla: metin → durum mesajı, mood → XEP-0107, fotoğraf →
        profil resmi (kare 256 px PNG). Ağ işleri bot thread'inde; hatalar
        bot üzerinden görünür bildirilir."""
        if not self.bot:
            return
        if text:
            self._publish_status(text, "chat")
        if mood:
            self.bot.publish_mood(mood, text)
        if photo_path:
            try:
                data = _square_avatar_png(photo_path)
            except Exception as e:
                messagebox.showerror("Hikaye", f"Fotoğraf okunamadı: {e}",
                                     parent=self.root)
                return
            old = self._avatars.get(self.jid)

            def _done(ok):
                if not ok:
                    self._safe_after(0, self._restore_avatar, self.jid, old)
            self.bot.publish_avatar(data, "image/png", _done)
            self._avatars[self.jid] = data
            _save_avatar_cache(self.jid, data)
            self._update_sidebar_avatar()
        self._show_toast("📖 Hikaye", "Durum yayınlandı")

    # ── Kişi kartı hover önizleme ────────────────────────────────────────────
    def _show_contact_card(self, event, jid):
        """Kişi üzerinde hover'da mini profil kartı göster (ui/sidebar)."""
        if hasattr(self, '_contact_card_pop') and self._contact_card_pop:
            try:
                self._contact_card_pop.destroy()
            except Exception:
                pass

        name = self._contacts.get(jid, jid) or jid
        pshow = self.presence.get(jid, "unavailable")
        common = [r for r in self.rooms
                  if jid.split("@")[0] in str(self.room_members.get(r, {}))]
        pop = _ui_sidebar.show_contact_card(
            self.root, jid, name, pshow, self._avatars.get(jid),
            self._photo_refs, len(common), event.x_root, event.y_root)
        self._contact_card_pop = pop

        def _hide(e=None):
            try:
                pop.destroy()
            except Exception:
                pass
            self._contact_card_pop = None

        pop.bind("<Leave>", _hide)
        self.root.after(3000, _hide)

    # ── Ortak gruplar göstergesi ─────────────────────────────────────────────
    def _common_groups_dialog(self, jid):
        """Kişiyle ortak gruplar penceresi (ui/dialogs)."""
        name = self._contacts.get(jid, jid) or jid
        _ui_rooms.show_common_groups(
            self.root, name, jid, self.rooms, self.room_members)

    # ── Log görüntüleyici (XML debug) ────────────────────────────────────────
    def _log_viewer_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("📋 XMPP Log Görüntüleyici")
        dlg.configure(bg=BG_CARD)
        dlg.geometry("600x500")
        dlg.transient(self.root)

        tk.Label(dlg, text="📋 XMPP XML Trafik Logu", font=(FONT, 12, "bold"),
                 fg=FG, bg=BG_CARD).pack(padx=16, pady=(16, 8))

        # Log text widget
        log_text = tk.Text(dlg, bg=BG_PANEL, fg=FG, font=("Courier", 8),
                           wrap="word", insertbackground=FG,
                           highlightthickness=0)
        log_text.pack(fill="both", expand=True, padx=16, pady=4)
        scrollbar = ttk.Scrollbar(log_text, command=log_text.yview)
        scrollbar.pack(side="right", fill="y")
        log_text.config(yscrollcommand=scrollbar.set)

        # Tag'ler
        log_text.tag_config("sent", foreground=ACCENT)
        log_text.tag_config("recv", foreground=ONLINE)
        log_text.tag_config("error", foreground=RED)
        log_text.tag_config("info", foreground=FG_DIM)

        self._log_text_ref = log_text
        self._log_active = True

        # Mevcut logları göster
        log_text.insert("end", "── XMPP Debug Log ──\n", "info")
        log_text.insert("end", f"Hesap: {self.jid}\n", "info")
        log_text.insert("end", f"Bağlı: {self.bot.is_connected() if self.bot else False}\n\n", "info")

        # Slixmpp filter ile canlı izleme (filter'lar XMPP thread'inde çalışır)
        def _log_sent(stanza):
            if self._log_active:
                xml_str = str(stanza)[:500]

                def _ui():
                    if dlg.winfo_exists():
                        log_text.insert("end", f"→ SENT:\n{xml_str}\n\n", "sent")
                        log_text.see("end")
                self._safe_after(0, _ui)
            return stanza

        def _log_recv(stanza):
            if self._log_active:
                xml_str = str(stanza)[:500]

                def _ui():
                    if dlg.winfo_exists():
                        log_text.insert("end", f"← RECV:\n{xml_str}\n\n", "recv")
                        log_text.see("end")
                self._safe_after(0, _ui)
            return stanza

        try:
            self.bot.add_filter('out', _log_sent)
            self.bot.add_filter('in', _log_recv)
            self._log_filters = (_log_sent, _log_recv)
        except Exception:
            log_text.insert("end", "⚠ Filter eklenemedi\n", "error")

        btn_f = tk.Frame(dlg, bg=BG_CARD)
        btn_f.pack(fill="x", padx=16, pady=8)

        def _clear():
            log_text.delete("1.0", "end")

        def _export():
            from tkinter import filedialog
            path = filedialog.asksaveasfilename(parent=dlg,
                defaultextension=".txt", filetypes=[("Text", "*.txt")])
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(log_text.get("1.0", "end"))

        filters_done = [False]

        def _cleanup_filters():
            if filters_done[0]:
                return
            filters_done[0] = True
            self._log_active = False
            try:
                filters = getattr(self, '_log_filters', None)
                if filters:
                    self.bot.del_filter('out', filters[0])
                    self.bot.del_filter('in', filters[1])
                    self._log_filters = None
            except Exception:
                _log.warning("Log filtreleri kaldırılamadı", exc_info=True)

        def _close():
            _cleanup_filters()
            dlg.destroy()

        ttk.Button(btn_f, text="🗑 Temizle", command=_clear).pack(side="left", padx=4)
        ttk.Button(btn_f, text="📤 Dışa Aktar", command=_export).pack(side="left", padx=4)
        ttk.Button(btn_f, text="Kapat", command=_close).pack(side="right", padx=4)

        dlg.protocol("WM_DELETE_WINDOW", _close)
        # Pencere ebeveynle birlikte yok edilirse filtreler sızmasın
        dlg.bind("<Destroy>", lambda e: _cleanup_filters()
                 if e.widget is dlg else None, add="+")

    # ── REST API endpoint ────────────────────────────────────────────────────
    def _api_lock_get(self):
        lock = getattr(self, "_api_lock", None)
        if lock is None:
            lock = self._api_lock = threading.Lock()
        return lock

    def _generate_api_token(self):
        """Her başlatmada yeni token üret ve config'e kaydet."""
        import secrets as _secrets
        token = _secrets.token_urlsafe(32)
        cfg = _load_config()
        cfg["api_token"] = token
        _save_config(cfg)
        self._api_token = token
        _log.info("REST API token üretildi")
        return token

    def _remember_api_port(self, port):
        cfg = _load_config()
        if cfg.get("api_port") != port:
            cfg["api_port"] = port
            _save_config(cfg)

    def _start_rest_api(self, port=8099):
        """Basit HTTP API — mesaj gönderme/alma için (Bearer token gerekli)."""
        lock = self._api_lock_get()
        with lock:
            if (getattr(self, "_closing", False)
                    or getattr(self, "_api_starting", False)
                    or getattr(self, "_api_stopping", False)
                    or getattr(self, "_api_server", None) is not None):
                return
            generation = getattr(self, "_api_generation", 0) + 1
            self._api_generation = generation
            self._api_starting = True
            self._api_error = None
        main_win = self
        try:
            token = self._generate_api_token()
        except Exception:
            with lock:
                self._api_starting = False
            raise

        class APIHandler(http.server.BaseHTTPRequestHandler):
            def setup(self):
                super().setup()
                self.connection.settimeout(_API_REQUEST_TIMEOUT)

            def log_message(self, *args):
                _log.debug("REST API: %s", args[0] % args[1:] if len(args) > 1 else args)

            def _check_auth(self) -> bool:
                auth = self.headers.get("Authorization", "")
                if auth == f"Bearer {main_win._api_token}":
                    return True
                _log.warning("REST API yetkisiz erişim denemesi: %s", self.client_address)
                self._send_json({"error": "unauthorized"}, 401)
                return False

            def _send_json(self, data, code=200):
                payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.close_connection = True
                try:
                    self.send_response(code)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(payload)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # İstemci cevap tamamlanmadan bağlantıyı kapattı.

            def _read_body(self):
                if self.headers.get("Transfer-Encoding"):
                    self._send_json({"error": "unsupported transfer encoding"}, 400)
                    return None
                try:
                    length = int(self.headers.get("Content-Length", 0))
                except (TypeError, ValueError):
                    self._send_json({"error": "invalid content length"}, 400)
                    return None
                if length < 0:
                    self._send_json({"error": "invalid content length"}, 400)
                    return None
                if length > _API_BODY_MAX:
                    self._send_json({"error": "request body too large"}, 413)
                    return None
                deadline = time.monotonic() + _API_REQUEST_TIMEOUT
                body = bytearray()
                try:
                    while len(body) < length:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise TimeoutError
                        self.connection.settimeout(remaining)
                        chunk = self.rfile.read1(min(65536, length - len(body)))
                        if not chunk:
                            break
                        body.extend(chunk)
                except TimeoutError:
                    self._send_json({"error": "request body timed out"}, 408)
                    return None
                if len(body) != length:
                    self._send_json({"error": "incomplete request body"}, 400)
                    return None
                return bytes(body)

            def _forward(self, to, message):
                bot = main_win.bot
                if bot is None or getattr(main_win, "_closing", False):
                    self._send_json({"error": "XMPP unavailable"}, 503)
                    return False
                future = None
                try:
                    if to in main_win.rooms:
                        future = bot.send_gc(to, message)
                    else:
                        future = bot.send_chat(to, message)
                    if future is not None and future.result(timeout=_API_SEND_TIMEOUT) is False:
                        self._send_json({"error": "XMPP send failed"}, 503)
                        return False
                except _FutureTimeoutError:
                    if future is not None:
                        future.cancel()
                    self._send_json({"error": "XMPP send timed out"}, 503)
                    return False
                except Exception:
                    _log.warning("REST API mesajı gönderilemedi", exc_info=True)
                    self._send_json({"error": "XMPP unavailable"}, 503)
                    return False
                return True

            def do_GET(self):
                if not self._check_auth():
                    return
                if self.path == "/api/status":
                    self._send_json({
                        "jid": main_win.jid,
                        "connected": main_win.bot.is_connected() if main_win.bot else False,
                        "contacts": len(main_win._contacts),
                        "rooms": len(main_win.rooms),
                        "ping_ms": main_win._last_ping_ms,
                    })
                elif self.path.startswith("/api/messages/"):
                    jid = urllib.parse.unquote(self.path[14:])
                    msgs = _db_load_msgs(jid, 50)
                    self._send_json([{"sender": m[0], "body": m[1],
                                      "is_me": m[2], "time": m[3],
                                      "local_path": m[7]} for m in msgs])
                elif self.path == "/api/contacts":
                    self._send_json([
                        {"jid": j, "name": main_win._contacts.get(j, j),
                         "presence": main_win.presence.get(j, "unavailable")}
                        for j in sorted(main_win._contacts.keys())
                    ])
                elif self.path == "/api/rooms":
                    self._send_json(main_win.rooms)
                else:
                    self._send_json({"error": "not found"}, 404)

            def do_POST(self):
                if not self._check_auth():
                    return
                body = self._read_body()
                if body is None:
                    return
                try:
                    data = json.loads(body) if body else {}
                except Exception:
                    self._send_json({"error": "invalid json"}, 400)
                    return
                if not isinstance(data, dict):
                    self._send_json({"error": "JSON object required"}, 400)
                    return

                if self.path == "/api/send":
                    to = data.get("to", "")
                    msg = data.get("message", "")
                    if (not isinstance(to, str) or not to.strip()
                            or not isinstance(msg, str) or not msg.strip()):
                        self._send_json({"error": "to and message required"}, 400)
                        return
                    to = to.strip()
                    if not self._forward(to, msg):
                        return
                    main_win.gui_q.put(("api_store", {
                        "target": to, "body": msg, "tag": "me",
                        "sender": "API", "is_me": True}))
                    _log.info("REST API ile mesaj gönderildi: %s", to)
                    self._send_json({"status": "sent"})
                elif self.path == "/api/draft":
                    # Yalnız taslak: "Yanıt taslakları" kutusuna düşer,
                    # gönderim her zaman kullanıcıya kalır (MCP draft_reply).
                    to = data.get("to", "")
                    text = data.get("text", "")
                    if (not isinstance(to, str) or "@" not in to
                            or not isinstance(text, str) or not text.strip()
                            or len(text) > 4000):
                        self._send_json({"error": "to and text required"}, 400)
                        return
                    source = data.get("source")
                    main_win.gui_q.put(("api_draft", {
                        "to": to.strip(), "text": text.strip(),
                        "source": source if isinstance(source, str) else ""}))
                    self._send_json({"status": "drafted"})
                else:
                    self._send_json({"error": "not found"}, 404)

        def _run_api():
            try:
                server = http.server.HTTPServer(("127.0.0.1", port), APIHandler)
            except Exception as e:
                with lock:
                    self._api_starting = False
                    if generation != self._api_generation:
                        self._api_stopping = False
                        return
                    self._api_error = str(e)
                _log.error("REST API başlatılamadı (port=%d)", port, exc_info=True)
                try:
                    self._safe_after(0, lambda err=str(e): messagebox.showerror(
                        "REST API", f"Sunucu başlatılamadı (port {port}):\n{err}",
                        parent=self.root))
                except Exception:
                    pass
                return
            with lock:
                if getattr(self, "_closing", False) or generation != self._api_generation:
                    server.server_close()
                    self._api_starting = False
                    self._api_stopping = False
                    return
                self._api_error = None
                self._api_starting = False
                self._api_server = server
                self._api_port = server.server_address[1]
            _log.info("REST API başlatıldı: 127.0.0.1:%d", self._api_port)
            # MCP sunucusu (xmpp_mcp.py) taslak için portu config'ten okur
            self._safe_after(0, self._remember_api_port, self._api_port)
            try:
                self._safe_after(0, self._show_toast,
                                 "🌐 REST API",
                                 f"http://127.0.0.1:{self._api_port}/api/\nToken: {token[:8]}…")
            except Exception:
                pass
            try:
                server.serve_forever()
            finally:
                with lock:
                    server.server_close()
                    if getattr(self, "_api_server", None) is server:
                        self._api_server = None

        self._api_port = port
        threading.Thread(target=_run_api, daemon=True).start()

    def _rest_api_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("🌐 REST API")
        dlg.configure(bg=BG_CARD)
        dlg.geometry("420x340")
        dlg.transient(self.root)

        tk.Label(dlg, text="🌐 REST API", font=(FONT, 12, "bold"),
                 fg=FG, bg=BG_CARD).pack(padx=16, pady=(16, 8))

        port_var = tk.IntVar(value=getattr(self, '_api_port', 8099))
        pf = tk.Frame(dlg, bg=BG_CARD)
        pf.pack(fill="x", padx=16)
        tk.Label(pf, text="Port:", font=(FONT, 9), fg=FG, bg=BG_CARD).pack(side="left")
        ttk.Entry(pf, textvariable=port_var, width=8, font=(FONT, 10)).pack(
            side="left", padx=(8, 0))

        api_err = getattr(self, '_api_error', None)
        running = getattr(self, '_api_server', None) is not None and not api_err
        if api_err:
            _status_text, _status_fg = f"🔴 Hata: {api_err}", RED
        elif running:
            _status_text, _status_fg = "🟢 Çalışıyor", ONLINE
        else:
            _status_text, _status_fg = "⚫ Durduruldu", FG_DIM
        status = tk.Label(dlg, text=_status_text, font=(FONT, 9, "bold"),
                          fg=_status_fg, bg=BG_CARD, wraplength=380)
        status.pack(pady=8)

        # Token göster
        token_var = tk.StringVar(value=getattr(self, '_api_token', '—'))
        tf = tk.Frame(dlg, bg=BG_CARD)
        tf.pack(fill="x", padx=16, pady=(0, 8))
        tk.Label(tf, text="Token:", font=(FONT, 9), fg=FG, bg=BG_CARD).pack(side="left")
        token_entry = ttk.Entry(tf, textvariable=token_var, width=30, font=(FONT_MONO, 8),
                                state="readonly")
        token_entry.pack(side="left", padx=(8, 4))
        def _copy_token():
            dlg.clipboard_clear()
            dlg.clipboard_append(token_var.get())
        ttk.Button(tf, text="📋", width=3, command=_copy_token).pack(side="left")

        def _start():
            self._start_rest_api(port_var.get())
            status.config(text="⏳ Başlatılıyor…", fg=AWAY)
            token_var.set(getattr(self, '_api_token', '—'))

            def _check_status():
                if not dlg.winfo_exists():
                    return
                err = getattr(self, '_api_error', None)
                if err:
                    status.config(text=f"🔴 Hata: {err}", fg=RED)
                elif getattr(self, '_api_server', None) is not None:
                    status.config(text="🟢 Çalışıyor", fg=ONLINE)
                elif getattr(self, '_api_starting', False):
                    _after_alive(dlg, 500, _check_status)
                else:
                    status.config(text="⚫ Durduruldu", fg=FG_DIM)

            _after_alive(dlg, 500, _check_status)

        def _stop():
            status.config(text="⏳ Durduruluyor…", fg=AWAY)

            def _done():
                if dlg.winfo_exists():
                    if getattr(self, "_api_stopping", False):
                        self._safe_after(100, _done)
                    else:
                        status.config(text="⚫ Durduruldu", fg=FG_DIM)

            def _worker():
                self._stop_api_server()
                self._safe_after(0, _done)

            threading.Thread(target=_worker, daemon=True).start()

        btn_f = tk.Frame(dlg, bg=BG_CARD)
        btn_f.pack(pady=8)
        ttk.Button(btn_f, text="▶ Başlat", command=_start).pack(side="left", padx=4)
        ttk.Button(btn_f, text="⏹ Durdur", command=_stop).pack(side="left", padx=4)

        # API endpoints
        tk.Label(dlg, text="API Endpoints:", font=(FONT, 9, "bold"),
                 fg=FG, bg=BG_CARD).pack(anchor="w", padx=16, pady=(12, 4))
        endpoints = [
            ("GET", "/api/status", "Bağlantı durumu"),
            ("GET", "/api/contacts", "Kişi listesi"),
            ("GET", "/api/rooms", "Oda listesi"),
            ("GET", "/api/messages/{jid}", "Mesaj geçmişi"),
            ("POST", "/api/send", "Mesaj gönder {to, message}"),
        ]
        for method, path, desc in endpoints:
            row = tk.Frame(dlg, bg=BG_CARD, padx=16)
            row.pack(fill="x", pady=1)
            mc = ONLINE if method == "GET" else ACCENT
            tk.Label(row, text=method, font=("Courier", 7, "bold"),
                     fg=mc, bg=BG_CARD, width=5).pack(side="left")
            tk.Label(row, text=path, font=("Courier", 7),
                     fg=FG, bg=BG_CARD).pack(side="left", padx=(4, 0))
            tk.Label(row, text=f"— {desc}", font=(FONT, 7),
                     fg=FG_DIM, bg=BG_CARD).pack(side="left", padx=(4, 0))

    def _conn_timeout(self):
        self._conn_timeout_id = None
        if self.bot._connected_ok:
            return  # Zaten bağlandı
        detail = getattr(self, "_last_conn_error", "") or "bilinmeyen hata"
        domain = str(getattr(self.bot, "default_domain", "") or "")
        port = getattr(self.bot, "default_port", 5222)
        addr = ""
        ca = getattr(self.bot, "custom_address", None)
        if ca:
            addr = f" ({ca[0]}:{ca[1]})"
        keep = messagebox.askyesno(
            "Bağlantı Kurulamadı",
            "20 saniye içinde sunucuya bağlanılamadı.\n\n"
            f"Sunucu: {domain}:{port}{addr}\n"
            f"Son hata: {detail}\n\n"
            "Arka planda yeniden bağlanma denemeleri sürüyor.\n"
            "Denemeye devam edilsin mi?\n"
            "(\"Hayır\" → giriş ekranına dönülür)",
            parent=self.root)
        if keep:
            return
        try:
            self.bot.cancel_connection_attempt()
        except Exception:
            pass
        self._relogin = True
        self._quit()

    def _on_close_request(self):
        """Kapatma tuşuna basınca seçenek diyalogu göster."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Kapat")
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.transient(self.root)
        _safe_grab_set(dlg)
        dlg.overrideredirect(True)

        # Ekran ortasına konumla
        dlg.update_idletasks()
        w, h = 340, 240
        x = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - h) // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")

        # Dış kenarlık efekti
        outer = tk.Frame(dlg, bg=BORDER, padx=1, pady=1)
        outer.pack(fill="both", expand=True)
        inner = tk.Frame(outer, bg=BG_CARD)
        inner.pack(fill="both", expand=True)

        # Üst dekoratif çizgi
        deco = tk.Canvas(inner, height=3, bg=BG_CARD, highlightthickness=0)
        deco.pack(fill="x")
        deco.bind("<Configure>",
            lambda e: (deco.delete("all"),
                       deco.create_rectangle(
                           e.width * 0.2, 0, e.width * 0.8, 3,
                           fill=ACCENT2, outline="")))

        tk.Label(inner, text="Ne yapmak istiyorsun?",
                 font=(FONT, 12, "bold"), fg=FG, bg=BG_CARD).pack(pady=(24, 20))

        btn_f = tk.Frame(inner, bg=BG_CARD)
        btn_f.pack(fill="x", padx=32)

        def _hide():
            dlg.destroy()
            self._minimize_to_tray()

        def _quit():
            dlg.destroy()
            self._quit()

        ttk.Button(btn_f, text="  Gizle (Tepsiye)  ",
                   command=_hide, style="Ghost.TButton").pack(fill="x", pady=4)
        ttk.Button(btn_f, text="  Uygulamadan Cik  ",
                   command=_quit, style="Danger.TButton").pack(fill="x", pady=4)
        ttk.Button(btn_f, text="  Iptal  ",
                   command=dlg.destroy, style="Small.TButton").pack(fill="x", pady=4)

        dlg.bind("<Escape>", lambda _: dlg.destroy())

    def _switch_account(self, acc):
        """Kayıtlı hesaba geç: oturumu kapatıp yeni hesapla yeniden bağlan."""
        try:
            jid = acc.get("jid", "")
            pw = _account_password(acc)
            if not jid:
                return
            cfg = _load_config()
            cfg["jid"] = jid
            cfg["pw"] = _encode_pw(pw) if pw else ""
            cfg["remember"] = True
            # Önceki hesabın özel sunucusu yeni hesaba taşınmasın (SRV)
            cfg.pop("server", None)
            cfg.pop("port", None)
            _save_config(cfg)
            self._show_toast("🔁 Hesap Değişimi",
                             f"{jid} hesabına geçiliyor…")
            self._after(800, self._switch_and_relogin)
        except Exception as e:
            messagebox.showerror("Hesap", f"Hesap değiştirilemedi: {e}",
                                 parent=self.root)

    def _apply_login_prefs(self, cfg: dict, remember: bool, auto_login: bool):
        """Ayarlar → giriş: "Şifremi hatırla" açılınca bu oturumun bilgileri
        saklanır, kapatılınca kayıtlı şifre silinir; değişmediyse kayıtlı
        sunucu/port ezilmez, yalnız otomatik giriş seçimi güncellenir."""
        if remember == bool(cfg.get("remember")):
            if remember:
                cfg["auto_login"] = bool(auto_login)
            return
        host, port = getattr(self.bot, "custom_address", None) or ("", 5222)
        _store_login(cfg, remember, self.jid,
                     getattr(self.bot, "password", ""), port, host,
                     auto_login=auto_login)

    def _switch_and_relogin(self):
        self._relogin = True
        self._relogin_auto = True  # yeni hesap giriş ekranı açılmadan bağlanır
        self._quit()

    def _stop_api_server(self):
        """REST API sunucusunu kapat (kapanışta ayrı thread'de çağrılır)."""
        lock = self._api_lock_get()
        with lock:
            self._api_generation = getattr(self, "_api_generation", 0) + 1
            self._api_error = None
            server = getattr(self, "_api_server", None)
            self._api_server = None
            if server is not None or getattr(self, "_api_starting", False):
                self._api_stopping = True
        if server is None:
            return
        try:
            server.shutdown()
        except Exception:
            _log.warning("REST API durdurulamadı", exc_info=True)
        finally:
            with lock:
                try:
                    server.server_close()
                finally:
                    self._api_stopping = False

    def _quit(self):
        if getattr(self, "_closing", False):
            return
        self._closing = True
        # [2O] Kapanış: ters-alias registry oturum-yerelidir
        self._mam_alias_clear_all()
        self._ai_speak_stop()           # sesli okuma süreci uygulamayla biter
        # Tcl bgerror filtresini devreye al (kapanış gürültüsünü sustur)
        try:
            self.root.tk.setvar("xmpp_closing", 1)
        except Exception:
            pass
        # İzlenen tüm `after` zincirlerini iptal et
        ids = getattr(self, "_after_ids", None)
        if ids:
            for aid in list(ids):
                try:
                    self.root.after_cancel(aid)
                except Exception:
                    pass
            ids.clear()
        # Bilinen zincir kimliklerini de temizle
        for attr in ("_poll_id", "_idle_check_id", "_ping_loop_id",
                     "_conn_timeout_id", "_auto_theme_id",
                     "_typing_anim_id", "_typing_send_id"):
            aid = getattr(self, attr, None)
            if aid:
                try:
                    self.root.after_cancel(aid)
                except Exception:
                    pass
                setattr(self, attr, None)
        # Tk'daki tüm bekleyen after script'lerini iptal et — destroy
        # sonrası "invalid command name" bgerror'u yapısal olarak imkânsız olur
        try:
            for aid in self.root.tk.splitlist(
                    self.root.tk.call("after", "info")):
                try:
                    self.root.tk.call("after", "cancel", aid)
                except Exception:
                    pass
        except Exception:
            pass
        # Pencere konumunu/boyutunu hatırla
        try:
            cfg = _load_config()
            try:
                cfg["win_maximized"] = (self.root.state() == "zoomed")
            except Exception:
                pass
            if not cfg.get("win_maximized"):
                cfg["win_geometry"] = self.root.winfo_geometry()
            cfg["last_chat"] = self.active or ""
            _save_config(cfg)
        except Exception:
            pass
        # Aktif ses kaydı/oynatmasını durdur (GUI'yi bloklamadan; V-5).
        # Kayıt thread'i _recording=False görünce stream'i kapatır; join yok.
        try:
            if getattr(self, "_recording", False):
                self._stop_recording(send=False)
        except Exception:
            _log.warning("Kayıt kapatılamadı", exc_info=True)
        try:
            self._stop_voice_playback()
        except Exception:
            _log.warning("Ses oynatma kapatılamadı", exc_info=True)
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
        # Yeniden bağlantıyı hemen engelle; stream kapanışı loop thread'inde.
        try:
            bot = self.bot
            if bot is not None:
                bot._closing = True
                stop = getattr(bot, "_reconnect_stop", None)
                if stop is not None:
                    stop.set()
                bot.loop.call_soon_threadsafe(
                    lambda: asyncio.ensure_future(bot._close_connection(), loop=bot.loop))
        except Exception:
            pass
        # REST API sunucusunu nazikçe durdur (GUI bloklanmadan)
        try:
            threading.Thread(target=self._stop_api_server, daemon=True).start()
        except Exception:
            pass
        self._cleanup_temp_registry()
        _log.info("Uygulama kapatılıyor")
        try:
            self.root.destroy()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# Başlatıcı
# ══════════════════════════════════════════════════════════════════════════════

def _shutdown_loop(loop):
    """Bekleyen asyncio görevlerini iptal et ve loop'u kapat."""
    if loop.is_closed():
        return
    try:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True))
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.run_until_complete(loop.shutdown_default_executor())
    except Exception:
        _log.warning("Loop görevleri kapatılamadı", exc_info=True)
    finally:
        try:
            loop.close()
        except Exception:
            pass


def start(jid: str, password: str, port: int = 5222, server: str = ""):
    """Bağlantı kur ve ana pencereyi aç. Auth fail → True döndürür (tekrar login);
    hesap değişimi → "auto" (kayıtlı bilgilerle formsuz yeniden giriş)."""
    gui_q     = queue.Queue()
    bot_ref   = []          # Thread'den bot referansını almak için

    def run_xmpp():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            bot = XMPPBot(jid, password, gui_q)
            bot.loop = loop
            bot_ref.append(bot)
            if server or port != 5222:
                bot.connect(host=server or bot.default_domain, port=port)
            else:
                bot.connect()
            loop.run_forever()
        except Exception as e:
            _log.error("XMPP thread'i beklenmedik şekilde durdu", exc_info=True)
            try:
                gui_q.put(("error", f"XMPP bağlantı thread'i durdu: {e}"))
            except Exception:
                pass
        finally:
            _shutdown_loop(loop)

    gui_q.put(("sys_msg", f"Bağlanıyor… {jid}"))
    t = threading.Thread(target=run_xmpp, daemon=True)
    t.start()

    # Bot oluşturulana kadar kısa bekle
    for _ in range(50):
        if bot_ref:
            break
        time.sleep(0.05)

    if not bot_ref:
        return True  # Bot oluşturulamadı, login'e geri dön

    win = MainWindow(bot_ref[0], jid, gui_q)
    t.join(timeout=3)
    if win._relogin and getattr(win, "_relogin_auto", False):
        return "auto"
    return win._relogin


def _check_pin_lock():
    """Uygulama PIN kilidi varsa doğrula."""
    cfg = _load_config()
    pin = cfg.get("app_pin")
    if not pin:
        return True
    root = tk.Tk()
    root.title("🔑 Uygulama Kilidi")
    root.geometry("300x180")
    root.configure(bg=BG)
    root.resizable(False, False)
    _apply_theme()

    result = [False]
    tk.Label(root, text="🔑 PIN Girin", font=(FONT, 14, "bold"),
             fg=FG, bg=BG).pack(pady=(24, 12))
    pin_var = tk.StringVar()
    entry = ttk.Entry(root, textvariable=pin_var, show="●",
                      font=(FONT, 16), justify="center")
    entry.pack(padx=40, ipady=8)
    entry.focus_set()
    err_lbl = tk.Label(root, text="", font=(FONT, 8), fg=RED, bg=BG)
    err_lbl.pack(pady=(4, 0))

    def _check(_=None):
        entered = pin_var.get()
        if _verify_pin(pin, entered):
            # Eski düz metin kaydını şifreli biçime yükselt
            if not str(pin).startswith("fernet:"):
                cfg["app_pin"] = _encode_pw(entered)
                _save_config(cfg)
            result[0] = True
            root.destroy()
        else:
            err_lbl.config(text="Yanlış PIN")
            pin_var.set("")

    entry.bind("<Return>", _check)
    ttk.Button(root, text="Giriş", command=_check).pack(pady=8)
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
    return result[0]


def main():
    # PIN kilidi kontrolü
    if not _check_pin_lock():
        return

    # Otomatik giriş yalnız açılışta ve hesap değişiminde; auth hatası ya da
    # "giriş ekranına dön" sonrası form (kayıtlı bilgilerle dolu) gösterilir.
    auto = True
    while True:
        result = {}

        def on_login(jid, pw, port, srv=""):
            result["args"] = (jid, pw, port, srv)

        cfg = _load_config()
        saved = (_saved_login(cfg)
                 if auto and _auto_login_enabled(cfg) else None)
        if saved:
            _log.info("Otomatik giriş yapılıyor: %s", saved[0])
            on_login(*saved)
        else:
            LoginWindow(on_login)

        if "args" not in result:
            break  # Pencere kapatıldı, çıkış

        relogin = start(*result["args"])
        if not relogin:
            break  # Normal çıkış
        auto = relogin == "auto"


if __name__ == "__main__":
    main()
