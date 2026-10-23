"""Sahte Tk testleri için `ui.selectable`'ın hafif sahtesi (gerçek Text yok).

Mesaj gövdesi artık seçilebilir metin (ui.selectable); sahte widget'larla
çalışan testler `install(monkeypatch, _W)` ile bunu takar: kutu, testin kendi
sahte widget sınıfından üretilir; metni `kw["text"]`'tedir (eski Label gibi).
"""
import types


def text_of(content):
    if isinstance(content, str):
        return content
    return "".join(chunk for chunk, _style in content)


def make(widget_cls):
    def selectable_text(parent, content, **kw):
        box = widget_cls(parent, text=text_of(content), fg=kw.get("fg"),
                         bg=kw.get("bg"), font=kw.get("font"))
        box.text = box
        box.parts = content
        box.selected = ""

        def set_content(new, fg=None, font=None):
            box.kw["text"] = text_of(new)
            box.parts = new
            if fg is not None:
                box.kw["fg"] = fg
            if font is not None:
                box.kw["font"] = font

        box.set_content = set_content
        box.set_bg = lambda color: box.kw.__setitem__("bg", color)
        return box

    return types.SimpleNamespace(
        selectable_text=selectable_text,
        selected_text=lambda w: getattr(w, "selected", "") if w else "",
        set_bg=lambda box, color: box.set_bg(color),
        copy_selection=lambda w: False,
        SELECT_TAG="SelectableText")


def install(monkeypatch, widget_cls):
    """xmpp._selectable'ı sahtesiyle değiştir; sahte modülü döndürür."""
    import xmpp
    fake = make(widget_cls)
    monkeypatch.setattr(xmpp, "_selectable", fake)
    return fake
