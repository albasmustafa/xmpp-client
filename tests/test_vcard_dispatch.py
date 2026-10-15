"""vCard olayı GUI'ye ulaşır ve bot'un info anahtarlarıyla gösterilir."""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402


def test_vcard_event_invokes_callback_with_info():
    got = []
    win = object.__new__(xmpp.MainWindow)
    info = {"fn": "Ayşe", "nickname": "ay", "email": "a@x", "url": "", "bday": ""}
    xmpp.MainWindow._handle(win, "vcard", {"jid": "a@x", "info": info, "cb": got.append})
    xmpp.MainWindow._handle(win, "vcard", {"jid": "a@x", "info": None,
                                           "error": "timeout", "cb": got.append})
    assert got == [info, None]


def test_vcard_callback_crash_does_not_propagate():
    win = object.__new__(xmpp.MainWindow)

    def boom(_):
        raise RuntimeError("x")

    xmpp.MainWindow._handle(win, "vcard", {"jid": "a@x", "info": {}, "cb": boom})


def test_profile_popup_reads_bot_info_keys():
    # Bot'un ürettiği anahtarlar profil penceresinin okuduklarıyla aynı olmalı
    bot_src = inspect.getsource(xmpp.XMPPBot._get_vcard)
    ui_src = inspect.getsource(xmpp.MainWindow)
    for key in ("fn", "nickname", "email", "url", "bday"):
        assert f'"{key}"' in bot_src
        assert f', "{key}")' in ui_src
    assert '"EMAIL/USERID"' not in ui_src
