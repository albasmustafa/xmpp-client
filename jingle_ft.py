"""Jingle dosya transferi — XEP-0166 / XEP-0234 / XEP-0261 (IBB) çekirdeği.

GUI'den bağımsızdır; olaylar ``xmpp.gui_q`` kuyruğuna ``(kind, data)``
biçiminde bırakılır. Veri akışı slixmpp'in xep_0047 (IBB) altyapısıyla
yapılır: XEP-0261, veri aşamasında düz XEP-0047 elemanları tanımlar.
"""

import asyncio
import base64
import hashlib
import mimetypes
import os
import uuid
from dataclasses import dataclass, field

from slixmpp import Iq
from slixmpp.exceptions import XMPPError
from slixmpp.plugins.xep_0234.stanza import File
from slixmpp.xmlstream import ET, ElementBase, register_stanza_plugin

from xmppcore.i18n import tr as _tr

NS_JINGLE = "urn:xmpp:jingle:1"
NS_FT = "urn:xmpp:jingle:apps:file-transfer:5"
NS_IBB = "urn:xmpp:jingle:transports:ibb:1"
NS_HASHES = "urn:xmpp:hashes:2"

DEFAULT_BLOCK_SIZE = 4096
MAX_BLOCK_SIZE = 8192
ACCEPT_TIMEOUT = 60.0
DATA_TIMEOUT = 30.0
MAX_FILE_BYTES = 2 * 1024 ** 3


class Reason(ElementBase):
    """session-terminate sebebi (XEP-0166 §7.3)."""
    name = "reason"
    namespace = NS_JINGLE
    plugin_attrib = "reason"
    bool_interfaces = {"success", "cancel", "decline", "failed"}
    interfaces = {"text"} | bool_interfaces
    sub_interfaces = {"text"}


class TransportIBB(ElementBase):
    """XEP-0261 IBB transport bilgisi."""
    name = "transport"
    namespace = NS_IBB
    plugin_attrib = "transport_ibb"
    interfaces = {"block_size", "sid", "stanza"}

    def get_block_size(self):
        return int(self._get_attr("block-size", "0") or 0)

    def set_block_size(self, value):
        self._set_attr("block-size", str(value))

    def del_block_size(self):
        self._del_attr("block-size")


class _PluginHost(ElementBase):
    """Eklenti yerine bütün bir stanza nesnesi atanabilen Jingle öğesi.

    slixmpp'te ``jingle["content"] = content`` gibi bir atama varsayılan
    olarak yalnızca boş bir eklenti oluşturur; bu taban sınıf, atanan
    nesnenin XML'ini olduğu gibi taşır.
    """

    def __setitem__(self, attrib, value):
        if isinstance(value, ElementBase) and attrib in self.plugin_attrib_map:
            del self[attrib]
            self.append(value)
            return self
        return super().__setitem__(attrib, value)


class Content(_PluginHost):
    """Jingle içerik öğesi."""
    name = "content"
    namespace = NS_JINGLE
    plugin_attrib = "content"
    interfaces = {"creator", "name", "senders"}


class Description(_PluginHost):
    """XEP-0234 dosya açıklaması sarmalayıcısı."""
    name = "description"
    namespace = NS_FT
    plugin_attrib = "description"


class Jingle(_PluginHost):
    """Jingle oturum öğesi."""
    name = "jingle"
    namespace = NS_JINGLE
    plugin_attrib = "jingle"
    interfaces = {"action", "sid", "initiator", "responder"}


_REGISTERED = False


def register_stanza_plugins():
    """Jingle stanza eklentilerini bir kez kaydet (idempotent)."""
    global _REGISTERED
    if _REGISTERED:
        return
    register_stanza_plugin(Iq, Jingle)
    register_stanza_plugin(Jingle, Content)
    register_stanza_plugin(Jingle, Reason)
    register_stanza_plugin(Content, Description)
    register_stanza_plugin(Description, File)
    register_stanza_plugin(Content, TransportIBB)
    _REGISTERED = True


def sanitize_filename(name: str) -> str:
    """Karşı taraftan gelen dosya adını güvenli hale getir (path traversal)."""
    base = os.path.basename((name or "").replace("\\", "/"))
    base = base.replace("\x00", "").strip()
    if base in ("", ".", ".."):
        return ""
    return base


def unique_download_path(directory: str, name: str) -> str:
    """İndirme klasöründe çakışmayan bir hedef yol üret (dosyayı yazmaz)."""
    base = sanitize_filename(name) or "dosya"
    candidate = os.path.join(directory, base)
    if not os.path.exists(candidate):
        return candidate
    stem, ext = os.path.splitext(base)
    for i in range(1, 1000):
        candidate = os.path.join(directory, f"{stem} ({i}){ext}")
        if not os.path.exists(candidate):
            return candidate
    return os.path.join(directory, f"{stem} ({uuid.uuid4().hex[:8]}){ext}")


def guess_media_type(path: str) -> str:
    return mimetypes.guess_type(path)[0] or "application/octet-stream"


def format_size(n: int) -> str:
    value = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} GB"


def format_speed(bps: float) -> str:
    return format_size(int(max(bps, 0))) + "/s"


def format_eta(seconds: float) -> str:
    total = int(max(seconds, 0))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def clamp_block_size(value, default: int = DEFAULT_BLOCK_SIZE) -> int:
    """Karşı tarafın bildirdiği blok boyutunu güvenli aralığa çek."""
    try:
        size = int(value)
    except (TypeError, ValueError):
        return default
    if size <= 0:
        return default
    return min(size, MAX_BLOCK_SIZE)


def set_file_hash(file_el, digest: bytes, algo: str = "sha-256"):
    """Dosya öğesine XEP-0300 hash elemanı ekle/değiştir."""
    old = file_el.xml.find("{%s}hash" % NS_HASHES)
    if old is not None:
        file_el.xml.remove(old)
    el = ET.Element("{%s}hash" % NS_HASHES, {"algo": algo})
    el.text = base64.b64encode(digest).decode("ascii")
    file_el.xml.append(el)


def get_file_hash(file_el):
    """Dosya öğesindeki XEP-0300 hash'i oku: (algo, base64) veya ("", "")."""
    el = file_el.xml.find("{%s}hash" % NS_HASHES)
    if el is None or not el.text:
        return "", ""
    return el.get("algo", ""), el.text.strip()


@dataclass
class FTSession:
    sid: str
    peer: str
    initiator: bool
    name: str = ""
    size: int = 0
    mime: str = ""
    desc: str = ""
    hash_algo: str = ""
    hash_value: str = ""
    ibb_sid: str = ""
    block_size: int = DEFAULT_BLOCK_SIZE
    filepath: str = ""
    state: str = "pending"
    accept_future: "asyncio.Future | None" = None
    stream: object = None
    cancelled: bool = False
    ui: dict = field(default_factory=dict)


def parse_offer(iq) -> "dict | None":
    """session-initiate IQ'sundan dosya teklifini ayrıştır."""
    j = iq["jingle"]
    content = j["content"]
    if content is None or content["senders"] != "initiator":
        return None
    desc = content["description"]
    if desc is None:
        return None
    f = desc["file"]
    if f is None:
        return None
    algo, digest = get_file_hash(f)
    t = content["transport_ibb"]
    return {
        "sid": j["sid"],
        "peer": iq["from"].full,
        "name": f["name"] or "",
        "size": f["size"] or 0,
        "mime": f["media-type"] or "",
        "desc": f["desc"] or "",
        "hash_algo": algo,
        "hash_value": digest,
        "ibb_sid": (t["sid"] if t is not None else "") or "",
        "block_size": (t["block_size"] if t is not None else 0) or DEFAULT_BLOCK_SIZE,
    }


async def send_stream(session: FTSession, stream, path: str, on_progress) -> str:
    """Dosyayı parça parça gönder; sha-256 base64 özetini döndür."""
    hasher = hashlib.sha256()
    sent = 0
    with open(path, "rb") as fh:
        while not session.cancelled:
            chunk = fh.read(session.block_size)
            if not chunk:
                break
            hasher.update(chunk)
            await stream.send(chunk, timeout=DATA_TIMEOUT)
            sent += len(chunk)
            on_progress(sent, session.size)
    return base64.b64encode(hasher.digest()).decode("ascii")


async def recv_stream(session: FTSession, stream, part_path: str, on_progress) -> str:
    """IBB kuyruğundan veriyi oku, geçici dosyaya yaz; sha-256 özetini döndür."""
    hasher = hashlib.sha256()
    received = 0
    os.makedirs(os.path.dirname(part_path) or ".", exist_ok=True)
    with open(part_path, "wb") as fh:
        while received < session.size and not session.cancelled:
            try:
                chunk = await asyncio.wait_for(
                    stream.recv_queue.get(), DATA_TIMEOUT)
            except asyncio.TimeoutError:
                raise TimeoutError(_tr("Veri zaman aşımı"))
            received += len(chunk)
            if received > session.size:
                raise ValueError(_tr("Beyan edilen boyut aşıldı"))
            fh.write(chunk)
            hasher.update(chunk)
            on_progress(received, session.size)
    return base64.b64encode(hasher.digest()).decode("ascii")


class JingleFTManager:
    """Jingle dosya transferi oturum yöneticisi (IBB transportu)."""

    def __init__(self, xmpp, gui_q=None):
        self.xmpp = xmpp
        self.gui_q = gui_q if gui_q is not None else getattr(xmpp, "gui_q", None)
        self.sessions: dict[str, FTSession] = {}
        self._caps_cache: dict[str, bool] = {}
        register_stanza_plugins()

    # ── yardımcılar ────────────────────────────────────────────────────────
    def _emit(self, kind: str, data: dict):
        try:
            if self.gui_q is not None:
                self.gui_q.put((kind, data))
        except Exception:
            pass

    def _progress(self, session: FTSession, done: int, total: int):
        session.ui["done"] = done
        self._emit("ft_progress", {
            "sid": session.sid, "done": done, "total": total,
            "direction": "out" if session.initiator else "in",
            "name": session.name,
        })

    def _ack(self, iq):
        """IQ ack'i (testlerde değiştirilebilir)."""
        iq.reply().send()

    async def _send_iq(self, iq, timeout=None):
        """IQ gönder (testlerde değiştirilebilir)."""
        return await iq.send(timeout=timeout)

    def _finish(self, session: FTSession, state: str, error: str = ""):
        if session.accept_future is not None and not session.accept_future.done():
            session.accept_future.set_result(False)
        session.state = state
        self.sessions.pop(session.sid, None)
        if state == "done":
            self._emit("ft_done", {
                "sid": session.sid,
                "direction": "out" if session.initiator else "in",
                "peer": session.peer, "name": session.name,
                "path": session.filepath, "size": session.size,
            })
        else:
            self._emit("ft_error", {
                "sid": session.sid, "error": error or state,
                "name": session.name, "peer": session.peer,
                "state": state,
            })

    async def _terminate(self, session: FTSession, reason_name: str, text: str = ""):
        try:
            iq = self.xmpp.Iq()
            iq["type"] = "set"
            iq["to"] = session.peer
            j = iq["jingle"]
            j["action"] = "session-terminate"
            j["sid"] = session.sid
            reason = Reason()
            reason[reason_name] = True
            if text:
                reason["text"] = text
            j["reason"] = reason
            await self._send_iq(iq, timeout=15)
        except Exception:
            pass

    async def is_capable(self, jid: str) -> bool:
        from slixmpp import JID
        bare = str(JID(jid).bare)
        if bare in self._caps_cache:
            return self._caps_cache[bare]
        ok = False
        try:
            info = await self.xmpp.plugin["xep_0030"].get_info(jid=bare)
            feats = set(info["disco_info"]["features"])
            ok = "urn:xmpp:jingle:1" in feats and NS_IBB in feats
        except Exception:
            ok = False
        self._caps_cache[bare] = ok
        return ok

    # ── gönderen ───────────────────────────────────────────────────────────
    async def start_send(self, peer: str, filepath: str,
                         block_size: int | None = None) -> str:
        import uuid
        size = os.path.getsize(filepath)
        if size > MAX_FILE_BYTES:
            raise ValueError(_tr("Dosya 2 GiB sınırını aşıyor"))
        hasher = hashlib.sha256()
        with open(filepath, "rb") as fh:
            for block in iter(lambda: fh.read(1024 * 1024), b""):
                hasher.update(block)
        sid = uuid.uuid4().hex
        session = FTSession(
            sid=sid, peer=peer, initiator=True,
            name=os.path.basename(filepath), size=size,
            mime=guess_media_type(filepath), filepath=filepath,
            hash_algo="sha-256",
            hash_value=base64.b64encode(hasher.digest()).decode("ascii"),
            ibb_sid=uuid.uuid4().hex,
            block_size=clamp_block_size(
                block_size if block_size is not None else DEFAULT_BLOCK_SIZE),
            state="initiating",
        )
        session.accept_future = asyncio.get_running_loop().create_future()
        self.sessions[sid] = session
        self._emit("ft_state", {
            "sid": sid, "state": "waiting_accept", "direction": "out",
            "peer": peer, "name": session.name, "size": size,
        })
        try:
            await self._send_iq(self._build_initiate(session), timeout=ACCEPT_TIMEOUT)
            accepted = await asyncio.wait_for(session.accept_future, ACCEPT_TIMEOUT)
            if accepted is False or session.cancelled:
                return sid
        except asyncio.TimeoutError:
            await self._terminate(session, "cancel", _tr("Kabul zaman aşımı"))
            self._finish(session, "failed", _tr("Kabul zaman aşımı"))
            return sid
        except Exception as e:
            self._finish(session, "failed", _tr("Teklif gönderilemedi: {}").format(e))
            return sid
        try:
            open_stream = self.xmpp.plugin["xep_0047"].open_stream
            stream = await open_stream(session.peer, sid=session.ibb_sid,
                                       block_size=session.block_size)
            session.stream = stream
            self._emit("ft_state", {
                "sid": sid, "state": "transferring", "direction": "out",
                "peer": peer, "name": session.name, "size": size,
            })
            await send_stream(session, stream, filepath,
                              lambda d, t: self._progress(session, d, t))
            if session.cancelled:
                return sid
            try:
                await stream.close()
            except Exception:
                pass
            await self._terminate(session, "success")
            self._finish(session, "done")
        except Exception as e:
            if session.stream is not None:
                try:
                    await session.stream.close()
                except Exception:
                    pass
            if session.cancelled:
                return sid
            await self._terminate(session, "failed", str(e))
            self._finish(session, "failed", str(e))
        return sid

    def _build_initiate(self, session: FTSession):
        from datetime import datetime, timezone
        iq = self.xmpp.Iq()
        iq["type"] = "set"
        iq["to"] = session.peer
        j = iq["jingle"]
        j["action"] = "session-initiate"
        j["sid"] = session.sid
        j["initiator"] = self.xmpp.boundjid.full
        content = Content()
        content["creator"] = "initiator"
        content["name"] = "file"
        content["senders"] = "initiator"
        f = File()
        f["name"] = session.name
        f["size"] = session.size
        f["date"] = datetime.fromtimestamp(
            os.path.getmtime(session.filepath), tz=timezone.utc)
        f["media-type"] = session.mime
        if session.desc:
            f["desc"] = session.desc
        set_file_hash(f, base64.b64decode(session.hash_value), session.hash_algo or "sha-256")
        t = TransportIBB()
        t["sid"] = session.ibb_sid
        t["block_size"] = session.block_size
        t["stanza"] = "iq"
        desc = Description()
        desc["file"] = f
        content["description"] = desc
        content["transport_ibb"] = t
        j["content"] = content
        return iq

    # ── alan ───────────────────────────────────────────────────────────────
    async def _wait_stream(self, ibb_sid: str, peer: str, timeout: float):
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        event_name = f"stream:{ibb_sid}:{peer}"

        def _on_stream(stream):
            if not fut.done():
                fut.set_result(stream)

        self.xmpp.add_event_handler(event_name, _on_stream, disposable=True)
        try:
            return await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            try:
                self.xmpp.del_event_handler(event_name, _on_stream)
            except Exception:
                pass
            raise

    def _build_accept(self, session: FTSession):
        iq = self.xmpp.Iq()
        iq["type"] = "set"
        iq["to"] = session.peer
        j = iq["jingle"]
        j["action"] = "session-accept"
        j["sid"] = session.sid
        j["responder"] = self.xmpp.boundjid.full
        content = Content()
        content["creator"] = "initiator"
        content["name"] = "file"
        content["senders"] = "initiator"
        f = File()
        f["name"] = session.name
        f["size"] = session.size
        f["media-type"] = session.mime
        desc = Description()
        desc["file"] = f
        content["description"] = desc
        t = TransportIBB()
        t["sid"] = session.ibb_sid
        t["block_size"] = session.block_size
        t["stanza"] = "iq"
        content["transport_ibb"] = t
        j["content"] = content
        return iq

    async def accept(self, sid: str, save_path: str):
        session = self.sessions.get(sid)
        if session is None or session.initiator or session.state != "pending":
            return
        session.filepath = save_path
        session.state = "accepting"
        self._emit("ft_state", {
            "sid": sid, "state": "accepting", "direction": "in",
            "peer": session.peer, "name": session.name, "size": session.size,
        })
        try:
            await self._send_iq(self._build_accept(session), timeout=ACCEPT_TIMEOUT)
            preauth = self.xmpp.plugin["xep_0047"].api["preauthorize_sid"]
            preauth(self.xmpp.boundjid, session.ibb_sid, session.peer)
            stream = await self._wait_stream(session.ibb_sid, session.peer,
                                             DATA_TIMEOUT)
            session.stream = stream
            self._emit("ft_state", {
                "sid": sid, "state": "transferring", "direction": "in",
                "peer": session.peer, "name": session.name, "size": session.size,
            })
            part = save_path + ".part"
            digest = await recv_stream(
                session, stream, part, lambda d, t: self._progress(session, d, t))
            if session.cancelled:
                _remove_quiet(part)
                return
            if session.hash_value and digest != session.hash_value:
                _remove_quiet(part)
                await self._terminate(session, "failed", _tr("Hash uyuşmadı"))
                self._finish(session, "failed", _tr("Hash uyuşmazlığı"))
                return
            os.replace(part, save_path)
            try:
                await stream.close()
            except Exception:
                pass
            await self._terminate(session, "success")
            self._finish(session, "done")
        except Exception as e:
            _remove_quiet(save_path + ".part")
            if session.cancelled:
                return
            await self._terminate(session, "failed", str(e))
            self._finish(session, "failed", str(e))

    async def decline(self, sid: str, text: str = ""):
        session = self.sessions.get(sid)
        if session is None:
            return
        await self._terminate(session, "decline", text)
        self._finish(session, "declined", _tr("Reddedildi"))

    async def cancel(self, sid: str):
        session = self.sessions.get(sid)
        if session is None:
            return
        session.cancelled = True
        await self._terminate(session, "cancel", _tr("İptal edildi"))
        if session.stream is not None:
            try:
                await session.stream.close()
            except Exception:
                pass
        if session.filepath:
            _remove_quiet(session.filepath + ".part")
        self._finish(session, "cancelled", _tr("İptal edildi"))

    # ── yönlendirme ────────────────────────────────────────────────────────
    async def handle_jingle_iq(self, iq):
        action = iq["jingle"]["action"]
        sid = iq["jingle"]["sid"]
        if action == "session-initiate":
            await self._on_initiate(iq, sid)
        elif action == "session-accept":
            await self._on_accept(iq, sid)
        elif action == "session-terminate":
            await self._on_terminate(iq, sid)
        else:
            self._ack(iq)

    async def _on_initiate(self, iq, sid: str):
        offer = parse_offer(iq)
        if offer is None:
            raise XMPPError("bad-request", "Geçersiz dosya teklifi", etype="cancel")
        name = sanitize_filename(offer["name"])
        if not name or offer["size"] <= 0 or offer["size"] > MAX_FILE_BYTES:
            raise XMPPError("not-acceptable", "Dosya kabul edilemez", etype="cancel")
        if sid in self.sessions:
            raise XMPPError("conflict", "Oturum zaten var", etype="cancel")
        for other in list(self.sessions.values()):
            if other.peer == offer["peer"] and other.state == "pending":
                await self._terminate(other, "cancel", _tr("Yeni teklif"))
                self._finish(other, "cancelled", _tr("Yeni teklif geldi"))
        session = FTSession(
            sid=sid, peer=offer["peer"], initiator=False, name=name,
            size=offer["size"], mime=offer["mime"], desc=offer["desc"],
            hash_algo=offer["hash_algo"], hash_value=offer["hash_value"],
            ibb_sid=offer["ibb_sid"], block_size=clamp_block_size(offer["block_size"]),
            state="pending",
        )
        self.sessions[sid] = session
        self._ack(iq)
        self._emit("ft_offer", {
            "sid": sid, "peer": offer["peer"], "name": name,
            "size": offer["size"], "mime": offer["mime"], "desc": offer["desc"],
            "hash_algo": offer["hash_algo"],
            "hash_short": offer["hash_value"][:16],
        })

    async def _on_accept(self, iq, sid: str):
        session = self.sessions.get(sid)
        if session is None or not session.initiator:
            raise XMPPError("item-not-found", etype="cancel")
        content = iq["jingle"]["content"]
        t = content["transport_ibb"] if content is not None else None
        if t is not None and t["block_size"]:
            session.block_size = clamp_block_size(t["block_size"], session.block_size)
        self._ack(iq)
        if session.accept_future is not None and not session.accept_future.done():
            session.accept_future.set_result(True)

    async def _on_terminate(self, iq, sid: str):
        session = self.sessions.get(sid)
        self._ack(iq)
        if session is None:
            return
        reason = iq["jingle"]["reason"]
        reason_name = ""
        if reason is not None:
            for nm in ("success", "cancel", "decline", "failed"):
                if reason[nm]:
                    reason_name = nm
                    break
        if reason_name == "success":
            # Başarılı transferi accept()/start_send() tamamlar; burada
            # oturuma dokunulmaz. Aksi halde yerel _finish ile çift olay
            # (ft_error + ft_done) yayılır ve .part erken silinir.
            return
        session.cancelled = True
        if session.stream is not None:
            try:
                session.stream.close()
            except Exception:
                pass
        if session.filepath:
            _remove_quiet(session.filepath + ".part")
        if session.sid not in self.sessions:
            return
        self._finish(session, "failed",
                     _tr("Karşı taraf kapattı: {}").format(reason_name or _tr('sebep yok')))


def _remove_quiet(path: str):
    try:
        if path and os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass
