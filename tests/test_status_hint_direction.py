"""Durum sözü yerel eşlemesi ters yöndeki isteği o duruma çevirmemeli.

Kanıt: `status_hint("Durumumu meşgulden çıkar")` ve "meşgul yapma" → dnd;
model doğru planlasa (online) bile `normalize_plan` onu dnd'ye çeviriyordu.
Çıkış ("-den/-dan çıkar") ve olumsuz emir ("yapma") belirsizdir: karar
modele kalır (onay kartı yine gösterilir).
"""
import pytest

from xmppcore import agent


@pytest.mark.parametrize("text", [
    "Durumumu meşgulden çıkar", "meşgulden çık", "uzaktan dön",
    "durumumu uzakta modundan çıkar", "Durumumu meşgul yapma",
    "beni meşgul yapmayın", "çevrimiçiden çıkar"])
def test_leaving_or_negated_status_is_left_to_model(text):
    assert agent.status_hint(text) is None
    assert agent.quick_intent(text) is None
    plan = agent.normalize_plan({"action": "set_status", "status": "online"},
                                text)
    assert plan["status"] == "online"


@pytest.mark.parametrize("text, show", [
    ("Durumumu meşgul yap", "dnd"), ("meşgulüm", "dnd"),
    ("uzaktayım", "away"), ("durumumu rahatsız etmeyin yap", "dnd"),
    ("rahatsız etme", "dnd"), ("Uzun süre uzaktayım", "xa"),
    ("çevrimiçi yap", "online")])
def test_plain_status_words_still_map(text, show):
    assert agent.status_hint(text) == show
