from __future__ import annotations

import base64
import hashlib
import os
from datetime import datetime, timedelta, timezone
from html import escape
from urllib.parse import urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree as ET

import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

from .classifier import classify_streams
from .models import (
    DeviceDetails,
    DeviceInformation,
    DiscoveredDevice,
    StreamProfile,
)
from .xmlutil import (
    child,
    child_text,
    descendant_text,
    descendants,
    first_descendant,
    safe_float,
    safe_int,
)

SOAP_ENV = "http://www.w3.org/2003/05/soap-envelope"
DEVICE_NS = "http://www.onvif.org/ver10/device/wsdl"
MEDIA_NS = "http://www.onvif.org/ver10/media/wsdl"
MEDIA2_NS = "http://www.onvif.org/ver20/media/wsdl"
SCHEMA_NS = "http://www.onvif.org/ver10/schema"
WSSE_NS = (
    "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
)
WSU_NS = (
    "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
)
PASSWORD_DIGEST_TYPE = (
    "http://docs.oasis-open.org/wss/2004/01/"
    "oasis-200401-wss-username-token-profile-1.0#PasswordDigest"
)
BASE64_NONCE_TYPE = (
    "http://docs.oasis-open.org/wss/2004/01/"
    "oasis-200401-wss-soap-message-security-1.0#Base64Binary"
)


class OnvifError(RuntimeError):
    pass


class OnvifAuthenticationError(OnvifError):
    pass


class OnvifClient:
    def __init__(
        self,
        device_service_url: str,
        username: str = "",
        password: str = "",
        timeout: float = 6.0,
        verify_tls: bool = False,
    ) -> None:
        self.device_service_url = device_service_url
        self.username = username
        self.password = password
        self.timeout = timeout
        self.verify_tls = verify_tls
        self.clock_offset = timedelta(0)
        self.media_service_url = ""
        self.media_namespace = MEDIA_NS
        self.media1_fallback_url = ""
        self.session = requests.Session()
        self.session.verify = verify_tls
        if username:
            self.session.auth = HTTPDigestAuth(username, password)

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> OnvifClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _security_header(self) -> str:
        if not self.username:
            return ""
        nonce = os.urandom(20)
        created_at = datetime.now(timezone.utc) + self.clock_offset
        created = created_at.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        digest = base64.b64encode(
            hashlib.sha1(
                nonce + created.encode("utf-8") + self.password.encode("utf-8")
            ).digest()
        ).decode("ascii")
        nonce_b64 = base64.b64encode(nonce).decode("ascii")
        return f"""
<wsse:Security s:mustUnderstand="1">
 <wsse:UsernameToken>
  <wsse:Username>{escape(self.username)}</wsse:Username>
  <wsse:Password Type="{PASSWORD_DIGEST_TYPE}">{digest}</wsse:Password>
  <wsse:Nonce EncodingType="{BASE64_NONCE_TYPE}">{nonce_b64}</wsse:Nonce>
  <wsu:Created>{created}</wsu:Created>
 </wsse:UsernameToken>
</wsse:Security>"""

    def _envelope(self, body: str, authenticated: bool) -> bytes:
        security = self._security_header() if authenticated else ""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="{SOAP_ENV}" xmlns:tds="{DEVICE_NS}"
 xmlns:trt="{MEDIA_NS}" xmlns:tr2="{MEDIA2_NS}" xmlns:tt="{SCHEMA_NS}"
 xmlns:wsse="{WSSE_NS}" xmlns:wsu="{WSU_NS}">
 <s:Header>{security}</s:Header>
 <s:Body>{body}</s:Body>
</s:Envelope>""".encode()

    def _post(
        self,
        url: str,
        action: str,
        body: str,
        *,
        authenticated: bool = True,
    ) -> ET.Element:
        headers = {
            "Content-Type": f'application/soap+xml; charset=utf-8; action="{action}"',
            "SOAPAction": f'"{action}"',
            "User-Agent": "ONVIF-Camera-Scanner/0.1",
        }
        try:
            response = self.session.post(
                url,
                data=self._envelope(body, authenticated),
                headers=headers,
                timeout=self.timeout,
            )
            challenge = response.headers.get("WWW-Authenticate", "").lower()
            if (
                response.status_code == 401
                and self.username
                and "basic" in challenge
                and "digest" not in challenge
            ):
                response = self.session.post(
                    url,
                    data=self._envelope(body, authenticated),
                    headers=headers,
                    timeout=self.timeout,
                    auth=HTTPBasicAuth(self.username, self.password),
                )
        except requests.RequestException as exc:
            raise OnvifError(f"连接失败：{exc}") from exc

        if response.status_code in (401, 403):
            raise OnvifAuthenticationError(
                "认证失败，请检查用户名、密码或摄像头 ONVIF 用户权限"
            )
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as exc:
            snippet = response.text[:160].strip()
            raise OnvifError(
                f"设备返回了无法解析的内容（HTTP {response.status_code}）：{snippet}"
            ) from exc

        fault = first_descendant(root, "Fault")
        if fault is not None:
            reason = descendant_text(fault, "Text") or descendant_text(fault, "Reason")
            code = descendant_text(fault, "Value") or descendant_text(fault, "Code")
            message = (
                " / ".join(part for part in (code, reason) if part) or "未知 SOAP Fault"
            )
            lowered = message.lower()
            if any(
                key in lowered
                for key in ("notauthorized", "unauthorized", "ter:notauthorized")
            ):
                raise OnvifAuthenticationError(f"认证失败：{message}")
            raise OnvifError(f"ONVIF 错误：{message}")
        if not response.ok:
            raise OnvifError(f"ONVIF 请求失败：HTTP {response.status_code}")
        return root

    def _normalize_advertised_url(self, advertised_url: str) -> str:
        """Make relative or placeholder-host service addresses usable."""

        candidate = urljoin(self.device_service_url, advertised_url)
        try:
            parsed = urlsplit(candidate)
            base = urlsplit(self.device_service_url)
            if parsed.hostname not in {"0.0.0.0", "127.0.0.1", "localhost"}:
                return candidate
            if not base.hostname:
                return candidate
            host = f"[{base.hostname}]" if ":" in base.hostname else base.hostname
            if parsed.port:
                host = f"{host}:{parsed.port}"
            return urlunsplit(
                (
                    parsed.scheme or base.scheme,
                    host,
                    parsed.path,
                    parsed.query,
                    parsed.fragment,
                )
            )
        except ValueError:
            return candidate

    def synchronize_clock(self) -> None:
        try:
            root = self._post(
                self.device_service_url,
                f"{DEVICE_NS}/GetSystemDateAndTime",
                "<tds:GetSystemDateAndTime/>",
                authenticated=False,
            )
        except OnvifError:
            return
        utc_block = first_descendant(root, "UTCDateTime")
        if utc_block is None:
            return
        date = child(utc_block, "Date")
        clock = child(utc_block, "Time")
        try:
            device_time = datetime(
                safe_int(child_text(date, "Year")),
                safe_int(child_text(date, "Month")),
                safe_int(child_text(date, "Day")),
                safe_int(child_text(clock, "Hour")),
                safe_int(child_text(clock, "Minute")),
                safe_int(child_text(clock, "Second")),
                tzinfo=timezone.utc,
            )
        except ValueError:
            return
        self.clock_offset = device_time - datetime.now(timezone.utc)

    def get_device_information(self) -> DeviceInformation:
        root = self._post(
            self.device_service_url,
            f"{DEVICE_NS}/GetDeviceInformation",
            "<tds:GetDeviceInformation/>",
        )
        response = first_descendant(root, "GetDeviceInformationResponse")
        if response is None:
            response = root
        return DeviceInformation(
            manufacturer=descendant_text(response, "Manufacturer"),
            model=descendant_text(response, "Model"),
            firmware_version=descendant_text(response, "FirmwareVersion"),
            serial_number=descendant_text(response, "SerialNumber"),
            hardware_id=descendant_text(response, "HardwareId"),
        )

    def get_media_service_url(self) -> str:
        try:
            root = self._post(
                self.device_service_url,
                f"{DEVICE_NS}/GetServices",
                "<tds:GetServices><tds:IncludeCapability>false</tds:IncludeCapability></tds:GetServices>",
            )
            service_urls: dict[str, str] = {}
            for service in descendants(root, "Service"):
                namespace = child_text(service, "Namespace")
                url = child_text(service, "XAddr")
                if namespace and url:
                    service_urls[namespace.rstrip("/")] = url

            media1_url = service_urls.get(MEDIA_NS.rstrip("/"), "")
            if media1_url:
                self.media1_fallback_url = self._normalize_advertised_url(media1_url)
            for namespace in (MEDIA2_NS, MEDIA_NS):
                url = service_urls.get(namespace.rstrip("/"))
                if url:
                    self.media_namespace = namespace
                    self.media_service_url = self._normalize_advertised_url(url)
                    return self.media_service_url
        except OnvifAuthenticationError:
            raise
        except OnvifError:
            pass

        root = self._post(
            self.device_service_url,
            f"{DEVICE_NS}/GetCapabilities",
            "<tds:GetCapabilities><tds:Category>All</tds:Category></tds:GetCapabilities>",
        )
        capabilities = first_descendant(root, "Capabilities")
        media = child(capabilities, "Media")
        url = child_text(media, "XAddr")
        if url:
            self.media_namespace = MEDIA_NS
            self.media_service_url = self._normalize_advertised_url(url)
            return self.media_service_url
        raise OnvifError("设备未公布 ONVIF Media/Media2 服务，无法读取视频 Profile")

    def get_profiles(self, media_url: str | None = None) -> list[StreamProfile]:
        media_url = media_url or self.media_service_url or self.get_media_service_url()
        is_media2 = self.media_namespace == MEDIA2_NS
        namespace = MEDIA2_NS if is_media2 else MEDIA_NS
        body = (
            "<tr2:GetProfiles><tr2:Type>All</tr2:Type></tr2:GetProfiles>"
            if is_media2
            else "<trt:GetProfiles/>"
        )
        root = self._post(media_url, f"{namespace}/GetProfiles", body)
        profiles: list[StreamProfile] = []
        for node in descendants(root, "Profiles"):
            token = node.attrib.get("token", "")
            if not token:
                continue
            if is_media2:
                configurations = child(node, "Configurations")
                source = child(configurations, "VideoSource")
                encoder = child(configurations, "VideoEncoder")
            else:
                source = child(node, "VideoSourceConfiguration")
                encoder = child(node, "VideoEncoderConfiguration")
            resolution = child(encoder, "Resolution")
            rate_control = child(encoder, "RateControl")
            profiles.append(
                StreamProfile(
                    token=token,
                    profile_name=child_text(node, "Name") or token,
                    source_token=child_text(source, "SourceToken"),
                    source_config_name=child_text(source, "Name"),
                    encoder_name=child_text(encoder, "Name"),
                    encoding=child_text(encoder, "Encoding"),
                    width=safe_int(child_text(resolution, "Width")),
                    height=safe_int(child_text(resolution, "Height")),
                    frame_rate=safe_float(child_text(rate_control, "FrameRateLimit")),
                    bitrate_kbps=safe_int(child_text(rate_control, "BitrateLimit")),
                )
            )
        if not profiles:
            raise OnvifError("Media 服务没有返回任何视频 Profile")
        return profiles

    def get_stream_uri(self, profile_token: str, media_url: str | None = None) -> str:
        media_url = media_url or self.media_service_url or self.get_media_service_url()
        if self.media_namespace == MEDIA2_NS:
            body = f"""
<tr2:GetStreamUri>
 <tr2:Protocol>RTSP</tr2:Protocol>
 <tr2:ProfileToken>{escape(profile_token)}</tr2:ProfileToken>
</tr2:GetStreamUri>"""
            action = f"{MEDIA2_NS}/GetStreamUri"
        else:
            body = f"""
<trt:GetStreamUri>
 <trt:StreamSetup>
  <tt:Stream>RTP-Unicast</tt:Stream>
  <tt:Transport><tt:Protocol>RTSP</tt:Protocol></tt:Transport>
 </trt:StreamSetup>
 <trt:ProfileToken>{escape(profile_token)}</trt:ProfileToken>
</trt:GetStreamUri>"""
            action = f"{MEDIA_NS}/GetStreamUri"
        root = self._post(media_url, action, body)
        if self.media_namespace == MEDIA2_NS:
            uri = descendant_text(first_descendant(root, "GetStreamUriResponse"), "Uri")
        else:
            uri = descendant_text(first_descendant(root, "MediaUri"), "Uri")
        if not uri:
            raise OnvifError("设备没有为该 Profile 返回 RTSP URI")
        return self._normalize_advertised_url(uri)

    def read_details(self, discovery: DiscoveredDevice) -> DeviceDetails:
        self.synchronize_clock()
        information = self.get_device_information()
        media_url = self.get_media_service_url()
        try:
            streams = self.get_profiles(media_url)
        except OnvifError:
            if self.media_namespace != MEDIA2_NS or not self.media1_fallback_url:
                raise
            self.media_namespace = MEDIA_NS
            self.media_service_url = self.media1_fallback_url
            media_url = self.media1_fallback_url
            streams = self.get_profiles(media_url)
        for stream in streams:
            try:
                stream.rtsp_uri = self.get_stream_uri(stream.token, media_url)
            except OnvifError as exc:
                stream.error = str(exc)
        classify_streams(streams)
        return DeviceDetails(
            discovery=discovery,
            information=information,
            streams=streams,
            media_service_url=media_url,
        )
