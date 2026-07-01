"""Parser for legacy TED (pre-eForms) XML — the ``<TED_EXPORT>`` schema.

eForms replaced the old TED S-series forms during 2023-2024. Notices
published before a buyer migrated (roughly 2023 to mid-2024) still
arrive as ``<TED_EXPORT>`` documents whose ``FORM_SECTION`` holds an
S-form (``F20_2014`` for contract modifications, ``F03_2014`` for
awards, …). The eForms extractors assume a ``<ContractAwardNotice>``
root with ``cbc:``/``cac:`` UBL elements and find nothing in these.

This module extracts the subset the pipeline consumes — buyer,
contractors, the (possibly modified) contract value, CPV, notice type —
from the legacy schema. It is deliberately narrow: modifications are
what the backfill needs, so the ``F20`` ``INFO_MODIFICATIONS`` value
block is first-class here.

Namespace-agnostic by design: legacy TED spans several schema versions
(R2.0.8 / R2.0.9 / …) whose namespace URIs differ, so every lookup
matches on ``local-name()`` rather than a fixed prefix map.
"""
from __future__ import annotations

import re

from lxml import etree

from .models import Award, LegalIdentifier, Notice, Organization

# Legacy ``TD_DOCUMENT_TYPE/@CODE`` -> eForms-style notice-type slug.
# Only the codes the pipeline acts on are mapped; "K" (modification of a
# contract/concession) is the reason this parser exists. The rest are a
# defensive courtesy — the loader stamps the authoritative notice-type
# from the search response regardless.
_DOC_TYPE_TO_NOTICE_TYPE = {
    "K": "can-modif",     # Modification of a contract/concession
    "7": "can-standard",  # Contract award notice
    "9": "can-social",    # Contract award — social & other specific services
}


def looks_like_ted_export(root: etree._Element) -> bool:
    """True if ``root`` is a legacy ``<TED_EXPORT>`` document."""
    return etree.QName(root.tag).localname == "TED_EXPORT"


def _local(ctx, name: str):
    """Descendants of ``ctx`` whose local name is ``name`` (any namespace)."""
    if ctx is None:
        return []
    return ctx.xpath(".//*[local-name()=$n]", n=name)


def _first(ctx, name: str):
    hits = _local(ctx, name)
    return hits[0] if hits else None


def _text(el) -> str | None:
    if el is None:
        return None
    txt = "".join(el.itertext()).strip()
    return txt or None


def _num(text: str | None) -> float | None:
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _fmt_date(raw: str | None) -> str | None:
    """``20240115`` -> ``2024-01-15``; anything else passes through."""
    if raw and len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    return raw


def _country(block, fallback: str | None) -> str | None:
    """Country of an address block: prefer ``ISO_COUNTRY``/``COUNTRY``
    ``@VALUE`` within the block, else the notice-level fallback."""
    for tag in ("ISO_COUNTRY", "COUNTRY"):
        el = _first(block, tag)
        if el is not None and el.get("VALUE"):
            return el.get("VALUE")
    return fallback


def _legal_id(block) -> LegalIdentifier | None:
    """Legacy contractor/buyer national registration id, when present."""
    val = _text(_first(block, "NATIONALID"))
    return LegalIdentifier(value=val, scheme_name="NATIONAL") if val else None


def _pick_form(root):
    """The single S-form to read. ``FORM_SECTION`` wraps one form per
    language; prefer ``CATEGORY="ORIGINAL"``, else the first, else the
    whole document (defensive — some exports inline the form)."""
    section = _first(root, "FORM_SECTION")
    if section is None:
        return root
    forms = list(section)
    for form in forms:
        if form.get("CATEGORY") == "ORIGINAL":
            return form
    return forms[0] if forms else root


def _modification_values(form) -> tuple[float | None, float | None, str | None]:
    """The before/after totals from an ``F20`` ``INFO_MODIFICATIONS`` block.

    Legacy modification notices self-contain the value change: the
    corruption signal is ``VAL_TOTAL_BEFORE`` -> ``VAL_TOTAL_AFTER``.
    ``VAL_TOTAL`` is a standalone total published when a notice carries
    only one figure. Returns ``(before, after, currency)`` where ``after``
    falls back to ``VAL_TOTAL``."""
    info = _first(form, "INFO_MODIFICATIONS")
    scope = _first(info, "VALUES") if info is not None else None
    if scope is None:
        scope = _first(form, "VALUES")

    def _one(tag):
        el = _first(scope, tag)
        return _num(_text(el)), (el.get("CURRENCY") if el is not None else None)

    before, cur_b = _one("VAL_TOTAL_BEFORE")
    after, cur_a = _one("VAL_TOTAL_AFTER")
    total, cur_t = _one("VAL_TOTAL")
    if after is None:
        after = total
    return before, after, (cur_a or cur_t or cur_b)


def _modifies_pubnum(root) -> str | None:
    """Publication-number of the notice this modification modifies.

    The legacy ``REF_NOTICE/NO_DOC_OJS`` carries the original notice's OJS
    reference (e.g. ``2017/S 147-305158``); convert it to the machine
    publication-number form (``305158-2017``) so it matches the
    ``modifies_publication_number`` the eForms path gets from the search
    API. Returns None when no reference is published."""
    ref = _first(root, "REF_NOTICE")
    ojs = _text(_first(ref, "NO_DOC_OJS")) if ref is not None else None
    match = re.match(r"\s*(\d{4})/S\s+\d+-(\d+)", ojs or "")
    return f"{match.group(2)}-{match.group(1)}" if match else None


def _extract_buyer(form, notice_country, organizations) -> str | None:
    """Add the contracting authority to ``organizations`` and return its
    (synthetic) org id, or None when no buyer name is present."""
    block = _first(form, "ADDRESS_CONTRACTING_BODY")
    name = _text(_first(block, "OFFICIALNAME")) if block is not None else None
    if not name:
        return None
    organizations["buyer"] = Organization(
        org_id="buyer",
        name=name,
        country=_country(block, notice_country),
        legal_id=_legal_id(block),
        address=_text(_first(block, "ADDRESS")),
    )
    return "buyer"


def _extract_awards(form, notice_country, organizations) -> list[Award]:
    """Add each winning contractor to ``organizations`` and return one
    :class:`Award` per contractor. Org ids are synthetic (legacy notices
    carry none) but stay distinct and internally consistent."""
    awards: list[Award] = []
    for award_contract in _local(form, "AWARD_CONTRACT"):
        lot_no = _text(_first(award_contract, "LOT_NO"))
        conclusion = _fmt_date(
            _text(_first(award_contract, "DATE_CONCLUSION_CONTRACT"))
        )
        for contractor in _local(award_contract, "CONTRACTOR"):
            addr = _first(contractor, "ADDRESS_CONTRACTOR")
            name = _text(
                _first(addr if addr is not None else contractor, "OFFICIALNAME")
            )
            if not name:
                continue
            org_id = f"contractor-{len(awards)}"
            organizations[org_id] = Organization(
                org_id=org_id,
                name=name,
                country=_country(addr, notice_country),
                legal_id=_legal_id(addr),
                address=_text(_first(addr, "ADDRESS")),
            )
            awards.append(
                Award(
                    lot_id=lot_no or org_id,
                    contractor_org_id=org_id,
                    conclusion_date=conclusion,
                )
            )
    return awards


def parse_ted_export(root: etree._Element) -> Notice:
    """Parse a legacy ``<TED_EXPORT>`` document into a :class:`Notice`.

    ``notice_id`` is set to the notice's own OJS number (``NO_DOC_OJS``)
    for standalone correctness; the TED loader overrides it with the
    machine publication-number from the search response, since legacy
    notices carry no eForms UUID.
    """
    coded = _first(root, "CODED_DATA_SECTION")
    notice_country = _country(coded, None)
    own_ojs = _text(_first(coded, "NO_DOC_OJS")) or _text(_first(root, "NO_DOC_OJS"))
    issue_date = _fmt_date(_text(_first(coded, "DATE_PUB")))

    doc_type = _first(root, "TD_DOCUMENT_TYPE")
    notice_type = _DOC_TYPE_TO_NOTICE_TYPE.get(
        doc_type.get("CODE") if doc_type is not None else None
    )

    form = _pick_form(root)
    organizations: dict[str, Organization] = {}
    buyer_org_id = _extract_buyer(form, notice_country, organizations)
    value_before, total_value, currency = _modification_values(form)
    awards = _extract_awards(form, notice_country, organizations)

    cpv = _first(form, "CPV_CODE")
    return Notice(
        notice_id=own_ojs or "",
        notice_type=notice_type,
        title=_text(_first(form, "TITLE")),
        cpv_main=cpv.get("CODE") if cpv is not None else None,
        issue_date=issue_date,
        buyer_org_id=buyer_org_id,
        total_value=total_value,
        currency=currency,
        modification_value_before=value_before,
        modifies_publication_number=_modifies_pubnum(root),
        organizations=organizations,
        awards=awards,
    )
