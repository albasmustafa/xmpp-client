"""FAZ 4C FINAL: chat modül sınır/ownership contract'ları.

AST tabanlı (docstring yanlış-pozitiflerinden bağımsız) kaynak kontratları +
regression test varlık kontrolü. Davranış testleri ilgili modül dosyalarında.
"""
import ast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAT = os.path.join(ROOT, "ui", "chat")
MODULES = ("shell", "render", "identity", "reactions", "composer", "typing",
           "actions", "media", "audio", "history")


def _src(name):
    with open(os.path.join(CHAT, f"{name}.py"), encoding="utf-8") as f:
        return f.read()


def _tree(name):
    return ast.parse(_src(name))


# ── 1) import graph: no xmpp/domain imports ─────────────────────────────────
def test_no_ui_chat_module_imports_xmpp_or_domain():
    allowed_roots = {"tkinter", "collections"}
    for name in MODULES:
        for n in ast.walk(_tree(name)):
            if isinstance(n, ast.Import):
                for a in n.names:
                    assert a.name.split(".")[0] in allowed_roots, (name, a.name)
            elif isinstance(n, ast.ImportFrom):
                root = (n.module or "").split(".")[0]
                assert root in allowed_roots, (name, n.module)


# ── 2) worker/network/timer ownership: none in ui/chat ──────────────────────
TIMER_ALLOWED = {"shell"}  # 4C-1 mevcut scroll presentation after(10)


def test_no_ui_chat_module_owns_worker_network_or_timer():
    for name in MODULES:
        for n in ast.walk(_tree(name)):
            if isinstance(n, ast.Call):
                attr = getattr(n.func, "attr", None)
                assert attr not in {"Thread", "urlopen", "Popen",
                                    "run_coroutine_threadsafe"}, (name, attr)
                if attr in ("after", "after_cancel", "after_idle"):
                    assert name in TIMER_ALLOWED, f"{name}.py timer: {attr}"


# ── 3) state tek sahibi: xmpp.py ────────────────────────────────────────────
def _xmpp_tree():
    with open(os.path.join(ROOT, "xmpp.py"), encoding="utf-8") as f:
        return ast.parse(f.read())


def _assign_count(tree, attr):
    c = 0
    for n in ast.walk(tree):
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Attribute):
            if n.target.attr == attr:
                c += 1
        elif isinstance(n, ast.Assign):
            for t0 in n.targets:
                if isinstance(t0, ast.Attribute) and t0.attr == attr:
                    c += 1
    return c


def test_bubble_widgets_and_photo_refs_single_owner():
    tree = _xmpp_tree()
    assert _assign_count(tree, "_bubble_widgets") == 1
    assert _assign_count(tree, "_photo_refs") == 1
    # ui/chat modülleri bu state'i assign etmiyor
    for name in MODULES:
        for n in ast.walk(_tree(name)):
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, ast.Attribute):
                        assert t.attr not in {"_bubble_widgets",
                                              "_photo_refs"}, name


# ── 4) ChatShell widget owner ───────────────────────────────────────────────
def test_chatshell_remains_widget_owner():
    from ui.chat.shell import ChatShell
    assert len(ChatShell.LEGACY_REFS) == 26
    assert hasattr(ChatShell, "show_chat")
    assert hasattr(ChatShell, "show_empty_state")


# ── 5) MainWindow lifecycle otoritesi ───────────────────────────────────────
def test_mainwindow_owns_lifecycle_resources():
    from xmpp import MainWindow
    for m in ("_safe_after", "_after", "_quit", "append_safe"):
        assert hasattr(MainWindow, m) or m == "append_safe"
    tree = _xmpp_tree()
    assert _assign_count(tree, "_after_ids") == 1
    for name in MODULES:
        src = _src(name)
        assert "_safe_after" not in src
        assert "gui_q" not in src


# ── 6) modül-spesifik sınır kontratları ─────────────────────────────────────
def test_identity_is_stateless():
    assert "self." not in _src("identity")


def test_reactions_owns_no_state():
    src = _src("reactions")
    assert "self._reactions" not in src and "_my_reactions" not in src
    assert "save_reaction" not in src and "send_reaction" not in src


def test_history_knows_no_mam_or_domain():
    src = _src("history")
    assert "chats" not in src and "mam_results" not in src
    for n in ast.walk(_tree("history")):
        if isinstance(n, ast.Name):
            assert n.id != "bot"
        if isinstance(n, ast.Attribute):
            assert n.attr != "bot"


def test_composer_has_no_send_protocol():
    src = _src("composer")
    for token in ("send_chat", "send_gc", "send_reply", "send_correction"):
        assert token not in src


def test_actions_has_no_domain_mutation():
    src = _src("actions")
    for token in ("send_reaction", "_toggle_reaction", "_edit_message",
                  "_retract_message", "send_correction"):
        assert token not in src


def test_media_audio_no_engine_or_decode():
    assert "ImageTk" not in _src("media")
    for token in ("pyaudio", "PyAudio", "wave.open", "subprocess",
                  "GStreamer"):
        assert token not in _src("audio")


def test_typing_has_no_timer_state():
    src = _src("typing")
    assert "_typing_anim_id" not in src and "_typing_send_id" not in src
    for n in ast.walk(_tree("typing")):
        if isinstance(n, ast.Call):
            assert getattr(n.func, "attr", None) not in (
                "after", "after_cancel", "after_idle")


# ── 7) modül docstring sınır beyanı ─────────────────────────────────────────
def test_modules_declare_boundary_docstring():
    for name in MODULES:
        doc = ast.get_docstring(_tree(name)) or ""
        assert len(doc) > 40, name


# ── 8) J/T/M/A regression testleri hâlâ mevcut ──────────────────────────────
REGRESSION_TESTS = {
    "tests/test_pre_bugfixes.py": ("test_mam_stale_result_after_clear_is_benign",
                                   "test_local_edit_updates_correct_row_history_and_db",
                                   "test_local_retract_updates_correct_row_maps_and_db",
                                   "test_date_separator_uses_message_date_and_dedupes"),
    "tests/test_chat_typing.py": ("test_t1_paused_targets_original_after_switch",
                                  "test_t2_switch_clears_foreign_indicator"),
    "tests/test_chat_media.py": ("test_place_image_skips_destroyed_holder",
                                 "test_image_download_error_late_callback_skips_destroyed_holder",
                                 "test_fullscreen_error_late_callback_skips_destroyed_label"),
    "tests/test_chat_audio.py": ("test_place_audio_skips_destroyed_holder",
                                 "test_place_audio_fallback_skips_destroyed_holder",
                                 "test_waveform_late_bars_callback_skips_destroyed_widgets"),
}


def test_verified_fix_regressions_still_present():
    for path, names in REGRESSION_TESTS.items():
        with open(os.path.join(ROOT, path), encoding="utf-8") as f:
            src = f.read()
        for n in names:
            assert f"def {n}" in src, (path, n)
