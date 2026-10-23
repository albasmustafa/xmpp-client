"""Seçilebilir salt-okunur metin (sohbet balonu, asistan yanıtı).

tk.Label metni fareyle seçilemez. Bu yardımcı Label gibi görünen (kenarlıksız,
aynı renk ve yazı tipi) ama sol tıkla seçilen kapalı bir tk.Text kurar:

- Sürükle: seçim · çift tık: kelime · üç tık: satır · Shift+tık: genişlet.
  `SELECT_TAG` bağlama etiketi Text sınıfının yalnız bu fare bağlamalarını
  taşır: tekerlek, tuş, orta tık ve otomatik kaydırma yok — tekerlek sohbeti
  kaydırmayı sürdürür, metin kendi içinde kaymaz, odak giriş kutusundan
  çalınmaz (X11'de kapalı Text tıklamayla odak almaz). Seçim odak yokken de
  görünür (inactiveselectbackground).
- Boyut: genişlik en uzun satır (en çok `wrap` px); yükseklik Tk'nin kendi
  düzeninden (`count -ypixels`) piksel piksel — emoji ya da kod satırı
  kesilmez. Text, boyutu sabit bir çerçevenin içindedir: çerçeve paketlenir,
  metin `çerçeve.text`'tedir.
- Kopyalama: `copy_selection` (Ctrl+C; odak giriş kutusundayken de) ve
  `selected_text` (sağ tık menüsü).
"""
import re
import tkinter as tk

SELECT_TAG = "SelectableText"
_SELECT_SEQS = ("<Button-1>", "<B1-Motion>", "<ButtonRelease-1>",
                "<Double-Button-1>", "<Triple-Button-1>", "<Shift-Button-1>",
                "<Double-Shift-Button-1>", "<Triple-Shift-Button-1>")
_SLACK = 4                  # satır sonu payı: tek satırlık metin kaydırılmasın
_WORD_RE = re.compile(r"\S+\s*|\s+")


def selectable_text(parent, content, *, fg, bg, font, wrap, sel_bg, sel_fg,
                    styles=None):
    """`content`: metin ya da [(parça, stil | None)]; `styles`: {stil: Text
    etiketi seçenekleri (font, background…)}. → çerçeve (`.text`: Text)."""
    box = tk.Frame(parent, bg=bg, width=1, height=1)
    box.pack_propagate(False)
    text = tk.Text(box, bd=0, highlightthickness=0, relief="flat", padx=0,
                   pady=0, wrap="word", font=font, fg=fg, bg=bg,
                   cursor="xterm", insertwidth=0, takefocus=0,
                   exportselection=True, selectbackground=sel_bg,
                   selectforeground=sel_fg, inactiveselectbackground=sel_bg,
                   width=1, height=1)
    text.pack(fill="both", expand=True)
    for name, opts in (styles or {}).items():
        text.tag_configure(name, **opts)
    _install(text)
    box.text = text
    box._font = font
    box._wrap = wrap
    box._styles = dict(styles or {})
    # Kutu kendi işlemlerini taşır: ui/chat modülleri bu modülü içe
    # aktarmadan günceller (yalnız tkinter/collections sözleşmesi)
    box.set_content = lambda content, **kw: set_content(box, content, **kw)
    box.set_bg = lambda color: set_bg(box, color)
    set_content(box, content)
    text.bind("<Configure>", lambda _e: _fit_height(box), add="+")
    return box


def set_content(box, content, *, fg=None, font=None):
    """Metni değiştir (düzeltme, geri çekme, akış) ve yeniden boyutla."""
    text = box.text
    if fg is not None:
        text.configure(fg=fg)
    if font is not None:
        text.configure(font=font)
        box._font = font
    parts = [(content, None)] if isinstance(content, str) else list(content)
    text.configure(state="normal")
    text.delete("1.0", "end")
    for chunk, style in parts:
        text.insert("end", chunk, (style,) if style else ())
    text.configure(state="disabled")
    box._parts = parts
    width, height = _measure(box, parts)
    box.configure(width=width, height=height)
    _fit_height(box)


def set_family(box, family):
    """Yazı tipi ailesini değiştir (Ayarlar): boyut, kalın/italik ve kodun
    eş aralıklı yazı tipi korunur; yeni ölçülerle yeniden boyutlanır."""
    old = box._font[0] if isinstance(box._font, tuple) else None

    def swap(font):
        if isinstance(font, tuple) and font and font[0] == old:
            return (family,) + tuple(font[1:])
        return font
    box._font = swap(box._font)
    box.text.configure(font=box._font)
    for name, opts in box._styles.items():
        if "font" in opts:
            opts["font"] = swap(opts["font"])
            box.text.tag_configure(name, font=opts["font"])
    set_content(box, box._parts)


def is_box(widget):
    """Seçilebilir metin kutusu mu (ör. ayar gezintilerinde ayırmak için)?"""
    text = getattr(widget, "text", None)
    try:
        return text is not None and SELECT_TAG in text.bindtags()
    except (tk.TclError, AttributeError):
        return False


def set_bg(box, color):
    """Arka planı değiştir (ör. alıntıya atlayınca kısa vurgu)."""
    box.configure(bg=color)
    box.text.configure(bg=color)


def selected_text(widget):
    """Seçili metin ("" = seçim yok); çerçeve ya da Text verilebilir."""
    text = getattr(widget, "text", widget)
    try:
        return text.get("sel.first", "sel.last")
    except (tk.TclError, AttributeError):
        return ""


def copy_selection(widget):
    """PRIMARY seçimi bir seçilebilir metindeyse panoya kopyala → kopyalandı mı.

    Ctrl+C odaktaki pencereye gider (giriş kutusu); onun kendi seçimi varsa
    PRIMARY onundur ve bu yardımcı bir şey yapmaz."""
    try:
        owner = widget.selection_own_get()
    except (tk.TclError, KeyError):
        return False
    if owner is None or SELECT_TAG not in owner.bindtags():
        return False
    chosen = selected_text(owner)
    if not chosen:
        return False
    widget.clipboard_clear()
    widget.clipboard_append(chosen)
    return True


def _install(text):
    """Text sınıfı yerine yalnız fareyle seçim bağlamaları (bkz. modül).

    Tk 8.6.16'nın tk::TextButton1'i kapalı Text'e de `focus $w` yapıyor:
    mesaja tıklayınca giriş kutusu odağı kaybedip yazılanlar boşa gidiyordu.
    Kurulu Tk'nin kendi gövdesi odak satırı çıkarılarak kopyalanır (sürümle
    uyumlu kalır)."""
    if not text.bind_class(SELECT_TAG):
        args = text.tk.eval("info args ::tk::TextButton1")
        body = re.sub(r"(?m)^\s*focus \$w\s*$", "",
                      text.tk.eval("info body ::tk::TextButton1"))
        text.tk.call("proc", "::tk::SelectableButton1", args, body)
        for seq in _SELECT_SEQS:
            script = text.bind_class("Text", seq)
            if script:
                text.bind_class(SELECT_TAG, seq, script.replace(
                    "tk::TextButton1", "::tk::SelectableButton1"))
    text.bindtags(tuple(SELECT_TAG if tag == "Text" else tag
                        for tag in text.bindtags()))


def _measure(box, parts):
    """(genişlik, tahmini yükseklik) px: Tk'nin wrap='word' düzenine yakın;
    yükseklik görününce `_fit_height` ile kesinleşir."""
    base = box._font
    fonts = {None: base}
    fonts.update({name: opts.get("font", base)
                  for name, opts in box._styles.items()})

    def measure(font, s):
        return int(box.tk.call("font", "measure", font, s))

    def linespace(font):
        return int(box.tk.call("font", "metrics", font, "-linespace"))

    lines = [[]]
    for chunk, style in parts:
        for i, seg in enumerate(chunk.split("\n")):
            if i:
                lines.append([])
            if seg:
                lines[-1].append((seg, fonts.get(style, base)))
    wrap = box._wrap
    widest = height = 0
    for line in lines:
        space = max((linespace(f) for _s, f in line), default=linespace(base))
        full = sum(measure(f, s) for s, f in line)
        if full <= wrap:
            widest = max(widest, full)
            height += space
            continue
        widest, count, cur = wrap, 1, 0
        for seg, font in line:
            for word in _WORD_RE.findall(seg):
                bare = measure(font, word.rstrip()) if word.strip() else 0
                if cur and cur + bare > wrap:
                    count, cur = count + 1, 0
                if bare > wrap:             # satırdan uzun kelime: kırılır
                    count += bare // wrap
                    cur = bare % wrap
                else:
                    cur += measure(font, word)
        height += count * space
    return widest + _SLACK, max(height, 1)


def _fit_height(box):
    """Görününce yüksekliği Tk'nin gerçek düzenine eşitle (piksel)."""
    text = box.text
    try:
        if text.winfo_width() <= 1:
            return
        need = int(text.tk.call(text._w, "count", "-update", "-ypixels",
                                "1.0", "end"))
        if need > 0 and need != int(box.cget("height")):
            box.configure(height=need)
    except (tk.TclError, ValueError, TypeError):
        pass
