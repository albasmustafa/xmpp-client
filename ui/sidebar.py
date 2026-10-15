"""Sidebar render/sıralama yardımcıları (Faz 4B-1).

"Veri ver → sidebar çiz" sınırı: bu modül yalnızca sıralama/filtreleme ve
satır metni/renk üretir. Widget sahipliği ve selection MainWindow'da kalır
(sidebar component'e geçiş sonraki dilimlerde). Domain/XMPP state'i yok;
roster/presence verisi parametreyle gelir.

Tema/renk haritası canlı `xmpp` modülünden çağrı anında okunur.
"""
import tkinter as tk  # noqa: F401  (widget tipleri için tip bağımsız)
import unicodedata

_ONLINE_STATUS = {"available", "", "online", "chat", "away", "dnd", "xa"}


def _app():
    import xmpp as _app_mod
    return _app_mod


def _search_text(value):
    text = unicodedata.normalize("NFKD", str(value or "").casefold()).replace("ı", "i")
    return "".join(char for char in text if not unicodedata.combining(char))


def _matches(tokens, *values):
    text = _search_text(" ".join(str(value or "") for value in values))
    return all(token in text for token in tokens)


def _visible(jid, view, pinned, unread_counts):
    if view == "unread":
        return unread_counts.get(jid, 0) > 0
    if view == "pinned":
        return jid in pinned
    return True


def ordered_contact_jids(contacts, presence, pinned, query="", *, unread_counts=None, view="all"):
    """Kişileri sabit → online → offline, alfabetik sırala; sorguya göre filtrele.

    MainWindow._refresh_contacts / _filter_sidebar için ortak sıra:
    `contacts`: {jid: isim}; `presence`: {jid: pshow}; `pinned`: jid listesi.
    Sorgunun bütün sözcükleri isim/JID birleşiminde, Unicode ve Türkçe
    karakterler normalize edilerek aranır.
    """
    unread_counts = unread_counts or {}
    tokens = _search_text(query).split()
    all_jids = sorted(contacts.keys())
    pinned_list = list(dict.fromkeys(j for j in pinned if j in contacts))
    pinned_set = set(pinned_list)
    unpinned = [j for j in all_jids if j not in pinned_set]
    unpinned_online = [j for j in unpinned
                       if presence.get(j, "unavailable") in _ONLINE_STATUS]
    online_set = set(unpinned_online)
    unpinned_offline = [j for j in unpinned if j not in online_set]
    full = pinned_list + unpinned_online + unpinned_offline
    return [j for j in full
            if _visible(j, view, pinned_set, unread_counts)
            and _matches(tokens, j, contacts.get(j, ""))]


def render_contacts(contact_list, contacts, presence, pinned, unread_counts,
                    jids):
    """Kişi listesini çiz (satır metni + renk + unread rozeti)."""
    colors = _app().PRESENCE_COLOR
    contact_list.delete(0, "end")
    for jid in jids:
        name = contacts[jid] or jid
        pshow = presence.get(jid, "unavailable")
        color = colors.get(pshow, "#72767d")
        pin_icon = "📌 " if jid in pinned else ""
        unread = unread_counts.get(jid, 0)
        badge = f" ({unread})" if unread > 0 else ""
        contact_list.insert("end", f"  ● {pin_icon}{name}{badge}")
        contact_list.itemconfig("end", fg=color)


def filtered_rooms(rooms, query="", *, pinned=(), unread_counts=None, view="all"):
    """Oda listesini sorguya göre filtrele."""
    tokens = _search_text(query).split()
    pinned_set = set(pinned)
    unread_counts = unread_counts or {}
    return [room for room in rooms
            if _visible(room, view, pinned_set, unread_counts) and _matches(tokens, room)]


def render_rooms(room_list, room_jids, *, pinned=(), unread_counts=None):
    """Oda listesini sabitleme ve okunmamış mesaj rozetleriyle çiz."""
    pinned_set = set(pinned)
    unread_counts = unread_counts or {}
    room_list.delete(0, "end")
    for room in room_jids:
        pin_icon = "📌 " if room in pinned_set else ""
        unread = unread_counts.get(room, 0)
        badge = f" ({unread})" if unread > 0 else ""
        room_list.insert("end", f"  💬  {pin_icon}{room.split('@')[0]}{badge}")


def quick_switch_targets(contacts, rooms, pinned=(), unread_counts=None, query=""):
    """Hızlı geçiş için (JID, etiket, oda mı) kayıtları üret; girdileri değiştirme."""
    unread_counts = unread_counts or {}
    pin_order = {jid: index for index, jid in enumerate(dict.fromkeys(pinned))}
    room_jids = list(dict.fromkeys(rooms))
    room_set = set(room_jids)
    records = [(jid, name or jid, False) for jid, name in contacts.items() if jid not in room_set]
    records.extend((jid, jid.split("@", 1)[0], True) for jid in room_jids)
    tokens = _search_text(query).split()

    def order(record):
        jid, name, _is_room = record
        if jid in pin_order:
            return (0, pin_order[jid], "", "")
        return (1 if unread_counts.get(jid, 0) > 0 else 2, 0,
                _search_text(name), _search_text(jid))

    targets = []
    for jid, name, is_room in sorted(records, key=order):
        if not _matches(tokens, jid, name):
            continue
        pin_icon = "📌 " if jid in pin_order else ""
        icon = "🏠" if is_room else "👤"
        unread = unread_counts.get(jid, 0)
        badge = f" ({unread})" if unread > 0 else ""
        targets.append((jid, f"{pin_icon}{icon} {name}{badge}", is_room))
    return targets


def update_sidebar_avatar(canvas, jid, data, photo_refs=None):
    """Hazır avatar verisini sidebar canvas'ına çiz (Faz 4B-2A).

    Network/bot çağrısı yok; veri parametre gelir. PIL yoksa/veri yoksa
    baş harf + online noktası fallback'i kullanılır (birebir eski davranış).
    """
    A = _app()
    canvas.delete("all")
    if data and A.HAS_PIL:
        try:
            import io

            from PIL import Image, ImageDraw, ImageTk
            img = Image.open(io.BytesIO(data))
            img = img.resize((40, 40), Image.LANCZOS)
            mask = Image.new("L", (40, 40), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 40, 40), fill=255)
            img.putalpha(mask)
            photo = ImageTk.PhotoImage(img)
            canvas.create_image(21, 21, image=photo)
            canvas._photo = photo
            if photo_refs is not None:
                photo_refs.append(photo)
            # Online nokta
            canvas.create_oval(30, 30, 40, 40, fill=A.ONLINE,
                               outline=A.BG_PANEL, width=2)
            return
        except Exception:
            pass
    # Fallback: harf
    initial = jid[0].upper() if jid else "?"
    canvas.create_oval(1, 1, 41, 41, fill=A.ACCENT2, outline="")
    canvas.create_text(21, 21, text=initial, fill=A.FG_ME,
                       font=(A.FONT, 14, "bold"))
    canvas.create_oval(30, 30, 40, 40, fill=A.ONLINE, outline=A.BG_PANEL,
                       width=2)


def show_contact_menu(parent, jid, is_pinned, on_open_chat, on_toggle_pin,
                      on_common_groups, on_remove_contact, x_root, y_root):
    """Kişi sağ tık menüsü (Faz 4B-2B).

    Menü yalnızca görsel kabuktur; eylemler callback'lere delege edilir
    (domain/XMPP çağrısı yapılmaz).
    """
    A = _app()
    menu = tk.Menu(parent, tearoff=0,
                   bg=A.BG_CARD, fg=A.FG, activebackground=A.ACCENT2,
                   activeforeground=A.FG_ME, borderwidth=1,
                   relief="flat", font=(A.FONT, 9))
    menu.add_command(label=jid, state="disabled")
    menu.add_separator()
    menu.add_command(label="  Sohbet Başlat", command=on_open_chat)
    if is_pinned:
        menu.add_command(label="📌 Sabitlemeyi Kaldır", command=on_toggle_pin)
    else:
        menu.add_command(label="📌 Sohbeti Sabitle", command=on_toggle_pin)
    menu.add_command(label="🏠 Ortak Gruplar", command=on_common_groups)
    menu.add_command(label="  Kişiyi Kaldır", command=on_remove_contact)
    menu.tk_popup(x_root, y_root)


def build_assistant_entry(parent, on_open, *, subtitle):
    """Kişi listesinin üstünde kişi görünümlü "✨ Asistan" girişi.

    Tıklama `on_open()` çağırır; asistan XMPP kişisi DEĞİLDİR (roster,
    presence, şifreleme ve stanza yollarına hiç girmez).
    """
    A = _app()
    row = tk.Frame(parent, bg=A.BG_PANEL, padx=6, pady=4, cursor="hand2")
    av = tk.Canvas(row, width=30, height=30, bg=A.BG_PANEL,
                   highlightthickness=0, cursor="hand2")
    av.create_oval(2, 2, 28, 28, fill=A.ACCENT2, outline="")
    av.create_text(15, 15, text="✨", fill=A.FG_ME, font=(A.FONT, 10))
    av.pack(side="left")
    info = tk.Frame(row, bg=A.BG_PANEL, cursor="hand2")
    info.pack(side="left", fill="x", expand=True, padx=(8, 0))
    name = tk.Label(info, text="Asistan", font=(A.FONT, 10, "bold"),
                    fg=A.FG, bg=A.BG_PANEL, anchor="w", cursor="hand2")
    name.pack(fill="x")
    sub = tk.Label(info, text=subtitle, font=(A.FONT, 7), fg=A.FG_DIM,
                   bg=A.BG_PANEL, anchor="w", cursor="hand2")
    sub.pack(fill="x")
    widgets = (row, av, info, name, sub)

    def _hover(on):
        bg = A.BG_HOVER if on else A.BG_PANEL
        for w in widgets:
            w.config(bg=bg)
    for w in widgets:
        w.bind("<Button-1>", lambda _e: on_open())
        w.bind("<Enter>", lambda _e: _hover(True))
        w.bind("<Leave>", lambda _e: _hover(False))
    row.subtitle = sub
    return row


def render_members(members_list, members_label, room_members):
    """KATILIMCILAR listesini çiz ve index→nick haritasını döndür (4B final shell).

    Gruplama/sıralama/ikon/renk semantiği MainWindow._refresh_members ile
    birebir; widget sahipliği çağıranda kalır.
    """
    A = _app()
    members_list.delete(0, "end")
    index_map = {}
    mbrs = room_members or {}
    count = len(mbrs)
    members_label.config(
        text=f"KATILIMCILAR — {count}" if count else "KATILIMCILAR")
    if not mbrs:
        return index_map

    # Rol/affiliation öncelik sırası
    _AFFIL_ORDER = {"owner": 0, "admin": 1, "member": 2, "none": 3, "": 3}
    _ROLE_ORDER = {"moderator": 0, "participant": 1, "visitor": 2,
                   "none": 3, "": 3}

    _AFFIL_ICON = {"owner": "👑", "admin": "🛡", "member": "", "none": "", "": ""}
    _ROLE_ICON = {"moderator": "⚔", "participant": "", "visitor": "👁",
                  "none": "", "": ""}

    _SHOW_ICON = {"": "●", "chat": "●", "away": "●", "xa": "●", "dnd": "●"}
    _SHOW_COLOR = {"": A.ONLINE, "chat": A.ONLINE, "away": A.AWAY,
                   "xa": A.FG_DIM, "dnd": A.RED}

    sorted_nicks = sorted(
        mbrs.items(),
        key=lambda x: (
            _AFFIL_ORDER.get(x[1].get("affil", ""), 3),
            _ROLE_ORDER.get(x[1].get("role", ""), 3),
            x[0].lower(),
        ),
    )

    _GROUP_NAMES = {
        "owner":     "─ SAHİPLER ─",
        "admin":     "─ YÖNETİCİLER ─",
        "moderator": "─ MODERATÖRLER ─",
    }

    last_group = None
    idx = 0
    for nick, info in sorted_nicks:
        affil = info.get("affil", "")
        role = info.get("role", "")
        show = info.get("show", "")

        group = affil if affil in ("owner", "admin") else (
            role if role == "moderator" else "other")
        if group != last_group and group in _GROUP_NAMES:
            members_list.insert("end", f"  {_GROUP_NAMES[group]}")
            members_list.itemconfig("end", fg=A.FG_DIM)
            idx += 1
            last_group = group
        elif group != last_group:
            last_group = group

        show_dot = _SHOW_ICON.get(show, "●")
        show_color = _SHOW_COLOR.get(show, A.FG_DIM)
        badge = _AFFIL_ICON.get(affil, "") or _ROLE_ICON.get(role, "")
        prefix = f"{badge} " if badge else ""

        members_list.insert("end", f"  {show_dot} {prefix}{nick}")
        members_list.itemconfig("end", fg=show_color)
        index_map[idx] = nick
        idx += 1
    return index_map


def show_contact_card(parent, jid, name, pshow, av_data, photo_refs,
                      common_count, x_root, y_root):
    """Hover mini profil kartını çiz ve popup'ı döndür (Faz 4B-2).

    Kapatma/`<Leave>` bağlama ve zamanlayıcı çağıranda kalır (widget
    lifecycle sahibi MainWindow). Domain/network çağrısı yok.
    """
    A = _app()
    pop = tk.Toplevel(parent)
    pop.overrideredirect(True)
    pop.configure(bg=A.BORDER)
    pop.attributes("-topmost", True)

    inner = tk.Frame(pop, bg=A.BG_CARD, padx=12, pady=10)
    inner.pack(padx=1, pady=1)

    color = A.PRESENCE_COLOR.get(pshow, A.FG_DIM)

    # Avatar
    av = A._avatar(inner, 36, name[0], A.ACCENT2, A.BG_CARD,
                   photo_data=av_data, _photo_refs=photo_refs)
    av.grid(row=0, column=0, rowspan=3, padx=(0, 10))

    tk.Label(inner, text=name, font=(A.FONT, 10, "bold"),
             fg=A.FG, bg=A.BG_CARD).grid(row=0, column=1, sticky="w")
    tk.Label(inner, text=jid, font=(A.FONT, 7),
             fg=A.FG_DIM, bg=A.BG_CARD).grid(row=1, column=1, sticky="w")

    status_text = pshow if pshow != "unavailable" else "Çevrimdışı"
    tk.Label(inner, text=f"● {status_text}", font=(A.FONT, 8),
             fg=color, bg=A.BG_CARD).grid(row=2, column=1, sticky="w")

    if common_count:
        tk.Label(inner, text=f"Ortak grup: {common_count}", font=(A.FONT, 7),
                 fg=A.FG_DIM, bg=A.BG_CARD).grid(row=3, column=0, columnspan=2,
                                                 sticky="w", pady=(4, 0))

    pop.geometry(f"+{x_root + 10}+{y_root + 10}")
    return pop
