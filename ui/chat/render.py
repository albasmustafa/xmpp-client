"""Saf/senkron mesaj sunum primitifleri (Faz 4C-2A).

Yalnız Tk widget construction + presentation. Domain/bot/storage/network/
threading/after YOKTUR. Theme değerleri çağrı anında input olarak alınır
(import-time snapshot yok). Row attribute contract'ı (row._mid, _is_me,
_body, _tag, _sender, _reply_to, _retracted, _edited) burada üretilir;
kimlik/state mutasyonu YAPILMAZ.
"""
import tkinter as tk
from collections import namedtuple

BaseMessageView = namedtuple(
    "BaseMessageView", ("row", "bubble", "colors", "body_kind", "body_widget"))


def bubble_colors(theme, is_me):
    """Balon renklerini saf olarak hesapla."""
    return {
        "bubble_bg": theme["BG_ME"] if is_me else theme["BG_THEM"],
        "bubble_fg": theme["FG_ME"] if is_me else theme["FG"],
        "border_color": "#6d28d9" if is_me else theme["BORDER"],
    }


def render_system_message(parent, theme, text):
    """Sistem/olay mesajı divider satırı (tag == 'sys')."""
    sf = tk.Frame(parent, bg=theme["BG_CHAT"])
    sf.pack(fill="x", padx=24, pady=8)
    sf.columnconfigure(0, weight=1)
    sf.columnconfigure(2, weight=1)
    tk.Frame(sf, bg=theme["BORDER"], height=1).grid(
        row=0, column=0, sticky="ew", padx=(0, 10), pady=8)
    tk.Label(sf, text=text, fg=theme["FG_DIM"], bg=theme["BG_CHAT"],
             font=(theme["FONT"], 7)).grid(row=0, column=1)
    tk.Frame(sf, bg=theme["BORDER"], height=1).grid(
        row=0, column=2, sticky="ew", padx=(10, 0), pady=8)
    return sf


def render_date_separator(parent, theme, label):
    """Tarih ayırıcı çizgisi (label kararı çağıranda)."""
    sf = tk.Frame(parent, bg=theme["BG_CHAT"])
    sf.pack(fill="x", padx=24, pady=(12, 4))
    sf.columnconfigure(0, weight=1)
    sf.columnconfigure(2, weight=1)
    tk.Frame(sf, bg=theme["BORDER"], height=1).grid(
        row=0, column=0, sticky="ew", padx=(0, 10), pady=8)
    tk.Label(sf, text=label, fg=theme["FG_DIM"], bg=theme["BG_CHAT"],
             font=(theme["FONT"], 7, "bold")).grid(row=0, column=1)
    tk.Frame(sf, bg=theme["BORDER"], height=1).grid(
        row=0, column=2, sticky="ew", padx=(10, 0), pady=8)
    return sf


def build_message_row(parent, theme, *, is_me, sender, same_sender, compact,
                      avatar_factory, avatar_photo, photo_refs):
    """Dış satır + avatar + gölgeli balon + gönderen adı.

    Döndürür: (row, bubble, colors). Row attribute contract'ı YAZILMAZ;
    çağıran (MainWindow) set eder.
    """
    colors = bubble_colors(theme, is_me)
    gap = (1 if same_sender else 4) if compact else (3 if same_sender else 10)
    pad_x = 10 if compact else 22

    row = tk.Frame(parent, bg=theme["BG_CHAT"])
    row.pack(fill="x", padx=pad_x, pady=(gap, 0))

    if not is_me and sender and not same_sender:
        av = avatar_factory(row, 30, sender[0], theme["ACCENT2"],
                            theme["BG_CHAT"], photo_data=avatar_photo,
                            _photo_refs=photo_refs)
        av.pack(side="left", anchor="n", padx=(0, 8), pady=(2, 0))
    elif not is_me:
        tk.Frame(row, width=38, bg=theme["BG_CHAT"]).pack(side="left")

    bpad = (10, 6) if compact else (16, 10)
    shadow_f = tk.Frame(row, bg=theme["SHADOW"], padx=1, pady=1)
    bubble_border = tk.Frame(shadow_f, bg=colors["border_color"], padx=1, pady=1)
    bubble_border.pack(fill="both", expand=True)
    bubble = tk.Frame(bubble_border, bg=colors["bubble_bg"],
                      padx=bpad[0], pady=bpad[1])
    bubble.pack(fill="both", expand=True)
    if is_me:
        shadow_f.pack(side="right", anchor="e", padx=(70, 0))
    else:
        shadow_f.pack(side="left", anchor="w", padx=(0, 70))

    if not is_me and sender and not same_sender:
        tk.Label(bubble, text=sender, fg=theme["ACCENT"],
                 bg=colors["bubble_bg"],
                 font=(theme["FONT"], 8, "bold")).pack(anchor="w")

    return row, bubble, colors


def render_reply_quote(bubble, theme, reply_to, on_jump):
    """Alıntı önizleme kartı; tıklama on_jump(mid) çağırır."""
    rq_f = tk.Frame(bubble, bg=theme["BORDER"], padx=1, pady=1,
                    cursor="hand2")
    rq_f.pack(anchor="w", fill="x", pady=(0, 4))
    rq_inner = tk.Frame(rq_f, bg=theme["BG_HOVER"], padx=8, pady=4,
                        cursor="hand2")
    rq_inner.pack(fill="x")
    tk.Frame(rq_inner, bg=theme["ACCENT"], width=3).pack(
        side="left", fill="y", padx=(0, 6))
    rq_txt_f = tk.Frame(rq_inner, bg=theme["BG_HOVER"], cursor="hand2")
    rq_txt_f.pack(side="left", fill="x")
    rq_sender = reply_to.get("sender", "")
    if rq_sender:
        tk.Label(rq_txt_f, text=f"↪ {rq_sender}",
                 font=(theme["FONT"], 7, "bold"), fg=theme["ACCENT"],
                 bg=theme["BG_HOVER"], cursor="hand2").pack(anchor="w")
    rq_body = reply_to.get("body", "")[:100]
    tk.Label(rq_txt_f, text=rq_body, font=(theme["FONT"], 7),
             fg=theme["FG_DIM"], bg=theme["BG_HOVER"], wraplength=300,
             justify="left", cursor="hand2").pack(anchor="w")
    rq_mid = reply_to.get("id", "")

    def _rq_click(_e, m=rq_mid):
        on_jump(m)

    for _w in (rq_f, rq_inner, rq_txt_f, *rq_txt_f.winfo_children()):
        _w.bind("<Button-1>", _rq_click)
    return rq_f


MESSAGE_WRAP = 420        # balon metninin en geniş satırı (px)


def message_styles(theme):
    """Markdown parçalarının Text etiketleri (formatter stilleri)."""
    return {"bold": {"font": (theme["FONT"], 11, "bold")},
            "italic": {"font": (theme["FONT"], 11, "italic")},
            "code": {"font": ("Courier", 10), "background": theme["BORDER"]}}


def render_message_body(bubble, theme, display_body, colors, formatter,
                        text_factory):
    """Markdown destekli, sol tıkla seçilebilen metin gövdesi (Label metni
    seçilemiyordu). `text_factory`: seçilebilir metin kurucu (MainWindow
    ui.selectable.selectable_text verir; bu modül yalnız tkinter/collections
    kullanır). Kalın/italik/kod tek metinde etiketlerle akar; satır kaydırma
    Label'ın wraplength'i gibi.

    Döndürür: ("text", çerçeve; metin `.text`'te) | (None, None).
    """
    if not display_body:
        return None, None
    box = text_factory(
        bubble, formatter(display_body), fg=colors["bubble_fg"],
        bg=colors["bubble_bg"], font=(theme["FONT"], 11), wrap=MESSAGE_WRAP,
        sel_bg=theme["SEL_BG"], sel_fg=theme["SEL_FG"],
        styles=message_styles(theme))
    box.pack(anchor="w")
    return "text", box


def render_meta_row(bubble, theme, time_str, is_me, encrypted, bubble_bg):
    """Zaman damgası + şifreleme kilidi + gönderildi işareti (sağ alt)."""
    ts_frame = tk.Frame(bubble, bg=bubble_bg)
    ts_frame.pack(anchor="e", pady=(3, 0))
    if encrypted:
        tk.Label(ts_frame, text="🔒", font=(theme["FONT"], 6),
                 fg=theme["ACCENT_G"], bg=bubble_bg).pack(
            side="left", padx=(0, 3))
    tk.Label(ts_frame, text=time_str,
             fg=("#c8c0ff" if is_me else theme["FG_DIM"]),
             bg=bubble_bg, font=(theme["FONT"], 7)).pack(side="left")
    if is_me:
        tk.Label(ts_frame, text=" ✓", font=(theme["FONT"], 6),
                 fg=theme["FG_DIM"], bg=bubble_bg).pack(side="left")
    return ts_frame


def render_base_message(parent, theme, *, is_me, sender, same_sender, compact,
                        reply_to, display_body, formatter, avatar_factory,
                        avatar_photo, photo_refs, on_jump, text_factory):
    """Temel mesaj gövdesi assembly: row + reply quote + body.

    Meta row (timestamp/kilit/✓) bilinçli olarak kapsam dışı: medya
    yerleşimi body ile meta arasına girdiğinden sıra MainWindow'da korunur.
    Domain/state mutasyonu YAPMAZ; yalnız sunum üretir.
    """
    row, bubble, colors = build_message_row(
        parent, theme, is_me=is_me, sender=sender,
        same_sender=same_sender, compact=compact,
        avatar_factory=avatar_factory, avatar_photo=avatar_photo,
        photo_refs=photo_refs)
    if reply_to:
        render_reply_quote(bubble, theme, reply_to, on_jump)
    body_kind, body_widget = render_message_body(
        bubble, theme, display_body, colors, formatter, text_factory)
    return BaseMessageView(row, bubble, colors, body_kind, body_widget)
