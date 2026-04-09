"""Main entry point: parse an eForms XML document into a Notice."""
from __future__ import annotations

from lxml import etree

from .extractors.awards import extract_awards, extract_total_value
from .extractors.lots import extract_lots
from .extractors.notice_metadata import (
    extract_dispatch_date,
    extract_issue_date,
    extract_notice_id,
    extract_notice_type,
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


def parse(xml_bytes: bytes) -> Notice:
    """Parse an eForms XML document and return a Notice dataclass."""
    root = etree.fromstring(xml_bytes)
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
        awards=extract_awards(root),
    )
