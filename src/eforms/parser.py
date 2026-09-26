"""Main entry point: parse an eForms XML document into a Notice."""
from __future__ import annotations

from lxml import etree

from .extractors.awards import (
    extract_awards,
    extract_lot_tender_counts,
    extract_total_value,
    extract_total_value_raw,
)
from .extractors.framework import (
    extract_framework_notice_reference,
    extract_framework_terms,
)
from .extractors.lots import extract_lots
from .extractors.notice_metadata import (
    extract_customization_id,
    extract_dispatch_date,
    extract_issue_date,
    extract_notice_language,
    extract_publication_date,
    extract_notice_id,
    extract_notice_type,
    extract_publication_number,
    extract_procedure_id,
    extract_notice_version,
    extract_changed_notice_identifier,
    extract_tender_result_award_date_raw,
    split_back_link,
)
from .extractors.integrity import (
    extract_award_criterion_type,
    extract_eu_funding,
    extract_is_framework,
    extract_submission_deadline,
)
from .extractors.organizations import extract_buyer_org_id, extract_organizations
from .extractors.procedure import (
    extract_cpv_main,
    extract_description,
    extract_nuts,
    extract_procedure_type,
    extract_title,
    extract_title_language,
)
from .models import Notice
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

    awards = extract_awards(root)
    tender_counts = extract_lot_tender_counts(root)
    for award in awards:
        award.tenders_received = tender_counts.get(award.lot_id)
    eu_funded, funding_programme = extract_eu_funding(root)
    back_link = extract_changed_notice_identifier(root)
    modifies_publication_number, modifies_notice_id = split_back_link(back_link)
    framework = extract_framework_terms(root)
    framework_ref = extract_framework_notice_reference(root)

    return Notice(
        notice_id=extract_notice_id(root) or "",
        notice_type=extract_notice_type(root),
        title=extract_title(root),
        title_lang=extract_title_language(root),
        description=extract_description(root),
        cpv_main=extract_cpv_main(root),
        procedure_type=extract_procedure_type(root),
        issue_date=extract_issue_date(root),
        dispatch_date=extract_dispatch_date(root),
        publication_date=extract_publication_date(root),
        publication_number=extract_publication_number(root),
        procedure_id=extract_procedure_id(root),
        notice_version=extract_notice_version(root),
        modifies_publication_number=modifies_publication_number,
        modifies_notice_id=modifies_notice_id,
        buyer_org_id=extract_buyer_org_id(root),
        total_value=total_value,
        currency=currency,
        total_value_raw=extract_total_value_raw(root),
        nuts=extract_nuts(root),
        organizations=orgs,
        lots=extract_lots(root),
        awards=awards,
        award_criterion_type=extract_award_criterion_type(root),
        submission_deadline=extract_submission_deadline(root),
        is_framework=extract_is_framework(root),
        eu_funded=eu_funded,
        funding_programme=funding_programme,
        tender_result_award_date_raw=extract_tender_result_award_date_raw(root),
        notice_language=extract_notice_language(root),
        customization_id=extract_customization_id(root),
        framework_max_value=framework.max_value,
        framework_max_value_currency=framework.max_value_currency,
        framework_max_value_raw=framework.max_value_raw,
        framework_reestimated_value=framework.reestimated_value,
        framework_reestimated_value_currency=framework.reestimated_value_currency,
        framework_duration_months=framework.duration_months,
        framework_duration_raw=framework.duration_raw,
        framework_max_operators=framework.max_operators,
        framework_notice_id=framework_ref.notice_id,
        framework_notice_id_raw=framework_ref.notice_id_raw,
        framework_notice_id_source=framework_ref.notice_id_source,
        framework_notice_id_conflict=framework_ref.notice_id_conflict,
    )
