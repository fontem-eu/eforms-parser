"""Main entry point: parse an eForms XML document into a Notice."""
from __future__ import annotations

from lxml import etree

from .extractors.awards import (
    extract_awards,
    extract_lot_tender_counts,
    extract_total_value,
)
from .extractors.lots import extract_lots
from .extractors.notice_metadata import (
    extract_dispatch_date,
    extract_issue_date,
    extract_notice_id,
    extract_notice_type,
)
from .extractors.integrity import (
    extract_award_criterion_type,
    extract_eu_funding,
    extract_is_framework,
    extract_submission_deadline,
)
from .extractors.organizations import extract_organizations
from .extractors.procedure import (
    extract_cpv_main,
    extract_description,
    extract_procedure_type,
    extract_title,
)
from .models import Notice
from .namespaces import NS
from .ted_export import looks_like_ted_export, parse_ted_export


def parse(xml_bytes: bytes) -> Notice:
    """Parse a TED notice XML document and return a Notice dataclass.

    Routes on the document format: eForms (``<ContractAwardNotice>`` and
    siblings, UBL ``cbc:``/``cac:`` elements) is the default; legacy TED
    (``<TED_EXPORT>``, the pre-eForms S-forms still seen for 2023-mid-2024
    notices) is handled by :func:`parse_ted_export`.
    """
    root = etree.fromstring(xml_bytes)
    if looks_like_ted_export(root):
        return parse_ted_export(root)
    orgs = extract_organizations(root)
    total_value, currency = extract_total_value(root)

    # Resolve buyer org ID
    buyer_org_id = None
    buyer_party = root.find(
        ".//cac:ContractingParty/cac:Party/cac:PartyIdentification/cbc:ID",
        NS,
    )
    if buyer_party is not None and buyer_party.text:
        buyer_org_id = buyer_party.text.strip()

    awards = extract_awards(root)
    tender_counts = extract_lot_tender_counts(root)
    for award in awards:
        award.tenders_received = tender_counts.get(award.lot_id)
    eu_funded, funding_programme = extract_eu_funding(root)

    return Notice(
        notice_id=extract_notice_id(root) or "",
        notice_type=extract_notice_type(root),
        title=extract_title(root),
        description=extract_description(root),
        cpv_main=extract_cpv_main(root),
        procedure_type=extract_procedure_type(root),
        issue_date=extract_issue_date(root),
        dispatch_date=extract_dispatch_date(root),
        buyer_org_id=buyer_org_id,
        total_value=total_value,
        currency=currency,
        organizations=orgs,
        lots=extract_lots(root),
        awards=awards,
        award_criterion_type=extract_award_criterion_type(root),
        submission_deadline=extract_submission_deadline(root),
        is_framework=extract_is_framework(root),
        eu_funded=eu_funded,
        funding_programme=funding_programme,
    )
