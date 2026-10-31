"""tools/phone_check.py: telefon testinin adımları DB değişikliklerini doğru
tanır — gerçek şema (xmppcore.storage) üzerinde, telefon hareketleri soru
anında DB'ye yazılarak taklit edilir. Ağ ve Tk yok."""
import importlib.util
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

import xmpp  # noqa: E402
from xmppcore import storage as st  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "phone_check", os.path.join(os.path.dirname(__file__), "..", "tools",
                                "phone_check.py"))
pc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pc)


@pytest.fixture()
def db(monkeypatch, tmp_path):
    path = str(tmp_path / "msgs.db")
    monkeypatch.setattr(xmpp, "_DB_PATH", path)
    xmpp._db_conn = None
    st._db_store_msg("ali@x.im", "ali", "eski", False, "10:00", "them")
    yield path
    if xmpp._db_conn is not None:
        xmpp._db_conn.close()
    xmpp._db_conn = None


def _writer():
    return st._get_db()


def test_markers_match_the_app():
    from xmppcore.ai import RETRACTED_BODY
    assert pc.RETRACTED == RETRACTED_BODY


def test_wait_for_times_out_without_real_sleep():
    t = [0.0]
    assert pc.wait_for(lambda: None, 5, clock=lambda: t[0],
                       sleep=lambda s: t.__setitem__(0, t[0] + s)) is None
    assert t[0] >= 5
    assert pc.wait_for(lambda: "ok", 5, sleep=lambda s: None) == "ok"


def test_full_flow_detects_each_phone_action(db, monkeypatch, capsys):
    ro = pc.connect(db)
    w = _writer()
    state = {}

    def phone(prompt):
        """Betik "Enter" beklerken telefonun yaptığını DB'ye yaz."""
        if "(e/h)" in prompt:
            return "e"
        out = capsys.readouterr().out
        if "1/7" in out:
            st._db_store_msg("ali@x.im", "Ben", "telefondan", True, "10:01",
                             "me", mid="ph-1")
        elif "2/7" in out:
            w.execute("UPDATE messages SET body='düzeltildi' WHERE mid='ph-1'")
            w.commit()
        elif "3/7" in out:
            st._db_save_reaction("ali@x.im", "ph-1", "👍", "Ben")
        elif "4/7" in out:
            w.execute("UPDATE messages SET body=? WHERE mid='ph-1'",
                      (pc.RETRACTED,))
            w.commit()
        elif "6/7" in out or "7/7" in out:
            state["n"] = state.get("n", 0) + 1
            st._db_store_msg("ali@x.im", "Ben", "", True, "10:02", "me",
                             oob=f"aesgcm://h/{state['n']}#k", encrypted=True,
                             mid=f"img-{state['n']}")
        return ""

    monkeypatch.setattr("builtins.input", phone)
    results = pc.run(ro, timeout=2)
    assert set(results.values()) == {"GEÇTİ"}, results
    assert len(results) == 7
    assert "telefondan" not in capsys.readouterr().out   # metin yazdırılmaz


def test_missing_phone_message_fails_and_skips_dependents(db, monkeypatch):
    ro = pc.connect(db)
    answers = iter(["", "a", "a", "a", "a"])            # 1 dene, gerisini atla
    monkeypatch.setattr("builtins.input", lambda p: next(answers, "a"))
    monkeypatch.setattr(pc, "wait_for", lambda check, timeout: check() or None)
    results = pc.run(ro, timeout=0)
    assert results["1 telefon→masaüstü"] == "KALDI"
    assert results["2 düzenleme"] == results["4 geri çekme"] == "ATLANDI"


def test_plain_image_is_not_counted_as_encrypted(db):
    ro = pc.connect(db)
    start = pc.last_id(ro)
    st._db_store_msg("ali@x.im", "Ben", "", True, "10:03", "me",
                     oob="https://h/plain.png", mid="p1")
    assert pc.new_own_rows(ro, start)                       # kendi mesajım
    assert not pc.new_own_rows(ro, start, encrypted_file=True)


def test_db_is_opened_read_only(db):
    import sqlite3
    ro = pc.connect(db)
    with pytest.raises(sqlite3.OperationalError):
        ro.execute("DELETE FROM messages")
