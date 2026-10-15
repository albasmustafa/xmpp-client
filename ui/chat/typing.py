"""Typing indicator presentation primitifleri (Faz 4C-4B).

Yalnız label text sunumu. Timer/`after`/state/`_typing` set/active JID/bot
bilmez; MainWindow timer ve lifecycle sahibidir.
"""


def show_typing(label, t, dots):
    """✎ <typing>... metnini yazar (dots 1..3)."""
    label.config(text=f"✎ {t('typing')}{'.' * dots}")


def hide_typing(label):
    """Indicator metnini temizler."""
    label.config(text="")
