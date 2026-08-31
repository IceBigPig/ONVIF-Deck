from __future__ import annotations

from xml.etree import ElementTree as ET

from onvif_scanner.classifier import classify_streams
from onvif_scanner.client import (
    BASE64_NONCE_TYPE,
    MEDIA2_NS,
    PASSWORD_DIGEST_TYPE,
    OnvifClient,
)
from onvif_scanner.credentials import SERVICE_NAME, Credential, CredentialStore
from onvif_scanner.dashboard import stream_text
from onvif_scanner.discovery import parse_probe_matches
from onvif_scanner.models import StreamProfile
from onvif_scanner.preview import safe_display_uri, uri_with_credentials


def test_discovery_response_is_parsed() -> None:
    payload = b"""<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
      xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
      xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing">
      <s:Body><d:ProbeMatches><d:ProbeMatch>
        <a:EndpointReference><a:Address>urn:uuid:camera-1</a:Address></a:EndpointReference>
        <d:Types>dn:NetworkVideoTransmitter</d:Types>
        <d:Scopes>onvif://www.onvif.org/name/Front%20Door onvif://www.onvif.org/type/video_encoder</d:Scopes>
        <d:XAddrs>http://192.168.1.20/onvif/device_service</d:XAddrs>
      </d:ProbeMatch></d:ProbeMatches></s:Body>
    </s:Envelope>"""
    devices = parse_probe_matches(payload, "192.168.1.20")
    assert len(devices) == 1
    assert devices[0].endpoint == "urn:uuid:camera-1"
    assert devices[0].host == "192.168.1.20"
    assert devices[0].display_name == "Front Door"


def test_main_sub_classification_is_per_video_source() -> None:
    streams = [
        StreamProfile(
            "wide-main",
            "Wide Main",
            "source-wide",
            width=3840,
            height=2160,
            bitrate_kbps=6000,
        ),
        StreamProfile(
            "wide-sub",
            "Wide Sub",
            "source-wide",
            width=640,
            height=360,
            bitrate_kbps=512,
        ),
        StreamProfile(
            "tele-main",
            "Tele Main",
            "source-tele",
            width=1920,
            height=1080,
            bitrate_kbps=3000,
        ),
        StreamProfile(
            "tele-sub",
            "Tele Sub",
            "source-tele",
            width=704,
            height=576,
            bitrate_kbps=700,
        ),
    ]
    classify_streams(streams)
    roles = {item.token: item.stream_role for item in streams}
    assert roles == {
        "wide-main": "主码流",
        "wide-sub": "子码流",
        "tele-main": "主码流",
        "tele-sub": "子码流",
    }
    assert {item.channel_label for item in streams} == {
        "通道 1 · 长焦",
        "通道 2 · 广角",
    }


def test_profile_xml_is_parsed() -> None:
    response = ET.fromstring(
        """<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
          xmlns:trt="http://www.onvif.org/ver10/media/wsdl"
          xmlns:tt="http://www.onvif.org/ver10/schema">
          <s:Body><trt:GetProfilesResponse><trt:Profiles token="p1">
            <tt:Name>MainStream</tt:Name>
            <tt:VideoSourceConfiguration token="vsc1">
              <tt:Name>Wide Lens</tt:Name><tt:SourceToken>source_1</tt:SourceToken>
            </tt:VideoSourceConfiguration>
            <tt:VideoEncoderConfiguration token="vec1">
              <tt:Name>Encoder 1</tt:Name><tt:Encoding>H264</tt:Encoding>
              <tt:Resolution><tt:Width>2560</tt:Width><tt:Height>1440</tt:Height></tt:Resolution>
              <tt:RateControl><tt:FrameRateLimit>25</tt:FrameRateLimit><tt:BitrateLimit>4096</tt:BitrateLimit></tt:RateControl>
            </tt:VideoEncoderConfiguration>
          </trt:Profiles></trt:GetProfilesResponse></s:Body>
        </s:Envelope>"""
    )
    client = OnvifClient("http://camera/onvif/device_service")
    client._post = lambda *_args, **_kwargs: response  # type: ignore[method-assign]
    profiles = client.get_profiles("http://camera/onvif/media_service")
    assert len(profiles) == 1
    assert profiles[0].source_token == "source_1"
    assert profiles[0].resolution == "2560×1440"
    assert profiles[0].frame_rate == 25
    assert profiles[0].bitrate_kbps == 4096
    client.close()


def test_rtsp_credentials_are_encoded_and_redacted() -> None:
    uri = uri_with_credentials(
        "rtsp://192.168.1.20:554/live/ch1", "admin@test", "p@ ss"
    )
    assert uri == "rtsp://admin%40test:p%40%20ss@192.168.1.20:554/live/ch1"
    assert safe_display_uri(uri) == "rtsp://admin%40test:***@192.168.1.20:554/live/ch1"


def test_copied_stream_text_contains_encoded_credentials() -> None:
    stream = StreamProfile(
        "main",
        "Main Stream",
        "source-1",
        rtsp_uri="rtsp://192.168.1.20:554/live/ch1",
    )
    copied = stream_text(stream, "admin@test", "p@ ss")
    assert "RTSP: rtsp://admin%40test:p%40%20ss@192.168.1.20:554/live/ch1" in copied


def test_media2_profiles_and_stream_uri_are_supported() -> None:
    profiles_response = ET.fromstring(
        """<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
          xmlns:tr2="http://www.onvif.org/ver20/media/wsdl"
          xmlns:tt="http://www.onvif.org/ver10/schema">
          <s:Body><tr2:GetProfilesResponse><tr2:Profiles token="m2-p1">
            <tr2:Name>Tele Main</tr2:Name><tr2:Configurations>
              <tr2:VideoSource token="source-config"><tt:Name>Tele Lens</tt:Name><tt:SourceToken>sensor-2</tt:SourceToken></tr2:VideoSource>
              <tr2:VideoEncoder token="encoder-2"><tt:Name>H265 Main</tt:Name><tt:Encoding>H265</tt:Encoding>
                <tt:Resolution><tt:Width>3840</tt:Width><tt:Height>2160</tt:Height></tt:Resolution>
                <tt:RateControl><tt:FrameRateLimit>20</tt:FrameRateLimit><tt:BitrateLimit>6144</tt:BitrateLimit></tt:RateControl>
              </tr2:VideoEncoder>
            </tr2:Configurations>
          </tr2:Profiles></tr2:GetProfilesResponse></s:Body>
        </s:Envelope>"""
    )
    uri_response = ET.fromstring(
        """<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:tr2="http://www.onvif.org/ver20/media/wsdl">
          <s:Body><tr2:GetStreamUriResponse><tr2:Uri>rtsp://0.0.0.0/live/m2</tr2:Uri></tr2:GetStreamUriResponse></s:Body>
        </s:Envelope>"""
    )
    requests_seen: list[str] = []
    client = OnvifClient("http://192.168.1.22/onvif/device_service")
    client.media_namespace = MEDIA2_NS

    def fake_post(_url: str, action: str, _body: str, **_kwargs: object) -> ET.Element:
        requests_seen.append(action)
        return uri_response if action.endswith("GetStreamUri") else profiles_response

    client._post = fake_post  # type: ignore[method-assign]
    profiles = client.get_profiles("http://192.168.1.22/onvif/media2")
    uri = client.get_stream_uri("m2-p1", "http://192.168.1.22/onvif/media2")
    assert profiles[0].source_token == "sensor-2"
    assert profiles[0].encoding == "H265"
    assert profiles[0].resolution == "3840×2160"
    assert uri == "rtsp://192.168.1.22/live/m2"
    assert requests_seen == [f"{MEDIA2_NS}/GetProfiles", f"{MEDIA2_NS}/GetStreamUri"]
    client.close()


def test_ws_security_uses_standard_profile_type_uris() -> None:
    client = OnvifClient("http://camera/onvif/device_service", "admin", "secret")
    header = client._security_header()
    assert PASSWORD_DIGEST_TYPE in header
    assert BASE64_NONCE_TYPE in header
    assert "<wsu:Created>" in header
    client.close()


def test_media2_is_preferred_and_media1_is_kept_as_fallback() -> None:
    services_response = ET.fromstring(
        """<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
          <s:Body><tds:GetServicesResponse>
            <tds:Service><tds:Namespace>http://www.onvif.org/ver10/media/wsdl</tds:Namespace><tds:XAddr>http://camera/onvif/media1</tds:XAddr></tds:Service>
            <tds:Service><tds:Namespace>http://www.onvif.org/ver20/media/wsdl</tds:Namespace><tds:XAddr>http://camera/onvif/media2</tds:XAddr></tds:Service>
          </tds:GetServicesResponse></s:Body>
        </s:Envelope>"""
    )
    client = OnvifClient("http://camera/onvif/device_service")
    client._post = lambda *_args, **_kwargs: services_response  # type: ignore[method-assign]
    assert client.get_media_service_url() == "http://camera/onvif/media2"
    assert client.media_namespace == MEDIA2_NS
    assert client.media1_fallback_url == "http://camera/onvif/media1"
    client.close()


class _MemoryVault:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.values.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.values[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self.values.pop((service, username), None)


def test_credentials_use_vault_and_support_device_override(tmp_path: object) -> None:
    from PySide6.QtCore import QSettings

    settings = QSettings(str(tmp_path) + "/settings.ini", QSettings.Format.IniFormat)
    vault = _MemoryVault()
    store = CredentialStore(settings, vault)
    store.save(Credential(username="admin", password="default-secret"))
    device_key = "uuid:camera-1"
    profile_id = store.device_profile_id(device_key)
    store.save(
        Credential(
            profile_id=profile_id,
            label="当前设备专用账号",
            username="operator",
            password="device-secret",
        )
    )
    store.bind_device(device_key, profile_id)

    assert store.load().password == "default-secret"
    assert store.resolve(device_key).username == "operator"
    assert vault.values[(SERVICE_NAME, profile_id)] == "device-secret"
