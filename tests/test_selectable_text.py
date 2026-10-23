"""Mesaj ve asistan yazıları sol tıkla seçilebilmeli (2026-10-21).

Kanıt: sohbet balonları tk.Label'dı — Label metni seçilemez; bir mesajın bir
kısmını (adres, kod, numara) kopyalamanın yolu yoktu, sağ tık "Kopyala" hep
tüm mesajı alıyordu. `ui.selectable`: Label gibi görünen kapalı tk.Text;
yalnız fareyle seçim bağlamaları (tekerlek sohbeti kaydırmaya devam eder,
metin kendi içinde kaymaz, odak giriş kutusunda kalır), içeriğe göre piksel
boyut, Ctrl+C ve sağ tıkla seçimi kopyalama.
"""
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui import selectable  # noqa: E402

FONT = ("DejaVu Sans", 11)
STYLES = {"bold": {"font": ("DejaVu Sans", 11, "bold")},
          "code": {"font": ("Courier", 10), "background": "#333333"}}


@pytest.fixture()
def host():
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        pytest.skip("Tk testleri bir ekran veya Xvfb gerektiriyor")
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    top = tk.Toplevel(root)                     # gizli kökün çocuğu görünmez
    top.geometry("700x400+150+150")
    yield top
    root.destroy()


def _settle(w, secs=0.3):
    import time
    end = time.monotonic() + secs
    while time.monotonic() < end:
        w.update()
        time.sleep(0.01)


def _box(parent, content, wrap=420):
    box = selectable.selectable_text(
        parent, content, fg="#eeeeee", bg="#222222", font=FONT, wrap=wrap,
        sel_bg="#4444aa", sel_fg="#ffffff", styles=STYLES)
    box.pack(anchor="w")
    return box


def _drag(text, start, end):
    x0, y0, _w, h0 = text.bbox(start)
    x1, y1, _w, h1 = text.bbox(end)
    text.event_generate("<ButtonPress-1>", x=x0 + 1, y=y0 + h0 // 2)
    text.event_generate("<B1-Motion>", x=x1, y=y1 + h1 // 2)
    text.event_generate("<ButtonRelease-1>", x=x1, y=y1 + h1 // 2)
    text.update()


def _all_visible(box):
    top, bottom = box.text.yview()
    return top == 0.0 and bottom == 1.0


def test_drag_selects_part_of_message(host):
    box = _box(host, "Adres: Atatürk Cad. 12, İzmir")
    _settle(host)
    _drag(box.text, "1.7", "1.22")
    assert selectable.selected_text(box) == "Atatürk Cad. 12"


def test_double_click_selects_a_word(host):
    box = _box(host, "kod 4815 geldi")
    _settle(host)
    x, y, _w, h = box.text.bbox("1.5")
    for t, kind in ((1000, "ButtonPress"), (1040, "ButtonRelease"),
                    (1080, "ButtonPress")):       # 2. basış: Double-1
        box.text.event_generate(f"<{kind}-1>", x=x, y=y + h // 2, time=t)
    box.text.update()
    assert selectable.selected_text(box) == "4815"


def test_click_does_not_take_focus_from_input(host):
    """Giriş kutusuna yazmaya devam edilebilmeli (kapalı Text odak almaz)."""
    import tkinter as tk
    entry = tk.Entry(host)
    entry.pack()
    box = _box(host, "seçilecek yazı")
    _settle(host)
    entry.focus_set()
    _drag(box.text, "1.0", "1.7")
    assert host.focus_get() is not box.text
    assert box.text.cget("state") == "disabled"


def test_only_mouse_selection_bindings(host):
    """Tekerlek/tuş bağlamaları yok: tekerlek sohbeti kaydırır, metin
    kendi içinde kaymaz; yazılamaz."""
    box = _box(host, "\n".join(f"satır {i}" for i in range(6)))
    _settle(host)
    tags = box.text.bindtags()
    assert "Text" not in tags and selectable.SELECT_TAG in tags
    seqs = set(box.text.bind_class(selectable.SELECT_TAG))
    assert "<Button-1>" in seqs and "<B1-Motion>" in seqs
    assert not any(s in seqs for s in ("<Button-4>", "<Button-5>",
                                       "<MouseWheel>", "<Key>", "<B1-Leave>",
                                       "<Button-2>"))
    box.text.event_generate("<Button-5>")
    box.text.update()
    assert _all_visible(box)


@pytest.mark.parametrize("content", [
    "kısa",
    "uzun " * 120,
    [("kalın ", "bold"), ("ve `kod` ", None), ("print(1)", "code"),
     (" 😊 emoji\nikinci satır", None)],
])
def test_whole_text_visible_and_wraps_like_label(host, content):
    box = _box(host, content)
    _settle(host, 0.4)
    assert _all_visible(box)
    need = int(box.text.tk.call(box.text._w, "count", "-update", "-ypixels",
                                "1.0", "end"))
    assert box.winfo_height() >= need
    assert box.winfo_width() <= 420 + 4         # Label'ın wraplength'i kadar


def test_set_content_replaces_text_and_resizes(host):
    box = _box(host, "ilk")
    _settle(host)
    short_w = box.winfo_width()
    selectable.set_content(box, "düzeltilmiş daha uzun bir mesaj  ✏")
    _settle(host)
    assert box.text.get("1.0", "end-1c") == "düzeltilmiş daha uzun bir mesaj  ✏"
    assert box.winfo_width() > short_w and _all_visible(box)
    selectable.set_content(box, "🗑 silindi", fg="#888888",
                           font=("DejaVu Sans", 9, "italic"))
    assert box.text.cget("fg") == "#888888"
    assert box.text.cget("state") == "disabled"


def test_copy_selection_copies_message_selection_only(host):
    box = _box(host, "kopyalanacak parça burada")
    _settle(host)
    _drag(box.text, "1.0", "1.12")
    copied = []
    fake = types.SimpleNamespace(
        selection_own_get=host.selection_own_get,
        clipboard_clear=lambda: copied.clear(),
        clipboard_append=copied.append)
    assert selectable.copy_selection(fake) is True
    assert copied == ["kopyalanacak"]
    # Giriş kutusunun kendi seçimi varsa ona dokunulmaz (PRIMARY onundur)
    import tkinter as tk
    entry = tk.Entry(host)
    entry.pack()
    entry.insert(0, "kendi metnim")
    entry.selection_range(0, 5)
    _settle(host, 0.1)
    copied.clear()
    assert selectable.copy_selection(fake) is False and copied == []


# ── Sohbete bağlantı ─────────────────────────────────────────────────────────
def test_real_message_body_is_selectable_with_markdown(host):
    import xmpp
    from ui.chat import render as render_mod
    theme = xmpp._chat_theme()
    colors = render_mod.bubble_colors(theme, is_me=False)
    kind, box = render_mod.render_message_body(
        host, theme, "*Kalın* not: `kod 42` ve devamı", colors,
        xmpp.MainWindow._format_markdown, selectable.selectable_text)
    _settle(host)
    assert kind == "text"
    assert box.text.get("1.0", "end-1c") == "Kalın not: kod 42 ve devamı"
    assert "bold" in box.text.tag_names("1.0")
    assert "code" in box.text.tag_names("1.12")
    _drag(box.text, "1.11", "1.17")
    assert selectable.selected_text(box) == "kod 42"
    assert _all_visible(box)


def _menu_window(monkeypatch, selected=""):
    import xmpp
    w = object.__new__(xmpp.MainWindow)
    copied = []
    w.root = types.SimpleNamespace(clipboard_clear=copied.clear,
                                   clipboard_append=copied.append)
    w.active, w.bot, w.rooms = "a@b", None, {}
    w._my_reactions, w._reactions = {}, {}
    w._ai_message_items = lambda row: set()
    w._ai_message_callbacks = lambda row: {}
    shown = {}
    monkeypatch.setattr(xmpp._actions_ui, "show_context_menu",
                        lambda *a, **k: shown.update(k["callbacks"]))
    body = types.SimpleNamespace(selected=selected)
    monkeypatch.setattr(xmpp._selectable, "selected_text",
                        lambda b: getattr(b, "selected", "") if b else "")
    row = types.SimpleNamespace(_body="Adres: Atatürk Cad. 12", _mid="",
                                _is_me=False, _sender="Ali", _retracted=False,
                                _reply_to=None, _body_text=body)
    return w, row, shown, copied


def test_context_menu_copy_takes_selection_else_whole_message(monkeypatch):
    import xmpp
    event = types.SimpleNamespace(x_root=1, y_root=1)
    w, row, shown, copied = _menu_window(monkeypatch, selected="Atatürk")
    xmpp.MainWindow._message_context_menu(w, event, row)
    shown["on_copy"]()
    assert copied == ["Atatürk"]
    w, row, shown, copied = _menu_window(monkeypatch, selected="")
    xmpp.MainWindow._message_context_menu(w, event, row)
    shown["on_copy"]()
    assert copied == ["Adres: Atatürk Cad. 12"]


def test_ctrl_c_in_main_window_copies_message_selection(monkeypatch):
    import xmpp
    w = object.__new__(xmpp.MainWindow)
    binds = {}
    w.root = types.SimpleNamespace(
        bind=lambda seq, fn: binds.__setitem__(seq, fn))
    calls = []
    monkeypatch.setattr(xmpp._selectable, "copy_selection", calls.append)
    xmpp.MainWindow._bind_shortcuts(w)
    binds["<<Copy>>"](None)
    assert calls == [w.root]


def test_jump_flash_works_on_selectable_body(monkeypatch):
    import xmpp
    w = object.__new__(xmpp.MainWindow)
    w.root = types.SimpleNamespace(after=lambda ms, fn, *a: fn(*a))
    seen = []
    box = types.SimpleNamespace(cget=lambda k: "#202020",
                                winfo_exists=lambda: True)
    monkeypatch.setattr(xmpp._selectable, "set_bg",
                        lambda b, c: seen.append(c))
    xmpp.MainWindow._flash_row(w, types.SimpleNamespace(_body_text=box), 2)
    assert seen == [xmpp.SEL_BG, "#202020", xmpp.SEL_BG, "#202020",
                    "#202020"]


def test_wheel_over_message_scrolls_the_chat(host):
    """Sohbetin tekerlek bağlaması (ui.chat.history.bind_scroll_widget)
    mesaj metninden de sohbeti kaydırır; metin kendi içinde kaymaz."""
    import tkinter as tk

    from ui.chat import history
    row = tk.Frame(host)                        # uygulamada: mesaj satırı
    row.pack()
    boxes = [_box(row, f"mesaj {i}") for i in range(3)]
    _settle(host)
    units = []
    history.bind_scroll_widget(row, lambda e: units.append("wheel"),
                               units.append)
    for seq in ("<Button-5>", "<Button-4>"):
        boxes[1].text.event_generate(seq)
    boxes[1].text.update()
    assert units == [3, -3]                     # aşağı, yukarı → sohbet
    assert boxes[1].text.yview() == (0.0, 1.0)


# ── Asistan penceresi ────────────────────────────────────────────────────────
def test_real_assistant_reply_and_result_are_selectable(host):
    import xmpp  # noqa: F401  (_app teması)
    from ui.dialogs import ai as ui_ai
    win = ui_ai.AssistantWindow(host, "alt", lambda t: None)
    win.add_reply("Toplantı yarın 10:00'da, oda B-204.")
    card = ui_ai.InlineResult(win, "📝 Özet")
    card.append_text("Ali adresi gönderdi: Kordon 5")
    _settle(win.top, 0.4)
    reply = [w for w in _walk(win.top)
             if selectable.SELECT_TAG in w.bindtags()
             and w.get("1.0", "end-1c").startswith("Toplantı")][0]
    _drag(reply, "1.29", "1.34")
    assert reply.get("sel.first", "sel.last") == "B-204"
    assert card._body.text.get("1.0", "end-1c") == "Ali adresi gönderdi: Kordon 5"
    assert selectable.SELECT_TAG in card._body.text.bindtags()
    assert win.top.bind("<<Copy>>")             # Ctrl+C seçimi kopyalar
    win.close()


def _walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk(child)


# ── Yazı tipi ve tema ayarları seçilebilir metni bozmamalı ───────────────────
def test_font_setting_keeps_size_style_code_and_refits(host, monkeypatch):
    """Ayarlar'dan yazı tipi değişince tüm Text'ler tek boyuta zorlanıyordu:
    mesaj gövdesi 11'den 10'a düşer, döküm italiğini kaybeder, sabit kutu
    yeniden ölçülmediği için metin kesilirdi."""
    import xmpp
    monkeypatch.setattr(xmpp, "FONT", xmpp.FONT)   # global'i test sonu geri al
    box = _box(host, [("kalın", "bold"), (" ve uzun bir cümle ", None),
                      ("kod()", "code")] * 6)
    _settle(host)
    w = object.__new__(xmpp.MainWindow)
    w.root = host
    xmpp.MainWindow._apply_font_settings(w, family="DejaVu Serif", size=10)
    _settle(host, 0.4)
    assert box._font == ("DejaVu Serif", 11)
    assert "DejaVu Serif" in box.text.tag_cget("bold", "font")
    assert "bold" in box.text.tag_cget("bold", "font")
    assert "Courier" in box.text.tag_cget("code", "font")   # kod eş aralıklı
    assert _all_visible(box)


def test_theme_refresh_recolors_code_spans_and_selection(host, monkeypatch):
    import xmpp
    box = _box(host, [("x = 1", "code")])
    monkeypatch.setattr(xmpp, "_COLOR_REMAP", {
        "#333333": "#999999", "#4444aa": "#55aa55", "#222222": "#101010"})
    w = object.__new__(xmpp.MainWindow)
    w.root = host
    xmpp.MainWindow._refresh_theme(w)
    assert box.text.tag_cget("code", "background") == "#999999"
    assert box.text.cget("selectbackground") == "#55aa55"
    assert box.text.cget("inactiveselectbackground") == "#55aa55"
    assert box.text.cget("bg") == "#101010" and box.cget("bg") == "#101010"
