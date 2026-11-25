"""XEP-0490 Message Displayed Synchronization: okundu bilgisi cihazlar arasında.

Aynı hesabın bir cihazı (ör. telefondaki Conversations) bir sohbeti okuyunca
kendi PEP düğümüne (`urn:xmpp:mds:displayed:0`, öge kimliği = sohbetin çıplak
JID'i) o sohbette gördüğü son mesajın SUNUCU stanza-id'sini yazar; diğer
cihazlar bildirim alıp okunmamış sayacını düzeltir. Biz okuyunca biz yazarız.
XEP-0333 okundu işaretinden farkı: karşı tarafa gitmez (okundu bilgisi kapalı
olsa da çalışır) ve odalarda da çalışır.

- `ReadSync`: bellekte, sınırlı eşleme; Tk/ağ/DB YOK (masaüstü ve web köprüsü
  ortak kullanır).
- `MDSMixin`: XMPPBot tarafı. Stanza-id'leri ayrı bir gözlemci handler'la
  okur; şifreleme (OMEMO/PGP) yollarına dokunmaz.
"""
from collections import OrderedDict, deque

from xmppcore.constants import _log
from xmppcore.helpers import _get_xep, _stanza_msg_id

NS = "urn:xmpp:mds:displayed:0"
_SID_TAG = "{urn:xmpp:sid:0}stanza-id"
_SEEN_PER_CHAT = 300          # "daha eski okunmuş mesaj" tanıma penceresi


def server_stanza_id(xml, by: str) -> str:
    """`by`'nin (arşiv sahibi: 1:1'de kendi çıplak JID'imiz, odada odanın
    kendisi) eklediği stanza-id; yoksa ""."""
    if xml is None or not by:
        return ""
    want = by.lower()
    for el in xml.findall(_SID_TAG):
        if (el.get("by") or "").lower() == want and el.get("id"):
            return el.get("id")
    return ""


class ReadSync:
    """Okunmamış sayacını başka cihazın okuduğu yere göre düzeltmek ve kendi
    okuduğumuzu yayımlamak için gereken, sınırlı bellek durumu."""

    def __init__(self, max_ids: int = 4000):
        self._max = max_ids
        self._sid: OrderedDict = OrderedDict()   # (sohbet, mid) → sunucu stanza-id
        self._unread: dict = {}                  # sohbet → okunmamış gelen mid'ler (sırayla)
        self._seen: dict = {}                    # sohbet → son görülen gelen mid'ler
        self._published: dict = {}               # sohbet → son yayımlanan/öğrenilen sid
        self._pending: dict = {}                 # sohbet → sid'i henüz bilinmeyen yayın

    def note_ids(self, jid, mid, sid) -> bool:
        """Gelen mesajın sunucu stanza-id'si. True: bekleyen yayın artık
        yapılabilir (stanza-id mesaj olayından sonra geldi)."""
        if not (jid and mid and sid):
            return False
        key = (jid, mid)
        self._sid[key] = sid
        self._sid.move_to_end(key)
        while len(self._sid) > self._max:
            self._sid.popitem(last=False)
        return self._pending.get(jid) == mid

    def note_incoming(self, jid, mid, unread: bool):
        """Başkasından gelen mesaj; `unread`: okunmamış sayacını artırdı."""
        self._seen.setdefault(jid, deque(maxlen=_SEEN_PER_CHAT)).append(mid or "")
        if unread:
            self._unread.setdefault(jid, []).append(mid or "")

    def clear(self, jid):
        """Sohbet bu cihazda okundu (açıldı, yanıtlandı, okundu işareti geldi)."""
        self._unread.pop(jid, None)

    def _matches(self, jid, mid, sid) -> bool:
        return bool(mid) and (mid == sid or self._sid.get((jid, mid)) == sid)

    def apply(self, jid, sid, current: int):
        """Başka cihaz `sid`'e kadar okudu: yeni okunmamış sayısı; değişiklik
        yoksa None. `current`: arayüzdeki sayaç (kaynak gerçek budur)."""
        self._published[jid] = sid           # kendi yayınımızın yankısı da buraya düşer
        ids = self._unread.get(jid, [])
        for i in range(len(ids) - 1, -1, -1):
            if self._matches(jid, ids[i], sid):
                rest = ids[i + 1:]
                if rest:
                    self._unread[jid] = rest
                else:
                    self._unread.pop(jid, None)
                return len(rest) if len(rest) != current else None
        if any(self._matches(jid, m, sid) for m in self._seen.get(jid, ())):
            return None                      # okunmamışlardan eski, bilinen mesaj
        # Bilinmeyen sid: diğer cihaz çevrimiçi ve sohbetteki en yeni mesajı
        # gördü (bizdeki her şey ondan eski) → hepsi okundu
        self._unread.pop(jid, None)
        return 0 if current else None

    def publish_sid(self, jid, mid) -> str:
        """`mid`'e kadar okuduk: yayımlanacak sunucu stanza-id'si. Bilinmiyorsa
        bekletir (""), aynısı zaten yayımlandıysa "" (tekrar yok)."""
        sid = self._sid.get((jid, mid)) if mid else None
        if not sid:
            if mid:
                self._pending[jid] = mid
            return ""
        self._pending.pop(jid, None)
        if self._published.get(jid) == sid:
            return ""
        self._published[jid] = sid
        return sid


class MDSMixin:
    """XMPPBot: stanza-id gözlemi, PEP bildirimi ve yayımlama."""

    def _mds_observe(self, msg):
        """Her gelen mesajın sunucu stanza-id'sini GUI'ye bildir. Ayrı bir
        handler'dır: mesajı işleyen (ve şifre çözen) yollara dokunmaz."""
        try:
            mtype = msg["type"]
            if mtype not in ("chat", "normal", "groupchat"):
                return
            room = mtype == "groupchat"
            chat = str(msg["from"].bare)
            by = chat if room else str(self.boundjid.bare)
            if not chat or chat == str(self.boundjid.bare):
                return
            sid = server_stanza_id(msg.xml, by)
            mid = _stanza_msg_id(msg)
        except Exception:
            return
        if sid and mid:
            self.gui_q.put(("msg_ids", {"jid": chat, "mid": mid, "sid": sid}))

    def _mds_observe_carbon(self, msg):
        """Başka cihazımıza gelen mesajın kopyası (XEP-0280)."""
        try:
            inner = msg["carbon_received"]
        except Exception:
            return
        self._mds_observe(inner)

    def _on_mds_publish(self, msg):
        """Kendi hesabımızın MDS düğümünden bildirim: bir cihaz okudu."""
        try:
            frm = str(msg["from"].bare)
            if frm and frm != str(self.boundjid.bare):
                return                       # yalnız kendi hesabımızın PEP'i
            item = msg["pubsub_event"]["items"]["item"]
            chat = str(item["id"] or "")
            sid = str(item["displayed"]["stanza_id"]["id"] or "")
        except Exception:
            return
        if chat and sid:
            self.gui_q.put(("mds_displayed", {"jid": chat, "sid": sid}))

    def mds_flag(self, chat, sid, room=False):
        """Sohbeti `sid`'e kadar okundu olarak PEP'e yaz (özel; karşı tarafa
        gitmez). GUI thread'inden çağrılabilir."""
        def _do():
            try:
                xep = _get_xep(self, "xep_0490")
                displayed = xep.stanza.Displayed()
                displayed["stanza_id"]["id"] = sid
                displayed["stanza_id"]["by"] = (
                    chat if room else str(self.boundjid.bare))
                _get_xep(self, "xep_0223").store(displayed, node=NS, id=chat)
            except Exception:
                _log.debug("MDS yayımlanamadı", exc_info=True)
        self._dispatch_loop(_do)
