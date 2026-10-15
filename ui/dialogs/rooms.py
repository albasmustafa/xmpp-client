"""Oda ile ilgili basit dialoglar (Faz 4A).

- ask_invite: davet edilecek JID + sebep sor (iki ardışık giriş).
- show_common_groups: kişiyle ortak grupları listele (salt görünüm).

MainWindow state'i parametreyle gelir; XMPPBot çağrısı yapılmaz.
Tema sembolleri çağrı anında `xmpp`'den okunur (canlı tema, döngü yok).
"""
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from ui.dialogs.simple import _app
from ui.timers import after_alive
from xmppcore.format import _bookmark_add
from xmppcore.helpers import _room_address


def ask_invite(parent, room):
    """Davet JID'i ve sebebini sor.

    Dönüş: (jid, reason) veya kullanıcı ilk adımı iptal ederse None.
    Orijinal davranış: sebep sorusu iptal edilirse reason "" olur.
    """
    jid = simpledialog.askstring(
        "Davet Gönder", f"{room} odasına davet edilecek JID:",
        parent=parent)
    if not jid:
        return None
    reason = simpledialog.askstring(
        "Davet Gönder", "Sebep (opsiyonel):", parent=parent) or ""
    return jid, reason


def show_common_groups(parent, name, jid, rooms, room_members):
    """Kişiyle ortak grupları listeleyen pencere (MainWindow._common_groups_dialog)."""
    A = _app()
    dlg = tk.Toplevel(parent)
    dlg.title("Ortak Gruplar")
    dlg.configure(bg=A.BG_CARD)
    dlg.geometry("340x300")
    dlg.transient(parent)

    tk.Label(dlg, text=f"🏠 {name} ile Ortak Gruplar", font=(A.FONT, 11, "bold"),
             fg=A.FG, bg=A.BG_CARD).pack(padx=16, pady=(16, 8))

    lb = tk.Listbox(dlg, bg=A.BG_PANEL, fg=A.FG, selectbackground=A.SEL_BG,
                    font=(A.FONT, 9), relief="flat", highlightthickness=0)
    lb.pack(fill="both", expand=True, padx=16, pady=8)

    bare = jid.split("@")[0]
    found = 0
    for room in rooms:
        members = room_members.get(room, {})
        for nick, info in members.items():
            if bare in nick.lower() or bare in str(info).lower():
                lb.insert("end", f"  🏠 {room.split('@')[0]}")
                found += 1
                break

    if found == 0:
        lb.insert("end", "  Ortak grup bulunamadı")

    ttk.Button(dlg, text="Kapat", command=dlg.destroy).pack(pady=8)


def show_join_room(parent, default_conf, default_nick, on_discover, on_join):
    """Odaya Katıl penceresi (MainWindow._join_room_dialog).

    - `on_discover(conf_server)`: oda keşfi isteği (network owner'da).
    - `on_join(room_jid, nick)`: katılma isteği (my_nick/join owner'da).
    Modal: `wait_window` ile eski davranış korunur.
    """
    A = _app()
    dlg = tk.Toplevel(parent)
    dlg.title("Odaya Katıl")
    dlg.configure(bg=A.SHADOW)
    dlg.resizable(False, False)
    dlg.transient(parent)
    A._safe_grab_set(dlg)

    shadow = tk.Frame(dlg, bg=A.SHADOW, padx=3, pady=3)
    shadow.pack(padx=20, pady=20)
    card = tk.Frame(shadow, bg=A.BG_CARD, padx=32, pady=28)
    card.pack()

    tk.Label(card, text="Odaya Katıl",
             font=(A.FONT, 14, "bold"),
             fg=A.FG, bg=A.BG_CARD).pack(anchor="w")
    tk.Label(card, text="Bir konferans sunucusu keşfedin veya doğrudan katılın",
             font=(A.FONT, 8), fg=A.FG_DIM,
             bg=A.BG_CARD).pack(anchor="w", pady=(2, 16))

    conf_var = tk.StringVar(value=default_conf)
    room_var = tk.StringVar()
    nick_var = tk.StringVar(value=default_nick)

    # -- Konferans sunucusu
    tk.Label(card, text="🌐  KONFERANS SUNUCUSU", fg=A.FG_DIM, bg=A.BG_CARD,
             font=(A.FONT, 7, "bold")).pack(anchor="w")
    cb = tk.Frame(card, bg=A.BORDER, padx=1, pady=1)
    cb.pack(fill="x", pady=(4, 0))
    conf_e = ttk.Entry(cb, textvariable=conf_var, font=(A.FONT, 10),
                       width=34, style="Modern.TEntry")
    conf_e.pack(fill="x", ipady=7, padx=2, pady=2)

    def _discover():
        srv = conf_var.get().strip()
        if srv:
            on_discover(srv)
            dlg.destroy()

    ttk.Button(card, text="Odaları Keşfet", style="Ghost.TButton",
               command=_discover).pack(anchor="w", pady=(8, 10), ipadx=4)

    tk.Frame(card, bg=A.BORDER, height=1).pack(fill="x", pady=6)

    # -- Doğrudan katılma
    tk.Label(card, text="🚪  ODA JID (doğrudan katıl)", fg=A.FG_DIM,
             bg=A.BG_CARD, font=(A.FONT, 7, "bold")).pack(anchor="w", pady=(6, 0))
    rb = tk.Frame(card, bg=A.BORDER, padx=1, pady=1)
    rb.pack(fill="x", pady=(4, 0))
    room_e = A.PlaceholderEntry(rb, placeholder="oda@conference.sunucu.tld",
                                textvariable=room_var, font=(A.FONT, 10),
                                width=34, style="Modern.TEntry")
    room_e.pack(fill="x", ipady=7, padx=2, pady=2)

    tk.Label(card, text="👤  TAKMA AD", fg=A.FG_DIM, bg=A.BG_CARD,
             font=(A.FONT, 7, "bold")).pack(anchor="w", pady=(10, 0))
    nb = tk.Frame(card, bg=A.BORDER, padx=1, pady=1)
    nb.pack(fill="x", pady=(4, 0))
    ttk.Entry(nb, textvariable=nick_var, font=(A.FONT, 10),
              width=34, style="Modern.TEntry").pack(
        fill="x", ipady=7, padx=2, pady=2)

    def _ok(_=None):
        room = room_var.get().strip() if not room_e._showing_ph else ""
        nick = nick_var.get().strip() or default_nick
        if not room:
            return
        if "@" not in room and conf_var.get().strip():
            # Yalnız oda adı yazıldı: yukarıdaki konferans sunucusunu kullan
            room = f"{room}@{conf_var.get().strip()}"
        dlg.destroy()
        on_join(room, nick)

    ttk.Button(card, text="Katıl",
               command=_ok).pack(pady=(16, 0), fill="x", ipady=5)
    dlg.bind("<Return>", _ok)
    dlg.lift()
    after_alive(dlg, 50, room_e.focus_force)
    parent.wait_window(dlg)


def show_create_room(parent, default_conf, default_nick, on_create):
    """Oda Oluştur penceresi (MainWindow._create_room_dialog).

    `on_create(room_jid, nick, kind, name)`: oda JID'i UI'da yazılan addan
    üretilir ("Şifreli Oda" → sifreli-oda@sunucu, `name` başlık olur; '@'
    içeren girdi tam adrestir). `kind` "normal" ya da "encrypted"; gerçek
    join/config owner'da yapılır. Kullanılamaz ad pencereyi kapatmaz.
    """
    A = _app()
    dlg = tk.Toplevel(parent)
    dlg.title("Oda Oluştur")
    dlg.configure(bg=A.SHADOW)
    dlg.resizable(False, False)
    dlg.transient(parent)
    A._safe_grab_set(dlg)

    shadow = tk.Frame(dlg, bg=A.SHADOW, padx=3, pady=3)
    shadow.pack(padx=20, pady=20)
    card = tk.Frame(shadow, bg=A.BG_CARD, padx=32, pady=28)
    card.pack()

    tk.Label(card, text="Oda Oluştur",
             font=(A.FONT, 14, "bold"),
             fg=A.FG, bg=A.BG_CARD).pack(anchor="w")
    tk.Label(card, text="Yeni bir sohbet odası oluşturun",
             font=(A.FONT, 8), fg=A.FG_DIM,
             bg=A.BG_CARD).pack(anchor="w", pady=(2, 16))

    conf_server = default_conf
    room_name_var = tk.StringVar()
    nick_var = tk.StringVar(value=default_nick)

    tk.Label(card, text="🏠  ODA ADI", fg=A.FG_DIM, bg=A.BG_CARD,
             font=(A.FONT, 7, "bold")).pack(anchor="w")
    rb = tk.Frame(card, bg=A.BORDER, padx=1, pady=1)
    rb.pack(fill="x", pady=(4, 0))
    room_entry = A.PlaceholderEntry(rb, placeholder="yeni-oda",
                                    textvariable=room_name_var,
                                    font=(A.FONT, 10), width=34,
                                    style="Modern.TEntry")
    room_entry.pack(fill="x", ipady=7, padx=2, pady=2)

    addr_lbl = tk.Label(card, text=f"Adres: …@{conf_server}", fg=A.FG_DIM,
                        bg=A.BG_CARD, font=(A.FONT, 7), wraplength=340,
                        justify="left")
    addr_lbl.pack(anchor="w", pady=(2, 0))

    def _name():
        return "" if room_entry._showing_ph else room_name_var.get().strip()

    def _preview(*_):
        try:
            jid, _title = _room_address(_name(), conf_server)
            addr_lbl.config(text=f"Adres: {jid}", fg=A.FG_DIM)
        except ValueError as e:
            addr_lbl.config(text=f"Adres: …@{conf_server}" if not _name()
                            else f"⚠ {e}", fg=A.FG_DIM if not _name() else A.RED)

    room_name_var.trace_add("write", _preview)

    tk.Label(card, text="👤  TAKMA AD", fg=A.FG_DIM, bg=A.BG_CARD,
             font=(A.FONT, 7, "bold")).pack(anchor="w", pady=(10, 0))
    nb = tk.Frame(card, bg=A.BORDER, padx=1, pady=1)
    nb.pack(fill="x", pady=(4, 0))
    ttk.Entry(nb, textvariable=nick_var, font=(A.FONT, 10),
              width=34, style="Modern.TEntry").pack(
        fill="x", ipady=7, padx=2, pady=2)

    # Oda türü: şifreli (OMEMO) oda yalnız davetlilere açık ve anonim değildir
    tk.Label(card, text="🛡  ODA TÜRÜ", fg=A.FG_DIM, bg=A.BG_CARD,
             font=(A.FONT, 7, "bold")).pack(anchor="w", pady=(10, 2))
    kind_var = tk.StringVar(value="normal")
    kinds = [
        ("normal", "🌐  Normal oda",
         "Adresi bilen herkes katılabilir, mesajlar şifresizdir."),
        ("encrypted", "🔒  Şifreli oda (OMEMO)",
         "Yalnız davet ettikleriniz katılır, mesajlar uçtan uca şifrelenir."
         if A.HAS_OMEMO else "OMEMO kütüphanesi (slixmpp-omemo) yüklü değil."),
    ]
    for value, label, hint in kinds:
        tk.Radiobutton(card, text=label, variable=kind_var, value=value,
                       state="normal" if value == "normal" or A.HAS_OMEMO
                       else "disabled",
                       bg=A.BG_CARD, fg=A.FG, selectcolor=A.BG_HOVER,
                       activebackground=A.BG_CARD, activeforeground=A.FG,
                       font=(A.FONT, 9)).pack(anchor="w")
        tk.Label(card, text=hint, fg=A.FG_DIM, bg=A.BG_CARD,
                 font=(A.FONT, 7)).pack(anchor="w", padx=(24, 0))

    def _create(_=None):
        name = _name()
        nick = nick_var.get().strip() or default_nick
        if not name:
            return
        try:
            room_jid, title = _room_address(name, conf_server)
        except ValueError:
            _preview()   # neden adres satırında; pencere açık kalır
            return
        dlg.destroy()
        on_create(room_jid, nick, kind_var.get(), title)

    ttk.Button(card, text="Oluştur ve Katıl",
               command=_create).pack(pady=(16, 0), fill="x", ipady=5)
    dlg.bind("<Return>", _create)
    dlg.lift()
    after_alive(dlg, 50, room_entry.focus_force)
    parent.wait_window(dlg)


def show_bookmarks(parent, jid, active, rooms, my_nick, bookmarks,
                   on_join, on_save):
    """Yer imleri penceresi (MainWindow._show_bookmarks).

    - `bookmarks`: MainWindow'un sahip olduğu liste (yerinde düzenlenir;
      formatlama `xmppcore.format._bookmark_add` ile).
    - `on_join(room_jid, nick)`: katılma isteği (my_nick/join owner'da).
    - `on_save(bookmarks)`: kalıcı kaydetme isteği (XMPP serialization owner'da).
    """
    A = _app()
    dlg = tk.Toplevel(parent)
    dlg.title("Yer İmleri")
    dlg.configure(bg=A.BG_CARD)
    dlg.geometry("440x380")
    dlg.transient(parent)
    A._safe_grab_set(dlg)

    tk.Label(dlg, text="📑  Yer İmleri", font=(A.FONT, 12, "bold"),
             fg=A.FG, bg=A.BG_CARD).pack(padx=16, pady=(16, 8), anchor="w")

    lb = tk.Listbox(dlg, bg=A.BG_PANEL, fg=A.FG, selectbackground=A.SEL_BG,
                    selectforeground=A.SEL_FG, font=(A.FONT, 9), relief="flat",
                    highlightthickness=0)
    lb.pack(fill="both", expand=True, padx=16, pady=4)

    def _reload():
        lb.delete(0, "end")
        for bm in bookmarks:
            name = bm.get("name", "") or bm["jid"]
            auto = " ⟳" if bm.get("autojoin") else ""
            lb.insert("end", f"  {name}{auto}  —  {bm['jid']}")

    _reload()

    btn_f = tk.Frame(dlg, bg=A.BG_CARD)
    btn_f.pack(fill="x", padx=16, pady=(4, 16))

    def _join_selected():
        sel = lb.curselection()
        if sel and sel[0] < len(bookmarks):
            bm = bookmarks[sel[0]]
            nick = bm.get("nick") or jid.split("@")[0]
            on_join(bm["jid"], nick)
            dlg.destroy()

    def _add_current():
        if active and active in rooms:
            nick = my_nick.get(active, jid.split("@")[0])
            _bookmark_add(bookmarks, active,
                          name=active.split("@")[0],
                          nick=nick, autojoin=True)
            on_save(bookmarks)
            _reload()

    def _delete_selected():
        sel = lb.curselection()
        if sel and sel[0] < len(bookmarks):
            del bookmarks[sel[0]]
            on_save(bookmarks)
            _reload()

    ttk.Button(btn_f, text="Katıl",
               command=_join_selected).pack(side="left", padx=4)
    ttk.Button(btn_f, text="Mevcut Odayı Ekle", style="Ghost.TButton",
               command=_add_current).pack(side="left", padx=4)
    ttk.Button(btn_f, text="🗑 Sil", style="Danger.TButton",
               command=_delete_selected).pack(side="left", padx=4)
    ttk.Button(btn_f, text="Kapat",
               command=dlg.destroy).pack(side="right", padx=4)


def show_room_config(parent, room, form, on_submit):
    """XEP-0004 Data Form'unu basit Tk diyaloğu olarak göster (Faz 4B-3E).

    UI yalnız render + kullanıcı değerlerini form alanlarına yazma yapar;
    `form['type']='submit'` ve `bot.set_room_config` çağrısı `on_submit(form)`
    ile owner'da yapılır. Field semantiği (boolean/list-single/list-multi/
    text-multi/text-private/hidden/fixed) birebir korunur.
    """
    A = _app()
    win = tk.Toplevel(parent)
    win.title(f"Oda Ayarları — {room}")
    win.configure(bg=A.BG_PANEL)
    win.geometry("520x560")
    win.transient(parent)
    A._safe_grab_set(win)

    # Başlık
    tk.Label(win, text=f"⚙  {room}", font=(A.FONT, 11, "bold"),
             fg=A.FG, bg=A.BG_PANEL).pack(padx=16, pady=(16, 8), anchor="w")

    # Scrollable alan
    canvas = tk.Canvas(win, bg=A.BG_PANEL, highlightthickness=0)
    scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
    scroll_frame = tk.Frame(canvas, bg=A.BG_PANEL)

    scroll_frame.bind("<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True, padx=(16, 0), pady=8)
    scrollbar.pack(side="right", fill="y", padx=(0, 4), pady=8)

    # Linux scroll
    canvas.bind("<Enter>",
        lambda _: (canvas.bind_all("<Button-4>",
            lambda _: canvas.yview_scroll(-3, "units")),
            canvas.bind_all("<Button-5>",
            lambda _: canvas.yview_scroll(3, "units"))))
    canvas.bind("<Leave>",
        lambda _: (canvas.unbind_all("<Button-4>"),
            canvas.unbind_all("<Button-5>")))

    # form.get_fields() → {var_name: FormField}
    fields = form.get_fields()
    field_vars = {}  # var_name → (type_tag, widget/var, [opt_vals])

    for var_name, field in fields.items():
        ftype = field['type'] or "text-single"
        label = field['label'] or var_name
        value = field['value']

        if ftype == "hidden" or ftype == "fixed" or not var_name:
            continue

        row = tk.Frame(scroll_frame, bg=A.BG_PANEL)
        row.pack(fill="x", padx=4, pady=3)
        tk.Label(row, text=label, font=(A.FONT, 9),
                 fg=A.FG, bg=A.BG_PANEL, wraplength=460,
                 justify="left").pack(anchor="w")

        if ftype == "boolean":
            bv = tk.BooleanVar(value=bool(value) if isinstance(value, bool)
                               else str(value).lower() in ("true", "1", "yes"))
            cb = tk.Checkbutton(row, variable=bv,
                bg=A.BG_PANEL, fg=A.FG, selectcolor=A.BG_CARD,
                activebackground=A.BG_PANEL, activeforeground=A.FG)
            cb.pack(anchor="w")
            field_vars[var_name] = ("boolean", bv)

        elif ftype == "list-single":
            options = field.get_options()  # [{'label': ..., 'value': ...}]
            if options:
                opt_labels = {o["value"]: o.get("label", o["value"]) for o in options}
                opt_values = list(opt_labels.keys())
                combo = ttk.Combobox(row,
                    values=[opt_labels.get(v, v) for v in opt_values],
                    state="readonly", width=40)
                cur = str(value) if value else ""
                if cur in opt_values:
                    combo.current(opt_values.index(cur))
                elif opt_values:
                    combo.current(0)
                combo.pack(anchor="w", pady=2)
                field_vars[var_name] = ("list-single", combo, opt_values)
            else:
                sv = tk.StringVar(value=str(value) if value else "")
                ent = tk.Entry(row, textvariable=sv, bg=A.BG_CARD, fg=A.FG,
                               insertbackground=A.FG, width=45, relief="flat")
                ent.pack(anchor="w", pady=2)
                field_vars[var_name] = ("text-single", sv)

        elif ftype == "list-multi":
            options = field.get_options()
            vals = value if isinstance(value, (list, tuple)) else [value] if value else []
            lb_frame = tk.Frame(row, bg=A.BG_CARD)
            lb = tk.Listbox(lb_frame, bg=A.BG_CARD, fg=A.FG, selectmode="multiple",
                            height=min(max(len(options), 1), 5), relief="flat",
                            font=(A.FONT, 9), highlightthickness=0,
                            selectbackground=A.ACCENT2, selectforeground=A.FG_ME)
            opt_vals = []
            for i, o in enumerate(options):
                ov = o["value"]
                ol = o.get("label", ov)
                lb.insert("end", ol)
                opt_vals.append(ov)
                if ov in vals:
                    lb.selection_set(i)
            lb.pack(fill="x")
            lb_frame.pack(fill="x", pady=2)
            field_vars[var_name] = ("list-multi", lb, opt_vals)

        elif ftype == "text-multi":
            tv = tk.Text(row, bg=A.BG_CARD, fg=A.FG, insertbackground=A.FG,
                         height=3, width=45, relief="flat", font=(A.FONT, 9))
            if value:
                txt = "\n".join(value) if isinstance(value, (list, tuple)) else str(value)
                tv.insert("1.0", txt)
            tv.pack(anchor="w", pady=2)
            field_vars[var_name] = ("text-multi", tv)

        else:  # text-single, jid-single, text-private, etc.
            sv = tk.StringVar(value=str(value) if value else "")
            ent = tk.Entry(row, textvariable=sv, bg=A.BG_CARD, fg=A.FG,
                           insertbackground=A.FG, width=45, relief="flat",
                           show="*" if ftype == "text-private" else "")
            ent.pack(anchor="w", pady=2)
            field_vars[var_name] = ("text-single", sv)

    # Butonlar
    btn_frame = tk.Frame(win, bg=A.BG_PANEL)
    btn_frame.pack(fill="x", padx=16, pady=(8, 16))

    def _save():
        for var_name, entry in field_vars.items():
            field = fields[var_name]
            if entry[0] == "boolean":
                field['value'] = entry[1].get()
            elif entry[0] == "list-single":
                combo = entry[1]
                opt_vals = entry[2]
                idx = combo.current()
                field['value'] = opt_vals[idx] if 0 <= idx < len(opt_vals) else ""
            elif entry[0] == "list-multi":
                lb = entry[1]
                opt_vals = entry[2]
                sel = lb.curselection()
                field['value'] = [opt_vals[i] for i in sel]
            elif entry[0] == "text-multi":
                field['value'] = entry[1].get("1.0", "end-1c")
            else:
                field['value'] = entry[1].get()
        on_submit(form)
        win.destroy()

    ttk.Button(btn_frame, text="Kaydet", command=_save).pack(side="right", padx=4)
    ttk.Button(btn_frame, text="İptal", command=win.destroy).pack(side="right", padx=4)


def show_room_admin(parent, room, members, subject, contacts,
                    on_set_subject, on_invite):
    """Oda Yönetimi penceresi (MainWindow._room_admin_dialog).

    - `members`: {nick: {"role","affil"}} salt-görünüm (owner'da).
    - `on_set_subject(new_subject) -> bool`: uygulandıysa True (UI kapanır).
    - `on_invite(jid) -> bool`: davet gönderildiyse True (bilgi kutusu).
    """
    A = _app()
    dlg = tk.Toplevel(parent)
    dlg.title(f"Oda Yönetimi — {room.split('@')[0]}")
    dlg.configure(bg=A.BG_CARD)
    dlg.geometry("460x440")
    dlg.transient(parent)
    A._safe_grab_set(dlg)

    nb = ttk.Notebook(dlg)
    nb.pack(fill="both", expand=True, padx=12, pady=12)

    # Üyeler sekmesi
    t_members = tk.Frame(nb, bg=A.BG_CARD, padx=16, pady=12)
    nb.add(t_members, text="  Üyeler  ")

    for nick, info in sorted(members.items()):
        mf = tk.Frame(t_members, bg=A.BG_HOVER, padx=10, pady=4)
        mf.pack(fill="x", pady=1)
        role = info.get("role", "participant")
        affil = info.get("affil", "none")
        role_icon = {"moderator": "👑", "participant": "👤",
                     "visitor": "👁"}.get(role, "👤")
        tk.Label(mf, text=f"{role_icon} {nick}", font=(A.FONT, 9),
                 fg=A.FG, bg=A.BG_HOVER).pack(side="left")
        tk.Label(mf, text=f"{affil}/{role}", font=(A.FONT, 7),
                 fg=A.FG_DIM, bg=A.BG_HOVER).pack(side="right")

    # Ayarlar sekmesi
    t_settings = tk.Frame(nb, bg=A.BG_CARD, padx=16, pady=12)
    nb.add(t_settings, text="  Ayarlar  ")

    tk.Label(t_settings, text="Oda Konusu:", font=(A.FONT, 9),
             fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w")
    subj_var = tk.StringVar(value=subject)
    ttk.Entry(t_settings, textvariable=subj_var,
              font=(A.FONT, 10)).pack(fill="x", ipady=4, pady=(0, 8))

    def _set_subject():
        new_subj = subj_var.get().strip()
        if on_set_subject(new_subj):
            dlg.destroy()

    ttk.Button(t_settings, text="Konuyu Güncelle",
               command=_set_subject).pack(anchor="w", pady=8)

    # Davet sekmesi
    t_invite = tk.Frame(nb, bg=A.BG_CARD, padx=16, pady=12)
    nb.add(t_invite, text="  Davet  ")

    tk.Label(t_invite, text="Davet edilecek JID:", font=(A.FONT, 9),
             fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w")
    inv_var = tk.StringVar()
    ttk.Entry(t_invite, textvariable=inv_var,
              font=(A.FONT, 10)).pack(fill="x", ipady=4, pady=(0, 4))

    # Kişi listesi
    inv_lb = tk.Listbox(t_invite, bg=A.BG_PANEL, fg=A.FG,
                        selectbackground=A.SEL_BG, font=(A.FONT, 9),
                        relief="flat", highlightthickness=0, height=8)
    inv_lb.pack(fill="both", expand=True, pady=4)
    inv_jids = sorted(contacts.keys())
    for j in inv_jids:
        inv_lb.insert("end", f"  {contacts[j] or j}")

    def _invite():
        jid = inv_var.get().strip()
        if not jid:
            sel = inv_lb.curselection()
            if sel:
                jid = inv_jids[sel[0]]
        if jid and on_invite(jid):
            messagebox.showinfo("Davet", f"{jid} davet edildi", parent=dlg)

    ttk.Button(t_invite, text="📨 Davet Gönder",
               command=_invite).pack(fill="x", ipady=4, pady=8)


_SORT_LABELS = {
    "name_asc":  "İsim A→Z",
    "name_desc": "İsim Z→A",
    "jid_asc":   "Adres A→Z",
    "jid_desc":  "Adres Z→A",
}


def filter_and_sort_rooms(rooms, query, sort_key):
    """Keşfedilen odaları sorguya göre süz ve sırala (Faz 4B-3F).

    Mevcut `_apply_filter` semantiği birebir: isim veya JID'de arama;
    sıralama isim/adres, artan/azalan.
    """
    if query:
        matched = [(j, n) for j, n in rooms
                   if query in (n or "").lower() or query in j.lower()]
    else:
        matched = list(rooms)
    if sort_key == "name_asc":
        matched.sort(key=lambda x: (x[1] or x[0]).lower())
    elif sort_key == "name_desc":
        matched.sort(key=lambda x: (x[1] or x[0]).lower(), reverse=True)
    elif sort_key == "jid_asc":
        matched.sort(key=lambda x: x[0].lower())
    elif sort_key == "jid_desc":
        matched.sort(key=lambda x: x[0].lower(), reverse=True)
    return matched


def show_rooms_browser(parent, default_nick, rooms, on_join):
    """Keşfedilen Odalar penceresi (MainWindow._show_rooms_browser).

    `rooms`: hazır `(jid, name)` listesi (discovery owner'da);
    `on_join(room_jid, nick)`: katılma isteği (my_nick/join owner'da).
    Modal: `wait_window` (eski davranış).
    """
    A = _app()
    dlg = tk.Toplevel(parent)
    dlg.title("Keşfedilen Odalar")
    dlg.configure(bg=A.SHADOW)
    dlg.geometry("660x560")
    dlg.minsize(520, 440)
    dlg.transient(parent)
    A._safe_grab_set(dlg)
    dlg.resizable(True, True)

    shadow = tk.Frame(dlg, bg=A.SHADOW, padx=3, pady=3)
    shadow.pack(fill="both", expand=True, padx=16, pady=16)
    card = tk.Frame(shadow, bg=A.BG_CARD, padx=22, pady=20)
    card.pack(fill="both", expand=True)
    card.columnconfigure(0, weight=1)
    card.rowconfigure(2, weight=1)

    # -- Başlık
    hdr = tk.Frame(card, bg=A.BG_CARD)
    hdr.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
    tk.Label(hdr, text="Keşfedilen Odalar",
             font=(A.FONT, 14, "bold"),
             fg=A.FG, bg=A.BG_CARD).pack(side="left")
    count_lbl = tk.Label(hdr, text=f"{len(rooms)} oda",
                         font=(A.FONT, 8), fg=A.FG_DIM, bg=A.BG_CARD)
    count_lbl.pack(side="right")

    # -- Arama ve sıralama çubuğu
    toolbar = tk.Frame(card, bg=A.BG_CARD)
    toolbar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
    toolbar.columnconfigure(0, weight=1)

    filter_var = tk.StringVar()
    fb = tk.Frame(toolbar, bg=A.BORDER, padx=1, pady=1)
    fb.grid(row=0, column=0, sticky="ew")
    filter_entry = A.PlaceholderEntry(
        fb, placeholder="Oda ara (isim veya adres)...",
        textvariable=filter_var,
        font=(A.FONT, 9), style="Modern.TEntry")
    filter_entry.pack(fill="x", ipady=5, padx=2, pady=2)

    sort_var = tk.StringVar(value="name_asc")
    sort_menu = ttk.OptionMenu(toolbar, sort_var, "name_asc",
                               "name_asc", "name_desc",
                               "jid_asc", "jid_desc",
                               command=lambda _: _apply_filter())
    sort_menu.grid(row=0, column=1, padx=(8, 0))

    sort_menu["menu"].delete(0, "end")
    for key, label in _SORT_LABELS.items():
        sort_menu["menu"].add_command(
            label=label,
            command=lambda v=key: (sort_var.set(v), _apply_filter()))

    # -- Oda listesi
    lb = tk.Listbox(card, bg=A.BG_HOVER, fg=A.FG,
                    selectbackground=A.SEL_BG, selectforeground=A.SEL_FG,
                    activestyle="none", relief="flat", bd=0,
                    font=(A.FONT, 9), highlightthickness=0)
    lb.grid(row=2, column=0, sticky="nsew")
    vsb = ttk.Scrollbar(card, command=lb.yview)
    vsb.grid(row=2, column=1, sticky="ns")
    lb.config(yscrollcommand=vsb.set)

    # Filtrelenen oda JID'lerini tutan liste
    filtered_jids: list[str] = []

    def _apply_filter(_=None):
        """Arama ve sıralama uygula."""
        query = filter_var.get().strip().lower() \
            if not filter_entry._showing_ph else ""
        sort_key = sort_var.get()
        matched = filter_and_sort_rooms(rooms, query, sort_key)

        # Listeye yaz
        lb.delete(0, "end")
        filtered_jids.clear()
        for jid, name in matched:
            display = name or jid
            lb.insert("end", f"  {display}  ({jid})")
            filtered_jids.append(jid)

        if not matched:
            lb.insert("end", "  (Eşleşen oda bulunamadı)")

        count_lbl.config(text=f"{len(matched)}/{len(rooms)} oda")

    filter_var.trace_add("write", lambda *_: _apply_filter())

    # İlk yükleme
    _apply_filter()

    # -- Takma ad
    nick_var = tk.StringVar(value=default_nick)
    inf = tk.Frame(card, bg=A.BG_CARD)
    inf.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(12, 0))
    inf.columnconfigure(1, weight=1)
    tk.Label(inf, text="👤  TAKMA AD", fg=A.FG_DIM, bg=A.BG_CARD,
             font=(A.FONT, 7, "bold")).grid(row=0, column=0, padx=(0, 8))
    nb = tk.Frame(inf, bg=A.BORDER, padx=1, pady=1)
    nb.grid(row=0, column=1, sticky="ew")
    ttk.Entry(nb, textvariable=nick_var,
              font=(A.FONT, 9), style="Modern.TEntry").pack(
        fill="x", ipady=6, padx=2, pady=2)

    def _join(_=None):
        sel = lb.curselection()
        if not sel or not filtered_jids:
            return
        idx = sel[0]
        if idx >= len(filtered_jids):
            return
        room = filtered_jids[idx]
        nick = nick_var.get().strip() or default_nick
        dlg.destroy()
        on_join(room, nick)

    ttk.Button(card, text="Seçilen Odaya Katıl", command=_join).grid(
        row=4, column=0, columnspan=2, pady=(12, 0), sticky="ew", ipady=5)
    lb.bind("<Double-Button-1>", _join)

    dlg.lift()
    after_alive(dlg, 50, lambda: filter_entry.focus_force())
    parent.wait_window(dlg)


def show_room_search(parent, default_nick, own_domain, known_servers,
                     on_search, on_join, on_add_bookmark, on_discover, *,
                     own_conf=None):
    """Oda Keşfet penceresi (MainWindow._search_rooms_dialog) — UI kabuğu.

    Çalışan HTTP worker/network MainWindow'da kalır:
      `on_search(query, on_results, on_error)` — worker sonucu `_safe_after`
      ile GUI thread'inde `on_results(items)`/`on_error(err)` çağırır.
      `on_join(room, nick)`, `on_discover(server)`,
      `on_add_bookmark(room, name, nick, set_saved)`.
    `own_conf`: kendi oda sunucumuz (XEP-0030 ile keşfedilen); verilmezse
    `conference.<own_domain>` tahmini kullanılır.
    Modal: `wait_window` (eski davranış). `_alive` yalnız GUI thread'inde
    okunur/yazılır; geç sonuçlar no-op'a düşer.
    """
    A = _app()
    _t = A._t

    dlg = tk.Toplevel(parent)
    dlg.title("Oda Keşfet")
    dlg.configure(bg=A.SHADOW)
    dlg.geometry("660x600")
    dlg.minsize(520, 440)
    dlg.transient(parent)
    A._safe_grab_set(dlg)
    dlg.resizable(True, True)

    _alive = [True]

    def _on_close():
        _alive[0] = False
        dlg.destroy()
    dlg.protocol("WM_DELETE_WINDOW", _on_close)

    shadow = tk.Frame(dlg, bg=A.SHADOW, padx=3, pady=3)
    shadow.pack(fill="both", expand=True, padx=14, pady=14)
    outer = tk.Frame(shadow, bg=A.BG_CARD)
    outer.pack(fill="both", expand=True)

    nb = ttk.Notebook(outer)
    nb.pack(fill="both", expand=True, padx=12, pady=12)

    lbox_kw = dict(bg=A.BG_HOVER, fg=A.FG,
                   selectbackground=A.SEL_BG, selectforeground=A.SEL_FG,
                   activestyle="none", relief="flat", bd=0,
                   font=(A.FONT, 9), highlightthickness=0)

    def _nick_row(parent_f, row):
        inf = tk.Frame(parent_f, bg=A.BG_CARD)
        inf.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        inf.columnconfigure(1, weight=1)
        tk.Label(inf, text="👤  TAKMA AD", fg=A.FG_DIM, bg=A.BG_CARD,
                 font=(A.FONT, 7, "bold")).grid(row=0, column=0, padx=(0, 8))
        nv = tk.StringVar(value=default_nick)
        nb_ = tk.Frame(inf, bg=A.BORDER, padx=1, pady=1)
        nb_.grid(row=0, column=1, sticky="ew")
        ttk.Entry(nb_, textvariable=nv,
                  font=(A.FONT, 9), style="Modern.TEntry").pack(
            fill="x", ipady=6, padx=2, pady=2)
        return nv

    # ── Sekme 1: search.jabber.network ────────────────────────────────────
    t1 = tk.Frame(nb, bg=A.BG_CARD, padx=16, pady=14)
    t1.columnconfigure(0, weight=1)
    t1.rowconfigure(2, weight=1)
    nb.add(t1, text="  Genel Ara  ")

    # Arama satırı
    sf = tk.Frame(t1, bg=A.BG_CARD)
    sf.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
    sf.columnconfigure(0, weight=1)
    query_var = tk.StringVar()
    sb = tk.Frame(sf, bg=A.BORDER, padx=1, pady=1)
    sb.grid(row=0, column=0, sticky="ew")
    search_entry = A.PlaceholderEntry(sb, placeholder="Oda adı veya konu ara...",
                                      textvariable=query_var,
                                      font=(A.FONT, 10), style="Modern.TEntry")
    search_entry.pack(fill="x", ipady=6, padx=2, pady=2)
    status_lbl = tk.Label(sf, text="", fg=A.FG_DIM, bg=A.BG_CARD,
                          font=(A.FONT, 8), width=16, anchor="w")
    status_lbl.grid(row=0, column=2, padx=(8, 0))

    # Sonuç listesi
    res_lb = tk.Listbox(t1, **lbox_kw)
    res_lb.grid(row=2, column=0, columnspan=2, sticky="nsew")
    vsb1 = ttk.Scrollbar(t1, command=res_lb.yview)
    vsb1.grid(row=2, column=2, sticky="ns")
    res_lb.config(yscrollcommand=vsb1.set)

    res_items: list[dict] = []

    details_lbl = tk.Label(t1, text="", fg=A.FG_DIM, bg=A.BG_CARD,
                           font=(A.FONT, 8), anchor="w", justify="left",
                           wraplength=580)
    details_lbl.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(6, 0))

    def _selected_item():
        sel = res_lb.curselection()
        if sel and sel[0] < len(res_items):
            return res_items[sel[0]]
        return None

    def _refresh_details(_=None):
        item = _selected_item()
        details_lbl.config(text=A._room_result_details(item) if item else "")

    def _do_search(_=None):
        q = query_var.get().strip() if not search_entry._showing_ph else ""
        if not q:
            return
        status_lbl.config(text="Aranıyor…")
        res_lb.delete(0, "end")
        res_items.clear()
        details_lbl.config(text="")

        def _show_results(items):
            if not _alive[0]:
                return
            res_lb.delete(0, "end")
            res_items.clear()
            details_lbl.config(text="")
            if not items:
                res_lb.insert("end", "  (Sonuç bulunamadı)")
                status_lbl.config(text="")
                return
            for item in items:
                res_lb.insert("end", A._room_result_line(item))
                res_items.append(item)
            status_lbl.config(text=f"{len(items)} sonuç")

        def _show_error(err):
            if _alive[0]:
                status_lbl.config(text="")
                res_lb.delete(0, "end")
                res_lb.insert("end", f"  ⚠ {err}")

        on_search(q, _show_results, _show_error)

    ttk.Button(sf, text="Ara",
               command=_do_search).grid(row=0, column=1, padx=(6, 0), ipady=2)
    search_entry.bind("<Return>", _do_search)

    nick1 = _nick_row(t1, 1)

    def _join_search(_=None):
        item = _selected_item()
        if item is None:
            return
        room = item.get("address", "")
        if not room:
            return
        nick = nick1.get().strip() or default_nick
        _alive[0] = False
        dlg.destroy()
        on_join(room, nick)

    def _add_selected_bookmark():
        item = _selected_item()
        if item is None:
            return
        room = item.get("address", "")
        if not room:
            return
        nick = nick1.get().strip() or default_nick
        name = item.get("name") or room.split("@")[0]
        status_lbl.config(text="…")

        def _set_saved():
            if _alive[0]:
                status_lbl.config(text=_t("bookmark_added"))

        on_add_bookmark(room, name, nick, _set_saved)

    acts = tk.Frame(t1, bg=A.BG_CARD)
    acts.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(10, 0))
    acts.columnconfigure(0, weight=1)
    acts.columnconfigure(1, weight=1)
    ttk.Button(acts, text=_t("join_selected"),
               command=_join_search).grid(row=0, column=0, sticky="ew",
                                          ipady=5, padx=(0, 4))
    ttk.Button(acts, text=_t("add_bookmark"),
               command=_add_selected_bookmark).grid(row=0, column=1,
                                                    sticky="ew", ipady=5)
    res_lb.bind("<Double-Button-1>", _join_search)
    res_lb.bind("<<ListboxSelect>>", _refresh_details)

    # ── Sekme 2: Popüler sunuculardan keşfet ─────────────────────────────
    t2 = tk.Frame(nb, bg=A.BG_CARD, padx=16, pady=14)
    t2.columnconfigure(0, weight=1)
    t2.rowconfigure(1, weight=1)
    nb.add(t2, text="  Popüler Sunucular  ")

    tk.Label(t2, text="Bir sunucu seçip 'Keşfet' ile odaları listeleyin.",
             fg=A.FG_DIM, bg=A.BG_CARD,
             font=(A.FONT, 8)).grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

    srv_lb = tk.Listbox(t2, **lbox_kw)
    srv_lb.grid(row=1, column=0, sticky="nsew")
    vsb2 = ttk.Scrollbar(t2, command=srv_lb.yview)
    vsb2.grid(row=1, column=1, sticky="ns")
    srv_lb.config(yscrollcommand=vsb2.set)

    if not own_conf:
        own_conf = f"conference.{own_domain}" if own_domain else ""
    all_servers = []
    if own_conf:
        all_servers.append((own_conf, f"Sunucum ({own_domain})"))
    all_servers.extend(known_servers)

    for addr, label in all_servers:
        srv_lb.insert("end", f"  {label}   —   {addr}")
    if own_conf:
        srv_lb.selection_set(0)

    def _discover_selected(_=None):
        sel = srv_lb.curselection()
        if not sel:
            return
        server, _ = all_servers[sel[0]]
        _alive[0] = False
        dlg.destroy()
        on_discover(server)

    ttk.Button(t2, text=_t("discover_selected"),
               command=_discover_selected).grid(
        row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0), ipady=5)
    srv_lb.bind("<Double-Button-1>", _discover_selected)

    # ── Diğer sunucu (elle giriş) ────────────────────────────────────────
    tk.Label(t2, text=f"🌐  {_t('server_address')}", fg=A.FG_DIM,
             bg=A.BG_CARD, font=(A.FONT, 7, "bold")).grid(
        row=3, column=0, columnspan=2, sticky="w", pady=(14, 0))
    custom_var = tk.StringVar()
    cb = tk.Frame(t2, bg=A.BORDER, padx=1, pady=1)
    cb.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(4, 0))
    custom_entry = A.PlaceholderEntry(cb, placeholder="muc.sunucu.tld",
                                      textvariable=custom_var,
                                      font=(A.FONT, 10), style="Modern.TEntry")
    custom_entry.pack(fill="x", ipady=6, padx=2, pady=2)

    def _discover_custom(_=None):
        srv = (custom_var.get().strip()
               if not custom_entry._showing_ph else "")
        if not srv:
            return
        _alive[0] = False
        dlg.destroy()
        on_discover(srv)

    ttk.Button(t2, text="  Keşfet  ", command=_discover_custom).grid(
        row=5, column=0, columnspan=2, sticky="e", pady=(6, 0), ipady=3)
    custom_entry.bind("<Return>", _discover_custom)

    dlg.bind("<Escape>", lambda _: _on_close())
    dlg.lift()
    after_alive(dlg, 50, lambda: search_entry.focus_force())
    parent.wait_window(dlg)
