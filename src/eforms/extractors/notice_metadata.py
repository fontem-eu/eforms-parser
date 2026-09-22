"""Extract top-level notice metadata (ID, type, dates)."""
from __future__ import annotations

import re

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


# ---------------------------------------------------------------------------
# Identity stamps read from the notice itself.
#
# Until 2026-09 these four came only from TED's search API, stamped onto the
# event by the incremental loader; the monthly-archive path had none of
# them, so an award loaded from an archive was keyed by its notice UUID and
# a later modification (search path, keyed by procedure) could never join
# it. Every one of them is in the XML. Reading them here is what makes one
# ingest path possible: the search API becomes discovery, not a data source.
# ---------------------------------------------------------------------------

# No leading "0*" group: "0*" and "\d+" overlap, which is a backtracking
# hazard (Sonar S5852). int() strips the zero padding instead.
_PUB_NUMBER = re.compile(r"^(\d+)-(\d{4})$")
_UUID_VERSION = re.compile(
    r"^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})-(\d{2})$",
    re.I,
)


def normalise_publication_number(raw: str | None) -> str | None:
    """TED's own form of a publication number, ``NNNNNN-YYYY``.

    The XML carries it zero-padded to eight digits (``00540529-2026``);
    the search API, the graph and every back-link use the unpadded form.
    A value whose number is all zeros is a buyer placeholder, returned
    verbatim so it stays recognisable as one rather than becoming ``0-2026``.
    """
    if not raw:
        return None
    raw = raw.strip()
    m = _PUB_NUMBER.match(raw)
    if not m or int(m.group(1)) == 0:
        return raw or None
    return f"{int(m.group(1))}-{m.group(2)}"


def extract_publication_number(root: etree._Element) -> str | None:
    """BT-? ``efbc:NoticePublicationID`` — the OJS publication number TED
    assigned. Absent from buyer-authored XML TED has not published yet."""
    el = root.find(".//efbc:NoticePublicationID", NS)
    return normalise_publication_number(el.text) if el is not None and el.text else None


def extract_notice_version(root: etree._Element) -> str | None:
    """BT-757 ``cbc:VersionID`` at root level (``01``, ``02``…). Together
    with the notice id it names one published version, which is the
    unit an idempotent loader should skip on — not the id alone."""
    el = root.find("cbc:VersionID", NS)
    return el.text.strip() if el is not None and el.text else None


def extract_procedure_id(root: etree._Element) -> str | None:
    """BT-04 ``cbc:ContractFolderID`` — the procedure identifier shared by
    every notice of one procedure: the call, the award, each modification.
    This is contract identity."""
    el = root.find("cbc:ContractFolderID", NS)
    return el.text.strip() if el is not None and el.text else None


def extract_changed_notice_identifier(root: etree._Element) -> str | None:
    """BT-1501 ``efbc:ChangedNoticeIdentifier`` on a modification notice:
    what it modifies. TED lets buyers write either the previous notice's
    publication number or its versioned notice id, so this returns the raw
    value; :func:`split_back_link` tells the two apart."""
    el = root.find(".//efac:ContractModification/efbc:ChangedNoticeIdentifier", NS)
    return el.text.strip() if el is not None and el.text else None


def split_back_link(raw: str | None) -> tuple[str | None, str | None]:
    """A back-link as ``(publication_number, notice_id)``, one of them set.

    ``549184-2020`` → publication number of a (pre-eForms) award.
    ``a64a67f4-…-01`` → the award's notice UUID with its version; the UUID
    is what the graph indexes, so it is returned bare. Anything else is
    kept as a publication number verbatim — provenance for a human, and a
    value resolution will fail on loudly rather than silently.
    """
    if not raw:
        return None, None
    raw = raw.strip()
    m = _UUID_VERSION.match(raw)
    if m:
        return None, m.group(1).lower()
    return normalise_publication_number(raw), None


# ---------------------------------------------------------------------------
# Raw signals + envelope (0.12). Verbatim on purpose: the cleaning stage
# downstream (data-backlog Part 5) keys on what the gateway wrote.
# ---------------------------------------------------------------------------


def _root_text(root: etree._Element, path: str) -> str | None:
    """Stripped text of the first ``path`` match under root, None when
    absent or blank."""
    el = root.find(path, NS)
    if el is None or not el.text or not el.text.strip():
        return None
    return el.text.strip()


def extract_notice_language(root: etree._Element) -> str | None:
    """``cbc:NoticeLanguageCode`` at root level — the language the notice
    was authored in, verbatim (three-letter, e.g. ``POR``, ``DEU``)."""
    return _root_text(root, "cbc:NoticeLanguageCode")


def extract_customization_id(root: etree._Element) -> str | None:
    """``cbc:CustomizationID`` at root level — the eForms SDK version the
    notice was authored against (``eforms-sdk-1.14``). The only version
    marker in the XML: a scale census groups gateways by it because
    nothing else says how a sender wrote its amounts."""
    return _root_text(root, "cbc:CustomizationID")


def extract_tender_result_award_date_raw(root: etree._Element) -> str | None:
    """Root ``cac:TenderResult/cbc:AwardDate`` verbatim — deliberately NOT
    through :func:`_clean_date`. Every eForms award notice seen so far
    carries the ``2000-01-01`` placeholder here (with TED's timezone
    suffix, ``2000-01-01Z`` / ``2000-01-01+02:00``); the raw text is what
    lets a census count it and tell it from absence."""
    return _root_text(root, "cac:TenderResult/cbc:AwardDate")
