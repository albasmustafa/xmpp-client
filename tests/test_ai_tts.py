"""Sesli okuma (xmppcore/tts + MainWindow).

Kanıtlar:
- Metin hazırlama: bağlantı/biçim ayıklanır, uzun metin cümle sınırında
  kesilir.
- Motor seçimi: "auto" piper → espeak-ng → espeak → spd-say sırasıyla
  dener; piper ses modeli ve çalar ister; yoksa kurulum ipuçlu hata.
- Komutlar kabuksuz listedir; metin stdin'den gider ("-" ile başlayan
  mesaj seçenek sayılmaz); spd-say'de "--" seçenekleri bitirir.
- MainWindow: adımlar sırayla çalışır, geçici wav silinir; yeni okuma
  eskisini durdurur; durdurulan süreç hata bildirmez, gerçek hata
  bildirir; kapanış okumayı durdurur; mesaj menüsü metinli ve yazıya
  dökülmüş sesli mesajlarda "Sesli oku" sunar.
"""
import inspect
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_history_window_bounds import _Cap  # noqa: E402

import xmpp  # noqa: E402
from xmppcore import ai, tts  # noqa: E402


def _which(*have):
    return lambda name: f"/usr/bin/{name}" if name in have else None


# ── 1) Metin ve motor ───────────────────────────────────────────────────────
def test_clean_for_speech():
    assert tts.clean_for_speech("**Bak** https://x.org/a?b ve `kod`") == \
        "Bak bağlantı ve kod"
    long = ("Cümle bir. " * 200).strip()
    out = tts.clean_for_speech(long)
    assert len(out) <= tts.MAX_CHARS + 2 and out.endswith("bir. …")


def test_engine_order_and_requirements(tmp_path):
    voice = tmp_path / "tr.onnx"
    voice.write_bytes(b"x")
    s = ai.load_settings({})
    assert tts.pick_engine(s, _which("espeak-ng", "spd-say")) == "espeak-ng"
    assert tts.pick_engine(s, _which("spd-say")) == "spd-say"
    # piper: komut + ses modeli + çalar gerekir
    assert tts.pick_engine(s, _which("piper", "espeak")) == "espeak"
    s_v = dict(s, tts_voice=str(voice))
    assert tts.pick_engine(s_v, _which("piper", "pw-play", "espeak")) == \
        "piper"
    with pytest.raises(ai.AISetupError, match="espeak-ng"):
        tts.pick_engine(s, _which())
    with pytest.raises(ai.AISetupError, match="Piper"):
        tts.pick_engine(dict(s, tts_engine="piper"), _which("piper"))
    with pytest.raises(ai.AISetupError, match="spd-say"):
        tts.pick_engine(dict(s, tts_engine="spd-say"), _which("espeak"))


def test_commands_pass_text_safely(tmp_path):
    s = ai.load_settings({"ai": {"tts_lang": "tr"}})
    text = "-rf --help merhaba"
    (step,) = tts.plan_speech(text, s, "/tmp/o.wav", _which("espeak-ng"))
    assert step.argv == ["/usr/bin/espeak-ng", "-v", "tr", "-s", "165",
                         "--stdin"]
    assert step.stdin == text
    (step,) = tts.plan_speech(text, s, "/tmp/o.wav", _which("spd-say"))
    assert step.argv[-2:] == ["--", text] and step.stdin is None
    voice = tmp_path / "tr.onnx"
    voice.write_bytes(b"x")
    synth, play = tts.plan_speech(text, dict(s, tts_voice=str(voice)),
                                  "/tmp/o.wav", _which("piper", "aplay"))
    assert synth.argv == ["/usr/bin/piper", "-m", str(voice), "-f",
                          "/tmp/o.wav"] and synth.stdin == text
    assert play.argv == ["/usr/bin/aplay", "-q", "/tmp/o.wav"]
    with pytest.raises(ai.AISetupError, match="Okunacak metin yok"):
        tts.plan_speech("** `` #", s, "/tmp/o.wav", _which("espeak"))


def test_settings_validation():
    s = ai.load_settings({"ai": {"tts_engine": "say", "tts_lang": "tr; rm"}})
    assert s["tts_engine"] == "auto" and s["tts_lang"] == "tr"
    assert ai.load_settings({"ai": {"tts_lang": "pt-BR"}})["tts_lang"] == \
        "pt-BR"
    assert tts.describe_engines(ai.load_settings({}), _which()).startswith(
        "ℹ")
    assert tts.describe_engines(ai.load_settings({}),
                                _which("espeak")) == "✓ Sesli okuma: espeak"


# ── 2) MainWindow süreç yönetimi ────────────────────────────────────────────
class _Proc:
    instances = []

    def __init__(self, argv, stdin=None, stdout=None, stderr=None):
        self.argv, self.rc, self.terminated = argv, None, False
        self.fed = None
        _Proc.instances.append(self)

    def communicate(self, data=None, timeout=None):
        self.fed = data
        if self.rc is None:
            self.rc = getattr(self, "next_rc", 0)

    @property
    def returncode(self):
        return self.rc

    def poll(self):
        return self.rc

    def terminate(self):
        self.terminated = True
        self.rc = -15


@pytest.fixture()
def sw(monkeypatch, tmp_path):
    _Proc.instances = []
    monkeypatch.setattr(xmpp._sp, "Popen", _Proc)
    w = object.__new__(xmpp.MainWindow)
    w.root = None
    temps = []
    w._remember_temp = lambda p: temps.append(p) or True
    w._forget_temp = lambda p: temps.remove(p)
    w._safe_after = _Cap()
    w._show_toast = _Cap()
    monkeypatch.setattr(xmpp, "_load_config", lambda: {"ai": {}})
    started = []

    class _T:
        def __init__(self, target, args, daemon, name):
            started.append((target, args))

        def start(self):
            pass
    monkeypatch.setattr(xmpp.threading, "Thread", _T)
    w.temps, w.started = temps, started
    return w


def test_speak_runs_steps_and_cleans_temp(sw, monkeypatch):
    monkeypatch.setattr(xmpp._tts, "plan_speech", lambda text, s, wav: [
        tts.Step(["/bin/synth", wav], text), tts.Step(["/bin/play", wav],
                                                      None)])
    xmpp.MainWindow._ai_speak_text(sw, "merhaba")
    (target, args), = sw.started
    wav = args[1]
    assert os.path.exists(wav) and sw.temps == [wav]
    target(*args)
    assert [p.argv[0] for p in _Proc.instances] == ["/bin/synth",
                                                    "/bin/play"]
    assert _Proc.instances[0].fed == "merhaba".encode()
    assert not os.path.exists(wav) and sw.temps == []
    assert sw._safe_after.calls == []


def test_new_speech_stops_old_without_error(sw, monkeypatch):
    monkeypatch.setattr(xmpp._tts, "plan_speech", lambda text, s, wav: [
        tts.Step(["/bin/say"], text)])
    xmpp.MainWindow._ai_speak_text(sw, "bir")
    target, args = sw.started[0]
    # Süreç başladı ama bitmedi: durdurma onu sonlandırmalı.
    sw._tts_proc = _Proc(["/bin/say"])          # kendini listeye ekler
    assert xmpp.MainWindow._ai_speaking(sw)
    xmpp.MainWindow._ai_speak_stop(sw)
    assert _Proc.instances[-1].terminated
    assert not xmpp.MainWindow._ai_speaking(sw)
    target(*args)                       # eski nesil: hiç süreç başlatmaz
    assert len(_Proc.instances) == 1 and sw._safe_after.calls == []


def test_real_failure_is_reported(sw, monkeypatch):
    monkeypatch.setattr(xmpp._tts, "plan_speech", lambda text, s, wav: [
        tts.Step(["/usr/bin/espeak-ng"], text)])
    orig = _Proc.__init__

    def failing(self, *a, **k):
        orig(self, *a, **k)
        self.next_rc = 1
    monkeypatch.setattr(_Proc, "__init__", failing)
    xmpp.MainWindow._ai_speak_text(sw, "x")
    target, args = sw.started[0]
    target(*args)
    (args_, _k), = sw._safe_after.calls
    assert args_[1] == sw._ai_speak_failed and args_[2] == "espeak-ng"


def test_missing_engine_shows_hint(sw, monkeypatch):
    shown = []
    monkeypatch.setattr(xmpp.messagebox, "showinfo",
                        lambda title, msg, **k: shown.append(msg))
    monkeypatch.setattr(xmpp._tts.shutil, "which", lambda n: None)
    xmpp.MainWindow._ai_speak_text(sw, "merhaba")
    assert sw.started == [] and "espeak-ng" in shown[0]
    assert sw.temps == []


def test_message_items_and_quit():
    w = object.__new__(xmpp.MainWindow)
    row = types.SimpleNamespace(_body="", _oob="https://x/v.ogg",
                                _local_path="", _retracted=False,
                                _stt_ref="https://x/v.ogg")
    assert "ai_speak" not in xmpp.MainWindow._ai_message_items(w, row)
    w._ai_stt_texts = {"https://x/v.ogg": "yarın geliyorum"}
    assert "ai_speak" in xmpp.MainWindow._ai_message_items(w, row)
    assert xmpp.MainWindow._ai_row_speech_text(w, row) == "yarın geliyorum"
    w._ai_stt_texts = {"https://x/v.ogg": ai.NO_SPEECH}
    assert xmpp.MainWindow._ai_row_speech_text(w, row) == ""
    quit_src = inspect.getsource(xmpp.MainWindow._quit)
    assert quit_src.index("self._ai_speak_stop()") < quit_src.index(
        "_load_config()")
    assert ("ai_speak", "🔊 Sesli oku") in xmpp._actions_ui.AI_MESSAGE_ITEMS
