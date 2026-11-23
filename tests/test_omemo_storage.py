"""OMEMO anahtar deposunun dayanıklılığı ve izinleri.

Önceden `_store` her güncellemede dosyayı `write_text` ile yerinde kesip
yeniden yazıyordu (yarıda kalırsa bozuk JSON), açılışta okunamayan dosyayı
`except: pass` ile yok sayıyordu (boş depo → yeni kimlik → ilk yazmada eski
anahtarların üzerine yazılır) ve özel anahtarları 0644 ile bırakıyordu.
"""
import asyncio
import json
import os
import stat

import pytest

import xmpp

pytestmark = pytest.mark.skipif(not getattr(xmpp, "HAS_OMEMO", False),
                                reason="OMEMO kütüphaneleri kurulu değil")


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


def _store(st, key, value):
    asyncio.run(st._store(key, value))


def test_store_is_atomic_and_private(tmp_path, monkeypatch):
    path = tmp_path / "a_at_b.json"
    st = xmpp._OmemoStorageImpl(path)
    _store(st, "k", {"v": 1})
    assert json.loads(path.read_text("utf-8")) == {"k": {"v": 1}}
    assert _mode(path) == 0o600

    # yazma yarıda kesilirse eski içerik bozulmadan kalır, geçici dosya kalmaz
    def boom(*_a, **_k):
        raise OSError("disk dolu")
    monkeypatch.setattr(xmpp.os, "fsync", boom)
    with pytest.raises(OSError):
        _store(st, "k", {"v": 2})
    assert json.loads(path.read_text("utf-8")) == {"k": {"v": 1}}
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a_at_b.json"]


def test_delete_persists(tmp_path):
    path = tmp_path / "a_at_b.json"
    st = xmpp._OmemoStorageImpl(path)
    _store(st, "x", 1)
    _store(st, "y", 2)
    asyncio.run(st._delete("x"))
    assert json.loads(path.read_text("utf-8")) == {"y": 2}
    assert json.loads(path.read_text("utf-8")) == xmpp._OmemoStorageImpl(path)._data


@pytest.mark.parametrize("content", ["{yarım".encode(), b"", b"[1, 2]", b"\xff\xfe"])
def test_unreadable_store_is_backed_up_not_overwritten(tmp_path, content):
    path = tmp_path / "a_at_b.json"
    path.write_bytes(content)
    st = xmpp._OmemoStorageImpl(path)
    assert st._data == {}
    assert not path.exists()
    backups = [p for p in tmp_path.iterdir() if ".bozuk-" in p.name]
    assert len(backups) == 1
    assert backups[0].read_bytes() == content
    _store(st, "k", 1)  # yeni kimlik yedeğe dokunmaz
    assert backups[0].read_bytes() == content


def test_existing_world_readable_store_is_tightened(tmp_path):
    path = tmp_path / "a_at_b.json"
    path.write_text(json.dumps({"k": 1}), "utf-8")
    path.chmod(0o644)
    st = xmpp._OmemoStorageImpl(path)
    assert st._data == {"k": 1}
    assert _mode(path) == 0o600


def test_key_dir_is_private(tmp_path):
    d = tmp_path / "omemo"
    xmpp._omemo_private_dir(d)
    assert _mode(d) == 0o700
    d.chmod(0o755)
    xmpp._omemo_private_dir(d)
    assert _mode(d) == 0o700
