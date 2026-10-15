"""Kısa ömürlü pencerelere güvenli zamanlayıcı."""


def after_alive(widget, ms, func):
    """``widget.after(ms, func)`` gibi; widget yok edilince bekleyeni iptal eder.

    tkinter after() callback'ini widget'a ait bir Tcl komutu olarak kaydeder
    ve komut adını id(callback)'ten türetir. Widget zamanlayıcı dolmadan yok
    edilirse komut silinir ama Tcl zamanlayıcısı beklemeye devam eder; Python
    o id'yi yeni bir callback'e verdiğinde zamanlayıcı ALAKASIZ bir fonksiyonu
    argümansız çağırır (ör. emoji seçicinin <Enter> lambda'sı → TypeError).

    Widget başına tek <Destroy> bağı kurulur; kendini yeniden kuran
    döngülerde bağ birikmez, biten zamanlayıcılar kümeden düşer.
    """
    pending = getattr(widget, "_after_alive_ids", None)
    if pending is None:
        pending = widget._after_alive_ids = set()

        def _cancel(event):
            if str(event.widget) != str(widget):
                return
            for aid in list(pending):
                try:
                    widget.after_cancel(aid)
                except Exception:
                    pass
            pending.clear()

        widget.bind("<Destroy>", _cancel, add="+")

    holder = []

    def _run():
        pending.discard(holder[0])
        func()

    aid = widget.after(ms, _run)
    holder.append(aid)
    pending.add(aid)
    return aid
