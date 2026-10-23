"""Açılır kartlar dışarı tıklayınca kapanmalı (profil kartı ve benzerleri).

Kanıt: "👤 Profil" kartı, emoji/GIF seçicileri, tepkiler, kısayollar… ayrı
Toplevel pencerelerdi; ana pencereye tıklamak onları kapatmıyordu (Hyprland'de
ana pencerenin üstünde yüzmeye devam ediyorlardı; emoji/GIF/ilet/hızlı geçiş
`-topmost` ile başka uygulamaların bile üstünde kalıyordu). Kendi avatarına
tıklayınca açılan "Profil Fotoğrafı" ve "Tepkiler" ise modal grab ile
uygulamanın geri kalanını kilitliyordu: dışarı tıklamak hiçbir şey yapmıyordu.

`_make_popover`: Tk yerel grab'i (grab.n: işaretçi pencere ağacının dışındayken
düğme basmaları grab penceresine bildirilir) + konum denetimi → dışarıdaki
basmada kapanır; Esc de kapatır. Ayrıca ipucu balonu ve kişi hover kartı
tıklamada kapanır (menü/diyalog açılınca <Leave> gelmediği için asılı
kalıyorlardı).

Formlar (2026-10-21, "düzelt hepsini"): Durum Mesajı, Ayarlar, oda/kişi
pencereleri… da aynı şikâyetin parçasıydı: çoğu modal grab ile uygulamayı
kilitliyor, dışarı tıklama hiçbir şey yapmıyordu. `form=True`: değişiklik
yoksa dışarı tıklama kapatır; yazılan/seçilen bir şey varsa ilk tıklama
uyarır ("Değişiklikler kaybolacak…"), ikincisi kapatır — tek yanlış
tıklama yazılanı silmez.
"""
import ast
import inspect
import os
import pathlib
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xmpp  # noqa: E402


# ── 1) Yardımcının davranışı (sahte pencere, ekran gerekmez) ────────────────
class _Win:
    """100,100 konumunda 200x150'lik pencere."""

    def __init__(self, path=".!toplevel"):
        self.path = path
        self.binds = {}
        self.destroyed = False
        self.grab = None

    def __str__(self):
        return self.path

    def bind(self, seq, fn, add=None):
        self.binds.setdefault(seq, []).append(fn)

    def winfo_rootx(self):
        return 100

    def winfo_rooty(self):
        return 100

    def winfo_width(self):
        return self.width if self.width > 1 else 200

    def winfo_height(self):
        return self.height if self.height > 1 else 150

    def winfo_exists(self):
        return not self.destroyed

    def destroy(self):
        self.destroyed = True

    def grab_current(self):
        return self.grab

    # Yerleştirme (sahte ekran 1920x1080; içerik isteği 120x80)
    master = None
    withdrawn = False
    geo = None
    mapped = False
    width = height = 1
    idle = ()

    def withdraw(self):
        self.withdrawn = True

    def deiconify(self):
        self.withdrawn = False
        self.mapped = True

    def after_idle(self, fn, *a):
        self.idle = list(self.idle) + [(fn, a)]
        return f"idle#{len(self.idle)}"

    def after(self, ms, fn, *a):
        fn(*a)
        return "after#"

    cancelled = ()

    def after_cancel(self, ident):
        self.cancelled = list(self.cancelled) + [ident]
        self.idle = []                          # bekleyen gösterme düşer

    def run_idle(self):
        while self.idle:
            fn, a = self.idle.pop(0)
            fn(*a)

    def update_idletasks(self):
        pass

    def geometry(self, g=None):
        self.geo = g

    def winfo_ismapped(self):
        return self.mapped

    req = (120, 80)                             # içeriğin istediği boyut
    mins = (1, 1)

    def winfo_reqwidth(self):
        return self.req[0]

    def winfo_reqheight(self):
        return self.req[1]

    def minsize(self, w=None, h=None):
        if w is None:
            return self.mins
        self.mins = (w, h)

    def winfo_screenwidth(self):
        return 1920

    def winfo_screenheight(self):
        return 1080

    def winfo_toplevel(self):
        return self

    trans = ""

    def transient(self, master=None):
        if master is None:
            return self.trans
        self.trans = str(master)

    def fire(self, seq, **kw):
        ev = types.SimpleNamespace(**kw)
        for fn in self.binds.get(seq, []):
            fn(ev)


@pytest.fixture()
def grabs(monkeypatch):
    calls = []
    monkeypatch.setattr(xmpp, "_safe_grab_set", calls.append)
    return calls


def _press(win, widget, x, y, num=1):
    win.fire("<ButtonPress>", widget=widget, x_root=x, y_root=y, num=num)


def test_click_outside_closes(grabs):
    win = _Win()
    xmpp._make_popover(win)
    assert grabs == [win]                       # dışarı tıklamayı görmek için
    _press(win, win, 20, 20)                    # grab'in yönlendirdiği basma
    assert win.destroyed


def test_click_inside_keeps_open(grabs):
    win = _Win()
    xmpp._make_popover(win)
    _press(win, ".!toplevel.!frame.!button", 150, 150)   # alt widget
    _press(win, win, 150, 150)                  # pencerenin kendi zemini
    _press(win, win, 299, 249)                  # sağ alt köşe (içeride)
    assert not win.destroyed


def test_click_on_other_window_inside_rect_still_closes(grabs):
    """Grab'in yönlendirdiği basmanın widget'ı popover'dır; başka bir
    pencerenin alt widget'ı adı popover'la başlamaz (".!toplevel2…")."""
    win = _Win(".!toplevel")
    xmpp._make_popover(win)
    _press(win, ".!toplevel2.!label", 20, 20)
    assert win.destroyed


def test_wheel_does_not_close(grabs):
    win = _Win()
    xmpp._make_popover(win)
    _press(win, win, 20, 20, num=4)
    _press(win, win, 20, 20, num=5)
    assert not win.destroyed


def test_escape_closes_once_with_custom_close(grabs):
    win = _Win()
    closed = []

    def close():
        closed.append(1)
        win.destroy()
    xmpp._make_popover(win, close)
    win.fire("<Escape>")
    _press(win, win, 20, 20)                    # kapandıktan sonra no-op
    assert closed == [1]


def test_focus_back_regrabs_when_grab_was_lost(grabs):
    """simpledialog gibi kapanınca grab'i geri vermeyen alt pencereden
    sonra dışarı tıklama yine görülmeli."""
    win = _Win()
    xmpp._make_popover(win)
    win.grab = None
    win.fire("<FocusIn>")
    assert grabs == [win, win]
    win.grab = win
    win.fire("<FocusIn>")
    assert grabs == [win, win]                  # zaten grab'te: yeniden yok


def test_closing_returns_grab_to_previous_holder(grabs):
    """Modal Ayarlar'dan açılan kart kapanınca grab Ayarlar'a döner (Tk
    menülerinin RestoreOldGrab'i gibi); yoksa Ayarlar açıkken ana pencere
    tıklanabilir kalırdı."""
    settings = _Win(".!toplevel")
    win = _Win(".!toplevel.!toplevel")
    win.grab = settings
    xmpp._make_popover(win)
    win.destroy()
    win.fire("<Destroy>", widget=win)
    assert grabs == [win, settings]
    other = _Win(".!toplevel2")                 # grab yoktu: geri verilecek yok
    xmpp._make_popover(other)
    other.fire("<Destroy>", widget=other)
    assert grabs == [win, settings, other]


class _Parent(_Win):
    """Ana pencere: 100,50 konumunda 1200x800, haritalanmış."""

    def __init__(self):
        super().__init__(".")
        self.mapped = True

    def winfo_rootx(self):
        return 100

    def winfo_rooty(self):
        return 50

    def winfo_width(self):
        return 1200

    def winfo_height(self):
        return 800


def test_popover_opens_centered_over_parent_not_screen_corner(grabs):
    """Konumsuz Toplevel X11'de +0+0'da açılır; Hyprland bunu uygular
    (ekranın sol üst köşesi, üst çubuğun üstü). Kart gizli başlar, içerik
    kurulunca açan pencerenin ortasına yerleşip görünür."""
    win = _Win(".!toplevel")
    win.master = _Parent()
    xmpp._make_popover(win)
    assert win.withdrawn and win.geo is None    # köşede bir an bile görünmez
    win.run_idle()
    assert not win.withdrawn
    assert win.geo == f"+{100 + (1200 - 120) // 2}+{50 + (800 - 80) // 2}"


def test_popover_recentered_with_real_size_after_map(grabs):
    """Gizliyken Tk açık boyutu (ör. 380x300) bildirmez; görününce gerçek
    boyutla bir kez yeniden ortalanır."""
    win = _Win(".!toplevel")
    win.master = _Parent()
    xmpp._make_popover(win)
    win.run_idle()
    win.width, win.height = 380, 300
    win.fire("<Map>", widget=win)
    assert win.geo == f"+{100 + (1200 - 380) // 2}+{50 + (800 - 300) // 2}"
    win.geo = "kullanıcı taşıdı"
    win.fire("<Map>", widget=win)               # yalnız ilk görünüşte
    win.fire("<Map>", widget=".!toplevel.!label")
    assert win.geo == "kullanıcı taşıdı"


def test_popover_stays_on_screen_and_handles_hidden_parent(grabs):
    win = _Win(".!toplevel")
    parent = _Parent()
    parent.mapped = False                       # ana pencere tepside
    win.master = parent
    xmpp._make_popover(win)
    win.run_idle()
    assert win.geo == f"+{(1920 - 120) // 2}+{(1080 - 80) // 2}"

    class _Edge(_Parent):
        def winfo_rootx(self):
            return 1880                         # ekranın sağ kenarında

    win2 = _Win(".!toplevel2")
    win2.master = _Edge()
    xmpp._make_popover(win2)
    win2.run_idle()
    x, y = (int(v) for v in win2.geo.strip("+").split("+"))
    assert 0 <= x <= 1920 - 120 and 0 <= y <= 1080 - 80


def test_popover_made_transient_to_its_opener(grabs):
    """transient olmayan pencereyi Hyprland döşer (boyut/konum onun olur)."""
    win = _Win(".!toplevel")
    win.master = _Parent()
    xmpp._make_popover(win)
    assert win.trans == "."
    other = _Win(".!toplevel2")
    other.master = _Parent()
    other.trans = ".!zaten"
    xmpp._make_popover(other)
    assert other.trans == ".!zaten"             # var olan bağ korunur


def test_popover_grows_to_fit_its_content(grabs):
    """Pencerelere piksel olarak sabit boyut veriliyordu (Durum Mesajı
    340x200…); büyük yazılı ekranda içerik kesiliyordu — 21 pencerede içerik
    sabit boyuttan büyüktü (Otomatik tema'nın Kaydet düğmesi 107 px dışarıda,
    Ayarlar'ın sekmeleri 312 px taşıyordu). Gösterilmeden önce en küçük boyut
    içeriğin istediği boyut olur; Tk sabit boyutu buna büyütür."""
    win = _Win(".!toplevel")
    win.req = (426, 197)
    xmpp._make_popover(win)
    win.run_idle()
    assert win.mins == (426, 197)


def test_popover_fit_keeps_own_minimum_and_stays_on_screen(grabs):
    win = _Win(".!toplevel")
    win.req, win.mins = (300, 200), (520, 440)  # pencerenin kendi en küçüğü
    xmpp._make_popover(win)
    win.run_idle()
    assert win.mins == (520, 440)
    big = _Win(".!toplevel2")
    big.req = (5000, 3000)
    xmpp._make_popover(big)
    big.run_idle()
    assert big.mins[0] < 1920 and big.mins[1] < 1080


def test_fast_close_cancels_pending_show(grabs):
    """Gösterilmeden kapatılan kartın bekleyen zamanlayıcısı silinmiş
    pencerenin komutunu çağırıyordu ("invalid command name …_show")."""
    win = _Win(".!toplevel")
    win.master = _Parent()
    xmpp._make_popover(win)
    win.fire("<Escape>")
    win.fire("<Destroy>", widget=win)
    assert win.cancelled and win.idle == []


# ── 1b) Formlar: değişiklik varsa ilk dışarı tıklama uyarır ─────────────────
class _Field:
    """Sahte form girdisi (Entry/Text/Checkbutton/Listbox/Label…)."""

    def __init__(self, path, cls="TEntry", value="", state="normal",
                 selectmode="browse", variable=""):
        self.path, self.cls, self.value = path, cls, value
        self.state, self.selectmode, self.variable = state, selectmode, variable

    def __str__(self):
        return self.path

    def winfo_class(self):
        return self.cls

    def winfo_children(self):
        return []

    def cget(self, key):
        return {"state": self.state, "selectmode": self.selectmode,
                "variable": self.variable}[key]

    def get(self, *a):
        return self.value

    def getvar(self, name):
        return self.value

    def curselection(self):
        return self.value


class _FormWin(_Win):
    """Alanları olan pencere; zamanlayıcılar elle ilerletilir."""

    def __init__(self, *fields):
        super().__init__(".!toplevel")
        self.fields = list(fields)
        self.timers = {}
        self.n = 0

    def winfo_children(self):
        return self.fields

    def after(self, ms, fn, *a):
        self.n += 1
        self.timers[f"after#{self.n}"] = (fn, a)
        return f"after#{self.n}"

    def after_cancel(self, ident):
        super().after_cancel(ident)
        self.timers.pop(ident, None)

    def run_timers(self):
        while self.timers:
            fn, a = self.timers.pop(next(iter(self.timers)))
            fn(*a)


@pytest.fixture()
def banners(monkeypatch):
    shown = []

    def fake(win):
        shown.append("shown")
        return lambda: shown.append("hidden")
    monkeypatch.setattr(xmpp, "_form_warning", fake)
    return shown


def _form(*fields):
    win = _FormWin(*fields)
    xmpp._make_popover(win, form=True)
    win.run_idle()                              # kurulunca ilk değerler alınır
    return win


def test_untouched_form_closes_on_outside_click(grabs, banners):
    win = _form(_Field(".!toplevel.!entry", value="eski"))
    _press(win, win, 20, 20)
    assert win.destroyed and banners == []


def test_changed_form_warns_first_then_closes(grabs, banners):
    """Yazılanı tek yanlış tıklama silmemeli: önce uyarı, ikincisi kapatır."""
    entry = _Field(".!toplevel.!entry", value="")
    win = _form(entry)
    entry.value = "yarım kalmış durum mesajı"
    _press(win, win, 20, 20)
    assert not win.destroyed and banners == ["shown"]
    _press(win, win, 20, 20)
    assert win.destroyed


def test_warning_expires_then_warns_again(grabs, banners):
    entry = _Field(".!toplevel.!entry", value="")
    win = _form(entry)
    entry.value = "x"
    _press(win, win, 20, 20)
    win.run_timers()                            # uyarı süresi doldu
    assert banners == ["shown", "hidden"]
    _press(win, win, 20, 20)
    assert not win.destroyed and banners[-1] == "shown"


def test_returning_to_form_rearms_warning(grabs, banners):
    """Uyarıdan sonra forma dönüp yazmaya devam eden yine uyarılır."""
    entry = _Field(".!toplevel.!entry", value="")
    win = _form(entry)
    entry.value = "x"
    _press(win, win, 20, 20)
    _press(win, ".!toplevel.!entry", 150, 150)  # forma tıkladı
    assert banners == ["shown", "hidden"]
    _press(win, win, 20, 20)
    assert not win.destroyed and banners[-1] == "shown"
    win.fire("<KeyPress>", widget=entry)        # yazmaya döndü
    assert banners[-1] == "hidden"
    _press(win, win, 20, 20)
    assert not win.destroyed


def test_escape_closes_changed_form_without_warning(grabs, banners):
    entry = _Field(".!toplevel.!entry", value="")
    win = _form(entry)
    entry.value = "x"
    win.fire("<Escape>")
    assert win.destroyed and banners == []


def test_reverted_edit_is_no_change(grabs, banners):
    entry = _Field(".!toplevel.!entry", value="eski")
    win = _form(entry)
    entry.value = "eski"                        # yazıp geri sildi
    _press(win, win, 20, 20)
    assert win.destroyed


def test_only_user_inputs_count_as_changes(grabs, banners):
    """Kapalı (kodun doldurduğu) metin, tek seçimli sonuç listesi ve
    etiketler kullanıcı girdisi değildir; çok seçimli liste (alıcılar) ve
    işaret kutusu girdidir."""
    text = _Field(".!toplevel.!text", "Text", "log", state="disabled")
    single = _Field(".!toplevel.!listbox", "Listbox", ())
    label = _Field(".!toplevel.!label", "Label", "durum")
    win = _form(text, single, label)
    text.value, single.value, label.value = "yeni log", (3,), "bitti"
    _press(win, win, 20, 20)
    assert win.destroyed
    multi = _Field(".!toplevel.!listbox", "Listbox", (), selectmode="multiple")
    win = _form(multi)
    multi.value = (0, 2)
    _press(win, win, 20, 20)
    assert not win.destroyed
    check = _Field(".!toplevel.!checkbutton", "Checkbutton", 0,
                   variable="PY_VAR1")
    win = _form(check)
    check.value = 1
    _press(win, win, 20, 20)
    assert not win.destroyed


def test_placeholder_text_is_not_a_value(grabs, banners):
    """PlaceholderEntry odakta ipucunu siler: get() değişir, değer değişmez."""
    entry = _Field(".!toplevel.!placeholderentry", value="Durum yazın...")
    entry.get_value = lambda: ""
    win = _form(entry)
    entry.value = ""
    _press(win, win, 20, 20)
    assert win.destroyed


def test_field_added_later_is_tracked_from_first_focus(grabs, banners):
    """Sonradan eklenen alan (ör. "+ seçenek") ilk odakta kaydedilir."""
    win = _form()
    option = _Field(".!toplevel.!entry3", value="")
    win.fields.append(option)
    win.fire("<FocusIn>", widget=option)
    option.value = "Pazartesi"
    _press(win, win, 20, 20)
    assert not win.destroyed


# ── 2) Gerçek Tk: bağlama yolları (ekran yoksa atlanır) ─────────────────────
@pytest.fixture()
def root():
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        pytest.skip("Tk testleri bir ekran veya Xvfb gerektiriyor")
    import tkinter as tk
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


def test_real_tk_outside_press_closes_inside_press_keeps(root):
    import tkinter as tk
    pop = tk.Toplevel(root)
    pop.geometry("200x120+300+300")
    btn = tk.Label(pop, text="içeride")
    btn.pack()
    xmpp._make_popover(pop)
    root.update()
    btn.event_generate("<ButtonPress-1>", x=2, y=2,
                       rootx=btn.winfo_rootx() + 2,
                       rooty=btn.winfo_rooty() + 2)
    root.update()
    assert pop.winfo_exists()
    pop.event_generate("<ButtonPress-1>", x=-30, y=-30,
                       rootx=pop.winfo_rootx() - 30,
                       rooty=pop.winfo_rooty() - 30)
    root.update()
    assert not pop.winfo_exists()


def test_real_tk_popover_centered_over_parent(root):
    import tkinter as tk
    host = tk.Toplevel(root)
    host.geometry("600x400+200+150")
    root.update()
    pop = tk.Toplevel(host)
    pop.geometry("200x100")
    tk.Label(pop, text="kart").pack()
    xmpp._make_popover(pop)
    import time
    end = time.monotonic() + 0.4                # gerçek boyutla yeniden ortalama
    while time.monotonic() < end:
        root.update()
        time.sleep(0.01)
    cx = pop.winfo_rootx() + pop.winfo_width() // 2
    cy = pop.winfo_rooty() + pop.winfo_height() // 2
    hx = host.winfo_rootx() + host.winfo_width() // 2
    hy = host.winfo_rooty() + host.winfo_height() // 2
    assert abs(cx - hx) <= 40 and abs(cy - hy) <= 40, (cx, cy, hx, hy)


def test_real_tk_bindings_installed(root):
    """Tuş olayları yalnız odaktaki pencereye gider (gizli kökte WM odak
    vermez); Esc davranışı yukarıdaki sahte testte, burada bağlamalar."""
    import tkinter as tk
    pop = tk.Toplevel(root)
    xmpp._make_popover(pop)
    for seq in ("<ButtonPress>", "<Escape>", "<FocusIn>", "<Destroy>"):
        assert pop.bind(seq), seq


def _settle(root, secs=0.3):
    import time
    end = time.monotonic() + secs
    while time.monotonic() < end:
        root.update()
        time.sleep(0.01)


def _click_outside(pop):
    pop.event_generate("<ButtonPress-1>", x=-30, y=-30,
                       rootx=pop.winfo_rootx() - 30,
                       rooty=pop.winfo_rooty() - 30)
    pop.update()


def _real_host(root):
    import tkinter as tk
    host = tk.Toplevel(root)                    # gizli kökün çocuğu görünmez
    host.geometry("500x300+200+150")
    return host


def test_real_tk_fixed_size_no_longer_cuts_content(root):
    import tkinter as tk
    host = _real_host(root)
    pop = tk.Toplevel(host)
    pop.geometry("150x60")                      # içerikten küçük sabit boyut
    row = tk.Frame(pop)
    row.pack()
    options = [tk.Label(row, text=f"Seçenek {i}") for i in range(4)]
    for lbl in options:
        lbl.pack(side="left")
    button = tk.Button(pop, text="Kaydet")
    button.pack()
    xmpp._make_popover(pop)
    _settle(root, 0.5)
    assert pop.winfo_width() >= pop.winfo_reqwidth()
    assert pop.winfo_height() >= pop.winfo_reqheight()
    last = options[-1]
    assert row.winfo_x() + last.winfo_x() + last.winfo_width() \
        <= pop.winfo_width()
    assert button.winfo_y() + button.winfo_height() <= pop.winfo_height()


def test_real_tk_form_closes_untouched_warns_when_typed(root):
    import tkinter as tk
    from tkinter import ttk
    host = _real_host(root)
    for typed in ("", "yarım mesaj"):
        pop = tk.Toplevel(host)
        entry = ttk.Entry(pop)
        entry.pack(padx=20, pady=20)
        xmpp._make_popover(pop, form=True)
        _settle(root)
        entry.insert(0, typed)
        _click_outside(pop)
        if not typed:
            assert not pop.winfo_exists()
            continue
        assert pop.winfo_exists()
        assert [w for w in pop.winfo_children() if isinstance(w, tk.Label)]
        _click_outside(pop)
        assert not pop.winfo_exists()


def test_real_tk_form_sees_checkbutton_and_combobox_changes(root):
    import tkinter as tk
    from tkinter import ttk
    host = _real_host(root)
    for change in ("check", "combo"):
        pop = tk.Toplevel(host)
        var = tk.IntVar(pop, value=0)
        check = tk.Checkbutton(pop, text="bildirim", variable=var)
        check.pack()
        combo = ttk.Combobox(pop, values=("açık", "koyu"), state="readonly")
        combo.set("açık")
        combo.pack()
        xmpp._make_popover(pop, form=True)
        _settle(root)
        if change == "check":
            check.invoke()
        else:
            combo.set("koyu")
        _click_outside(pop)
        assert pop.winfo_exists(), change
        pop.destroy()


def test_real_tk_tooltip_hides_before_button1_handler(root):
    """Gerçek Tk etiket sırası: "Tooltip" etiketi widget'ın sonradan
    bağlanan <Button-1>'inden önce çalışır ve onu engellemez."""
    import tkinter as tk
    xmpp._apply_theme()
    host = tk.Toplevel(root)                    # gizli köke fare olayı gitmez
    host.geometry("120x60+320+320")
    btn = tk.Label(host, text="⋮")
    btn.pack()
    xmpp._add_tooltip(btn, "Menü")

    def balloons():                             # balon düğmenin alt penceresi
        return [w for w in btn.winfo_children() if isinstance(w, tk.Toplevel)]
    seen = []
    btn.bind("<Button-1>", lambda e: seen.append(balloons()))
    root.update()
    btn.event_generate("<Enter>")
    root.update()
    assert balloons()
    btn.event_generate("<ButtonPress-1>")
    root.update()
    assert seen == [[]]                         # işleyici çalışırken balon yok


# ── 3) Her pencere sınıflandırılmış: kart, form ya da bilinçli pencere ──────
PLAIN = {   # dışarı tıklama hemen kapatır
    "xmpp.MainWindow._profile_card",            # ⋮ → 👤 Profil (bildirilen)
    "xmpp.MainWindow._show_pinned",
    "xmpp.MainWindow._omemo_fingerprint_dialog",
    "xmpp.MainWindow._omemo_qr_dialog",
    "xmpp.MainWindow._show_emoji_picker",
    "xmpp.MainWindow._show_gif_panel",
    "xmpp.MainWindow._split_view_dialog",
    "xmpp.MainWindow._blocking_dialog",
    "xmpp.MainWindow._open_media_overflow_viewer",
    "xmpp.MainWindow._on_close_request",
    "xmpp.MainWindow._search_messages_dialog",
    "xmpp.MainWindow._backup_dialog",
    "xmpp.MainWindow._wallpaper_dialog",
    "ui.profile.show_avatar_dialog",            # kendi avatarına tıklayınca
    "ui.sidebar.show_quick_switch",
    "ui.dialogs.simple.show_shortcuts",
    "ui.dialogs.simple.show_reaction_details",
    "ui.dialogs.chat_options.show_disappearing",
    "ui.dialogs.chat_options.show_clear_history",
    "ui.dialogs.chat_actions.show_forward",
    "ui.dialogs.rooms.show_common_groups",
    "ui.dialogs.rooms.show_bookmarks",
    "ui.dialogs.rooms.show_rooms_browser",
    "ui.dialogs.rooms.show_room_search",
    "ui.dialogs.contact.show_search_users",
    "ui.dialogs.contact.show_contact_groups",   # kapanış kaydeder (eskisi gibi)
}
FORMS = {   # yazılan/seçilen varsa ilk dışarı tıklama uyarır
    "xmpp.MainWindow._schedule_message_dialog",
    "xmpp.MainWindow._broadcast_dialog",
    "xmpp.MainWindow._auto_theme_dialog",
    "xmpp.MainWindow._pin_lock_dialog",
    "xmpp.MainWindow._proxy_dialog",
    "xmpp.MainWindow._poll_dialog",
    "xmpp.MainWindow._rest_api_dialog",
    "ui.profile.show_story_dialog",
    "ui.dialogs.presence.show_status",
    "ui.dialogs.presence.show_location",
    "ui.dialogs.contact.show_add_contact",
    "ui.dialogs.contact.show_contact_groups._add_to_group",
    "ui.dialogs.rooms.show_join_room",
    "ui.dialogs.rooms.show_create_room",
    "ui.dialogs.rooms.show_room_config",
    "ui.dialogs.rooms.show_room_admin",
    "ui.dialogs.settings.show_settings",
    "ui.dialogs.ai.show_settings",
}
MADE_BY_CALLER = {  # pencereyi kuran yardımcı; kartı çağıran yapar
    "ui.chat.media.fullscreen_window": "xmpp.MainWindow._show_image_fullscreen",
}
WINDOWS = {   # bilerek açılır kart DEĞİL
    "xmpp._add_tooltip._show": "ipucu balonu: çıkınca/tıklayınca kapanır",
    "xmpp.MainWindow._show_toast": "bildirim: kendiliğinden kaybolur",
    "xmpp.MainWindow._ft_offer_dialog":
        "gelen dosya teklifi karar ister: dışarı tıklama reddetmemeli",
    "xmpp.MainWindow._make_ft_progress_window": "aktarım ilerlemesi (İptal)",
    "xmpp.MainWindow._open_chat_tab": "ayrı sohbet penceresi",
    "xmpp.MainWindow._log_viewer_dialog":
        "XML trafiği izlenirken uygulama kullanılır",
    "ui.sidebar.show_contact_card": "hover kartı: fare çıkınca kapanır",
    "ui.dialogs.ai.AssistantWindow.__init__": "asistan: yanında çalışılır",
    "ui.dialogs.ai.ResultWindow.__init__": "sonuç sohbetle yan yana okunur",
    "ui.dialogs.ai.SemanticSearchWindow.__init__":
        "sonuç açılınca pencere kalır (sıradaki sonuç)",
    "ui.dialogs.ai.ActionsWindow.__init__": "görev listesi: yan yana",
    "ui.dialogs.ai.PendingQuestionsWindow.__init__": "soru listesi: yan yana",
    "ui.dialogs.ai.DraftsWindow.__init__": "taslak listesi: yan yana",
}

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _own_source(lines, fn):
    """İşlevin kendi satırları (iç içe tanımlanan işlevler hariç)."""
    nested = [(n.lineno, n.end_lineno) for n in ast.walk(fn)
              if n is not fn and isinstance(n, (ast.FunctionDef,
                                                ast.AsyncFunctionDef))]
    return "\n".join(
        line for no, line in enumerate(lines[fn.lineno - 1:fn.end_lineno],
                                       fn.lineno)
        if not any(a <= no <= b for a, b in nested))


def _scan():
    """({pencere açan işlev: kendi kaynağı}, {her işlev: kendi kaynağı});
    pencere açan = `tk.Toplevel(` çağıran en içteki işlev."""
    makers, sources = {}, {}
    for path in [ROOT / "xmpp.py", *sorted((ROOT / "ui").rglob("*.py"))]:
        lines = path.read_text(encoding="utf-8").splitlines()
        mod = ".".join(path.relative_to(ROOT).with_suffix("").parts)

        def visit(node, stack):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                      ast.ClassDef)):
                    if not isinstance(child, ast.ClassDef):
                        name = ".".join([mod, *(n.name for n in stack),
                                         child.name])
                        sources[name] = _own_source(lines, child)
                    visit(child, stack + [child])
                    continue
                if (isinstance(child, ast.Call)
                        and isinstance(child.func, ast.Attribute)
                        and child.func.attr == "Toplevel" and stack):
                    name = ".".join([mod, *(n.name for n in stack)])
                    makers[name] = sources[name]
                visit(child, stack)
        visit(ast.parse("\n".join(lines)), [])
    return makers, sources


MAKERS, SOURCES = _scan()


def test_every_window_is_classified():
    """"Bu ve bunun gibi her şey": yeni bir pencere sınıflandırılmadan
    eklenemez (kart mı, form mu, bilinçli pencere mi)."""
    known = PLAIN | FORMS | set(MADE_BY_CALLER) | set(WINDOWS)
    assert set(MAKERS) - known == set()
    assert known - set(MAKERS) == set()


@pytest.mark.parametrize("name", sorted(PLAIN | FORMS))
def test_popovers_close_on_outside_click(name):
    src = MAKERS[name]
    assert "_make_popover(" in src
    assert ("form=True" in src) is (name in FORMS)
    # Kalıcı üstte durma ve modal kilit, açılır kartla çelişir
    assert '"-topmost"' not in src and "_safe_grab_set(" not in src


def test_window_built_by_helper_is_made_popover_by_caller():
    for maker, caller in MADE_BY_CALLER.items():
        assert "_make_popover(" not in MAKERS[maker]
        assert "_make_popover(" in SOURCES[caller]


@pytest.mark.parametrize("name", sorted(WINDOWS))
def test_deliberate_windows_are_not_popovers(name):
    assert "_make_popover(" not in MAKERS[name]


# ── 4) İpucu balonu tıklamada kapanır ───────────────────────────────────────
class _Widget:
    """Bağlama etiketleri olan sahte widget; sınıf bağlamaları ortak."""
    classes = {}

    def __init__(self):
        self.binds = {}
        self.tags = (".w", "Label", ".", "all")

    def bind(self, seq, fn, add=None):
        self.binds.setdefault(seq, []).append(fn)

    def bindtags(self, tags=None):
        if tags is None:
            return self.tags
        self.tags = tuple(tags)

    def bind_class(self, tag, seq=None, fn=None, add=None):
        if fn is None:
            return "script" if (tag, seq) in _Widget.classes else ""
        _Widget.classes[(tag, seq)] = fn

    def fire(self, seq):
        for fn in self.binds.get(seq, []):
            fn(None)

    def click(self):
        """Etiket sırasıyla: önce sınıf etiketleri (Tooltip), sonra widget."""
        ev = types.SimpleNamespace(widget=self)
        for tag in self.tags:
            fn = _Widget.classes.get((tag, "<ButtonPress>"))
            if fn is not None:
                fn(ev)
        for fn in self.binds.get("<Button-1>", []):
            fn(ev)

    def winfo_rootx(self):
        return 10

    def winfo_rooty(self):
        return 40


@pytest.fixture()
def tooltip_tk(monkeypatch):
    made = []

    class _Top:
        def __init__(self, master=None):
            self.destroyed = False
            made.append(self)

        def wm_overrideredirect(self, flag):
            pass

        def wm_geometry(self, g):
            pass

        def destroy(self):
            self.destroyed = True

    class _Label:
        def __init__(self, *a, **k):
            pass

        def pack(self, **k):
            pass
    monkeypatch.setattr(xmpp.tk, "Toplevel", _Top)
    monkeypatch.setattr(xmpp.tk, "Label", _Label)
    monkeypatch.setattr(_Widget, "classes", {})
    return made


def test_tooltip_hides_on_click(tooltip_tk):
    """Simge düğmesi menü/diyalog açınca <Leave> gelmiyor, balon asılı
    kalıyordu."""
    w = _Widget()
    xmpp._add_tooltip(w, "Menü")
    w.fire("<Enter>")
    assert tooltip_tk and not tooltip_tk[0].destroyed
    w.click()
    assert tooltip_tk[0].destroyed


def test_tooltip_click_hide_survives_later_button1_binding(tooltip_tk):
    """Tk aynı etikette yalnız en özgül bağlamayı çalıştırır: widget'ın
    sonradan bağlanan <Button-1>'i balonun gizleyicisini ezmemeli —
    gizleyici ayrı ve önde duran "Tooltip" etiketindedir."""
    w = _Widget()
    xmpp._add_tooltip(w, "Menü")
    opened = []
    w.bind("<Button-1>", lambda e: opened.append("menü"))   # sonradan
    w.fire("<Enter>")
    w.click()
    assert tooltip_tk[0].destroyed and opened == ["menü"]
    assert w.tags[0] == "Tooltip"
    w2 = _Widget()
    xmpp._add_tooltip(w2, "İki")                # sınıf bağlaması bir kez
    assert w2.tags.count("Tooltip") == 1
    xmpp._add_tooltip(w2, "İki")                # aynı widget'a ikinci kez
    assert w2.tags.count("Tooltip") == 1


# ── 5) Kişi hover kartı ─────────────────────────────────────────────────────
class _Root:
    def __init__(self):
        self.timers = {}
        self.n = 0

    def after(self, ms, fn):
        self.n += 1
        self.timers[self.n] = (ms, fn)
        return self.n

    def after_cancel(self, ident):
        self.timers.pop(ident, None)


class _Card:
    def __init__(self):
        self.destroyed = False
        self.binds = {}

    def bind(self, seq, fn):
        self.binds[seq] = fn

    def destroy(self):
        self.destroyed = True


def _hover_win(monkeypatch):
    w = object.__new__(xmpp.MainWindow)
    w.root = _Root()
    w._contacts = {"ali@x": "Ali", "ayse@x": "Ayşe"}
    w._contact_jids = ["ali@x", "ayse@x"]
    w.presence = {}
    w.rooms = {}
    w.room_members = {}
    w._avatars = {}
    w._photo_refs = []
    w.contact_list = types.SimpleNamespace(nearest=lambda y: y // 20)
    cards = []

    def _show(*a, **k):
        cards.append(_Card())
        return cards[-1]
    monkeypatch.setattr(xmpp._ui_sidebar, "show_contact_card", _show)
    return w, cards


def _ev(y=5):
    return types.SimpleNamespace(y=y, x_root=1, y_root=1)


def test_click_cancels_pending_hover_card(monkeypatch):
    """Kişiye tıklayınca 0,8 sn sonra kart yine beliriyordu."""
    w, cards = _hover_win(monkeypatch)
    xmpp.MainWindow._contact_hover_motion(w, _ev())
    assert len(w.root.timers) == 1
    xmpp.MainWindow._contact_hover_click(w, _ev())
    assert w.root.timers == {} and cards == []


def test_click_hides_visible_hover_card(monkeypatch):
    w, cards = _hover_win(monkeypatch)
    xmpp.MainWindow._show_contact_card(w, _ev(), "ali@x")
    xmpp.MainWindow._contact_hover_click(w, _ev())
    assert cards[0].destroyed and w._contact_card_pop is None


def test_old_card_timer_does_not_orphan_new_card(monkeypatch):
    """Eski kartın 3 sn'lik zamanlayıcısı yeni kartın kaydını siliyordu:
    yeni kart sahipsiz kalıp bir sonraki gösterimde kapatılamıyordu."""
    w, cards = _hover_win(monkeypatch)
    xmpp.MainWindow._show_contact_card(w, _ev(), "ali@x")
    old_timer = max(w.root.timers)
    xmpp.MainWindow._show_contact_card(w, _ev(), "ayse@x")
    assert cards[0].destroyed
    w.root.timers[old_timer][1]()               # eski kartın zamanlayıcısı
    assert w._contact_card_pop is cards[1] and not cards[1].destroyed


def test_card_stays_quiet_on_clicked_row_until_pointer_moves_on(monkeypatch):
    """Tıklamadan sonra farenin kıpırdaması (aynı satır) kartı yeniden
    açtırmaz; başka satıra geçince ya da listeden çıkıp girince açar."""
    w, cards = _hover_win(monkeypatch)
    xmpp.MainWindow._contact_hover_click(w, _ev(5))      # satır 0
    xmpp.MainWindow._contact_hover_motion(w, _ev(8))     # hâlâ satır 0
    assert w.root.timers == {}
    xmpp.MainWindow._contact_hover_motion(w, _ev(25))    # satır 1
    assert len(w.root.timers) == 1
    xmpp.MainWindow._contact_hover_click(w, _ev(25))
    xmpp.MainWindow._contact_hover_end(w, _ev(25))       # listeden çıktı
    xmpp.MainWindow._contact_hover_motion(w, _ev(25))
    assert len(w.root.timers) == 1


def test_contact_list_click_is_wired():
    src = inspect.getsource(xmpp.MainWindow._build_sidebar)
    assert ('self.contact_list.bind("<ButtonPress>",' in src
            and "self._contact_hover_click" in src)
