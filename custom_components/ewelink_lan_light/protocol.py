"""eWeLink LAN-mode client: AES-128-CBC keyed by MD5(devicekey). No cloud.

Pure Python (no Home Assistant imports) so it can be tested and reused.

Verified on a BL602 CK0205PWM bulb:
  POST /zeroconf/switch   {"switch":"on"|"off"}
  POST /zeroconf/dimmable {"ltype":"white","white":{"br":1-100,"ct":0-100}}
  POST /zeroconf/dimmable {"ltype":"color","color":{"br":1-100,"r":0-255,"g":0-255,"b":0-255}}
The device also broadcasts its encrypted state in mDNS TXT records
(_ewelink._tcp, fields data1..data4 + iv), which `parse_txt_state` decodes.
"""
from __future__ import annotations

import base64
import hashlib
import http.client
import json
import random
import struct
import time
import urllib.request
from typing import Mapping

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

PORT = 8081


def _key(devicekey: str) -> bytes:
    return hashlib.md5(devicekey.encode("utf-8")).digest()


def _make_iv() -> bytes:
    return str(random.randint(0, 10**16 - 1)).zfill(16).encode("ascii")


def encrypt(devicekey: str, data: dict) -> tuple[str, str]:
    """Return (base64 ciphertext, base64 iv)."""
    iv = _make_iv()
    plaintext = json.dumps(data, separators=(",", ":")).encode("utf-8")
    ct = AES.new(_key(devicekey), AES.MODE_CBC, iv).encrypt(pad(plaintext, 16))
    return base64.b64encode(ct).decode(), base64.b64encode(iv).decode()


def decrypt(devicekey: str, data_b64: str, iv_b64: str) -> dict:
    iv = base64.b64decode(iv_b64)
    ct = base64.b64decode(data_b64)
    pt = unpad(AES.new(_key(devicekey), AES.MODE_CBC, iv).decrypt(ct), 16)
    return json.loads(pt)


def parse_txt_state(devicekey: str, properties: Mapping) -> dict | None:
    """Decode the state from an mDNS TXT record set; None if not decodable.

    `properties` maps keys to values as bytes or str (zeroconf gives bytes).
    """

    def text(v):
        return v.decode() if isinstance(v, (bytes, bytearray)) else v

    props = {text(k): text(v) for k, v in properties.items() if v is not None}
    if props.get("encrypt") != "true" or "iv" not in props:
        return None
    raw = "".join(props[f"data{i}"] for i in range(1, 5) if f"data{i}" in props)
    if not raw:
        return None
    try:
        return decrypt(devicekey, raw, props["iv"])
    except Exception:  # wrong key or truncated record
        return None


def send_command(
    ip: str, deviceid: str, devicekey: str, command: str, data: dict, timeout: float = 6.0
) -> dict:
    """Send one /zeroconf/<command> request. Blocking; run it in an executor."""
    enc_data, iv_b64 = encrypt(devicekey, data)
    payload = {
        "sequence": str(int(time.time() * 1000)),
        "deviceid": deviceid,
        "selfApikey": "123",
        "encrypt": True,
        "data": enc_data,
        "iv": iv_b64,
    }
    req = urllib.request.Request(
        f"http://{ip}:{PORT}/zeroconf/{command}",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json",
            "Package-Name": "com.coolkit",
            "Cache-Control": "no-store",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def check_credentials(ip: str, deviceid: str, devicekey: str, timeout: float = 5.0) -> bool:
    """Side-effect-free key check; raises OSError if the bulb is unreachable.

    An empty `switch` payload is invalid, so a bulb that can decrypt it
    answers `error:400`. A bulb that cannot (wrong key) drops the
    connection without replying. The bulb also drops requests when busy,
    so a drop is retried before it is treated as a wrong key.
    """
    for attempt in range(3):
        try:
            send_command(ip, deviceid, devicekey, "switch", {}, timeout)
            return True
        except http.client.RemoteDisconnected:
            time.sleep(0.4 * (attempt + 1))
    return False


MDNS_PORT = 5353


def build_txt_query(deviceid: str) -> bytes:
    """A unicast mDNS question for the bulb's TXT record, which carries its state.

    Sent straight to the bulb's port 5353 from an ordinary source port, so it
    is routed like any unicast packet (works across VLANs, no repeater).
    """
    name = f"eWeLink_{deviceid}._ewelink._tcp.local"
    qname = b"".join(bytes([len(label)]) + label.encode() for label in name.split(".")) + b"\0"
    header = struct.pack(">HHHHHH", random.randint(1, 0xFFFF), 0, 1, 0, 0, 0)
    return header + qname + struct.pack(">HH", 16, 1)  # TXT, IN


def txt_props_from_response(data: bytes) -> dict[bytes, bytes] | None:
    """Pull the TXT key/value pairs out of an mDNS reply; None if there are none."""
    from zeroconf import DNSIncoming, DNSText

    try:
        answers = DNSIncoming(data).answers()
    except Exception:  # malformed or unrelated packet
        return None
    for rec in answers:
        if isinstance(rec, DNSText):
            props: dict[bytes, bytes] = {}
            raw, i = rec.text, 0
            while i < len(raw):
                n = raw[i]
                key, _, value = raw[i + 1 : i + 1 + n].partition(b"=")
                props[key] = value
                i += 1 + n
            return props
    return None
