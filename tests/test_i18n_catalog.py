"""İngilizce arayüz: katalog eksiksiz, yer tutucular uyumlu, yeni Türkçe
arayüz metni sarılmadan eklenemez.

Kanıt (2026-10-25): Ayarlar'da "English" seçilebiliyordu ama 137 anahtarlı
dizenin 65'i hiç okunmuyordu ve arayüz metinlerinin neredeyse tamamı koda
Türkçe yazılıydı; İngilizce seçilince ekranın küçük bir kısmı değişiyordu.
Artık metinler gettext tarzı `_tr("Türkçe metin")` ile çevrilir
(`xmppcore/i18n.py`, katalog `xmppcore/locale_en.py`).
"""
import ast
import re
import string
from pathlib import Path

import pytest

import xmpp
from webapp.server import web_msgids
from xmppcore import agent, i18n
from xmppcore import ai as _ai
from xmppcore.locale_en import EN

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ([ROOT / "xmpp.py", ROOT / "jingle_ft.py"]
           + sorted((ROOT / "ui").rglob("*.py"))
           + sorted((ROOT / "xmppcore").rglob("*.py"))
           + sorted((ROOT / "webapp").glob("*.py")))
_TR_CALLS = {"_tr", "tr", "N_"}
_TURKISH = re.compile(r"[çğıöşüÇĞİÖŞÜ]")


def _name(func):
    if isinstance(func, ast.Name):
        return func.id
    return func.attr if isinstance(func, ast.Attribute) else ""


def _msgids():
    """Kaynaktaki çevrilecek metinler: `_tr`/`N_`/`tr_in` sabitleri + KEYS."""
    found = {}
    for path in SOURCES:
        if path.name in ("i18n.py", "locale_en.py"):
            continue
        for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(n, ast.Call):
                continue
            fn = _name(n.func)
            arg = (n.args[0] if fn in _TR_CALLS and n.args else
                   n.args[1] if fn == "tr_in" and len(n.args) > 1 else None)
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                found.setdefault(arg.value, f"{path.name}:{n.lineno}")
    for key, text in i18n.KEYS.items():
        found.setdefault(text, f"KEYS[{key}]")
    for text in web_msgids():                  # index.html + app.js
        found.setdefault(text, "webapp/static")
    return found


MSGIDS = _msgids()


@pytest.fixture()
def english(monkeypatch):
    monkeypatch.setattr(i18n, "_lang", "en")


# ── Katalog ─────────────────────────────────────────────────────────────────
def test_every_ui_text_has_an_english_entry():
    missing = {k: v for k, v in MSGIDS.items() if k not in EN}
    assert not missing, missing


def test_catalog_has_no_stale_entries():
    stale = sorted(set(EN) - set(MSGIDS))
    assert not stale, stale


def _fields(text):
    """Yer tutucular (sıra numarası, dönüşüm, biçim); `{}` sırayla numaralanır,
    böylece çeviri `{1} … {0}` ile sözcük sırasını değiştirebilir."""
    out, auto = [], 0
    for _lit, name, spec, conv in string.Formatter().parse(text):
        if name is None:
            continue
        if name == "":
            name, auto = str(auto), auto + 1
        out.append((name, conv, spec))
    return sorted(out)


@pytest.mark.parametrize("msgid", sorted(m for m in MSGIDS if "{" in m))
def test_translation_keeps_placeholders(msgid):
    try:
        expected = _fields(msgid)
    except ValueError:                  # biçimlenmeyen metin ("{to, message}")
        assert EN[msgid].count("{") == msgid.count("{")
        return
    assert _fields(EN[msgid]) == expected, (msgid, EN[msgid])


def test_translations_are_english():
    turkish = {k: v for k, v in EN.items()
               if _TURKISH.search(v) and "Ayşe" not in v}
    assert not turkish, turkish


# ── Çalışma zamanı ──────────────────────────────────────────────────────────
def test_turkish_is_identity_and_english_translates(monkeypatch):
    assert i18n.language() == "tr"
    assert xmpp._tr("Kaydet") == "Kaydet"
    monkeypatch.setattr(i18n, "_lang", "en")
    assert xmpp._tr("Kaydet") == "Save"
    assert xmpp._t("copy") == "Copy"
    assert xmpp._tr("bilinmeyen metin") == "bilinmeyen metin"
    assert xmpp._tr("") == ""
    assert xmpp._tr("{} sonuç").format(3) == "3 results"


def test_unknown_language_falls_back_to_turkish(monkeypatch):
    monkeypatch.setattr(i18n, "_lang", "tr")
    assert i18n.set_language("xx") == "tr"
    assert i18n.set_language("en") == "en"
    assert i18n.tr_in("tr", "Kaydet") == "Kaydet"
    assert i18n.tr_in("en", "Kaydet") == "Save"


def test_ui_chat_views_get_the_translator():
    """ui/chat yalnız tkinter/collections içe aktarır: çevirmen xmpp'den takılır."""
    for path in sorted((ROOT / "ui" / "chat").glob("*.py")):
        if "_tr(" in path.read_text(encoding="utf-8"):
            mod = __import__(f"ui.chat.{path.stem}", fromlist=["_tr"])
            assert mod in xmpp._TR_HOOKED, path.name
            assert mod._tr is i18n.tr, path.name


def test_menus_have_no_turkish_in_english(english):
    for spec in (xmpp._sidebar_menu_spec(has_active_chat=True),
                 xmpp._chat_header_menu_spec(is_room=True, compact=False)):
        for item in spec:
            for part in item:
                if isinstance(part, str):
                    assert not _TURKISH.search(part), part
                elif isinstance(part, (list, tuple)):
                    for sub in part:
                        for s in (sub if isinstance(sub, tuple) else (sub,)):
                            if isinstance(s, str):
                                assert not _TURKISH.search(s), s


def test_status_and_action_labels_follow_language(english):
    assert [lbl for lbl, _s in xmpp._status_options()] == [
        "Online", "Away", "Busy", "Extended away"]
    assert xmpp.STATUS_OPTIONS[0][0] == "Çevrimiçi"     # kaynak sözlük değişmez
    groups = agent.quick_action_groups("Ali", 2, 3, 1)
    assert [title for title, _i in groups] == ["💬 This chat", "🗂 All chats"]
    assert groups[0][1][0] == ("📬 Summarize unread (2)", "summarize_unread")


def test_stored_markers_stay_turkish_but_display_in_english(english):
    """Silindi/ses mesajı işaretleri DB'de ve karşılaştırmada Türkçe kalır."""
    assert _ai.RETRACTED_BODY == "🚫 Bu mesaj silindi"
    assert _ai.display_text(_ai.RETRACTED_BODY) == "🚫 This message was deleted"
    assert _ai.display_text(_ai.NO_SPEECH) == "(No speech detected)"
    assert _ai.display_text("Merhaba") == "Merhaba"     # kullanıcı içeriği


# ── İngilizce asistan komutları (örnekler modelsiz kısa yola düşer) ─────────
def test_english_shortcuts_skip_the_model():
    assert agent.quick_intent("Ask history: What address did Ali give?") == (
        agent.normalize_plan({"action": "ask_history",
                              "text": "What address did Ali give?"}))
    assert agent.quick_intent("Set my status to busy")["status"] == "dnd"
    assert agent.quick_intent("status away")["status"] == "away"
    assert agent.quick_intent("What have I missed?")["action"] == "missed"
    assert agent.quick_intent("Summarize this chat")["action"] == "summarize_chat"
    assert agent.quick_intent("Geçmişe sor: adres?")["action"] == "ask_history"


def test_english_examples_are_translated(english):
    w = object.__new__(xmpp.MainWindow)
    examples = [xmpp._tr(e) for e in w._AGENT_EXAMPLES]
    assert "Set my status to busy" in examples
    assert all(not _TURKISH.search(e.replace("Ayşe", "")) for e in examples)


# ── AI yanıt dili ───────────────────────────────────────────────────────────
def test_ai_reply_language_follows_english_ui_until_chosen(english):
    assert _ai.load_settings({})["target_language"] == "English"
    chosen = {"ai": {"target_language": "Deutsch"}}
    assert _ai.load_settings(chosen)["target_language"] == "Deutsch"


def test_ai_reply_language_default_stays_turkish():
    assert _ai.load_settings({})["target_language"] == "Türkçe"


# ── Dil değişimi: yeniden başlatınca (yarı çevrilmiş arayüz olmasın) ───────
def test_language_change_applies_after_restart(monkeypatch):
    toasts = []
    w = object.__new__(xmpp.MainWindow)
    w._show_toast = lambda title, body: toasts.append((title, body))
    monkeypatch.setattr(i18n, "_lang", "tr")
    src = ast.get_source_segment(
        (ROOT / "xmpp.py").read_text(encoding="utf-8"),
        next(n for n in ast.walk(ast.parse((ROOT / "xmpp.py").read_text(
            encoding="utf-8")))
            if isinstance(n, ast.FunctionDef) and n.name == "_settings_apply"))
    assert "set_language" not in src            # canlı geçiş yok
    assert "tr_in(v[\"language\"]" in src
    assert i18n.tr_in("en", "Yeni dil uygulama yeniden başlatılınca geçerli "
                            "olur.").startswith("The new language")


# ── Koruma: arayüze sarılmamış Türkçe metin eklenemez ──────────────────────
_SINK_KW = {"text", "label", "title", "message", "placeholder", "ask_hint",
            "subtitle", "hint"}
_SINK_POS = {"showinfo", "showerror", "showwarning", "askyesno",
             "askyesnocancel", "askokcancel", "askstring", "askinteger",
             "_show_toast", "_ai_notice", "set_status", "set_busy",
             "set_error", "_append", "title"}
# Bilinçli Türkçe kalanlar: dil seçilmeden (içe aktarmada) gösterilenler
_ALLOWED = {("xmpp.py", "XMPP İstemcisi")}


def _plain_turkish(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value if _TURKISH.search(node.value) else None
    if isinstance(node, ast.JoinedStr):
        text = "".join(v.value for v in node.values
                       if isinstance(v, ast.Constant))
        return text if _TURKISH.search(text) else None
    return None


def test_no_unwrapped_turkish_ui_text():
    bad = []
    for path in SOURCES:
        if path.name in ("i18n.py", "locale_en.py", "mcp_server.py"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if not isinstance(n, ast.Call) or _name(n.func) in _TR_CALLS:
                continue
            fn = _name(n.func)
            cands = [k.value for k in n.keywords if k.arg in _SINK_KW]
            if fn in _SINK_POS:
                cands += n.args[:2]
            for c in cands:
                text = _plain_turkish(c)
                if text and (path.name, text) not in _ALLOWED:
                    bad.append(f"{path.relative_to(ROOT)}:{n.lineno} {text!r}")
    assert not bad, bad


def test_theme_names_display_in_language_but_keys_are_saved(english):
    from xmppcore.theme import theme_label
    assert theme_label("gece-mavisi") == "Night blue"
    assert theme_label("dracula") == "Dracula"          # özel ad çevrilmez
    src = (ROOT / "xmpp.py").read_text(encoding="utf-8")
    assert 'cfg["day_theme"] = to_key.get(day_var.get()' in src


# ── Diğer diller (İngilizce dışı katalogların hepsi) ───────────────────────
OTHER_LANGS = [code for code in i18n.LANGUAGES if code not in ("tr", "en")]
# Dilden bağımsız metinler (İngilizcesi Türkçesiyle aynı: kısayollar, OMEMO,
# JID…) diğer kataloglarda olmayabilir; İngilizce yedekten gelir
NEUTRAL = {k for k, v in EN.items() if k == v}


def _edges(text):
    return (text[:len(text) - len(text.lstrip())],
            text[len(text.rstrip()):])


@pytest.mark.parametrize("lang", OTHER_LANGS)
def test_other_language_catalog_is_complete(lang):
    cat = i18n.catalog(lang)
    missing = sorted(set(MSGIDS) - NEUTRAL - set(cat))
    assert not missing, (lang, missing[:20])
    stale = sorted(set(cat) - set(MSGIDS))
    assert not stale, (lang, stale[:20])


@pytest.mark.parametrize("lang", OTHER_LANGS)
def test_other_language_keeps_placeholders_and_spacing(lang):
    cat = i18n.catalog(lang)
    bad = []
    for msgid, text in cat.items():
        if "{" in msgid:
            try:
                if _fields(text) != _fields(msgid):
                    bad.append((msgid, text))
            except ValueError:
                if text.count("{") != msgid.count("{"):
                    bad.append((msgid, text))
        if _edges(text) != _edges(msgid):
            bad.append(("boşluk", msgid, text))
    assert not bad, (lang, bad[:10])


@pytest.mark.parametrize("lang", OTHER_LANGS)
def test_other_language_is_actually_translated(lang):
    """Katalog İngilizce ya da Türkçe kopyası olmamalı (dilden bağımsızlar hariç)."""
    cat = i18n.catalog(lang)
    same_en = [k for k, v in cat.items() if v == EN.get(k) and len(v) > 12]
    same_tr = [k for k, v in cat.items() if v == k and len(v) > 12]
    assert len(same_en) < len(cat) * 0.05, (lang, same_en[:10])
    assert len(same_tr) < len(cat) * 0.02, (lang, same_tr[:10])


def test_missing_text_falls_back_to_english(monkeypatch):
    monkeypatch.setattr(i18n, "_lang", "de")
    monkeypatch.setitem(i18n._catalogs, "de", {})
    assert xmpp._tr("Kaydet") == "Save"
    assert xmpp._tr("Ctrl+F") == "Ctrl+F"


def test_language_picker_lists_every_language_by_native_name():
    assert len(i18n.LANGUAGES) == 14
    assert set(i18n.AI_LANGUAGE_NAMES) == set(i18n.LANGUAGES)
    assert i18n.LANGUAGES["de"] == "Deutsch" and i18n.LANGUAGES["ja"] == "日本語"


@pytest.mark.parametrize("lang, name", [("de", "German"), ("ja", "Japanese"),
                                        ("zh", "Simplified Chinese")])
def test_ai_reply_language_follows_every_ui_language(monkeypatch, lang, name):
    monkeypatch.setattr(i18n, "_lang", lang)
    assert _ai.load_settings({})["target_language"] == name


def test_other_languages_translate_at_runtime(monkeypatch):
    monkeypatch.setattr(i18n, "_lang", "de")
    assert xmpp._tr("Kaydet") == "Speichern"
    assert xmpp._tr("{} sonuç").format(3) == "3 Ergebnisse"
    monkeypatch.setattr(i18n, "_lang", "ja")
    assert xmpp._t("copy") == "コピー"
