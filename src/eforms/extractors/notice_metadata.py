"""Extract top-level notice metadata (ID, type, dates)."""
from __future__ import annotations

from lxml import etree

from ..namespaces import NS


def extract_notice_id(root: etree._Element) -> str | None:
    """Extract BT-701 Notice Identifier (cbc:ID at root level)."""
    el = root.find("cbc:ID", NS)
    return el.text.strip() if el is not None and el.text else None


def extract_issue_date(root: etree._Element) -> str | None:
    """Extract notice issue date."""
    el = root.find("cbc:IssueDate", NS)
    if el is not None and el.text:
        return _clean_date(el.text.strip())
    return None


def extract_dispatch_date(root: etree._Element) -> str | None:
    """Extract notice dispatch/transmission date (when sent to TED)."""
    # Try TransmissionDate first (common in eForms)
    for tag in ("cbc:TransmissionDate", "cbc:DispatchDate", ".//cbc:RequestedPublicationDate"):
        el = root.find(tag, NS)
        if el is not None and el.text:
            return _clean_date(el.text.strip())
    return None


def extract_publication_date(root: etree._Element) -> str | None:
    """Extract the date TED published the notice (OJS publication).

    This is ``efbc:PublicationDate`` from the TED-assigned publication
    block, which is distinct from ``cbc:IssueDate`` (the date the buyer
    issued/dispatched the notice) and typically falls a day or so later.
    Consumers that mean "when did this become public" want this one.
    Absent from buyer-authored XML that TED has not published yet.
    """
    el = root.find(".//efbc:PublicationDate", NS)
    if el is not None and el.text:
        return _clean_date(el.text.strip())
    return None


def _clean_date(raw: str) -> str | None:
    """Clean a date string: strip timezone suffix, reject bogus sentinels."""
    if not raw:
        return None
    # Strip timezone like '+02:00' or 'Z'
    d = raw[:10]
    # Reject sentinel dates (TED uses 2000-01-01 for 'unknown')
    if d.startswith(("2000-01-01", "1900-01-01")):
        return None
    return d


def extract_notice_type(root: etree._Element) -> str | None:
    """Extract the notice sub-type code."""
    el = root.find(
        ".//cbc:NoticeTypeCode", NS
    )
    return el.text.strip() if el is not None and el.text else None
