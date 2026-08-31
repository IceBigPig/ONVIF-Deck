from __future__ import annotations

import select
import socket
import time
import uuid
from collections.abc import Callable
from threading import Event
from urllib.parse import unquote
from xml.etree import ElementTree as ET

from .models import DiscoveredDevice
from .xmlutil import descendant_text, descendants

WS_DISCOVERY_ADDRESS = ("239.255.255.250", 3702)


def _probe_message() -> bytes:
    message_id = f"uuid:{uuid.uuid4()}"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
 xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing"
 xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
 xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
 <s:Header>
  <a:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</a:Action>
  <a:MessageID>{message_id}</a:MessageID>
  <a:ReplyTo><a:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</a:Address></a:ReplyTo>
  <a:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</a:To>
 </s:Header>
 <s:Body><d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types></d:Probe></s:Body>
</s:Envelope>""".encode()


def local_ipv4_addresses() -> list[str]:
    addresses: list[str] = []
    try:
        import psutil

        stats = psutil.net_if_stats()
        for name, records in psutil.net_if_addrs().items():
            if name in stats and not stats[name].isup:
                continue
            for record in records:
                if record.family != socket.AF_INET:
                    continue
                address = record.address
                if address and not address.startswith("127.") and address != "0.0.0.0":
                    addresses.append(address)
    except (ImportError, OSError):
        try:
            for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                address = item[4][0]
                if address and not address.startswith("127."):
                    addresses.append(address)
        except OSError:
            pass
    return list(dict.fromkeys(addresses)) or ["0.0.0.0"]


def parse_probe_matches(
    data: bytes, remote_address: str = ""
) -> list[DiscoveredDevice]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []

    devices: list[DiscoveredDevice] = []
    for match in descendants(root, "ProbeMatch"):
        endpoint = descendant_text(match, "Address")
        xaddrs = descendant_text(match, "XAddrs").split()
        scopes = [unquote(value) for value in descendant_text(match, "Scopes").split()]
        types = descendant_text(match, "Types").split()
        if xaddrs:
            devices.append(
                DiscoveredDevice(
                    endpoint=endpoint or xaddrs[0],
                    xaddrs=xaddrs,
                    scopes=scopes,
                    types=types,
                    remote_address=remote_address,
                )
            )
    return devices


def _make_socket(interface_address: str) -> socket.socket | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        if interface_address != "0.0.0.0":
            sock.setsockopt(
                socket.IPPROTO_IP,
                socket.IP_MULTICAST_IF,
                socket.inet_aton(interface_address),
            )
        sock.bind((interface_address, 0))
        sock.setblocking(False)
        return sock
    except OSError:
        sock.close()
        return None


def discover_devices(
    timeout: float = 4.0,
    stop_event: Event | None = None,
    on_device: Callable[[DiscoveredDevice], None] | None = None,
) -> list[DiscoveredDevice]:
    """Discover ONVIF NetworkVideoTransmitters on every active IPv4 interface."""

    stop_event = stop_event or Event()
    sockets = [
        sock
        for address in local_ipv4_addresses()
        if (sock := _make_socket(address)) is not None
    ]
    if not sockets:
        fallback = _make_socket("0.0.0.0")
        if fallback:
            sockets = [fallback]
    if not sockets:
        raise OSError("无法创建 WS-Discovery UDP 套接字")

    probe = _probe_message()
    deadline = time.monotonic() + max(0.5, timeout)
    resend_at = time.monotonic() + min(1.5, timeout / 2)
    seen: set[str] = set()
    results: list[DiscoveredDevice] = []

    try:
        sent = 0
        for sock in sockets:
            try:
                sock.sendto(probe, WS_DISCOVERY_ADDRESS)
                sent += 1
            except OSError:
                pass
        if not sent:
            raise OSError("所有网卡都无法发送 WS-Discovery 组播，请检查网络或防火墙")

        while not stop_event.is_set() and time.monotonic() < deadline:
            wait = min(0.2, max(0.0, deadline - time.monotonic()))
            readable, _, _ = select.select(sockets, [], [], wait)
            for sock in readable:
                try:
                    payload, remote = sock.recvfrom(65535)
                except OSError:
                    continue
                for device in parse_probe_matches(payload, remote[0]):
                    key = device.endpoint or device.device_service_url
                    if key in seen:
                        continue
                    seen.add(key)
                    results.append(device)
                    if on_device:
                        on_device(device)
            if time.monotonic() >= resend_at:
                for sock in sockets:
                    try:
                        sock.sendto(probe, WS_DISCOVERY_ADDRESS)
                    except OSError:
                        pass
                resend_at = deadline + 1
    finally:
        for sock in sockets:
            sock.close()
    return results
