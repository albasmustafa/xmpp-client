"""Oda/MUC presentation ve menü kabukları (Faz 4B-3).

Kurallar:
- Domain/XMPP/MUC protocol çağrısı yok; tüm eylemler callback'lere delege
  edilir (MainWindow/XMPPBot owner).
- Yetki hesaplama (affiliation rank) domain kabul edilir ve MainWindow
  wrapper'ında kalır; UI yalnız hazır `can_mod`/`can_admin` bayraklarını
  kullanır.
- Tema sembolleri çağrı anında `xmpp`'den okunur (canlı tema, döngü yok).
"""
import tkinter as tk


def _app():
    import xmpp as _app_mod
    return _app_mod


def _tr(text):
    """Arayüz metnini seçili dile çevir (`xmpp._tr`)."""
    return _app()._tr(text)


def show_room_menu(parent, room, subject, can_admin, is_owner,
                    on_change_subject, on_invite, on_config, on_leave,
                   on_destroy, x_root, y_root, is_pinned=False, on_toggle_pin=None):
    """Oda sağ tık menüsü (MainWindow._room_context_menu)."""
    A = _app()
    menu = tk.Menu(parent, tearoff=0,
                   bg=A.BG_CARD, fg=A.FG, activebackground=A.ACCENT2,
                   activeforeground=A.FG_ME, borderwidth=1,
                   relief="flat", font=(A.FONT, 9))
    menu.add_command(label=f"  {room}", state="disabled")
    # Konu bilgisi
    if subject:
        short = (subject[:40] + "…") if len(subject) > 40 else subject
        menu.add_command(label=f"  📌 {short}", state="disabled")
    menu.add_separator()

    if on_toggle_pin is not None:
        menu.add_command(label=f"📌 {A._t('unpin' if is_pinned else 'pin')}",
                         command=on_toggle_pin)
        menu.add_separator()

    menu.add_command(label=_tr("  📝 Konu Değiştir"), command=on_change_subject)
    menu.add_command(label=_tr("  📨 Davet Gönder"), command=on_invite)
    if can_admin:
        menu.add_command(label=_tr("  ⚙ Oda Ayarları"), command=on_config)
    menu.add_separator()
    menu.add_command(label=_tr("  🚪 Odayı Terk Et"), command=on_leave)
    if is_owner:
        menu.add_command(label=_tr("  💣 Odayı Sil"), command=on_destroy)
    menu.tk_popup(x_root, y_root)


def show_member_menu(parent, nick, t_affil, t_role, can_mod, can_admin,
                     on_private, on_kick, on_set_role, on_ban,
                     on_set_affiliation, x_root, y_root):
    """Üye sağ tık menüsü (MainWindow._member_context_menu).

    `on_set_role(role)` ve `on_set_affiliation(affil)` yalnız hedef değeri
    taşır; stanza/gönderim owner'da yapılır.
    """
    A = _app()
    menu = tk.Menu(parent, tearoff=0,
                   bg=A.BG_CARD, fg=A.FG, activebackground=A.ACCENT2,
                   activeforeground=A.FG_ME, borderwidth=1,
                   relief="flat", font=(A.FONT, 9))
    menu.add_command(label=f"  {nick}", state="disabled")
    if t_affil:
        menu.add_command(label=_tr("  Yetki: {}").format(t_affil), state="disabled")
    if t_role:
        menu.add_command(label=_tr("  Rol: {}").format(t_role), state="disabled")
    menu.add_separator()

    # Özel mesaj
    menu.add_command(label=_tr("  💬 Özel Mesaj"), command=on_private)

    if can_mod:
        menu.add_separator()
        # Kick
        menu.add_command(label=_tr("  👢 At (Kick)"), command=on_kick)
        # Sustur / Konuştur
        if t_role != "visitor":
            menu.add_command(label=_tr("  🔇 Sustur"),
                             command=lambda: on_set_role("visitor"))
        else:
            menu.add_command(label=_tr("  🔊 Konuşmaya İzin Ver"),
                             command=lambda: on_set_role("participant"))
        # Moderatör yap/al
        if t_role != "moderator":
            menu.add_command(label=_tr("  ⚔ Moderatör Yap"),
                             command=lambda: on_set_role("moderator"))
        else:
            menu.add_command(label=_tr("  ⚔ Moderatörlüğü Al"),
                             command=lambda: on_set_role("participant"))

    if can_admin:
        menu.add_separator()
        # Ban
        menu.add_command(label=_tr("  🚫 Yasakla (Ban)"), command=on_ban)
        # Affiliation
        if t_affil != "admin":
            menu.add_command(label=_tr("  🛡 Yönetici Yap"),
                             command=lambda: on_set_affiliation("admin"))
        if t_affil != "member":
            menu.add_command(label=_tr("  👤 Üye Yap"),
                             command=lambda: on_set_affiliation("member"))
        if t_affil not in ("none", ""):
            menu.add_command(label=_tr("  ↓ Yetkiyi Kaldır"),
                             command=lambda: on_set_affiliation("none"))

    menu.tk_popup(x_root, y_root)
