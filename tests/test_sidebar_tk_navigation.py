"""Gerçek Tk widget'larıyla sohbet filtreleri ve klavye geçişi."""
import os
import re
import sys
import tkinter as tk
import traceback
import types
from tkinter import ttk

import pytest

import xmpp


@pytest.fixture()
def window(monkeypatch):
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        pytest.skip("Tk testleri bir ekran veya Xvfb gerektiriyor")
    root = tk.Tk()
    root.withdraw()
    errors = []
    root.report_callback_exception = lambda exc_type, value, tb: errors.append(
        "".join(traceback.format_exception(exc_type, value, tb)))
    root.tk.createcommand("record_navigation_bgerror", errors.append)
    root.tk.eval("proc bgerror {msg} {record_navigation_bgerror $msg}")
    xmpp._apply_theme()
    win = object.__new__(xmpp.MainWindow)
    win.root = root
    win.jid = "tester@example.test"
    win._photo_refs = []
    win._contacts = {"ali@example.com": "Ali", "light@example.net": "IŞIK Güngör"}
    win.presence = {"ali@example.com": "available"}
    win.rooms = ["dev@conf", "genel@conf"]
    win._pinned_chats = ["dev@conf", "ali@example.com"]
    win._unread_counts = {"light@example.net": 3, "genel@conf": 2}
    win._closing = False
    win.active = None
    win.opened = []
    win.roles = []
    win.my_nick = {}
    win.room_members = {}
    win._room_subjects = {}

    def load_chat(jid):
        win.active = jid
        win.opened.append(jid)

    win._load_chat = load_chat
    win._hide_members = lambda: win.roles.append("contact")
    win._show_members = lambda jid: win.roles.append(("room", jid))
    monkeypatch.setattr(xmpp, "_load_config", lambda: {})
    monkeypatch.setattr(xmpp, "_save_config", lambda cfg: None)
    win._build_sidebar()
    win.msg_var = tk.StringVar(master=root, value="Taslağım burada kalmalı")
    win._msg_entry = ttk.Entry(root, textvariable=win.msg_var)
    win._msg_entry.grid(row=0, column=1)
    win._bind_shortcuts()
    win._filter_sidebar()
    try:
        yield win, errors
        assert errors == []
    finally:
        for aid in root.tk.splitlist(root.tk.call("after", "info")):
            root.tk.call("after", "cancel", aid)
        root.destroy()


def _popup(win):
    return next(widget for widget in win.root.winfo_children() if isinstance(widget, tk.Toplevel))


def _controls(pop):
    entry = next(widget for widget in pop.winfo_children() if isinstance(widget, ttk.Entry))
    results = next(widget for widget in pop.winfo_children() if isinstance(widget, tk.Listbox))
    return entry, results


def _key(widget, sequence, keysym="Return"):
    """Kayıtlı Tk callback'ini çağır; sistem klavye odağına dokunma."""
    binding = widget.bind(sequence)
    assert binding, f"Widget klavye bağlantısı eksik: {sequence}"
    command = re.search(r"\[([^\s\]]+)", binding).group(1)
    values = {code: "0" for code in widget._subst_format}
    values.update({"%W": widget._w, "%K": keysym, "%A": "", "%T": "2"})
    return widget.tk.call(command, *(values[code] for code in widget._subst_format))


def test_quick_switch_selects_first_result_and_opens_it_with_enter(window):
    win, _errors = window
    win._quick_switch_dialog()
    entry, results = _controls(_popup(win))

    assert results.curselection() == (0,)
    _key(entry, "<Return>")
    assert win.opened == ["dev@conf"]
    assert win.roles == [("room", "dev@conf")]


def test_quick_switch_arrows_select_the_correct_target(window):
    win, _errors = window
    win._quick_switch_dialog()
    entry, results = _controls(_popup(win))

    assert _key(entry, "<Down>", "Down") == "break"
    assert results.curselection() == (1,)
    _key(entry, "<Return>")
    assert win.opened == ["ali@example.com"]
    assert win.roles == ["contact"]


def test_quick_switch_filter_and_no_matches_do_not_open_wrong_chat(window):
    win, _errors = window
    win._quick_switch_dialog()
    pop = _popup(win)
    entry, results = _controls(pop)
    win.root.tk.setvar(entry.cget("textvariable"), "ISIK example.net")

    assert results.size() == 1
    assert results.curselection() == (0,)
    win.root.tk.setvar(entry.cget("textvariable"), "not-found-anywhere")
    assert results.size() == 0
    assert _key(entry, "<Return>") == "break"
    assert pop.winfo_exists()
    assert win.opened == []


def test_ctrl_k_intercepts_entry_class_binding_and_preserves_the_draft(window):
    win, _errors = window
    assert _key(win._msg_entry, "<Control-k>", "k") == "break"
    assert win.msg_var.get() == "Taslağım burada kalmalı"
    _key(_popup(win), "<Escape>", "Escape")
    assert win.msg_var.get() == "Taslağım burada kalmalı"


def test_fast_escape_does_not_leave_invalid_tk_timer_commands(window):
    win, errors = window
    win._quick_switch_dialog()
    _key(_popup(win), "<Escape>", "Escape")
    win.root.after(60, win.root.quit)
    win.root.mainloop()

    assert errors == []


def test_quick_switch_removes_its_variable_trace_when_closed(window):
    win, _errors = window
    win._quick_switch_dialog()
    pop = _popup(win)
    entry, _results = _controls(pop)
    variable = entry.cget("textvariable")
    assert win.root.tk.call("trace", "info", "variable", variable)

    _key(pop, "<Escape>", "Escape")

    assert not win.root.tk.call("trace", "info", "variable", variable)


def test_real_filter_buttons_change_the_visible_contacts_and_rooms(window):
    win, _errors = window

    def descendants(widget):
        for child in widget.winfo_children():
            yield child
            yield from descendants(child)

    unread = next(widget for widget in descendants(win._sidebar_frame)
                  if isinstance(widget, ttk.Radiobutton)
                  and widget.cget("value") == "unread")
    unread.invoke()

    assert win._contact_jids == ["light@example.net"]
    assert win._room_jids == ["genel@conf"]
    assert win.room_list.get(0) == "  💬  genel (2)"


def test_room_context_menu_can_pin_rooms_for_the_pinned_filter(window, monkeypatch):
    win, _errors = window
    menus = []
    real_menu = tk.Menu

    def menu(*args, **kwargs):
        widget = real_menu(*args, **kwargs)
        widget.tk_popup = lambda *args: None
        menus.append(widget)
        return widget

    monkeypatch.setattr(tk, "Menu", menu)
    win._pinned_chats = []
    win._filter_sidebar()
    win._room_context_menu(types.SimpleNamespace(y=0, x_root=0, y_root=0))
    labels = [menus[0].entrycget(index, "label")
              for index in range(menus[0].index("end") + 1)
              if menus[0].type(index) != "separator"]

    assert any("Sabitle" in label for label in labels)
    index = next(index for index in range(menus[0].index("end") + 1)
                 if menus[0].type(index) != "separator"
                 and "Sabitle" in menus[0].entrycget(index, "label"))
    menus[0].invoke(index)
    win._sidebar_filter_var.set("pinned")
    assert win._room_jids == ["dev@conf"]
    assert win.room_list.get(0) == "  💬  📌 dev"
