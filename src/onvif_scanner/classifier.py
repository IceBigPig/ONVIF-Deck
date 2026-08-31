from __future__ import annotations

import re
from collections import defaultdict

from .models import StreamProfile

_LENS_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("长焦", ("长焦", "telephoto", "tele", "zoom", "bullet")),
    ("广角", ("广角", "wide-angle", "wide angle", "wide", "overview")),
    ("全景", ("全景", "panorama", "panoramic", "fisheye", "鱼眼")),
    ("近景", ("近景", "close-up", "closeup", "detail")),
    ("热成像", ("热成像", "thermal", "infrared thermal")),
)


def infer_lens_hint(profile: StreamProfile) -> str:
    haystack = (
        f"{profile.profile_name} {profile.source_config_name} "
        f"{profile.encoder_name} {profile.source_token}"
    ).lower()
    for label, keywords in _LENS_RULES:
        if any(keyword.lower() in haystack for keyword in keywords):
            return label
    return ""


def _natural_key(value: str) -> list[int | str]:
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", value)
    ]


def classify_streams(streams: list[StreamProfile]) -> list[StreamProfile]:
    """Add channel, lens, and main/sub-stream labels in place.

    A channel is a distinct VideoSourceToken. Quality is ranked only within
    that channel; this prevents a low-resolution telephoto sensor from being
    mistaken for the sub-stream of a high-resolution wide-angle sensor.
    """

    groups: dict[str, list[StreamProfile]] = defaultdict(list)
    for stream in streams:
        group_key = stream.source_token or stream.source_config_name or "__unknown__"
        groups[group_key].append(stream)

    ordered_keys = sorted(groups, key=_natural_key)
    for channel_index, group_key in enumerate(ordered_keys, start=1):
        group = groups[group_key]
        hints = [hint for hint in (infer_lens_hint(item) for item in group) if hint]
        group_hint = hints[0] if hints else ""
        channel = f"通道 {channel_index}"
        if group_hint:
            channel += f" · {group_hint}"

        ranked = sorted(group, key=lambda item: item.quality_score, reverse=True)
        for rank, stream in enumerate(ranked):
            stream.channel_label = channel
            stream.lens_hint = infer_lens_hint(stream) or group_hint
            if len(ranked) == 1 or rank == 0:
                stream.stream_role = "主码流"
            elif rank == len(ranked) - 1:
                stream.stream_role = "子码流"
            else:
                stream.stream_role = f"辅助码流 {rank}"

    return streams
