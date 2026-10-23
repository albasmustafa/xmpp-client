"""Gerçek modelde görülen kalite hatalarına karşı istem kuralları.

Kanıt (gemma4:e2b-it-qat, 2026-10-23 Cuma; scratchpad smoke_model.py):
- M1 görev çıkarma: "yarın 10'da, A blok 3. katta toplantı" hiç çıkmadı
  (yalnız rapor görevi geldi).
- M2 özetler: "Ben sunumu hazırlayacak" (kullanıcı üçüncü şahıs) ve
  "Ali'den bütçe raporu istendi" (istek yönü ters: Ali, kullanıcıdan istedi).
- "Neler kaçırdım?" (kişi kuralı eklenince 3/3 koşuda) "Acil bir durum yok"
  diye başladı; oysa bugün 17:00 teslimli bir istek ve yanıt bekleyen soru
  vardı: ilk bölüm "bekleyen her şey" olarak açıkça tarif edilir.
- M3 yanıt önerileri bekleyen sorulara yanıt vermiyordu ("Hangi konuda bilgi
  verebilirim?").
"""
from datetime import datetime

from xmppcore import ai

FRIDAY = datetime(2026, 10, 23, 14, 0)


def test_actions_request_asks_for_every_meeting():
    system, _user = ai.actions_request("t", FRIDAY, "Türkçe")
    assert "every meeting" in system


def test_summaries_address_user_and_keep_request_direction():
    for system in (ai.summary_request("t", "Türkçe")[0],
                   ai.digest_request("t", "Türkçe")[0]):
        assert "second person" in system
        assert "who asked whom" in system


def test_suggestions_answer_open_questions():
    system, _user = ai.suggest_request("t")
    assert "answer the questions or requests" in system


def test_digest_lists_waiting_items_first():
    system, _user = ai.digest_request("t", "Türkçe")
    assert "everything waiting for the user" in system
    assert "Never claim that nothing is waiting" in system
