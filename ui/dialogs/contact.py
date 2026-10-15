"""Kişi/roster dialogları (Faz 4B-2B).

Kurallar:
- Domain/XMPP/DB çağrısı yok; kalıcı yazım `on_save` callback'i ile çağırana
  aittir (MainWindow._save_contact_groups).
- `groups` geçici çalışma kopyasıdır; orijinal davranışın aynısı olarak
  pencere X ile kapatılsa bile kaydedilir (cancel semantiği yok).
- Tema/yardımcı semboller çağrı anında `xmpp`'den okunur.
"""
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from ui.dialogs.simple import _app
from ui.timers import after_alive
from xmppcore.helpers import _normalize_user_jid


def show_contact_groups(parent, contacts, groups, on_save):
    """Kişi grupları yönetim penceresi (MainWindow._contact_groups_dialog).

    `contacts`: {jid: isim}; `groups`: {grup: [jid, ...]} (yerinde düzenlenir);
    `on_save(groups)` kaydet/`WM_DELETE_WINDOW` yolunda bir kez çağrılır.
    """
    A = _app()
    dlg = tk.Toplevel(parent)
    dlg.title("Kişi Grupları")
    dlg.configure(bg=A.BG_CARD)
    dlg.geometry("420x400")
    dlg.transient(parent)
    A._safe_grab_set(dlg)

    tk.Label(dlg, text="🏷 Kişi Grupları", font=(A.FONT, 12, "bold"),
             fg=A.FG, bg=A.BG_CARD).pack(padx=16, pady=(16, 8))

    list_f = tk.Frame(dlg, bg=A.BG_CARD)
    list_f.pack(fill="both", expand=True, padx=16)

    def _refresh():
        for w in list_f.winfo_children():
            w.destroy()
        for gname, members in groups.items():
            gf = tk.Frame(list_f, bg=A.BG_HOVER, padx=10, pady=6)
            gf.pack(fill="x", pady=2)
            tk.Label(gf, text=f"🏷 {gname} ({len(members)})",
                     font=(A.FONT, 9, "bold"), fg=A.FG, bg=A.BG_HOVER).pack(
                         side="left")
            rm = tk.Label(gf, text="✕", font=(A.FONT, 9), fg=A.RED,
                          bg=A.BG_HOVER, cursor="hand2")
            rm.pack(side="right")
            rm.bind("<Button-1>", lambda _, g=gname: (
                groups.pop(g, None), _refresh()))
            # Kişileri göster
            for jid in members:
                name = contacts.get(jid, jid)
                tk.Label(gf, text=f"  • {name}", font=(A.FONT, 7),
                         fg=A.FG_DIM, bg=A.BG_HOVER).pack(anchor="w")
        if not groups:
            tk.Label(list_f, text="Henüz grup yok",
                     font=(A.FONT, 8), fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w")

    _refresh()

    def _add_group():
        name = simpledialog.askstring("Grup Ekle", "Grup adı:", parent=dlg)
        if name and name.strip():
            groups[name.strip()] = []
            _refresh()

    def _add_to_group():
        if not groups:
            messagebox.showinfo("Bilgi", "Önce bir grup oluşturun", parent=dlg)
            return
        pop2 = tk.Toplevel(dlg)
        pop2.title("Gruba Ekle")
        pop2.configure(bg=A.BG_CARD)
        pop2.geometry("300x300")
        pop2.transient(dlg)

        tk.Label(pop2, text="Grup:", font=(A.FONT, 9),
                 fg=A.FG_DIM, bg=A.BG_CARD).pack(anchor="w", padx=12, pady=(12, 0))
        grp_var = tk.StringVar(value=list(groups.keys())[0])
        ttk.Combobox(pop2, textvariable=grp_var,
                     values=list(groups.keys()), state="readonly",
                     font=(A.FONT, 9)).pack(fill="x", padx=12, pady=(0, 8))

        lb = tk.Listbox(pop2, bg=A.BG_PANEL, fg=A.FG, selectbackground=A.SEL_BG,
                        font=(A.FONT, 9), selectmode="multiple",
                        relief="flat", highlightthickness=0)
        lb.pack(fill="both", expand=True, padx=12)
        jids_list = sorted(contacts.keys())
        for j in jids_list:
            lb.insert("end", f"  {contacts[j] or j}")

        def _do_add():
            sel = lb.curselection()
            g = grp_var.get()
            for i in sel:
                jid = jids_list[i]
                if jid not in groups.get(g, []):
                    groups.setdefault(g, []).append(jid)
            pop2.destroy()
            _refresh()

        ttk.Button(pop2, text="Ekle", command=_do_add).pack(
            fill="x", padx=12, ipady=4, pady=8)

    btn_f = tk.Frame(dlg, bg=A.BG_CARD, padx=16)
    btn_f.pack(fill="x", pady=8)
    ttk.Button(btn_f, text="+ Yeni Grup", command=_add_group).pack(
        side="left", padx=(0, 6))
    ttk.Button(btn_f, text="+ Kişi Ekle", command=_add_to_group).pack(
        side="left")

    def _save_groups():
        on_save(groups)
        dlg.destroy()

    ttk.Button(btn_f, text="Kaydet", command=_save_groups).pack(side="right")
    # Pencere X ile kapatılsa bile değişiklikler kaybolmasın
    dlg.protocol("WM_DELETE_WINDOW",
                 lambda: (on_save(groups), dlg.destroy()))


def validate_jid(raw):
    """JID yerel doğrulaması; geçerli JID bare ve küçük harfli döner.

    Dönüş: (jid, hata_mesajı). Geçersizse jid None, mesaj doludur.
    """
    try:
        return _normalize_user_jid(raw), ""
    except ValueError as e:
        return None, str(e)


def show_add_contact(parent, contacts, presence, default_server,
                     on_open_chat, on_subscribe, on_search, on_search_refs):
    """Yeni Sohbet / kişi ekle penceresi — 3 sekme (MainWindow._add_contact_dialog).

    - `on_open_chat(jid)`: sohbet başlat (kontakt/refresh/load owner'da).
    - `on_subscribe(jid)`: kişi olarak ekle (open + bot.add_contact owner'da).
    - `on_search(server, query)`: XEP-0055 arama isteği (network owner'da).
    - `on_search_refs(dlg, s_list, jids)`: arama sekmesi kurulur kurulmaz
      çağrılır; `_handle("search_results")` kontratı için referanslar.
    Modal: `wait_window` ile dialog kapanana kadar bekler (eski davranış).
    """
    A = _app()
    dlg = tk.Toplevel(parent)
    dlg.title("Yeni Sohbet")
    dlg.configure(bg=A.BG_CARD)
    dlg.geometry("420x460")
    dlg.resizable(False, True)
    dlg.transient(parent)
    A._safe_grab_set(dlg)

    tk.Label(dlg, text="Yeni Sohbet", font=(A.FONT, 14, "bold"),
             fg=A.FG, bg=A.BG_CARD).pack(anchor="w", padx=20, pady=(16, 0))

    nb = ttk.Notebook(dlg)
    nb.pack(fill="both", expand=True, padx=12, pady=8)

    # ── Sekme 1: JID Gir ──
    t1 = tk.Frame(nb, bg=A.BG_CARD, padx=20, pady=16)
    nb.add(t1, text="  JID Gir  ")

    tk.Label(t1, text="Bir XMPP adresi girerek doğrudan sohbet\n"
                      "başlatabilir veya abonelik isteği gönderebilirsiniz.",
             fg=A.FG_DIM, bg=A.BG_CARD,
             font=(A.FONT, 8), justify="left").pack(anchor="w", pady=(0, 12))

    tk.Label(t1, text="JID (XMPP Adresi)", fg=A.FG_DIM, bg=A.BG_CARD,
             font=(A.FONT, 7, "bold")).pack(anchor="w")
    jid_var = tk.StringVar()
    inp_b = tk.Frame(t1, bg=A.BORDER, padx=1, pady=1)
    inp_b.pack(fill="x", pady=(4, 4))
    e = A.PlaceholderEntry(inp_b, placeholder="kullanici@sunucu.tld",
                           textvariable=jid_var,
                           font=(A.FONT, 10), style="Modern.TEntry")
    e.pack(fill="x", ipady=7, padx=2, pady=2)

    err_lbl = tk.Label(t1, text="", fg=A.RED, bg=A.BG_CARD,
                       font=(A.FONT, 7))
    err_lbl.pack(anchor="w")

    def _get_jid():
        """Entry'den JID al, doğrula."""
        jid, err = validate_jid(e.get_value())
        err_lbl.config(text=err)
        return jid

    def _open_chat(_=None):
        jid = _get_jid()
        if not jid:
            return
        dlg.destroy()
        on_open_chat(jid)

    def _subscribe(_=None):
        jid = _get_jid()
        if not jid:
            return
        dlg.destroy()
        on_subscribe(jid)

    bf = tk.Frame(t1, bg=A.BG_CARD)
    bf.pack(fill="x", pady=(12, 0))
    ttk.Button(bf, text="  Sohbet Başlat  ",
               command=_open_chat).pack(side="left", ipadx=8, ipady=4)
    ttk.Button(bf, text="  Kişi Olarak Ekle  ",
               command=_subscribe).pack(side="right", ipadx=8, ipady=4)
    e.bind("<Return>", _open_chat)

    # ── Sekme 2: Kişiler ──
    t_contacts = tk.Frame(nb, bg=A.BG_CARD, padx=20, pady=12)
    nb.add(t_contacts, text="  Kişiler  ")

    tk.Label(t_contacts, text="Mevcut kişilerinizden birini seçerek\n"
                              "sohbet başlatabilirsiniz.",
             fg=A.FG_DIM, bg=A.BG_CARD, font=(A.FONT, 8),
             justify="left").pack(anchor="w", pady=(0, 8))

    # Filtre
    filter_var = tk.StringVar()
    filter_b = tk.Frame(t_contacts, bg=A.BORDER, padx=1, pady=1)
    filter_b.pack(fill="x", pady=(0, 6))
    fe = A.PlaceholderEntry(filter_b, placeholder="Filtrele...",
                            textvariable=filter_var,
                            font=(A.FONT, 9), style="Modern.TEntry")
    fe.pack(fill="x", ipady=3, padx=1, pady=1)

    c_list = tk.Listbox(t_contacts, bg=A.BG_PANEL, fg=A.FG,
                        selectbackground=A.SEL_BG, selectforeground=A.SEL_FG,
                        font=(A.FONT, 9), relief="flat",
                        highlightthickness=0, height=10)
    c_list.pack(fill="both", expand=True, pady=(0, 4))

    _c_jids: list[str] = []

    def _populate_contacts(filter_text=""):
        c_list.delete(0, "end")
        _c_jids.clear()
        ft = filter_text.lower()
        for jid in sorted(contacts.keys()):
            name = contacts[jid] or jid
            if ft and ft not in name.lower() and ft not in jid.lower():
                continue
            _c_jids.append(jid)
            pshow = presence.get(jid, "unavailable")
            dot = {"chat": "🟢", "away": "🟡", "dnd": "🔴",
                   "xa": "🟠"}.get(pshow, "⚫")
            c_list.insert("end", f"  {dot}  {name}")

    _populate_contacts()

    def _on_filter(*_):
        txt = fe.get_value()
        _populate_contacts(txt)
    filter_var.trace_add("write", _on_filter)

    def _pick_contact(_=None):
        sel = c_list.curselection()
        if not sel:
            return
        jid = _c_jids[sel[0]]
        dlg.destroy()
        on_open_chat(jid)

    c_list.bind("<Double-1>", _pick_contact)

    cbf = tk.Frame(t_contacts, bg=A.BG_CARD)
    cbf.pack(fill="x")
    ttk.Button(cbf, text="  Sohbet Başlat  ",
               command=_pick_contact).pack(side="right", ipadx=8, ipady=4)

    # ── Sekme 3: Kullanıcı Ara ──
    t2 = tk.Frame(nb, bg=A.BG_CARD, padx=20, pady=12)
    nb.add(t2, text="  Kullanıcı Ara  ")

    tk.Label(t2, text="Sunucuda kullanıcı arayın (XEP-0055).\n"
                      "Tüm sunucular bu özelliği desteklemeyebilir.",
             fg=A.FG_DIM, bg=A.BG_CARD, font=(A.FONT, 8),
             justify="left").pack(anchor="w", pady=(0, 8))

    srv_var = tk.StringVar(value=default_server)
    q_var = tk.StringVar()

    sf = tk.Frame(t2, bg=A.BG_CARD)
    sf.pack(fill="x")
    sf.columnconfigure(1, weight=1)
    tk.Label(sf, text="Sunucu:", font=(A.FONT, 8), fg=A.FG_DIM,
             bg=A.BG_CARD).grid(row=0, column=0, sticky="w")
    srv_b = tk.Frame(sf, bg=A.BORDER, padx=1, pady=1)
    srv_b.grid(row=0, column=1, sticky="ew", padx=(6, 0), pady=2)
    ttk.Entry(srv_b, textvariable=srv_var, font=(A.FONT, 9),
              style="Modern.TEntry").pack(fill="x", ipady=3, padx=1, pady=1)

    tk.Label(sf, text="Arama:", font=(A.FONT, 8), fg=A.FG_DIM,
             bg=A.BG_CARD).grid(row=1, column=0, sticky="w")
    q_b = tk.Frame(sf, bg=A.BORDER, padx=1, pady=1)
    q_b.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=2)
    qe = A.PlaceholderEntry(q_b, placeholder="İsim veya JID...",
                            textvariable=q_var,
                            font=(A.FONT, 9), style="Modern.TEntry")
    qe.pack(fill="x", ipady=3, padx=1, pady=1)

    s_list = tk.Listbox(t2, bg=A.BG_PANEL, fg=A.FG, selectbackground=A.SEL_BG,
                        selectforeground=A.SEL_FG, font=(A.FONT, 9),
                        relief="flat", highlightthickness=0, height=8)
    s_list.pack(fill="both", expand=True, pady=(6, 4))

    _s_jids: list = []
    on_search_refs(dlg, s_list, _s_jids)

    def _do_search(_=None):
        q = qe.get_value().strip()
        srv = srv_var.get().strip()
        if not q:
            return
        if not srv:
            return
        s_list.delete(0, "end")
        _s_jids.clear()
        s_list.insert("end", "  Aranıyor…")
        _s_jids.append(None)
        on_search(srv, q)

    def _pick_from_search(_=None):
        sel = s_list.curselection()
        if sel and sel[0] < len(_s_jids) and _s_jids[sel[0]]:
            jid = _s_jids[sel[0]]
            dlg.destroy()
            on_open_chat(jid)

    qe.bind("<Return>", _do_search)
    s_list.bind("<Double-1>", _pick_from_search)

    sbf = tk.Frame(t2, bg=A.BG_CARD)
    sbf.pack(fill="x")
    ttk.Button(sbf, text="  Ara  ", command=_do_search).pack(
        side="left", ipadx=8, ipady=4)
    ttk.Button(sbf, text="  Sohbet Başlat  ",
               command=_pick_from_search).pack(side="right", ipadx=8, ipady=4)

    dlg.lift()
    after_alive(dlg, 50, e.focus_force)
    parent.wait_window(dlg)
    return dlg, s_list, _s_jids


def show_search_users(parent, default_server, on_search, on_start_chat):
    """Kullanıcı arama penceresi (MainWindow._search_users_dialog).

    `on_search(server, query)`: arama isteği (network owner'da).
    `on_start_chat(jid)`: seçilen kullanıcıyla sohbet isteği.
    Dönüş: (dlg, result_list, jids) — sonuç render'ı MainWindow
    `_handle("search_results")` tarafından bu referanslarla yapılır.
    """
    A = _app()
    dlg = tk.Toplevel(parent)
    dlg.title("Kullanıcı Ara")
    dlg.configure(bg=A.BG_CARD)
    dlg.geometry("460x420")
    dlg.transient(parent)
    A._safe_grab_set(dlg)

    tk.Label(dlg, text="🔍  Kullanıcı Ara", font=(A.FONT, 12, "bold"),
             fg=A.FG, bg=A.BG_CARD).pack(padx=16, pady=(16, 4), anchor="w")
    tk.Label(dlg, text="Sunucuda kullanıcı arayın (XEP-0055)",
             font=(A.FONT, 8), fg=A.FG_DIM, bg=A.BG_CARD).pack(
                 padx=16, anchor="w")

    inp = tk.Frame(dlg, bg=A.BG_CARD, padx=16)
    inp.pack(fill="x", pady=(8, 0))

    server_var = tk.StringVar(value=default_server)
    query_var = tk.StringVar()

    tk.Label(inp, text="Sunucu:", font=(A.FONT, 8), fg=A.FG_DIM,
             bg=A.BG_CARD).pack(anchor="w")
    sb = tk.Frame(inp, bg=A.BORDER, padx=1, pady=1)
    sb.pack(fill="x", pady=(2, 6))
    ttk.Entry(sb, textvariable=server_var, font=(A.FONT, 10),
              style="Modern.TEntry").pack(fill="x", ipady=5, padx=2, pady=2)

    tk.Label(inp, text="Arama:", font=(A.FONT, 8), fg=A.FG_DIM,
             bg=A.BG_CARD).pack(anchor="w")
    qb = tk.Frame(inp, bg=A.BORDER, padx=1, pady=1)
    qb.pack(fill="x", pady=(2, 0))
    qe = A.PlaceholderEntry(qb, placeholder="İsim veya JID...",
                            textvariable=query_var,
                            font=(A.FONT, 10), style="Modern.TEntry")
    qe.pack(fill="x", ipady=5, padx=2, pady=2)

    result_list = tk.Listbox(dlg, bg=A.BG_PANEL, fg=A.FG,
                             selectbackground=A.SEL_BG,
                             selectforeground=A.SEL_FG, font=(A.FONT, 9),
                             relief="flat", highlightthickness=0)
    result_list.pack(fill="both", expand=True, padx=16, pady=8)

    _jids = []

    def _search(_=None):
        q = query_var.get().strip()
        srv = server_var.get().strip()
        if q and srv:
            result_list.delete(0, "end")
            _jids.clear()
            result_list.insert("end", "  Aranıyor…")
            on_search(srv, q)

    def _start_chat():
        sel = result_list.curselection()
        if sel and sel[0] < len(_jids) and _jids[sel[0]]:
            jid = _jids[sel[0]]
            dlg.destroy()
            on_start_chat(jid)

    qe.bind("<Return>", _search)
    ttk.Button(dlg, text="Ara", command=_search).pack(padx=16, pady=(0, 4))

    btn_f = tk.Frame(dlg, bg=A.BG_CARD)
    btn_f.pack(fill="x", padx=16, pady=(0, 12))
    ttk.Button(btn_f, text="Sohbet Başlat", command=_start_chat).pack(side="left")
    ttk.Button(btn_f, text="Kapat", command=dlg.destroy).pack(side="right")

    after_alive(dlg, 50, qe.focus_force)
    return dlg, result_list, _jids
