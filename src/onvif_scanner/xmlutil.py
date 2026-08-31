from __future__ import annotations

from collections.abc import Iterable
from xml.etree import ElementTree as ET


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":")[-1]


def children(element: ET.Element | None, name: str) -> list[ET.Element]:
    if element is None:
        return []
    return [child for child in element if local_name(child.tag) == name]


def child(element: ET.Element | None, name: str) -> ET.Element | None:
    matches = children(element, name)
    return matches[0] if matches else None


def descendants(element: ET.Element | None, name: str) -> list[ET.Element]:
    if element is None:
        return []
    return [item for item in element.iter() if local_name(item.tag) == name]


def first_descendant(element: ET.Element | None, name: str) -> ET.Element | None:
    if element is None:
        return None
    return next((item for item in element.iter() if local_name(item.tag) == name), None)


def text(element: ET.Element | None, default: str = "") -> str:
    if element is None or element.text is None:
        return default
    return element.text.strip()


def child_text(element: ET.Element | None, name: str, default: str = "") -> str:
    return text(child(element, name), default)


def descendant_text(element: ET.Element | None, name: str, default: str = "") -> str:
    return text(first_descendant(element, name), default)


def safe_int(value: str | None, default: int = 0) -> int:
    try:
        return int(float(value or ""))
    except (TypeError, ValueError):
        return default


def safe_float(value: str | None, default: float = 0.0) -> float:
    try:
        return float(value or "")
    except (TypeError, ValueError):
        return default


def first_by_local_names(
    elements: Iterable[ET.Element], names: set[str]
) -> ET.Element | None:
    return next((item for item in elements if local_name(item.tag) in names), None)
