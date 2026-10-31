#!/usr/bin/env python3
"""Telefon + masaüstü çoklu cihaz denetimi (kullanıcıyla birlikte koşulur).

Kullanım:
    ./xmpp-client.sh                      # gerçek hesap, masaüstü açık
    .venv-xmpp/bin/python tools/phone_check.py [--timeout SN]

Telefon aynı hesaba bağlı olmalı (carbons). Betik her adımda ne yapılacağını
yazar, sonra masaüstünün mesaj DB'sinde beklenen değişikliği bekler:

1. Telefondan gönderilen mesaj masaüstünde "Ben" olarak kaydedilir.
2-4. Telefonda aynı mesaj düzenlenir, tepki alır, geri çekilir → DB'ye yansır.
5. Telefonda okunan sohbet masaüstünde okunmamış kalmaz (göz kontrolü).
6. Masaüstünden OMEMO sohbetine resim (aesgcm://) → telefonda açılır mı.
7. Telefondan OMEMO sohbetine resim → masaüstünde görünür mü.

DB salt okunur açılır (uygulamanın yazmasıyla yarışmaz) ve mesaj metni
yazdırılmaz: yalnız satır kimliği, sohbet ve bayraklar görünür.
"""
import argparse
import hashlib
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RETRACTED = "🚫 Bu mesaj silindi"          # xmppcore.ai.RETRACTED_BODY (DB'de Türkçe)
ME = "Ben"                                  # kendi tepkilerimin göndericisi


def connect(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def last_id(db):
    return db.execute("SELECT COALESCE(MAX(id), 0) FROM messages").fetchone()[0]


def new_own_rows(db, after, encrypted_file=False):
    """`after`'dan sonra eklenen kendi mesajlarım (sistem satırları hariç)."""
    sql = ("SELECT id, jid, mid, encrypted, oob FROM messages "
           "WHERE id > ? AND is_me = 1 AND COALESCE(tag, '') != 'sys'")
    if encrypted_file:
        sql += " AND encrypted = 1 AND oob LIKE 'aesgcm://%'"
    return [dict(zip(("id", "jid", "mid", "encrypted", "oob"), r))
            for r in db.execute(sql + " ORDER BY id", (after,))]


def body_digest(db, row_id):
    row = db.execute("SELECT body FROM messages WHERE id = ?", (row_id,)).fetchone()
    body = row[0] if row else None
    return None if body is None else hashlib.sha256(body.encode()).hexdigest()


def is_retracted(db, row_id):
    row = db.execute("SELECT body FROM messages WHERE id = ?", (row_id,)).fetchone()
    return bool(row) and row[0] == RETRACTED


def reactions_on(db, jid, mid):
    return set(db.execute(
        "SELECT emoji, sender FROM reactions WHERE jid = ? AND mid = ?",
        (jid, mid)))


def wait_for(check, timeout, interval=1.0, clock=time.monotonic, sleep=time.sleep):
    """`check()` doğru (truthy) değer verene kadar bekle; zaman aşımında None."""
    deadline = clock() + timeout
    while True:
        value = check()
        if value:
            return value
        if clock() >= deadline:
            return None
        sleep(interval)


# ── Etkileşimli akış ────────────────────────────────────────────────────────
def _ask(prompt):
    try:
        return input(prompt).strip().lower()
    except EOFError:
        return "a"


def _step(title, todo):
    print(f"\n── {title}\n   {todo}")
    return _ask("   Hazır olunca Enter (atlamak için a): ") != "a"


def _yes(question):
    return _ask(f"   {question} (e/h): ").startswith("e")


def run(db, timeout):
    results = {}

    def record(name, ok, note=""):
        results[name] = ("GEÇTİ" if ok else "KALDI") if ok is not None else "ATLANDI"
        print(f"   → {results[name]}{'  ' + note if note else ''}")

    # 1) Telefondan giden mesaj
    row = None
    start = last_id(db)
    if _step("1/7 Telefondan mesaj",
             "Telefondan bir kişiye kısa bir mesaj gönder (OMEMO kapalı sohbet "
             "de olur)."):
        rows = wait_for(lambda: new_own_rows(db, start), timeout)
        row = rows[-1] if rows else None
        record("1 telefon→masaüstü", bool(row),
               f"satır #{row['id']} · {row['jid']}" if row else
               "masaüstü DB'sine kendi mesajım olarak düşmedi")
    else:
        record("1 telefon→masaüstü", None)

    # 2-4) Aynı mesajda düzenleme, tepki, geri çekme
    for name, title, todo, check in (
        ("2 düzenleme", "2/7 Düzenleme", "Telefonda AYNI mesajı düzenle.",
         lambda r, before: body_digest(db, r["id"]) != before[0]),
        ("3 tepki", "3/7 Tepki", "Telefonda aynı mesaja bir tepki (emoji) ver.",
         lambda r, before: reactions_on(db, r["jid"], r["mid"]) - before[1]),
        ("4 geri çekme", "4/7 Geri çekme", "Telefonda aynı mesajı herkesten sil.",
         lambda r, before: is_retracted(db, r["id"])),
    ):
        if not (row and row["mid"]):
            print(f"\n── {title}\n   1. adım olmadan yapılamaz.")
            record(name, None)
            continue
        before = (body_digest(db, row["id"]),
                  reactions_on(db, row["jid"], row["mid"]))
        if _step(title, todo):
            ok = wait_for(lambda: check(row, before), timeout)
            record(name, bool(ok))
        else:
            record(name, None)

    # 5) Başka cihazda okundu (okunmamış sayısı bellekte: göz kontrolü)
    if _step("5/7 Telefonda okundu",
             "Masaüstünde okunmamışı olan bir sohbeti telefonda aç ve oku."):
        record("5 okundu bilgisi",
               _yes("Masaüstündeki okunmamış rozeti ve asistanın "
                    "'📬 Okunmamışları özetle' sayısı sıfırlandı mı?"))
    else:
        record("5 okundu bilgisi", None)

    # 6) Masaüstünden şifreli resim → telefon
    start = last_id(db)
    if _step("6/7 Masaüstü→telefon şifreli resim",
             "Masaüstünde OMEMO açık bir sohbete bir resim gönder."):
        rows = wait_for(lambda: new_own_rows(db, start, encrypted_file=True),
                        timeout)
        if not rows:
            record("6 şifreli resim gönder", False,
                   "aesgcm:// satırı oluşmadı (şifreli yükleme yok)")
        else:
            record("6 şifreli resim gönder",
                   _yes("Resim telefonda açıldı mı?"), f"satır #{rows[-1]['id']}")
    else:
        record("6 şifreli resim gönder", None)

    # 7) Telefondan şifreli resim → masaüstü (carbon kopyası)
    start = last_id(db)
    if _step("7/7 Telefon→masaüstü şifreli resim",
             "Telefondan OMEMO açık bir sohbete bir resim gönder."):
        rows = wait_for(lambda: new_own_rows(db, start, encrypted_file=True),
                        timeout)
        if not rows:
            record("7 şifreli resim al", False,
                   "masaüstüne aesgcm:// kopyası gelmedi")
        else:
            record("7 şifreli resim al",
                   _yes("Resim masaüstünde görünüyor mu?"),
                   f"satır #{rows[-1]['id']}")
    else:
        record("7 şifreli resim al", None)

    print("\n══ Özet")
    for name, verdict in results.items():
        print(f"   {verdict:8} {name}")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--timeout", type=float, default=120,
                        help="her adımda DB değişikliği için bekleme (sn)")
    args = parser.parse_args()
    from xmppcore.constants import _DB_PATH
    if not os.path.exists(_DB_PATH):
        raise SystemExit(f"✗ Mesaj DB'si yok: {_DB_PATH}")
    print(f"Mesaj DB'si (salt okunur): {_DB_PATH}")
    results = run(connect(_DB_PATH), args.timeout)
    return 1 if "KALDI" in results.values() else 0


if __name__ == "__main__":
    sys.exit(main())
