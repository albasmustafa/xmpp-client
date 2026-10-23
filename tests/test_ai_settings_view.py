"""AI Ayarları penceresi (sahte tk): yeni seçenekler kaydedilir.

Kanıtlar:
- Kaydet tüm ayar anahtarlarını (yeni asistan, sesli okuma ve MCP
  seçenekleri dahil) döndürür; varsayılanlar güvenlidir (MCP kapalı,
  şifreli içerik MCP'ye kapalı, satır içi öneri ve taslaklar kapalı).
- Değiştirilen onay kutuları değeri taşır; load_settings ile doğrulanır.
- MCP kayıt komutu gösterilir ve panoya kopyalanabilir.
"""
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_ai_dialog_view import _W, _find, fake_tk  # noqa: E402,F401

import ui.dialogs.ai as ui_ai  # noqa: E402
import xmpp  # noqa: E402
from xmppcore import ai  # noqa: E402


class _Notebook(_W):
    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self.tabs = []

    def add(self, child, text=""):
        self.tabs.append((text, child))


@pytest.fixture()
def dialog(request, monkeypatch):
    request.getfixturevalue("fake_tk")
    ns = ui_ai.tk
    monkeypatch.setattr(ui_ai, "tk", types.SimpleNamespace(
        **vars(ns), Radiobutton=_W))
    monkeypatch.setattr(ui_ai, "ttk", types.SimpleNamespace(
        **vars(ui_ai.ttk), Notebook=_Notebook))
    monkeypatch.setattr(xmpp, "_make_popover", lambda *a, **k: None)
    saved = []
    dlg = ui_ai.show_settings(
        _W(), ai.load_settings({}), False, ai.WHISPER_MODELS,
        lambda values, key: saved.append((values, key)),
        lambda *a: None, tts_engines=ai.TTS_ENGINES,
        keep_alive_choices=ai.KEEP_ALIVE_CHOICES,
        gpu_choices=ai.OLLAMA_GPU_CHOICES,
        mcp_command="claude mcp add xmpp -- py /p/xmpp_mcp.py")
    return dlg, saved


def _save(dlg):
    _find(dlg, "Kaydet").kw["command"]()


def _checkbox(dlg, text_start):
    stack = [dlg]
    while stack:
        w = stack.pop()
        if str(w.kw.get("text", "")).startswith(text_start):
            return w.kw["variable"]
        stack.extend(w.children)
    raise AssertionError(text_start)


def test_defaults_are_safe_and_complete(dialog):
    dlg, saved = dialog
    _save(dlg)
    values, key = saved[0]
    assert key is None
    assert set(values) == set(ai.DEFAULTS) - {"claude_api_key"}
    assert values["mcp_enabled"] is False
    assert values["mcp_include_encrypted"] is False
    assert values["inline_complete"] is False and values["away_drafts"] is \
        False
    assert values["tts_engine"] == "auto" and values["tts_lang"] == "tr"
    assert values["ollama_gpu"] == "auto"


def test_toggles_are_saved(dialog):
    dlg, saved = dialog
    for text in ("Yazarken satır içi", "Uzaktayken gelen", "MCP erişimi"):
        _checkbox(dlg, text).set(True)
    _save(dlg)
    s = ai.load_settings({"ai": saved[0][0]})
    assert s["inline_complete"] and s["away_drafts"] and s["mcp_enabled"]
    assert not s["mcp_include_encrypted"]


def test_mcp_command_copy(dialog):
    dlg, _saved = dialog
    assert _find(dlg, "claude mcp add xmpp -- py /p/xmpp_mcp.py")
    _find(dlg, "📋").click()
    assert dlg.clip == "claude mcp add xmpp -- py /p/xmpp_mcp.py"


def test_settings_are_grouped_into_tabs(dialog):
    dlg, _saved = dialog
    nb = next(c for c in dlg.children if isinstance(c, _Notebook))
    titles = [t for t, _p in nb.tabs]
    assert titles == ["🤖 Model", "☁ Claude", "✨ Özellikler", "🎙 Ses",
                      "🔌 MCP"]
    pages = dict(nb.tabs)
    assert _find(pages["🤖 Model"], "Sohbet modeli")
    assert _find(pages["🤖 Model"], "Model sıcak")
    assert _find(pages["🎙 Ses"], "Whisper modeli")
    assert _find(pages["🎙 Ses"], "Motor")
    assert _find(pages["🔌 MCP"], "📋")
    assert _find(pages["☁ Claude"], "API anahtarı")
    assert _find(pages["🤖 Model"], "Whisper modeli") is None
