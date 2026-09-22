"""One reader for every UBL amount element (``cbc:*Amount``, ``efbc:*Amount``).

Amounts are parsed with ``float()`` for arithmetic, but the text the buyer
published is a signal in its own right: ``24474133`` and ``24474133.00``
are the same float and not the same statement about scale (data-backlog
Part 5, C4: "no decimals" does not imply cents, and nothing else in the
XML marks the scale). Every amount reader therefore hands back the
verbatim text next to the number, and the models keep it as ``*_raw``.
"""
from __future__ import annotations

from lxml import etree


def read_amount(
    el: etree._Element | None,
) -> tuple[float | None, str | None, str | None]:
    """``(value, currency, raw)`` of one amount element.

    ``raw`` is the element text stripped of surrounding whitespace and
    nothing else, kept even when it does not parse as a number (``value``
    is then None). ``currency`` is the ``currencyID`` attribute. All
    three are None when the element is absent or blank.
    """
    if el is None or el.text is None or not el.text.strip():
        return None, None, None
    raw = el.text.strip()
    try:
        value: float | None = float(raw)
    except ValueError:
        value = None
    return value, el.get("currencyID"), raw
